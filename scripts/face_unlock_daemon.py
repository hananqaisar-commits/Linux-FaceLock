#!/usr/bin/env python3
"""
NovaUnlock — Face Unlock Daemon (lock-screen unlock + presence guard).

Two modes, ONE recognition path:
  - unlock mode (default): launched by the watcher when the screen locks.
    Shows the SAME FaceUnlockWidget + FaceWorker used by the greeter/demo,
    embedded on the lock screen via the trusted universal_embed pattern. On a
    real match it writes the PAM face-cache (/var/lib/novaunlock/pam_cache.json)
    so the lock screen unlocks.
  - --guard mode: continuous face-presence watcher (auto-lock when the enrolled
    face disappears). Kept for installations that run the daemon as a service.

Faces + threshold + PAM cache path ALL come from nova_unlock.vision.face_recognizer
(get_faces_dir / get_threshold / get_pam_cache_file), so the daemon reads the
exact same profiles the enrollment wrote — which is what makes facelock work.
"""

import sys
import os
import time
import json
import logging
import threading
import subprocess
from pathlib import Path

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
        p = Path("/var/lib/novaunlock/deps_status.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"ok": False, "missing": miss, "remediation": cmd}, indent=2))
    except Exception:
        pass
    return miss, msg


# ── Nova root resolver (same as the greeter) ───────────────────────────────
# When the release is built, every .py is compiled to .pyc and the .py deleted,
# so this daemon runs as ``nova_bundle/scripts/face_unlock_daemon.pyc``. Its own
# __file__ points inside ``nova_bundle/`` but config/nova.conf lives at
# ``nova_bundle/config/nova.conf``. ``find_nova_root`` (in nova_unlock.core)
# already handles that via system_detect's __file__, but the installer/watcher
# does not always export NOVA_ROOT — so we resolve it here and export it BEFORE
# setup_environment() runs. Without this the daemon can resolve the wrong root,
# fail to find enrolled faces, and exit immediately (UI shows, then nothing).
sys.path.insert(0, str(Path(__file__).parent.parent))


def _resolve_entry():
    """Resolve the NovaUnlock root when launched as a compiled .pyc bundle.

    Returns the directory that contains ``config/nova.conf``. Honours the
    NOVA_ROOT environment variable first, then walks the candidate layouts for
    both the development tree and the installed ``nova_bundle`` tree. Referenced
    by the release smoke test (test_daemon_resolves_pyc_entrypoint).
    """
    env = os.environ.get("NOVA_ROOT", "").strip()
    if env and (Path(env) / "config" / "nova.conf").exists():
        return Path(env)

    here = Path(__file__).resolve()
    # <bundle>/scripts/..       == nova_bundle    (installed)
    # <bundle>/scripts/../..    == install_dir     (fallback)
    for cand in (here.parent.parent, here.parent.parent.parent):
        if (cand / "config" / "nova.conf").exists():
            return cand

    if env:
        return Path(env)
    # Last resort: the nova_bundle directory itself.
    return here.parent.parent


try:
    os.environ["NOVA_ROOT"] = str(_resolve_entry())
except Exception:
    pass

try:
    from nova_unlock.core import setup_environment, find_nova_root
    env_info = setup_environment()
    REAL_USER = env_info.get("user", os.environ.get("USER", "root"))
except Exception:
    REAL_USER = os.environ.get("SUDO_USER", os.environ.get("USER", "root"))
    def find_nova_root():
        return Path(__file__).resolve().parent.parent

ROOT = find_nova_root()
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
os.environ.pop("WAYLAND_DISPLAY", None)

# ── Canonical paths / recognition config ───────────────────────────────────
from nova_unlock.vision.face_recognizer import (
    get_faces_dir, get_threshold, get_pam_cache_file,
    get_enrolled_users, load_face, get_max_attempts,
)
from nova_unlock.vision.camera_detector import open_camera
try:
    from nova_unlock.ui.face_unlock_widget import Sig, FaceUnlockWidget, FaceWorker
except ImportError:
    from nova_unlock.ui.face_unlock_widget import Sig, FaceUnlockWidget, FaceWorker
from nova_unlock.ui.universal_embed import smart_embed, raise_embedded, ensure_on_top

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

FACES_DIR  = get_faces_dir()
CACHE_FILE = get_pam_cache_file()
LOCK_FILE  = Path("/tmp/nova_unlock_face.lock")
# State file gating the "Hello <username>" greeting to once per lock→unlock cycle.
HELLO_SHOWN = Path("/var/lib/novaunlock/hello_shown")


def clear_hello_marker() -> None:
    """Allow the next successful face match to show the greeting again.

    Called when a NEW unlock session begins (screen locked / lid reopened), so
    the greeting appears exactly once per unlock, not on every subsequent scan.
    """
    try:
        HELLO_SHOWN.unlink(missing_ok=True)
    except Exception:
        pass

# ── Retry / behaviour constants ────────────────────────────────────────────
FACE_LEAVE_TIMEOUT  = 10.0   # seconds before auto-lock triggers (guard mode)
CHECK_INTERVAL      = 0.15   # seconds between camera frames (guard mode)
LIVENESS_REQUIRED   = False  # disabled — face match only
CAMERA_INDEX        = 0

LOG_DIR  = Path("/var/log/novaunlock")
LOG_FILE = LOG_DIR / "face_auth.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("nova_daemon")


# ── Load enrolled faces (used by the guard presence watcher) ───────────────
def load_known_faces() -> tuple:
    """Load all enrolled face encodings from the canonical faces dir."""
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


# ── Write PAM cache (same path the installed PAM auth script reads) ────────
def write_pam_cache(username: str) -> None:
    data = {
        "user":    username.strip().lower(),
        "profile": username.strip().lower(),
        "ts":      time.time(),
    }
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(str(CACHE_FILE), "w") as f:
            json.dump(data, f)
        os.chmod(str(CACHE_FILE), 0o600)
        logger.info("PAM cache written for: %s (%s)", username, CACHE_FILE)
    except Exception as e:
        logger.error("PAM cache write failed: %s", e)


# ── Lock screen ────────────────────────────────────────────────────────────
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


# ════════════════════════════════════════════════════════════════════════════
# Face recognizer (used by the guard presence watcher)
# ════════════════════════════════════════════════════════════════════════════
def recognize_face(frame, known_encs, known_names, threshold=None):
    """Returns (name, distance) or (None, 1.0)"""
    if threshold is None:
        threshold = get_threshold()
    try:
        try:
            import face_recognition as fr
        except ImportError:
            _ml = _nova_require_ml_deps()
            if _ml:
                logger.error("ML deps missing — face unlock disabled: %s", _ml[1])
            raise
        import cv2
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


# ════════════════════════════════════════════════════════════════════════════
# FacePresenceGuard — Auto-Lock on Face Leave
# ════════════════════════════════════════════════════════════════════════════
class FacePresenceGuard:
    """
    Monitors camera continuously.
    If enrolled face disappears for FACE_LEAVE_TIMEOUT seconds → auto-lock.
    """

    def __init__(self, known_encs, known_names,
                 timeout: float = FACE_LEAVE_TIMEOUT,
                 threshold=None):
        self.known_encs   = known_encs
        self.known_names  = known_names
        self.threshold    = get_threshold() if threshold is None else threshold
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
        import cv2
        cap = open_camera(max_index=6, width=320, height=240, fps=10)
        if cap is None or not cap.isOpened():
            logger.error("FacePresenceGuard: camera not available")
            self._running = False
            return

        logger.info("FacePresenceGuard: camera opened")

        while self._running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.5)
                continue

            name, dist = recognize_face(
                frame, self.known_encs, self.known_names, self.threshold
            )

            with self._lock:
                if name is not None:
                    self._last_seen    = time.time()
                    self._face_absent  = False
                    self._current_user = name
                else:
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


# ════════════════════════════════════════════════════════════════════════════
# Lock-screen unlock UI — identical FaceUnlockWidget path as greeter/demo
# ════════════════════════════════════════════════════════════════════════════
class DaemonUnlockApp:
    """
    Show the canonical FaceUnlockWidget on the lock screen and write the PAM
    cache on a real match. Uses universal_embed so the UI is reliably visible
    above the screensaver/lock dialog on XFCE/GNOME/KDE/Cinnamon/MATE + LightDM/GDM.
    The FaceWorker performs exactly get_max_attempts() (5) scans; on the 5th
    failed scan it stops and the system password prompt is the fallback (the
    watcher kills this daemon when the screen is unlocked). On the FIRST match
    of each unlock session it also plays the instant "hello, <username>"
    greeting overlay (gated by the hello_shown marker so it appears once).
    """

    def __init__(self):
        self.result = None
        self._matched = None

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()
        w = FaceUnlockWidget(sig, demo_mode=False)

        # New unlock session → let the greeting show once on first match.
        clear_hello_marker()

        ensure_on_top(w, 50)
        app.processEvents()
        logger.info("widget shown")

        for delay in (200, 500, 900, 1400, 2000, 3000):
            QTimer.singleShot(delay, lambda _w=w: smart_embed(_w, 50))

        top_timer = QTimer()
        top_timer.timeout.connect(lambda _w=w: raise_embedded(_w, 50))
        top_timer.start(200)

        def on_ok(name):
            # Match detected — only record the name here. The actual PAM cache
            # write (which releases the lock screen) and the greeting must wait
            # until the success ring animation has fully played, i.e. until
            # sig.unlock_complete.
            self.result = name
            self._matched = name

        def on_unlock_complete():
            # Ring animation finished — NOW commit the unlock so the screen
            # releases only after the green wireframe ring completes.
            name = getattr(self, "_matched", None) or self.result
            try:
                if name:
                    write_pam_cache(name)
                    # Instant "hello, <username>" on first face match of this
                    # unlock session. Gated by the hello_shown marker so it is
                    # shown exactly once per lock→unlock cycle, not on every scan.
                    show_hello_for(name)
            except Exception as e:
                logger.error("unlock-complete handler error: %s", e)
            top_timer.stop()
            QTimer.singleShot(400, app.quit)

        # NOTE: on_fail is intentionally NOT handled. The FaceWorker already
        # performs exactly get_max_attempts() (5) scans internally and emits the
        # final fail itself. Restarting the worker here was the old bug that
        # could run up to 25 scans. After the 5th failed scan we do nothing —
        # the watcher kills this daemon on unlock, and until then the system
        # password prompt is the fallback. (No fewer, no more than 5 attempts.)

        sig.ok.connect(on_ok)
        sig.unlock_complete.connect(on_unlock_complete)

        # Restart the recognition scan when the user clicks the retry icon after
        # all 5 attempts are exhausted. Without this the retry icon appears but
        # clicking it does nothing — "UI shows, then nothing".
        def do_retry():
            nonlocal wk
            try:
                if wk.isRunning():
                    wk.stop()
                    wk.wait(1000)
                wk = FaceWorker(sig)
                wk.start()
            except Exception as e:
                logger.error("retry restart failed: %s", e)

        sig.retry_requested.connect(do_retry)

        def _spawn_worker():
            wk = FaceWorker(sig)
            wk.start()
            return wk

        wk = _spawn_worker()
        self._worker = wk

        app.exec_()
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(1000)
        return self.result


def show_hello_for(username: str) -> None:
    """Play the instant 'hello, <username>' greeting overlay on the lock screen.

    Fires only the FIRST time a face match succeeds in an unlock session (the
    hello_shown marker is cleared by clear_hello_marker() at session start).
    Any failure is swallowed — the greeting is non-blocking eye-candy, never a
    gateway to the desktop, so it must never interfere with the unlock itself.
    """
    try:
        if not username:
            return
        # Only once per lock→unlock cycle.
        if HELLO_SHOWN.exists():
            return
        HELLO_SHOWN.write_text(str(username).strip().lower())
        import subprocess
        python = sys.executable
        root = str(ROOT)
        name = username.strip().lower()
        subprocess.Popen(
            [python, "-m", "nova_unlock.ui.welcome_screen", name],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logger.info("hello overlay triggered for: %s", name)
    except Exception as e:
        logger.error("hello overlay error (non-fatal): %s", e)


# ════════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════════
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

    import signal
    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT,  cleanup)

    logger.info("═══ NovaUnlock Daemon starting ═══")

    # Import numpy lazily (used by load_known_faces / recognize_face)
    global np
    import numpy as np

    known_encs, known_names = load_known_faces()
    if not known_encs:
        logger.warning("No enrolled faces found in %s — daemon idle", FACES_DIR)
        cleanup()
        return

    # ── Mode: unlock or guard? ────────────────────────────────────────────
    # Called with --guard → start presence watcher (auto-lock)
    # Called without args (by the watcher on lock) → run one unlock session
    mode = "unlock"
    if len(sys.argv) > 1 and sys.argv[1] == "--guard":
        mode = "guard"

    try:
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
            logger.info("Starting lock-screen unlock UI")
            result = DaemonUnlockApp().run()
            if result:
                logger.info("✅ Face unlocked: %s", result)
                cleanup()
                sys.exit(0)
            else:
                logger.info("No match within session (password fallback)")
                cleanup()
                sys.exit(1)
    finally:
        # Guarantee the lock file is released even on an unexpected exception,
        # so a crashed session can't block the next unlock daemon from starting.
        try:
            LOCK_FILE.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
