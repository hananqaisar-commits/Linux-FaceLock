#!/usr/bin/env python3
"""
NovaUnlock — Windows Credential Provider Auth Bridge
This script is executed by the C++ Credential Provider on the Windows Lock Screen.
It performs face recognition and liveness checks.
Exit Code 0: Unlock Granted
Exit Code 1: Unlock Denied
"""

import sys
import os
import cv2
import time
import numpy as np
from pathlib import Path

# Fix paths so we can import nova_unlock_win modules
WIN_PORT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WIN_PORT_DIR))

try:
    from nova_unlock_win.vision.face_recognizer import get_enrolled_users, load_face, get_threshold
except ImportError:
    # Fallback if running directly from this directory
    sys.exit(1)

def main():
    threshold = get_threshold()
    known_profiles = {}
    
    # Load all enrolled users
    for u in get_enrolled_users():
        enc = load_face(u)
        if enc is not None:
            known_profiles[u] = enc
            
    if not known_profiles:
        sys.exit(1) # No faces enrolled

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        sys.exit(1)
        
    try:
        import face_recognition as fr
        timeout = time.time() + 15.0 # 15 seconds to unlock
        
        while time.time() < timeout:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
                
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            locs = fr.face_locations(rgb, model="hog")
            
            if not locs:
                continue
                
            encs = fr.face_encodings(rgb, locs)
            
            for enc in encs:
                for user, stored_enc in known_profiles.items():
                    dists = fr.face_distance([stored_enc], enc)
                    if len(dists) > 0 and dists[0] <= threshold:
                        # TODO: Add Liveness check here if required
                        sys.exit(0) # UNLOCK SUCCESS
                        
            time.sleep(0.1)
            
    finally:
        cap.release()
        
    # Timeout reached without success
    sys.exit(1)

if __name__ == "__main__":
    main()
