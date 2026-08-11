#!/usr/bin/env python3
"""NovaUnlock — GUI Face Enrollment (PyQt5)

A genuine Qt enrollment window (NOT cv2.imshow). The product ships
opencv-python-headless (no GUI/Qt backend) so OpenCV's highgui window can never
open here — drawing with cv2.imshow silently fails and the enrollment would run
text-only. This module captures frames with cv2.VideoCapture (which works with
headless OpenCV) on a background thread and renders a live, mirrored preview +
green face box + iOS-style progress ring entirely in PyQt5, matching the login
screen's aesthetic.

Stores the enrolled profile in the ONE canonical faces dir
(nova_unlock.vision.face_recognizer.get_faces_dir → /var/lib/novaunlock/faces),
so the greeter, lock-screen daemon and enrollment all read/write the SAME place.

Exit codes: 0 success · 1 no camera · 3 missing ML deps · 130 cancelled.
A non-zero exit lets enroll_entry.py fall through to the CLI enrollment.
"""

import sys
import os
import time
import threading
from pathlib import Path

# Make the nova_unlock package importable when run from the repo or /opt tree.
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── pip-only ML dependency guard (production failure handling) ──────────────
# dlib / face_recognition / face_recognition_models are NOT shipped by any OS
# package manager; the installer pip-installs them. If that step was interrupted
# (no network / missing build tools), fail with a clear, actionable message
# instead of a raw ImportError traceback. The user's password stays a fallback.
def _nova_require_ml_deps():
    import importlib.util
    miss = [m for m in ("dlib", "face_recognition", "face_recognition_models")
            if importlib.util.find_spec(m) is None]
    if not miss:
        return None
    cmd = "python3 -m pip install --break-system-packages " + " ".join(miss)
    msg = (
        "NovaUnlock: required ML dependencies are missing: " + ", ".join(miss) + ".\n"
        "These are not provided by your OS package manager; install them from PyPI as root:\n\n"
        "    sudo " + cmd + "\n\n"
        "If you installed via the universal .bin, activate its venv and re-run the installer.\n"
        "NovaUnlock keeps your password as a fallback, so you are not locked out."
    )
    try:
        import json
        p = Path("/var/lib/novaunlock/deps_status.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ok": False, "missing": miss, "remediation": cmd}, indent=2))
    except Exception:
        pass
    return miss, msg

_ml = _nova_require_ml_deps()
if _ml:
    sys.stderr.write("\n" + _ml[1] + "\n")
    sys.exit(3)

import face_recognition
import numpy as np
import cv2

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QMessageBox, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QPointF, QRectF
from PyQt5.QtGui import QPainter, QColor, QPen, QFont, QImage, QPixmap, QBrush


# ── Canonical faces directory (single source of truth) ─────────────────────
from nova_unlock.vision import face_recognizer as fr

FACES_DIR = fr.get_faces_dir()
META_FILE = fr.get_meta_file()

SAMPLES_NEEDED = 10
MAX_ATTEMPTS = 120


# ════════════════════════════════════════════════════════════════════════════
# Background camera + recognition worker
# ════════════════════════════════════════════════════════════════════════════
class EnrollWorker(QThread):
    preview = pyqtSignal(QImage)        # latest mirrored BGR→RGB frame (box drawn)
    sample = pyqtSignal(int)            # a new sample was captured (running count)
    status = pyqtSignal(str)            # short status text
    done = pyqtSignal(list)             # finished OK with list of encodings
    failed = pyqtSignal(str)            # fatal error (e.g. "no_camera")

    def __init__(self, needed=SAMPLES_NEEDED, parent=None):
        super().__init__(parent)
        self.needed = needed
        self.on = True
        self.encodings = []
        self._last_sample_t = 0.0

    def stop(self):
        self.on = False

    @staticmethod
    def _to_qimage(bgr, box=None):
        """Convert a BGR numpy frame to a mirrored RGB QImage, drawing a box."""
        frame = bgr
        # Mirror horizontally for a natural "selfie" preview.
        frame = cv2.flip(frame, 1)
        if box is not None:
            top, right, bottom, left = box
            # Box coords were computed on the un-mirrored frame; mirror them too.
            w = frame.shape[1]
            left_m, right_m = w - right, w - left
            cv2.rectangle(frame, (left_m, top), (right_m, bottom),
                          (48, 209, 88), 2)
            cv2.putText(frame, "✓", (left_m, top - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (48, 209, 88), 2)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        # .copy() so the QImage owns its buffer (the numpy array is about to be
        # garbage-collected). The signal then carries a stable image.
        return QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()

    def run(self):
        cap = None
        for idx in (0, 1, 2):
            c = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if not c.isOpened():
                c = cv2.VideoCapture(idx)
            if c.isOpened():
                c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                c.set(cv2.CAP_PROP_FPS, 30)
                ok, _ = c.read()
                if ok:
                    cap = c
                    break
            try:
                c.release()
            except Exception:
                pass

        if not cap:
            self.failed.emit("no_camera")
            return

        # Warm up auto-exposure.
        for _ in range(8):
            cap.read()
            time.sleep(0.05)

        self.status.emit(f"Look straight at the camera — {self.needed} samples needed")
        attempts = 0

        while self.on and len(self.encodings) < self.needed and attempts < MAX_ATTEMPTS:
            attempts += 1
            ok, frame = cap.read()
            if not ok or frame is None:
                time.sleep(0.05)
                continue

            box = None
            try:
                small = cv2.resize(frame, (160, 120))
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb_small, model="hog")
                if locs:
                    sx = frame.shape[1] / 160.0
                    sy = frame.shape[0] / 120.0
                    (t, r, b, l) = locs[0]
                    full_box = (int(t * sy), int(r * sx), int(b * sy), int(l * sx))
                    rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    encs = face_recognition.face_encodings(rgb_full, [full_box])
                    if encs:
                        box = full_box
                        now = time.time()
                        # Throttle so consecutive samples are spaced out a bit.
                        if now - self._last_sample_t >= 0.25:
                            self.encodings.append(encs[0])
                            self._last_sample_t = now
                            self.sample.emit(len(self.encodings))
            except Exception:
                pass

            try:
                self.preview.emit(self._to_qimage(frame, box))
            except Exception:
                pass
            time.sleep(0.03)

        try:
            cap.release()
        except Exception:
            pass

        if len(self.encodings) >= 3:
            self.done.emit(self.encodings)
        else:
            self.failed.emit("too_few")


# ════════════════════════════════════════════════════════════════════════════
# iOS-style progress ring
# ════════════════════════════════════════════════════════════════════════════
class ProgressRing(QWidget):
    def __init__(self, needed=SAMPLES_NEEDED, size=84, parent=None):
        super().__init__(parent)
        self.needed = needed
        self.count = 0
        self.setFixedSize(size, size)
        self._size = size

    def set_count(self, count):
        self.count = count
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w = self._size
        m = 8
        rect = QRectF(m, m, w - 2 * m, w - 2 * m)
        # Track
        p.setPen(QPen(QColor(60, 60, 67, 200), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 0, 360 * 16)
        # Progress
        frac = min(1.0, self.count / self.needed)
        p.setPen(QPen(QColor(48, 209, 88), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(rect, 90 * 16, int(-frac * 360 * 16))
        # Count text
        p.setPen(QColor(245, 245, 248))
        p.setFont(QFont("Helvetica", 22, QFont.Bold))
        p.drawText(rect, Qt.AlignCenter, f"{self.count}")
        p.end()


# ════════════════════════════════════════════════════════════════════════════
# Enrollment window
# ════════════════════════════════════════════════════════════════════════════
class FaceEnrollWidget(QWidget):
    def __init__(self, username, needed=SAMPLES_NEEDED, parent=None):
        super().__init__(parent)
        self.username = username
        self.needed = needed
        self._pix = None
        self._success = False

        self.setWindowTitle("NovaUnlock — Face Enrollment")
        self.setMinimumWidth(380)
        self.setStyleSheet("QWidget { background: #0b0b0f; color: #f5f5f8; }")
        self.cancelled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        title = QLabel("NovaUnlock")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #f5f5f8;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.video = QLabel()
        self.video.setMinimumSize(320, 240)
        self.video.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video.setStyleSheet(
            "background: #000; border-radius: 14px; border: 1px solid #2a2a30;")
        self.video.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.video, 1)

        # Ring + status row
        row = QHBoxLayout()
        row.setSpacing(14)
        self.ring = ProgressRing(needed=self.needed)
        row.addWidget(self.ring)

        col = QVBoxLayout()
        col.setSpacing(6)
        self.stat_lbl = QLabel("Starting camera…")
        self.stat_lbl.setStyleSheet("font-size: 13px; color: #b8b8c0;")
        self.stat_lbl.setWordWrap(True)
        col.addWidget(self.stat_lbl)
        self.prog_lbl = QLabel(f"0 / {self.needed} samples")
        self.prog_lbl.setStyleSheet("font-size: 12px; color: #8a8a92;")
        col.addWidget(self.prog_lbl)
        row.addLayout(col, 1)
        layout.addLayout(row)

        hint = QLabel("Stay still and look straight at the camera. "
                      "Press Esc to cancel.")
        hint.setStyleSheet("font-size: 11px; color: #6a6a72;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.resize(400, 520)

    def set_preview(self, qimg):
        self._pix = QPixmap.fromImage(qimg)
        self._repaint_video()

    def _repaint_video(self):
        if self._pix is None:
            return
        target = self.video.size()
        scaled = self._pix.scaled(
            target, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video.setPixmap(scaled)

    def set_progress(self, count):
        self.ring.set_count(count)
        self.prog_lbl.setText(f"{count} / {self.needed} samples")
        if count >= self.needed:
            self.show_success()
        else:
            self.stat_lbl.setText("Capturing… keep looking at the camera")

    def show_success(self):
        if self._success:
            return
        self._success = True
        self.stat_lbl.setText(f"✅ Enrolled {self.username}!")
        self.stat_lbl.setStyleSheet("font-size: 14px; color: #30d158; font-weight: 600;")
        self.video.setStyleSheet(
            "background: #06140b; border-radius: 14px; border: 1px solid #1f7a3f;")

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._repaint_video()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled = True
            self.close()


# ════════════════════════════════════════════════════════════════════════════
# App runner
# ════════════════════════════════════════════════════════════════════════════
class EnrollApp:
    def __init__(self, username, force=False):
        self.username = username
        self.force = force
        self.rc = 1

    def ensure_dirs(self):
        FACES_DIR.mkdir(parents=True, exist_ok=True)

    def save_meta(self, samples):
        meta = fr.load_meta()
        meta[self.username] = {
            "samples": samples,
            "version": "5.0",
            "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "machine": os.uname().nodename if hasattr(os, "uname") else "",
        }
        fr.save_meta(meta)

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        app.setStyleSheet("QWidget { background: #0b0b0f; }")

        self.ensure_dirs()
        face_file = FACES_DIR / f"{self.username}.npy"
        if face_file.exists() and not self.force:
            QMessageBox.information(
                None, "NovaUnlock",
                f"Face already enrolled for '{self.username}'.\n"
                f"Use --force to re-enroll.")
            return 0

        w = FaceEnrollWidget(self.username, needed=SAMPLES_NEEDED)
        try:
            from nova_unlock.ui.universal_embed import ensure_on_top
            ensure_on_top(w, 50)
        except Exception:
            pass
        w.show()
        w.raise_()
        w.activateWindow()

        worker = EnrollWorker(needed=SAMPLES_NEEDED)

        def on_preview(qimg):
            w.set_preview(qimg)

        def on_sample(count):
            w.set_progress(count)

        def on_done(encs):
            avg = np.mean(encs, axis=0)
            if fr.save_face(self.username, avg):
                try:
                    os.chmod(str(face_file), 0o600)
                except Exception:
                    pass
                self.save_meta(len(encs))
                self.rc = 0
            else:
                self.rc = 1
                QMessageBox.critical(None, "NovaUnlock",
                                     f"Failed to save enrollment for '{self.username}'.")
            QTimer.singleShot(1300, app.quit)

        def on_failed(reason):
            if reason == "no_camera":
                QMessageBox.critical(None, "NovaUnlock", "No camera found.")
                self.rc = 1
            elif reason == "too_few":
                QMessageBox.warning(
                    None, "NovaUnlock",
                    "Not enough samples captured (lighting / no face?). Try again.")
                self.rc = 1
            else:
                self.rc = 1
            QTimer.singleShot(200, app.quit)

        worker.preview.connect(on_preview)
        worker.sample.connect(on_sample)
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)

        worker.start()
        app.exec_()
        worker.stop()
        worker.wait(1500)
        # User cancelled (Esc) — don't let the launcher fall back to the CLI.
        if getattr(w, "cancelled", False):
            return 130
        return self.rc


def main():
    force = "--force" in sys.argv
    username = os.environ.get("USER", os.environ.get("USERNAME", "user"))

    app = EnrollApp(username, force=force)
    try:
        rc = app.run()
    except Exception as e:
        sys.stderr.write(f"NovaUnlock enrollment error: {e}\n")
        rc = 1
    sys.exit(rc)


if __name__ == "__main__":
    main()
