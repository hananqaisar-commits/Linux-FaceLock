#!/usr/bin/env python3
"""NovaUnlock — GUI Face Enrollment v4.5 (Simple Mode)"""

import cv2
import face_recognition
import numpy as np
import os
import sys
import time
import json
from pathlib import Path

PROJECT_DIR = Path.home() / "NovaUnlock"
DATA_DIR = PROJECT_DIR / "data" / "faces"
META_FILE = DATA_DIR / "users_meta.json"

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
    ensure_dirs()
    username = os.environ.get("USER", "user")
    force = "--force" in sys.argv

    face_file = DATA_DIR / f"{username}.npy"

    if face_file.exists() and not force:
        print(f"✅ Already enrolled: {username}")
        sys.exit(0)

    # Open camera
    cap = None
    for idx in [0, 1, 2]:
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            break
        cap.release()

    if not cap or not cap.isOpened():
        print("❌ No camera found")
        sys.exit(1)

    # Warm up
    for _ in range(10):
        cap.read()
        time.sleep(0.1)

    encodings = []
    samples_needed = 10
    attempts = 0
    max_attempts = 100

    print(f"📷 Enrolling: {username}")
    print(f"→  Look straight at camera — {samples_needed} samples needed")

    while len(encodings) < samples_needed and attempts < max_attempts:
        ret, frame = cap.read()
        if not ret:
            attempts += 1
            continue

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb, model="hog")

        display = frame.copy()

        if locations:
            face_encs = face_recognition.face_encodings(rgb, locations)
            if face_encs:
                encodings.append(face_encs[0])
                count = len(encodings)

                # Green box
                for (top, right, bottom, left) in locations:
                    cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)
                    cv2.putText(display,
                        f"✓ {count}/{samples_needed}",
                        (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(display,
                "No face — look at camera",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Progress bar
        h, w = display.shape[:2]
        progress = int((len(encodings) / samples_needed) * (w - 20))
        cv2.rectangle(display, (10, h-25), (w-10, h-10), (50, 50, 50), -1)
        cv2.rectangle(display, (10, h-25), (10+progress, h-10), (0, 255, 0), -1)
        cv2.putText(display,
            f"Progress: {len(encodings)}/{samples_needed}",
            (10, h-30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        try:
            cv2.imshow("NovaUnlock Enrollment — Q to cancel", display)
            key = cv2.waitKey(100) & 0xFF
            if key == ord('q'):
                print("⚠️ Cancelled")
                cap.release()
                cv2.destroyAllWindows()
                sys.exit(1)
        except:
            pass

        attempts += 1

    cap.release()
    try:
        cv2.destroyAllWindows()
    except:
        pass

    if len(encodings) < 3:
        print(f"❌ Only {len(encodings)} samples — not enough")
        sys.exit(1)

    # Save average encoding
    avg_encoding = np.mean(encodings, axis=0)
    np.save(str(face_file), avg_encoding)
    os.chmod(str(face_file), 0o600)
    save_meta(username, len(encodings))

    print(f"🎉 Enrolled! {len(encodings)} samples — {face_file}")
    sys.exit(0)

if __name__ == '__main__':
    main()
