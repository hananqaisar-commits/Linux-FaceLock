#!/usr/bin/env python3
"""NovaUnlock — Simple CLI Face Enrollment v4.5

Stores the enrolled profile in the ONE canonical faces dir
(nova_unlock.vision.face_recognizer.get_faces_dir → /var/lib/novaunlock/faces),
so the greeter, lock-screen daemon and enrollment all read/write the SAME place.
That shared location is what makes facelock work end-to-end.
"""

import cv2
import sys
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
import os
import time
import json
import pwd

from nova_unlock.vision import face_recognizer as fr

# ── Canonical faces directory (single source of truth) ─────────────────────
FACES_DIR = fr.get_faces_dir()
META_FILE = fr.get_meta_file()


def ensure_dirs():
    FACES_DIR.mkdir(parents=True, exist_ok=True)


def save_meta(username, samples):
    meta = fr.load_meta()
    meta[username] = {
        "samples": samples,
        "version": "4.5",
        "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "machine": os.uname().nodename if hasattr(os, "uname") else "",
    }
    fr.save_meta(meta)


def main():
    print("\n" + "=" * 50)
    print("  NovaUnlock — CLI Face Enrollment v4.5")
    print("=" * 50)

    force = "--force" in sys.argv
    ensure_dirs()

    username = input("\n  Enter your Linux username (same as whoami): ").strip()
    if not username:
        print("  ❌ No username entered.")
        sys.exit(1)

    # Validate user exists
    try:
        pwd.getpwnam(username)
    except KeyError:
        print(f"  ❌ '{username}' is not a valid Linux user.")
        sys.exit(1)

    face_file = FACES_DIR / f"{username}.npy"

    if face_file.exists() and not force:
        print(f"  ⚠️  Face already enrolled for '{username}'.")
        print(f"  Use --force to re-enroll.")
        sys.exit(0)

    print(f"\n  📋 Instructions:")
    print(f"  1. Camera ke saamne seedha dekho")
    print(f"  2. Normal lighting chahiye")
    print(f"  3. Glasses hata lo agar ho sake")
    print(f"  4. Sirf seedha dekho — angles ki zaroorat nahi\n")
    print(f"  Faces will be saved to: {FACES_DIR}")
    input("  Press ENTER when ready...")

    # Open camera
    cap = None
    for idx in [0, 1, 2]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            print(f"  ✅ Camera found (index {idx})")
            break
        cap.release()

    if not cap or not cap.isOpened():
        print("  ❌ No camera found!")
        sys.exit(1)

    # Warm up
    print("  →  Camera warming up...")
    for _ in range(10):
        cap.read()
        time.sleep(0.1)

    encodings = []
    samples_needed = 10
    attempts = 0
    max_attempts = 60

    print(f"  →  Capturing {samples_needed} samples...")
    print(f"  →  Just look straight at camera!\n")

    while len(encodings) < samples_needed and attempts < max_attempts:
        ret, frame = cap.read()
        if not ret:
            attempts += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")

        if locations:
            face_encs = face_recognition.face_encodings(rgb, locations)
            if face_encs:
                encodings.append(face_encs[0])
                print(f"  ✅ Sample {len(encodings)}/{samples_needed}")
        else:
            if attempts % 8 == 0:
                print(f"  ⚠️  No face detected — keep looking at camera")

        attempts += 1
        time.sleep(0.3)

    cap.release()

    if len(encodings) < 3:
        print(f"\n  ❌ Only {len(encodings)} samples — not enough")
        print(f"  →  Try better lighting and try again")
        sys.exit(1)

    # Average encoding save karo (canonical dir + meta)
    avg_encoding = np.mean(encodings, axis=0)
    if fr.save_face(username, avg_encoding):
        os.chmod(str(face_file), 0o600)
        save_meta(username, len(encodings))
        print(f"\n  🎉 Enrollment Complete!")
        print(f"  →  User: {username}")
        print(f"  →  Samples: {len(encodings)}")
        print(f"  →  Saved: {face_file}")
        print(f"  →  NovaUnlock is ready!\n")
        sys.exit(0)
    else:
        print(f"\n  ❌ Failed to save enrollment for '{username}'.")
        sys.exit(1)


if __name__ == '__main__':
    main()
