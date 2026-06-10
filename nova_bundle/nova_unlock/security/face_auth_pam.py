#!/usr/bin/env python3
"""
NovaUnlock Professional Face Authentication
- Login: scan → match ANY user → return username
- Unlock: scan → match SPECIFIC user → return True/False
"""
import os
import sys
import time
import json
import logging
from pathlib import Path

# ── Auto-detect everything ──────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from nova_unlock.core import setup_environment, find_nova_root

env_info = setup_environment()
ROOT = find_nova_root()
REAL_USER = env_info["user"]

sys.path.insert(0, str(ROOT))

log = logging.getLogger("nova.face.pam")

def get_face_map():
    """Load profile-to-linux-user mapping."""
    map_path = ROOT / "data" / "face_user_map.json"
    try:
        if map_path.exists():
            return json.loads(map_path.read_text())
    except Exception:
        pass
    return {}

def face_login():
    """
    LOGIN MODE: Scan face, match ANY enrolled user, return linux username.
    Used at LightDM greeter / boot.
    Returns: linux_username or None
    """
    import cv2
    import numpy as np
    import face_recognition
    from nova_unlock.vision.face_recognizer import get_enrolled_users, load_face, get_threshold

    face_map = get_face_map()
    threshold = get_threshold()

    profiles = {}
    for profile_name in get_enrolled_users():
        emb = load_face(profile_name)
        if emb is not None:
            profiles[profile_name] = {"emb": emb, "linux_user": profile_name}

    if not profiles:
        log.warning("No enrolled faces")
        return None

    cap = None
    for i in range(10):
        c = cv2.VideoCapture(i)
        if c.isOpened():
            c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, _ = c.read()
            if ok:
                cap = c
                break
        c.release()

    if not cap:
        log.error("Camera not available")
        return None

    try:
        for _ in range(4):
            cap.read()

        for attempt in range(5):
            embs = []
            for _ in range(6):
                ok, frame = cap.read()
                if not ok:
                    continue
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    locs = face_recognition.face_locations(rgb, model="hog")
                    if locs:
                        encs = face_recognition.face_encodings(rgb, locs)
                        if encs:
                            embs.append(encs[0])
                except Exception:
                    pass
                time.sleep(0.04)

            if not embs:
                time.sleep(0.5)
                continue

            live = np.mean(embs, axis=0)
            best_profile = None
            best_dist = 999.0

            for pname, pdata in profiles.items():
                dist = float(face_recognition.face_distance([pdata["emb"]], live)[0])
                if dist < best_dist:
                    best_dist = dist
                    best_profile = pname

            if best_dist <= threshold and best_profile:
                linux_user = profiles[best_profile]["linux_user"]
                log.info(f"LOGIN: matched {best_profile} → linux user {linux_user}")
                return linux_user

            time.sleep(0.5)

        return None
    finally:
        cap.release()


def face_unlock(target_user: str):
    """
    UNLOCK MODE: Scan face, match ONLY target_user's profiles.
    Used at lockscreen.
    Returns: True if matched, False otherwise
    """
    import cv2
    import numpy as np
    import face_recognition
    from nova_unlock.vision.face_recognizer import get_enrolled_users, load_face, get_threshold

    target_user = target_user.strip().lower()
    face_map = get_face_map()
    threshold = get_threshold()

    profiles = {}
    for profile_name in get_enrolled_users():
        linux_user = profile_name.strip().lower()
        if linux_user != target_user:
            continue
        emb = load_face(profile_name)
        if emb is not None:
            profiles[profile_name] = emb

    if not profiles:
        log.warning(f"No enrolled face for user {target_user}")
        return False

    cap = None
    for i in range(10):
        c = cv2.VideoCapture(i)
        if c.isOpened():
            c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, _ = c.read()
            if ok:
                cap = c
                break
        c.release()

    if not cap:
        log.error("Camera not available")
        return False

    try:
        for _ in range(4):
            cap.read()

        for attempt in range(5):
            embs = []
            for _ in range(6):
                ok, frame = cap.read()
                if not ok:
                    continue
                try:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    locs = face_recognition.face_locations(rgb, model="hog")
                    if locs:
                        encs = face_recognition.face_encodings(rgb, locs)
                        if encs:
                            embs.append(encs[0])
                except Exception:
                    pass
                time.sleep(0.04)

            if not embs:
                time.sleep(0.5)
                continue

            live = np.mean(embs, axis=0)

            for pname, saved in profiles.items():
                dist = float(face_recognition.face_distance([saved], live)[0])
                if dist <= threshold:
                    log.info(f"UNLOCK: matched {pname} for user {target_user}")
                    return True

            time.sleep(0.5)

        return False
    finally:
        cap.release()
