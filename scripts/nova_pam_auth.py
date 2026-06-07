#!/usr/bin/env python3
"""
PAM Face Auth Helper
Called by PAM during login/unlock
Exit 0 = success, Exit 1 = fail
Prints username on success (for login mode)
"""
import os
import sys
import logging
from pathlib import Path

# ── Auto-detect everything ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))
from nova_unlock.core import setup_environment, find_nova_root

env_info = setup_environment()
ROOT = find_nova_root()
REAL_USER = env_info["user"]

sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

os.environ.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")

os.makedirs(ROOT / "logs", exist_ok=True)
logging.basicConfig(
    filename=str(ROOT / "logs" / "pam_nova_face.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s : %(message)s"
)

from nova_unlock.security.face_auth_pam import face_login, face_unlock


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "login"
    target_user = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PAM_USER", "")

    if mode == "unlock" and target_user:
        if face_unlock(target_user):
            print(f"SUCCESS:{target_user}")
            return 0
        else:
            print("FAIL")
            return 1
    else:
        user = face_login()
        if user:
            print(f"SUCCESS:{user}")
            return 0
        else:
            print("FAIL")
            return 1


if __name__ == "__main__":
    sys.exit(main())
