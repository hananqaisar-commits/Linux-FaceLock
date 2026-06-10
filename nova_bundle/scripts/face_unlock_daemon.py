#!/usr/bin/env python3
"""
NovaUnlock — Universal Face Unlock Daemon v4.5
Watches lock screen → launches UI → unlocks
Supports: Ubuntu/GNOME, Kali/XFCE, Fedora, Debian, KDE, Mint
"""

import os
import sys
import time
import fcntl
import signal
import logging
import subprocess
import threading
import re
from pathlib import Path

# ─── Setup ───────────────────────────────────────
_DAEMON_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_DAEMON_ROOT))
from nova_unlock.core import setup_environment, find_nova_root

setup_environment()
HOME        = Path.home()
PROJECT_DIR = find_nova_root()
LOG_DIR     = PROJECT_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("NOVA_ROOT", str(PROJECT_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_DIR / "daemon.log")),
        logging.StreamHandler(sys.stdout),
    ]
)
log = logging.getLogger("NovaUnlock")

# ─── Singleton lock ───────────────────────────────
LOCK_FILE = "/tmp/nova_unlock_daemon.lock"
try:
    _lfd = open(LOCK_FILE, "w")
    fcntl.flock(_lfd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("NovaUnlock daemon already running")
    sys.exit(0)

# ─── Globals ─────────────────────────────────────
running       = True
ui_running    = False
UI_LOCK       = "/tmp/nova_unlock_ui.lock"


# ══════════════════════════════════════════════════
# SIGNAL HANDLERS
# ══════════════════════════════════════════════════

def _stop(sig, frame):
    global running
    log.info("Shutdown signal received")
    running = False


signal.signal(signal.SIGINT,  _stop)
signal.signal(signal.SIGTERM, _stop)


# ══════════════════════════════════════════════════
# DISPLAY AUTO-DETECT
# ══════════════════════════════════════════════════

def get_display_env() -> dict:
    """Auto-detect DISPLAY and XAUTHORITY"""
    env   = dict(os.environ)
    uid   = os.getuid()
    user  = env.get("USER", "")

    # Find DISPLAY from who
    display = env.get("DISPLAY", "")
    if not display:
        try:
            out = subprocess.check_output(
                ["who"], text=True, timeout=3
            )
            for line in out.splitlines():
                m = re.search(r'\(:(\d+)\)', line)
                if m:
                    display = f":{m.group(1)}"
                    break
        except Exception:
            pass
        display = display or ":1"

    # Find XAUTHORITY
    xauth = env.get("XAUTHORITY", "")
    if not xauth or not os.path.exists(xauth):
        candidates = [
            f"/run/user/{uid}/gdm/Xauthority",
            f"{HOME}/.Xauthority",
            f"/var/run/lightdm/{user}/xauthority",
            f"/var/run/sddm/{{Xauthority}}",
            f"/run/user/{uid}/Xauthority",
        ]
        for c in candidates:
            if os.path.exists(c):
                xauth = c
                break

    # DBus session
    dbus = env.get("DBUS_SESSION_BUS_ADDRESS", "")
    if not dbus:
        dbus = f"unix:path=/run/user/{uid}/bus"

    env["DISPLAY"]                  = display
    env["XAUTHORITY"]               = xauth
    env["DBUS_SESSION_BUS_ADDRESS"] = dbus
    env["QT_QPA_PLATFORM"]          = "xcb"
    env.pop("WAYLAND_DISPLAY", None)

    return env


# ══════════════════════════════════════════════════
# LOCK SCREEN DETECTION — Universal
# ══════════════════════════════════════════════════

def _dbus_locked(dest, path, iface) -> bool:
    try:
        r = subprocess.run([
            "dbus-send", "--session",
            f"--dest={dest}",
            "--type=method_call", "--print-reply",
            path, f"{iface}.GetActive"
        ], capture_output=True, text=True, timeout=3)
        return "true" in r.stdout.lower()
    except Exception:
        return False


def is_screen_locked() -> bool:
    """Check all known lock screen DBus interfaces"""
    # GNOME (Ubuntu, Fedora, Debian, Kali-GNOME)
    if _dbus_locked(
        "org.gnome.ScreenSaver",
        "/org/gnome/ScreenSaver",
        "org.gnome.ScreenSaver"
    ):
        return True

    # freedesktop (KDE, XFCE, generic)
    if _dbus_locked(
        "org.freedesktop.ScreenSaver",
        "/ScreenSaver",
        "org.freedesktop.ScreenSaver"
    ):
        return True

    # Cinnamon (Mint)
    if _dbus_locked(
        "org.cinnamon.ScreenSaver",
        "/org/cinnamon/ScreenSaver",
        "org.cinnamon.ScreenSaver"
    ):
        return True

    # loginctl fallback (all systemd distros)
    try:
        r = subprocess.run(
            ["loginctl", "show-session", "self",
             "-p", "LockedHint"],
            capture_output=True, text=True, timeout=3
        )
        if "yes" in r.stdout.lower():
            return True
    except Exception:
        pass

    return False


# ══════════════════════════════════════════════════
# UI LAUNCHER
# ══════════════════════════════════════════════════

def _ui_is_running() -> bool:
    try:
        fd = open(UI_LOCK, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        return False
    except IOError:
        return True


def _resolve_entry(rel: str) -> Path:
    """Resolve .py or .pyc entrypoint (binary bundle ships .pyc only)."""
    base = PROJECT_DIR / rel
    if base.exists():
        return base
    pyc = base.with_suffix(".pyc")
    if pyc.exists():
        return pyc
    return base


def launch_ui():
    """Launch face unlock UI as separate process"""
    global ui_running

    if _ui_is_running():
        log.info("UI already running — skip")
        return

    env    = get_display_env()
    env["NOVA_ROOT"] = str(PROJECT_DIR)
    script = _resolve_entry("nova_unlock/ui/face_id_embed.py")

    python_candidates = [
        str(PROJECT_DIR / ".venv" / "bin" / "python3"),
        "/usr/bin/python3.13",
        "/usr/local/bin/python3.13",
        "/usr/bin/python3",
    ]
    python = next((p for p in python_candidates if os.path.exists(p)), None)

    if not python or not script.exists():
        log.error("Python or UI script not found at %s", PROJECT_DIR)
        return

    log.info(f"Launching UI: {python} {script}")
    log.info(f"DISPLAY={env.get('DISPLAY')} "
             f"XAUTH={env.get('XAUTHORITY', '')[:30]}")

    try:
        subprocess.Popen(
            [python, str(script)],
            env=env,
            stdout=open(str(LOG_DIR / "ui.log"), "a"),
            stderr=open(str(LOG_DIR / "ui.log"), "a"),
        )
        ui_running = True
        log.info("✅ UI launched")
    except Exception as e:
        log.error(f"UI launch failed: {e}")


def kill_ui():
    """Kill face unlock UI"""
    global ui_running
    try:
        subprocess.run(
            ["pkill", "-f", "face_id_embed"],
            capture_output=True
        )
        subprocess.run(
            ["pkill", "-f", "FaceIDApp"],
            capture_output=True
        )
    except Exception:
        pass
    try:
        os.remove(UI_LOCK)
    except Exception:
        pass
    ui_running = False


# ══════════════════════════════════════════════════
# MAIN WATCH LOOP
# ══════════════════════════════════════════════════

def main():
    global running

    log.info("=" * 55)
    log.info("NovaUnlock Daemon v4.5 Starting")
    log.info(f"PID  : {os.getpid()}")
    log.info(f"User : {os.environ.get('USER','?')}")
    log.info(f"Home : {HOME}")
    log.info("=" * 55)

    # Lock-on-start: launched by watcher/lock script while screen is locked
    if is_screen_locked():
        log.info("Screen already locked — launching UI immediately")
        time.sleep(1.2)
        launch_ui()
        was_locked = True
    else:
        log.info("Waiting 3s for desktop to load...")
        time.sleep(3)
        log.info("Screen unlocked — watching for lock events")
        was_locked = False

    while running:
        try:
            locked = is_screen_locked()

            # Lock event
            if locked and not was_locked:
                log.info("🔒 LOCK EVENT DETECTED")
                time.sleep(1)  # Let lock screen appear
                launch_ui()

            # Unlock event
            elif not locked and was_locked:
                log.info("🔓 UNLOCK EVENT DETECTED")
                kill_ui()

            was_locked = locked
            time.sleep(1.5)

        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error(f"Watch loop error: {e}")
            time.sleep(2)

    # Cleanup
    log.info("Daemon stopping...")
    kill_ui()
    try:
        fcntl.flock(_lfd, fcntl.LOCK_UN)
        _lfd.close()
        os.remove(LOCK_FILE)
    except Exception:
        pass
    log.info("Daemon stopped")


if __name__ == "__main__":
    main()
