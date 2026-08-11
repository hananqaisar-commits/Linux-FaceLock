#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

import cv2
import face_recognition
import numpy as np

NOVA_PATH = Path(os.environ.get('ProgramData', 'C:\\ProgramData')) / 'NovaUnlock'
FACES_DIR = NOVA_PATH / 'data' / 'faces'
META_FILE = FACES_DIR / 'users_meta.json'


def save_meta(username, samples):
    meta = {}
    if META_FILE.exists():
        try:
            meta = json.loads(META_FILE.read_text())
        except Exception:
            meta = {}
    meta[username] = {
        'samples': samples,
        'version': 'windows-v5.4',
        'enrolled_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'machine': os.environ.get('COMPUTERNAME', ''),
    }
    META_FILE.write_text(json.dumps(meta, indent=2))


def open_camera():
    cap = cv2.VideoCapture(0)
    if not cap or not cap.isOpened():
        if cap:
            cap.release()
        return None
    
    ok, frame = cap.read()
    if ok and frame is not None:
        print('[OK] Camera opened: index=0 (default backend)')
        return cap
        
    cap.release()
    return None


def detect_locations(rgb):
    try:
        return face_recognition.face_locations(rgb, model='hog')
    except Exception as exc:
        print(f'[WARN] Face detector error: {exc}')
        return []


def encode_faces(rgb, locations):
    try:
        return face_recognition.face_encodings(rgb, locations)
    except Exception as exc:
        print(f'[WARN] Face encoding error: {exc}')
        return []


def main():
    username = os.environ.get('USERNAME') or os.environ.get('USER') or 'user'
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    face_file = FACES_DIR / f'{username}.npy'

    print('=============================================')
    print(' NovaUnlock - Windows Face Enrollment')
    print('=============================================')
    print(f'User: {username}')
    print('Look directly at the camera until enrollment completes.')

    try:
        input('Press ENTER when ready...')
    except EOFError:
        pass

    try:
        cap = open_camera()
        if not cap or not cap.isOpened():
            print('[ERROR] No camera found. Windows registration will continue; rerun enrollment after allowing camera access.')
            return 2

        for _ in range(10):
            cap.read()
            time.sleep(0.1)

        encodings = []
        attempts = 0
        samples_needed = 5
        min_samples = 1
        max_attempts = 180

        while len(encodings) < samples_needed and attempts < max_attempts:
            ok, frame = cap.read()
            attempts += 1
            if not ok or frame is None:
                time.sleep(0.1)
                continue

            small = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            locations = detect_locations(rgb)

            if locations:
                face_encs = encode_faces(rgb, locations)
                if face_encs:
                    encodings.append(face_encs[0])
                    print(f'[OK] Sample {len(encodings)}/{samples_needed}')

            display = frame.copy()
            for top, right, bottom, left in locations:
                top, right, bottom, left = top * 2, right * 2, bottom * 2, left * 2
                cv2.rectangle(display, (left, top), (right, bottom), (0, 255, 0), 2)

            color = (0, 255, 0) if locations else (0, 0, 255)
            cv2.putText(
                display,
                f'NovaUnlock Enrollment {len(encodings)}/{samples_needed}',
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )

            try:
                cv2.imshow('NovaUnlock Face Enrollment - Q to cancel', display)
                if cv2.waitKey(100) & 255 == ord('q'):
                    print('[ERROR] Enrollment cancelled.')
                    try:
                        cap.release()
                        try:
                            cv2.destroyAllWindows()
                        except Exception:
                            pass
                        return 1
                    except Exception:
                        return 1
            except Exception as exc:
                print(f'[WARN] Preview unavailable: {exc}')
                time.sleep(0.1)
    except Exception:
        return 1
    finally:
        try:
            cap.release()
        except Exception:
            pass
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    try:
        if len(encodings) < min_samples:
            print(f'[ERROR] Only {len(encodings)} valid samples captured. Windows registration will continue; rerun enrollment with better lighting/camera access.')
            return 2

        np.save(str(face_file), np.mean(encodings, axis=0))
        save_meta(username, len(encodings))
        print(f'[OK] Face enrolled: {face_file}')
        return 0
    except Exception:
        return 1


if __name__ == '__main__':
    sys.exit(main())
