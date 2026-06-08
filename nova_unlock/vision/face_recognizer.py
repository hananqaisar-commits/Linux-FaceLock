#!/usr/bin/env python3
"""
nova_unlock/vision/face_recognizer.py
══════════════════════════════════════════════════════════════
Multi-User Face Login Manager

Rules:
  - 1 face profile per system user
  - Face file stored as: data/faces/<username>.npy
  - Any user can enroll/update their OWN face
  - At boot: scan face → find matching user → auto-login
══════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import sys
import pwd
import json
import time
import logging
import numpy as np
from pathlib import Path

log = logging.getLogger("nova.face_recognizer")

NOVA_DIR    = Path(__file__).parent.parent.parent
FACES_DIR   = NOVA_DIR / "data" / "faces"
META_FILE   = NOVA_DIR / "data" / "faces" / "users_meta.json"
THRESHOLD   = 0.42   # distance threshold (lower = stricter)


# ══════════════════════════════════════════════════════════════
# Face Storage — 1 per user
# ══════════════════════════════════════════════════════════════

def get_system_users() -> list[dict]:
    """Get all real system users (have /home directory)."""
    users = []
    for p in pwd.getpwall():
        if (p.pw_dir.startswith("/home") and
                os.path.exists(p.pw_dir) and
                p.pw_uid >= 1000):
            users.append({
                "username": p.pw_name,
                "uid":      p.pw_uid,
                "home":     p.pw_dir,
                "fullname": p.pw_gecos.split(",")[0] if p.pw_gecos else p.pw_name,
            })
    return users


def get_face_path(username: str) -> Path:
    """Get face file path for a user."""
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    return FACES_DIR / f"{username}.npy"


def is_enrolled(username: str) -> bool:
    """Check if user has a face enrolled."""
    return get_face_path(username).exists()


def get_enrolled_users() -> list[str]:
    """Get list of usernames with enrolled faces."""
    FACES_DIR.mkdir(parents=True, exist_ok=True)
    enrolled = []
    for f in FACES_DIR.glob("*.npy"):
        if f.stem != "meta":  # skip old meta files
            enrolled.append(f.stem)
    return enrolled


def save_face(username: str, embedding: np.ndarray) -> bool:
    """Save face embedding for a user."""
    try:
        FACES_DIR.mkdir(parents=True, exist_ok=True)
        path = get_face_path(username)
        np.save(str(path), embedding)

        # Update metadata
        meta = load_meta()
        meta[username] = {
            "enrolled_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "machine":     os.uname().nodename,
        }
        save_meta(meta)
        log.info(f"Face saved for user: {username}")
        return True
    except Exception as e:
        log.error(f"Failed to save face for {username}: {e}")
        return False


def load_face(username: str) -> np.ndarray | None:
    """Load face embedding for a user."""
    path = get_face_path(username)
    if not path.exists():
        return None
    try:
        return np.load(str(path))
    except Exception as e:
        log.error(f"Failed to load face for {username}: {e}")
        return None


def delete_face(username: str) -> bool:
    """Delete face enrollment for a user."""
    path = get_face_path(username)
    if path.exists():
        path.unlink()
        # Update metadata
        meta = load_meta()
        meta.pop(username, None)
        save_meta(meta)
        log.info(f"Face deleted for user: {username}")
        return True
    return False


def load_meta() -> dict:
    """Load enrollment metadata."""
    try:
        if META_FILE.exists():
            return json.loads(META_FILE.read_text())
    except Exception:
        pass
    return {}


def save_meta(meta: dict):
    """Save enrollment metadata."""
    try:
        META_FILE.write_text(json.dumps(meta, indent=2))
    except Exception as e:
        log.warning(f"Could not save meta: {e}")


# ══════════════════════════════════════════════════════════════
# Face Enrollment
# ══════════════════════════════════════════════════════════════

def enroll_user_face(username: str,
                     num_frames: int = 40,
                     verbose: bool = True) -> bool:
    """
    Enroll face for a specific system user.
    Captures from camera, saves as data/faces/<username>.npy
    """
    try:
        import cv2
        import face_recognition
    except ImportError as e:
        print(f"❌ Missing: {e} — run: pip install face-recognition")
        return False

    # Verify user exists
    system_users = [u["username"] for u in get_system_users()]
    if username not in system_users:
        print(f"❌ User '{username}' not found on this system")
        print(f"   Available users: {system_users}")
        return False

    if verbose:
        print(f"\n  Enrolling face for system user: {username}")
        if is_enrolled(username):
            print(f"  ⚠️  Replacing existing face for {username}")

    # Open camera
    cap = _open_camera(verbose)
    if cap is None:
        return False

    if verbose:
        print(f"\n  📷 Instructions:")
        print("  • Look directly at the camera")
        print("  • Good lighting, face clearly visible")
        print("  • Stay still during capture\n")
        for i in range(3, 0, -1):
            print(f"  Starting in {i}...", end='\r')
            time.sleep(1)
        print(f"  Capturing {num_frames} frames...      ")

    # Warmup
    for _ in range(10):
        cap.read()

    # Capture
    encodings  = []
    attempts   = 0
    max_tries  = num_frames * 3

    while len(encodings) < num_frames and attempts < max_tries:
        ret, frame = cap.read()
        if not ret:
            attempts += 1
            continue
        attempts += 1

        try:
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs  = face_recognition.face_locations(rgb, model="hog")
            if locs:
                encs = face_recognition.face_encodings(rgb, locs)
                if encs:
                    encodings.append(encs[0])
                    if verbose:
                        pct = len(encodings) / num_frames
                        bar = int(pct * 30)
                        print(f"  [{'█'*bar}{'░'*(30-bar)}] "
                              f"{len(encodings)}/{num_frames}", end='\r')
            else:
                if verbose:
                    print(f"  ⚠️  No face detected — look at camera      ", end='\r')
        except Exception:
            pass
        time.sleep(0.05)

    cap.release()
    print()

    if len(encodings) < 5:
        print(f"  ❌ Only {len(encodings)} frames detected — try better lighting")
        return False

    # Average all encodings → single robust embedding
    avg_enc = np.mean(encodings, axis=0)
    success = save_face(username, avg_enc)

    if success and verbose:
        print(f"  ✅ Face enrolled for '{username}' ({len(encodings)} frames)")

    return success


# ══════════════════════════════════════════════════════════════
# Face Identification — Boot Login
# ══════════════════════════════════════════════════════════════

def identify_user(timeout: int = 30,
                  max_attempts: int = 5,
                  log_file: str | None = None) -> str | None:
    """
    Capture face from camera and identify which system user it is.
    Returns username string if matched, None if no match.
    Used at boot by LightDM hook.
    """
    # Setup logging
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s : %(message)s"
        ))
        log.addHandler(fh)
        log.setLevel(logging.DEBUG)

    log.info("Face identification starting")

    try:
        import cv2
        import face_recognition
    except ImportError as e:
        log.error(f"Missing dependency: {e}")
        return None

    # Load ALL enrolled user profiles
    profiles = {}
    for username in get_enrolled_users():
        emb = load_face(username)
        if emb is not None:
            profiles[username] = emb
            log.info(f"Loaded profile: {username}")

    if not profiles:
        log.error("No faces enrolled — cannot identify")
        return None

    log.info(f"Enrolled users: {list(profiles.keys())}")

    # Open camera
    cap = _open_camera(verbose=False)
    if cap is None:
        log.error("No camera found")
        return None

    # Warmup
    for _ in range(10):
        cap.read()

    start     = time.time()
    matched   = None

    # ── Wait for UI animation to be ready (non-blocking) ──
    waited = 0
    while waited < 1.2:
        time.sleep(0.05)
        waited += 0.05

    FRAMES_NEEDED  = 4
    FRAME_INTERVAL = 0.08

    for attempt in range(1, max_attempts + 1):
        if time.time() - start > timeout:
            log.warning("Timeout reached")
            break

        log.info(f"--- Attempt {attempt}/{max_attempts} ---")

        # Collect embeddings (non-blocking grab)
        embeddings   = []
        frames_tried = 0

        while len(embeddings) < FRAMES_NEEDED and frames_tried < 12:
            cap.grab()
            ret, frame = cap.retrieve()
            frames_tried += 1

            if not ret or frame is None:
                time.sleep(0.03)
                continue
            try:
                # Small frame for speed
                small = cv2.resize(frame, (160, 120))
                rgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs  = face_recognition.face_locations(
                    rgb, model="hog"
                )
                if locs:
                    sx = frame.shape[1] / 160
                    sy = frame.shape[0] / 120
                    scaled = [
                        (int(t*sy), int(r*sx),
                         int(b*sy), int(l*sx))
                        for (t, r, b, l) in locs
                    ]
                    rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    encs = face_recognition.face_encodings(
                        rgb_full, scaled
                    )
                    if encs:
                        embeddings.append(encs[0])
            except Exception as e:
                log.debug(f"Frame error: {e}")
            time.sleep(FRAME_INTERVAL)

        if not embeddings:
            log.warning("No face detected")
            # Non-blocking wait between attempts
            for _ in range(20):
                time.sleep(0.08)
            continue

        # Average embeddings
        live_enc  = np.mean(embeddings, axis=0)

        # Compare against ALL users
        best_user = None
        best_dist = float("inf")

        for username, stored_enc in profiles.items():
            dists = face_recognition.face_distance([stored_enc], live_enc)
            dist  = float(dists[0])
            log.debug(f"  {username} → dist={dist:.4f}")
            if dist < best_dist:
                best_dist = dist
                best_user = username

        log.info(f"Best: {best_user} dist={best_dist:.4f} "
                 f"(threshold={THRESHOLD})")

        if best_dist <= THRESHOLD:
            log.info(f"✅ IDENTIFIED as '{best_user}'")
            matched = best_user
            break
        else:
            log.info(f"❌ No confident match")
            for _ in range(20):
                time.sleep(0.08)

    cap.release()

    if matched:
        log.info(f"✅ Login user: {matched}")
    else:
        log.warning("❌ Could not identify user — fallback to greeter")

    return matched


# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def _open_camera(verbose: bool = True) -> "cv2.VideoCapture | None":
    """Find and open first working camera."""
    import cv2
    try:
        from nova_unlock.vision.camera_detector import detect_camera
        idx = detect_camera()
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            if verbose:
                print(f"  ✓ Using camera {idx}")
            return cap
    except Exception:
        pass

    for idx in range(10):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                if verbose:
                    print(f"  ✓ Using camera {idx}")
                return cap
        cap.release()

    if verbose:
        print("  ❌ No camera found")
    return None


def print_status():
    """Print enrollment status for all system users."""
    print("\n╔══════════════════════════════════════════╗")
    print("║     NovaUnlock Face Login — User Status  ║")
    print("╚══════════════════════════════════════════╝\n")

    system_users = get_system_users()
    meta         = load_meta()

    print(f"  {'Username':<15} {'Face Enrolled':<15} {'Enrolled At'}")
    print(f"  {'─'*15} {'─'*15} {'─'*20}")

    for u in system_users:
        uname    = u["username"]
        enrolled = is_enrolled(uname)
        status   = "✅ Yes" if enrolled else "❌ No"
        when     = meta.get(uname, {}).get("enrolled_at", "—")
        print(f"  {uname:<15} {status:<15} {when}")

    print()
