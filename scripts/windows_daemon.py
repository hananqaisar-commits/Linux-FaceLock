#!/usr/bin/env python3
"""
NovaUnlock — Windows Face Unlock Daemon
Features:
  - Continuous face presence monitoring
  - Auto-lock via Windows API when enrolled face disappears
"""

import cv2
import time
import sys
import os
import logging
import threading
import ctypes
import numpy as np
from pathlib import Path

# Paths
NOVA_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = NOVA_DIR / "data"
FACES_DIR   = DATA_DIR / "faces"
LOCK_FILE   = Path(os.environ.get("TEMP", "C:\\Temp")) / "nova_unlock_face.lock"
LOG_DIR     = NOVA_DIR / "logs"
LOG_FILE    = LOG_DIR / "face_auth_win.log"

# Daemon Config
FACE_LEAVE_TIMEOUT  = 10.0   # seconds before auto-lock triggers
CHECK_INTERVAL      = 0.15   # seconds between camera frames
RECOGNITION_THRESH  = 0.62   
CAMERA_INDEX        = 0

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("nova_daemon_win")

def load_known_faces() -> tuple[list, list]:
    encodings, names = [], []
    if not FACES_DIR.exists():
        return encodings, names
    for npy_file in FACES_DIR.glob("*.npy"):
        try:
            enc = np.load(str(npy_file))
            encodings.append(enc)
            names.append(npy_file.stem)
        except Exception:
            pass
    return encodings, names

def trigger_lock(reason: str = "face_leave") -> None:
    logger.info("🔒 AUTO-LOCK triggered — reason: %s", reason)
    try:
        # Native Windows Lock API
        ctypes.windll.user32.LockWorkStation()
        logger.info("Successfully called LockWorkStation()")
    except Exception as e:
        logger.error("Failed to lock workstation: %s", e)

def recognize_face(frame, known_encs, known_names, threshold=RECOGNITION_THRESH):
    try:
        import face_recognition as fr
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = fr.face_locations(rgb, model="hog")
        if not locs:
            return None, 1.0
        encs = fr.face_encodings(rgb, locs)
        for enc in encs:
            dists = fr.face_distance(known_encs, enc)
            if len(dists) == 0:
                continue
            idx = int(np.argmin(dists))
            if dists[idx] <= threshold:
                return known_names[idx], float(dists[idx])
        return None, 1.0
    except Exception:
        return None, 1.0

class FacePresenceGuard:
    def __init__(self, known_encs, known_names, timeout: float = FACE_LEAVE_TIMEOUT):
        self.known_encs   = known_encs
        self.known_names  = known_names
        self.timeout      = timeout
        self._running     = False
        self._thread      = None
        self._last_seen   = time.time()
        self._face_absent = False
        self._lock        = threading.Lock()

    def start(self):
        if self._running: return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _loop(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened(): return
        
        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            name, dist = recognize_face(frame, self.known_encs, self.known_names)

            with self._lock:
                if name is not None:
                    self._last_seen    = time.time()
                    self._face_absent  = False
                else:
                    absent_for = time.time() - self._last_seen
                    if absent_for >= self.timeout and not self._face_absent:
                        self._face_absent = True
                        threading.Thread(
                            target=trigger_lock,
                            args=("face_leave",),
                            daemon=True,
                        ).start()

            time.sleep(CHECK_INTERVAL)
        cap.release()

def main():
    if LOCK_FILE.exists():
        try:
            os.remove(LOCK_FILE) # Cleanup stale lock
        except Exception:
            return
            
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.touch()

    known_encs, known_names = load_known_faces()
    if not known_encs:
        LOCK_FILE.unlink(missing_ok=True)
        return

    guard = FacePresenceGuard(known_encs, known_names)
    guard.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        guard.stop()
    finally:
        LOCK_FILE.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
