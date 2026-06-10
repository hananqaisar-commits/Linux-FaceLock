#!/usr/bin/env python3
"""NovaUnlock — Simple CLI Face Enrollment v4.5"""

import cv2
import face_recognition
import numpy as np
import os
import sys
import time
import json
from pathlib import Path

def get_project_dir():
    home = Path.home()
    return home / "NovaUnlock"

PROJECT_DIR = get_project_dir()
DATA_DIR = PROJECT_DIR / "data" / "faces"
META_FILE = PROJECT_DIR / "data" / "faces" / "users_meta.json"

def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def save_meta(username, samples):
    meta = {}
    if META_FILE.exists():
        try:
            meta = json.loads(META_FILE.read_text())
        except:
            pass
    meta[username] = {"samples": samples, "version": "4.5"}
    META_FILE.write_text(json.dumps(meta, indent=2))

def main():
    print("\n" + "="*50)
    print("  NovaUnlock — CLI Face Enrollment v4.5")
    print("="*50)

    force = "--force" in sys.argv
    ensure_dirs()

    username = input("\n  Enter your Linux username (same as whoami): ").strip()
    if not username:
        print("  ❌ No username entered.")
        sys.exit(1)

    # Validate user exists
    import pwd
    try:
        pwd.getpwnam(username)
    except KeyError:
        print(f"  ❌ '{username}' is not a valid Linux user.")
        sys.exit(1)

    face_file = DATA_DIR / f"{username}.npy"

    if face_file.exists() and not force:
        print(f"  ⚠️  Face already enrolled for '{username}'.")
        print(f"  Use --force to re-enroll.")
        sys.exit(0)

    print(f"\n  📋 Instructions:")
    print(f"  1. Camera ke saamne seedha dekho")
    print(f"  2. Normal lighting chahiye")
    print(f"  3. Glasses hata lo agar ho sake")
    print(f"  4. Sirf seedha dekho — angles ki zaroorat nahi\n")
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

    # Average encoding save karo
    avg_encoding = np.mean(encodings, axis=0)
    np.save(str(face_file), avg_encoding)
    os.chmod(str(face_file), 0o600)
    save_meta(username, len(encodings))

    print(f"\n  🎉 Enrollment Complete!")
    print(f"  →  User: {username}")
    print(f"  →  Samples: {len(encodings)}")
    print(f"  →  Saved: {face_file}")
    print(f"  →  NovaUnlock is ready!\n")
    sys.exit(0)

if __name__ == '__main__':
    main()
