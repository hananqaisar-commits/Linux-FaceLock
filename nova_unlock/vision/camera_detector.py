#!/usr/bin/env python3
"""
nova_unlock/vision/camera_detector.py
Detects the best available camera index.
"""
import cv2
import logging

log = logging.getLogger("nova.camera_detector")

def detect_camera(max_index: int = 10) -> int:
    """
    Find first working camera index.
    Returns camera index (int), default 0 if none found.
    """
    for idx in range(max_index):
        try:
            cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                cap.release()
                continue
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None:
                log.info(f"Camera found at index {idx}")
                return idx
        except Exception as e:
            log.debug(f"Camera {idx} error: {e}")
    log.warning("No camera found, defaulting to index 0")
    return 0


def list_cameras(max_index: int = 10) -> list:
    """Return list of working camera indices."""
    found = []
    for idx in range(max_index):
        try:
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    found.append(idx)
            cap.release()
        except Exception:
            pass
    return found
