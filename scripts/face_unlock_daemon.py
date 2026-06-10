#!/usr/bin/env python3
"""
NovaUnlock — Face Unlock Daemon v5.2
Features:
  - Continuous face presence monitoring
  - Auto-lock when enrolled face disappears for N seconds
  - Anti-spoof blink liveness on unlock
  - GTK theme-aware overlay
  - PAM cache writer on successful match
"""

import cv2
import time
import sys
import os
import json
import logging
import threading
import subprocess
import signal
import numpy as np
from pathlib import Path

# ── Nova root resolver ───────────────────────────────────────
def find_nova_root() -> "Path":
    """
    Resolve the NovaUnlock project root from any entrypoint.
    Works whether running from .py source or compiled .pyc binary.
    """
    import sys
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(sys.argv[0]).resolve().parent.parent,
        Path.home() / "Desktop" / "NovaUnlock",
        Path("/opt/nova_unlock"),
    ]
    for p in candidates:
        if (p / "data").exists() or (p / "nova_unlock").exists():
            return p
    return Path(__file__).resolve().parent.parent


# ── Paths ──────────────────────────────────────────────────────
NOVA_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = NOVA_DIR / "data"
FACES_DIR   = DATA_DIR / "faces"
META_FILE   = FACES_DIR / "users_meta.json"
MAP_FILE    = DATA_DIR / "face_user_map.json"
CACHE_FILE  = Path("/tmp/nova_unlock_pam_cache.json")
LOCK_FILE   = Path("/tmp/nova_unlock_face.lock")
LOG_DIR     = NOVA_DIR / "logs"
LOG_FILE    = LOG_DIR / "face_auth.log"

# ── Daemon Config ──────────────────────────────────────────────
FACE_LEAVE_TIMEOUT  = 10.0   # seconds before auto-lock triggers
CHECK_INTERVAL      = 0.15   # seconds between camera frames
RECOGNITION_THRESH  = 0.52   # face distance threshold (lower = stricter)
LIVENESS_REQUIRED   = True   # require blink to unlock
CAMERA_INDEX        = 0

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("nova_daemon")


# ── Load enrolled faces ────────────────────────────────────────

# ── .pyc entrypoint resolver ─────────────────────────────────
def nova_py_entry(rel_path: str) -> str:
    """
    Return .py path if exists, else .pyc path, else original.
    Allows daemon to run from compiled PyInstaller binaries.
    """
    root = find_nova_root()
    src  = root / rel_path
    pyc  = src.with_suffix(".pyc")
    if src.is_file():
        return str(src)
    if pyc.is_file():
        return str(pyc)
    return str(src)

def load_known_faces() -> tuple[list, list]:
    encodings, names = [], []
    if not FACES_DIR.exists():
        logger.warning("Faces dir missing: %s", FACES_DIR)
        return encodings, names
    for npy_file in FACES_DIR.glob("*.npy"):
        try:
            enc = np.load(str(npy_file))
            name = npy_file.stem
            encodings.append(enc)
            names.append(name)
            logger.info("Loaded face: %s", name)
        except Exception as e:
            logger.error("Failed to load %s: %s", npy_file, e)
    return encodings, names

# ── Entry resolver (.py / .pyc support) ──────────────────────
def _resolve_entry(rel_path: str) -> str:
    """
    Resolve script entrypoint — returns .py if present, else .pyc.
    Enables daemon to run from compiled PyInstaller binaries.
    Alias: nova_py_entry() calls this internally.
    """
    from pathlib import Path as _P
    root = find_nova_root()
    src  = root / rel_path
    pyc  = src.with_suffix(".pyc")
    if src.is_file():
        return str(src)
    if pyc.is_file():
        return str(pyc)
    return str(src)




# ── Write PAM cache ────────────────────────────────────────────
def write_pam_cache(username: str) -> None:
    data = {
        "user"   : username.strip().lower(),
        "profile": username.strip().lower(),
        "ts"     : time.time(),
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
        os.chmod(CACHE_FILE, 0o600)
        logger.info("PAM cache written for: %s", username)
    except Exception as e:
        logger.error("PAM cache write failed: %s", e)


# ── Lock screen ────────────────────────────────────────────────
def trigger_lock(reason: str = "face_leave") -> None:
    logger.info("🔒 AUTO-LOCK triggered — reason: %s", reason)
    cmds = [
        ["xfce4-screensaver-command", "-l"],
        ["gnome-screensaver-command", "-l"],
        ["loginctl", "lock-session"],
        ["dm-tool", "lock"],
        ["xdg-screensaver", "lock"],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, timeout=3,
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                logger.info("Lock via: %s", cmd[0])
                return
        except Exception:
            continue
    logger.error("All lock commands failed")


# ── Face recognizer ────────────────────────────────────────────
def recognize_face(frame, known_encs, known_names, threshold=RECOGNITION_THRESH):
    """Returns (name, distance) or (None, 1.0)"""
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
    except Exception as e:
        logger.error("Recognition error: %s", e)
        return None, 1.0


# ══════════════════════════════════════════════════════════════
# FacePresenceGuard — Auto-Lock on Face Leave
# ══════════════════════════════════════════════════════════════
class FacePresenceGuard:
    """
    Monitors camera continuously.
    If enrolled face disappears for FACE_LEAVE_TIMEOUT seconds → auto-lock.
    """

    def __init__(self, known_encs, known_names,
                 timeout: float = FACE_LEAVE_TIMEOUT):
        self.known_encs   = known_encs
        self.known_names  = known_names
        self.timeout      = timeout
        self._running     = False
        self._thread      = None
        self._last_seen   = time.time()
        self._face_absent = False
        self._lock        = threading.Lock()
        self._current_user = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("FacePresenceGuard started (timeout=%.1fs)", self.timeout)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
        logger.info("FacePresenceGuard stopped")

    def _loop(self):
        cap = cv2.VideoCapture(CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS,          10)

        if not cap.isOpened():
            logger.error("FacePresenceGuard: camera not available")
            self._running = False
            return

        logger.info("FacePresenceGuard: camera opened")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            name, dist = recognize_face(frame, self.known_encs, self.known_names)

            with self._lock:
                if name is not None:
                    # Face present
                    self._last_seen    = time.time()
                    self._face_absent  = False
                    self._current_user = name
                else:
                    # Face absent
                    absent_for = time.time() - self._last_seen
                    if absent_for >= self.timeout and not self._face_absent:
                        self._face_absent = True
                        logger.warning(
                            "⚠️  Face absent for %.1fs — triggering auto-lock", absent_for
                        )
                        threading.Thread(
                            target=trigger_lock,
                            args=("face_leave",),
                            daemon=True,
                        ).start()

            time.sleep(CHECK_INTERVAL)

        cap.release()
        logger.info("FacePresenceGuard: camera released")

    @property
    def current_user(self):
        with self._lock:
            return self._current_user

    @property
    def face_absent_for(self) -> float:
        with self._lock:
            return time.time() - self._last_seen


# ══════════════════════════════════════════════════════════════
# UnlockSession — one unlock attempt with liveness
# ══════════════════════════════════════════════════════════════
class UnlockSession:
    """
    Runs one face+liveness unlock cycle.
    Writes PAM cache on success.
    """

    def __init__(self, known_encs, known_names):
        self.known_encs  = known_encs
        self.known_names = known_names

        try:
            from nova_unlock.vision.liveness import LivenessDetector
            self.liveness = LivenessDetector(required_blinks=1, challenge_secs=7)
        except Exception:
            self.liveness = None
            logger.warning("Liveness detector not available")

    def run(self) -> bool:
        cap = cv2.VideoCapture(CAMERA_INDEX)
        if not cap.isOpened():
            logger.error("UnlockSession: camera unavailable")
            return False

        logger.info("UnlockSession started")
        deadline     = time.time() + 15.0
        face_matched = False
        matched_user = None
        live_passed  = False

        try:
            while time.time() < deadline:
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue

                # Step 1 — face recognition
                if not face_matched:
                    name, dist = recognize_face(
                        frame, self.known_encs, self.known_names
                    )
                    if name:
                        face_matched = True
                        matched_user = name
                        logger.info("Face matched: %s (dist=%.3f)", name, dist)
                        if self.liveness:
                            self.liveness.reset()

                # Step 2 — liveness check
                if face_matched:
                    if self.liveness and LIVENESS_REQUIRED:
                        res = self.liveness.update(frame)
                        if res["status"] == "passed":
                            live_passed = True
                            break
                        elif res["status"] == "failed":
                            logger.warning("Liveness failed for %s", matched_user)
                            return False
                    else:
                        # Liveness disabled → trust face match
                        live_passed = True
                        break

                time.sleep(0.05)

        finally:
            cap.release()

        if face_matched and live_passed and matched_user:
            write_pam_cache(matched_user)
            logger.info("✅ Unlock SUCCESS: %s", matched_user)
            return True

        logger.info("Unlock FAILED (face=%s live=%s)", face_matched, live_passed)
        return False


# ══════════════════════════════════════════════════════════════
# Main Daemon
# ══════════════════════════════════════════════════════════════
def main():
    # Lock file — prevent multiple instances
    if LOCK_FILE.exists():
        logger.info("Already running (lock file exists)")
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.touch()

    def cleanup(sig=None, frame=None):
        LOCK_FILE.unlink(missing_ok=True)
        logger.info("Daemon exiting (sig=%s)", sig)
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT,  cleanup)

    logger.info("═══ NovaUnlock Daemon v5.2 starting ═══")

    known_encs, known_names = load_known_faces()
    if not known_encs:
        logger.warning("No enrolled faces found — daemon idle")
        cleanup()
        return

    # ── Mode: unlock or guard? ────────────────────────────────
    # Called with --guard → start presence watcher (auto-lock)
    # Called without args → run one unlock session
    mode = "unlock"
    if len(sys.argv) > 1 and sys.argv[1] == "--guard":
        mode = "guard"

    if mode == "guard":
        logger.info("Starting FacePresenceGuard mode")
        guard = FacePresenceGuard(known_encs, known_names,
                                  timeout=FACE_LEAVE_TIMEOUT)
        guard.start()
        try:
            while True:
                time.sleep(5)
                logger.debug(
                    "Guard alive — user=%s absent_for=%.1fs",
                    guard.current_user, guard.face_absent_for
                )
        except KeyboardInterrupt:
            guard.stop()
        finally:
            cleanup()
    else:
        # Single unlock attempt
        session = UnlockSession(known_encs, known_names)
        success = session.run()
        LOCK_FILE.unlink(missing_ok=True)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
