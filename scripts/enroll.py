#!/usr/bin/env python3
"""
NovaUnlock Face Enrollment
Usage:
    python3 scripts/enroll.py
    python3 scripts/enroll.py --force
"""
import os
import sys
import pwd
import time
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

FACES_DIR = ROOT / "data" / "faces"

def valid_linux_user(username):
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite existing enrollment")
    args = parser.parse_args()

    print()
    print("  NovaUnlock — Face Enrollment")
    print()

    username = input("  Enter your Linux username (same as whoami): ").strip().lower()

    if not username:
        print("  No username entered.")
        sys.exit(1)

    if not valid_linux_user(username):
        print(f"  '{username}' is not a valid Linux user on this system.")
        sys.exit(1)

    output = FACES_DIR / f"{username}.npy"

    if output.exists() and not args.force:
        print(f"  Face already enrolled for '{username}'.")
        print("  Use --force to re-enroll.")
        sys.exit(0)

    try:
        import cv2
        import numpy as np
        import face_recognition
    except ImportError as e:
        print(f"  Missing dependency: {e}")
        print("  Run: pip install face_recognition opencv-python numpy")
        sys.exit(1)

    print()
    print(f"  Enrolling face for: {username}")
    print("  Look at the camera. Collecting 30 samples...")
    print()

    cap = None
    for i in range(5):
        c = cv2.VideoCapture(i)
        if c.isOpened():
            c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            ok, _ = c.read()
            if ok:
                cap = c
                break
        c.release()

    if not cap:
        print("  Camera not found.")
        sys.exit(1)

    for _ in range(5):
        cap.read()

    samples = []
    attempts = 0
    max_attempts = 120

    while len(samples) < 30 and attempts < max_attempts:
        ok, frame = cap.read()
        if not ok:
            continue
        attempts += 1

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb, model="hog")

        if locs:
            encs = face_recognition.face_encodings(rgb, locs)
            if encs:
                samples.append(encs[0])
                collected = len(samples)
                bar = "█" * collected + "░" * (30 - collected)
                print(f"\r  [{bar}] {collected}/30", end="", flush=True)

        time.sleep(0.05)

    cap.release()
    print()

    if len(samples) < 10:
        print(f"  Only got {len(samples)} samples. Try better lighting.")
        sys.exit(1)

    import numpy as np
    avg = np.mean(samples, axis=0)
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(output), avg)

    print(f"  Done. Enrolled {username} with {len(samples)} samples.")
    print(f"  Saved to: {output}")
    print()

if __name__ == "__main__":
    main()
