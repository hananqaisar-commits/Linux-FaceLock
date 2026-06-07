#!/usr/bin/env python3
import sys
import os
import json
import time
import fcntl
import logging
import subprocess
from pathlib import Path

# ── Auto-detect everything ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from nova_unlock.core import setup_environment, find_nova_root

env_info = setup_environment()
ROOT = find_nova_root()
REAL_USER = env_info["user"]

sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

LOCK_FILE = "/tmp/nova_face_unlock.lock"
CACHE_FILE = "/tmp/nova_face_pam_cache.json"

try:
    lock_fd = open(LOCK_FILE, "w")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Face unlock already running")
    sys.exit(0)

os.makedirs(str(ROOT / "logs"), exist_ok=True)
logging.basicConfig(
    filename=str(ROOT / "logs" / "face_auth.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s : %(message)s"
)
log = logging.getLogger()

def load_face_map():
    try:
        p = ROOT / "data" / "face_user_map.json"
        if p.exists():
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}

def write_pam_cache(linux_user: str, profile_name: str):
    data = {
        "user": linux_user.strip().lower(),
        "profile": profile_name,
        "ts": time.time()
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    os.chmod(CACHE_FILE, 0o600)

def trigger_pam_unlock():
    cmds = [
        ["xdotool", "key", "Return"],
        ["bash", "-lc", "sleep 0.6; xdotool key Return"],
        ["bash", "-lc", "sleep 1.2; xdotool key Return"],
    ]
    for cmd in cmds:
        try:
            if cmd[0] == "bash":
                subprocess.Popen(cmd)
            else:
                subprocess.run(cmd, timeout=2, capture_output=True)
        except Exception:
            pass

try:
    try:
        os.remove(CACHE_FILE)
    except FileNotFoundError:
        pass

    log.info("=" * 50)
    log.info("Nova face unlock daemon starting")
    log.info(f"DISPLAY={os.environ.get('DISPLAY')}")
    log.info(f"XAUTHORITY={os.environ.get('XAUTHORITY')}")
    log.info(f"User: {REAL_USER}")
    log.info(f"Desktop: {env_info['desktop']}")
    log.info(f"Display Manager: {env_info['display_manager']}")

    from nova_unlock.ui.face_id_embed import FaceIDLoginApp
    log.info("Launching face unlock UI")
    result = FaceIDLoginApp().run()
    log.info(f"UI result: {result}")

    if result:
        face_map = load_face_map()
        resolved_user = str(result).strip().lower()
        current_user = REAL_USER.strip().lower()

        if resolved_user == current_user:
            log.info(f"✅ Matched '{result}' → user '{resolved_user}' → creating PAM cache")
            write_pam_cache(resolved_user, result)
            trigger_pam_unlock()
            log.info("✅ PAM unlock triggered via Enter key sequence")
            sys.exit(0)
        else:
            log.warning(f"❌ Profile '{result}' maps to '{resolved_user}', not '{current_user}' → refusing")
            sys.exit(1)
    else:
        log.warning("❌ No face match")
        sys.exit(1)

except Exception as ex:
    import traceback
    log.error(f"Error: {ex}")
    traceback.print_exc()
    sys.exit(1)

finally:
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        os.remove(LOCK_FILE)
    except Exception:
        pass
