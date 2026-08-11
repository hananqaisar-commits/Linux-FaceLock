#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

# ── Auto-detect everything ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from nova_unlock.core import setup_environment, find_nova_root

env_info = setup_environment()
ROOT = find_nova_root()
REAL_USER = env_info["user"]

sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.pop("WAYLAND_DISPLAY", None)

RESULT_FILE = "/tmp/nova_unlock_greeter_result"
LOG_FILE = "/tmp/nova_greeter_ui.log"

def log(msg):
    with open(LOG_FILE, "a") as f:
        f.write(f"{time.strftime('%F %T')} {msg}\n")

# ── pip-only ML dependency guard (production failure handling) ──────────────
# dlib / face_recognition / face_recognition_models are NOT shipped by any OS
# package manager; the installer pip-installs them. If that step was interrupted
# (no network / missing build tools), report a clear, actionable message instead
# of a raw ImportError traceback. The user's password stays a fallback.
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
        from pathlib import Path
        p = Path("/var/lib/novaunlock/deps_status.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ok": False, "missing": miss, "remediation": cmd}, indent=2))
    except Exception:
        pass
    return miss, msg

# Canonical UI + recognition (single source of truth — same widget the demo and
# the in-session lock daemon use, so the login greeter shows the SAME modern UI).
from nova_unlock.ui.face_id_screen import Sig, FaceUnlockWidget, FaceWorker
# Trusted lock/greeter-screen embedding pattern (universal across GNOME/XFCE/KDE/
# Cinnamon/MATE + LightDM/GDM) — this is what makes the UI actually VISIBLE on the
# greeter/lock screen in every distro. Keep it.
from nova_unlock.ui.universal_embed import smart_embed, raise_embedded, ensure_on_top

class GreeterWorker(FaceWorker):
    def run(self):
        try:
            import cv2
            import numpy as np
            try:
                import face_recognition
            except ImportError:
                _ml = _nova_require_ml_deps()
                if _ml:
                    log(_ml[1])
                self.sig.fail.emit()
                return
            from nova_unlock.vision.face_recognizer import get_enrolled_users, load_face, get_threshold, get_max_attempts
            from nova_unlock.vision.camera_detector import open_camera
            threshold = get_threshold()
            # Single source of truth for the "exactly N attempts, no more no less"
            # rule. The worker performs ALL attempts itself and then stops; the app
            # must NOT restart it (that was the old bug → up to 25 scans).
            max_attempts = get_max_attempts()

            pf = {}
            for u in get_enrolled_users():
                e = load_face(u)
                if e is not None:
                    pf[u] = e

            if not pf:
                self.sig.fail.emit()
                return

            # Robust multi-backend camera open (CAP_V4L2 + default + warm-up
            # reads). The old V4L2-only probe silently failed on systems where
            # the camera only opens via the default backend → no light → no scan.
            cap = open_camera(max_index=6, width=320, height=240, fps=30)

            if not cap:
                # Camera unavailable → show the retry prompt (NOT just a fail
                # that leaves the UI stuck with no way to recover).
                self.sig.exhausted.emit()
                return

            for _ in range(2):
                cap.read()

            for attempt in range(max_attempts):
                if not self.on:
                    break

                embs = []
                for _ in range(4):
                    if not self.on:
                        break
                    ok, frame = cap.read()
                    if not ok:
                        continue
                    try:
                        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(rgb, model="hog")
                        if locs:
                            encs = face_recognition.face_encodings(rgb, locs)
                            if encs:
                                embs.append(encs[0])
                    except Exception:
                        pass
                    time.sleep(0.03)

                if not embs:
                    self.sig.fail.emit()
                    time.sleep(0.5)
                    continue

                live = np.mean(embs, axis=0)
                best_user = None
                best_dist = 999.0

                for user, saved in pf.items():
                    dist = float(face_recognition.face_distance([saved], live)[0])
                    if dist < best_dist:
                        best_dist = dist
                        best_user = user

                log(f"attempt={attempt+1} best={best_user} dist={best_dist:.4f}")

                if best_user is not None and best_dist <= threshold:
                    self.result = best_user
                    self.sig.ok.emit(best_user)
                    cap.release()
                    return
                else:
                    self.sig.fail.emit()
                    time.sleep(0.5)

            cap.release()
            self.sig.fail.emit()

        except Exception as e:
            import traceback
            log(f"worker error: {e}")
            log(traceback.format_exc())
            self.sig.fail.emit()

class GreeterApp:
    def __init__(self):
        self.result = None
        self._matched = None
        # The GreeterWorker performs exactly get_max_attempts() (5) scans on its
        # own; this app does NOT restart it (that was the old nested-attempts
        # bug). After the 5th failed scan the greeter falls back to manual
        # password login. So there is no attempt counter to track here.

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()
        w = FaceUnlockWidget(sig, demo_mode=False)

        # New login session → let the greeting show once on first match.
        try:
            from face_unlock_daemon import clear_hello_marker
            clear_hello_marker()
        except Exception:
            pass

        ensure_on_top(w, 50)
        app.processEvents()
        log("widget shown")

        for delay in (200, 500, 900, 1400, 2000, 3000):
            QTimer.singleShot(delay, lambda _w=w: smart_embed(_w, 50))

        top_timer = QTimer()
        top_timer.timeout.connect(lambda _w=w: raise_embedded(_w, 50))
        top_timer.start(200)

        wk = GreeterWorker(sig)

        def on_ok(name):
            # Match detected — record only. The result file (which triggers
            # lightdm autologin) must be written only AFTER the success ring
            # animation completes, i.e. on sig.unlock_complete.
            self._matched = name

        def on_unlock_complete():
            name = self._matched or self.result
            self.result = name
            try:
                if name:
                    with open(RESULT_FILE, "w") as f:
                        f.write(name)
                    # Login-time greeting marker — the per-user session watcher
                    # shows "hello, {username}" inside the fresh session and
                    # clears this file. (The greeter itself is killed when
                    # lightdm restarts, so it can't render the overlay.)
                    try:
                        marker = Path("/var/lib/novaunlock/last_login_user")
                        marker.parent.mkdir(parents=True, exist_ok=True)
                        import time as _t
                        marker.write_text(
                            f"{name.strip().lower()}\n{_t.time()}\n")
                    except Exception as e:
                        log(f"write login marker failed: {e}")
            except Exception as e:
                log(f"write result failed: {e}")
            top_timer.stop()
            QTimer.singleShot(400, app.quit)

        # NOTE: on_fail is intentionally NOT handled. The GreeterWorker already
        # performs exactly get_max_attempts() (5) scans internally and then
        # emits a final fail. After the 5th failed scan the greeter shows the
        # retry icon; clicking it restarts the worker for another 5 attempts
        # (never fewer/more than 5 per scan), falling back to manual password
        # login handled by the login manager if still unmatched.
        sig.ok.connect(on_ok)
        sig.unlock_complete.connect(on_unlock_complete)

        def do_retry():
            nonlocal wk
            try:
                if wk.isRunning():
                    wk.stop()
                    wk.wait(1000)
                wk = GreeterWorker(sig)
                wk.start()
            except Exception as e:
                log(f"retry restart failed: {e}")

        sig.retry_requested.connect(do_retry)

        QTimer.singleShot(100, wk.start)
        app.exec_()
        wk.stop()
        wk.wait(1000)
        return self.result

if __name__ == "__main__":
    log("greeter ui daemon start")
    try:
        GreeterApp().run()
    except Exception as e:
        import traceback
        log(f"fatal: {e}")
        log(traceback.format_exc())
