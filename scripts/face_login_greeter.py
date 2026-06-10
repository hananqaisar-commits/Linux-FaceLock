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

from nova_unlock.ui.face_unlock_widget import Sig, FaceUnlockWidget, FaceWorker
from nova_unlock.ui.universal_embed import smart_embed, raise_embedded, ensure_on_top

class GreeterWorker(FaceWorker):
    def run(self):
        try:
            import cv2
            import numpy as np
            import face_recognition
            from nova_unlock.vision.face_recognizer import get_enrolled_users, load_face, get_threshold
            threshold = get_threshold()

            pf = {}
            for u in get_enrolled_users():
                e = load_face(u)
                if e is not None:
                    pf[u] = e

            if not pf:
                self.sig.fail.emit()
                return

            cap = None
            for i in range(2):
                try:
                    c = cv2.VideoCapture(i, cv2.CAP_V4L2)
                except Exception:
                    c = cv2.VideoCapture(i)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    c.set(cv2.CAP_PROP_FPS, 30)
                    ok, _ = c.read()
                    if ok:
                        cap = c
                        break
                c.release()

            if not cap:
                self.sig.fail.emit()
                return

            for _ in range(2):
                cap.read()

            for attempt in range(2):
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

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()
        w = FaceUnlockWidget(sig, demo_mode=False)

        ensure_on_top(w, 50)
        app.processEvents()
        log("widget shown")

        for delay in (200, 500, 900, 1400, 2000, 3000):
            QTimer.singleShot(delay, lambda _w=w: smart_embed(_w, 50))

        top_timer = QTimer()
        top_timer.timeout.connect(lambda _w=w: raise_embedded(_w, 50))
        top_timer.start(200)

        wk = GreeterWorker(sig)

        def done(name):
            self.result = name
            try:
                with open(RESULT_FILE, "w") as f:
                    f.write(name)
            except Exception as e:
                log(f"write result failed: {e}")
            top_timer.stop()
            QTimer.singleShot(1000, app.quit)

        sig.ok.connect(done)

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
