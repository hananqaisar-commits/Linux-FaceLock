#!/usr/bin/env python3
"""
nova_unlock/vision/camera_detector.py
Detects the best available camera index.
Cross-platform: Windows (DirectShow/MSMF) and Linux (V4L2).
"""
import cv2
import logging
import platform
import time

log = logging.getLogger("nova.camera_detector")

_IS_WINDOWS = platform.system() == "Windows"


def _get_backends():
    """Return platform-appropriate OpenCV camera backends."""
    if _IS_WINDOWS:
        return [cv2.CAP_DSHOW, cv2.CAP_MSMF, 0]
    return [cv2.CAP_V4L2, 0]


def detect_camera(max_index: int = 10) -> int:
    """
    Find first working camera index.
    Returns camera index (int), default 0 if none found.
    Tries multiple backends on Windows for robust detection.
    """
    backends = _get_backends()
    for idx in range(max_index):
        for backend in backends:
            try:
                if backend != 0:
                    cap = cv2.VideoCapture(idx, backend)
                else:
                    cap = cv2.VideoCapture(idx)
                if not cap.isOpened():
                    cap.release()
                    continue
                # Windows cameras need warm-up time for permission
                # prompts and hardware initialization
                if _IS_WINDOWS:
                    time.sleep(0.5)
                for _ in range(8):
                    cap.grab()
                ok, frame = cap.read()
                cap.release()
                if ok and frame is not None:
                    log.info(f"Camera found at index {idx} (backend={backend})")
                    return idx
            except Exception as e:
                log.debug(f"Camera {idx} backend {backend} error: {e}")
    log.warning("No camera found, defaulting to index 0")
    return 0


def list_cameras(max_index: int = 10) -> list:
    """Return list of working camera indices."""
    found = []
    backends = _get_backends()
    for idx in range(max_index):
        for backend in backends:
            try:
                if backend != 0:
                    cap = cv2.VideoCapture(idx, backend)
                else:
                    cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    if _IS_WINDOWS:
                        time.sleep(0.3)
                    for _ in range(5):
                        cap.grab()
                    ok, _ = cap.read()
                    cap.release()
                    if ok:
                        found.append(idx)
                        break  # found working backend for this index
                else:
                    cap.release()
            except Exception:
                pass
    return found


def open_camera(max_index: int = 10, width: int = 320, height: int = 240,
                fps: int = 30, warmup_reads: int = 6):
    """Open the first working camera, trying every backend + warm-up reads.

    Returns an opened ``cv2.VideoCapture`` (already configured) or ``None``.

    Why this exists: the workers used to only probe ``cv2.VideoCapture(i,
    cv2.CAP_V4L2)``. On many systems the camera only opens via the DEFAULT
    backend (or needs a few warm-up reads before the first frame arrives), so
    the V4L2-only probe silently failed → no camera light → no scan → no login.
    This central helper mirrors ``detect_camera``'s multi-backend strategy and
    is the single source of truth for opening the camera everywhere.
    """
    backends = _get_backends()

    def _try_open(idx, backend):
        try:
            if backend != 0:
                cap = cv2.VideoCapture(idx, backend)
            else:
                cap = cv2.VideoCapture(idx)
            if not cap.isOpened():
                cap.release()
                return None
            # Configure capture parameters (ignore failures — some drivers
            # reject set(), but the stream still works).
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, fps)
            except Exception:
                pass
            # Warm-up: grab a few frames, then attempt real reads. Some cameras
            # return nothing on the very first read even when opened fine.
            for _ in range(warmup_reads):
                cap.grab()
            for _ in range(warmup_reads):
                ok, frame = cap.read()
                if ok and frame is not None:
                    return cap
            # Opened but no frame yet — keep it anyway; recognition will retry.
            return cap
        except Exception:
            return None

    # Prefer the index detect_camera() already validated, then scan broadly.
    preferred = detect_camera(max_index) if not _IS_WINDOWS else 0
    candidates = []
    if preferred is not None:
        candidates.append(preferred)
    candidates += [i for i in range(max_index) if i != preferred]

    for idx in candidates:
        for backend in backends:
            cap = _try_open(idx, backend)
            if cap is not None:
                log.info("open_camera: opened camera index=%s backend=%s", idx, backend)
                return cap
    log.warning("open_camera: no working camera found")
    return None
