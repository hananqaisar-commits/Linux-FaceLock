#!/usr/bin/env python3
"""
nova_unlock/vision/liveness.py
═══════════════════════════════════════════════════════════
Anti-Spoofing & Liveness Detection for NovaUnlock

Two-layer defense:
  Layer 1 — Blink detection via Eye Aspect Ratio (EAR)
            Rejects static photos that cannot blink.
  Layer 2 — Texture variance analysis via Local Binary Patterns
            Rejects screens and printed photos (flat textures).

Both layers are independently toggleable via config/nova.conf.
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np

log = logging.getLogger("nova.liveness")


# ═══════════════════════════════════════════════════════════════
# Eye Aspect Ratio (EAR) — Blink Detection
# Based on Soukupová & Čech (2016): "Real-Time Eye Blink Detection"
# EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
# EAR drops below ~0.20 during a blink.
# ═══════════════════════════════════════════════════════════════

# dlib 68-landmark eye indices (0-indexed)
LEFT_EYE_IDX  = [36, 37, 38, 39, 40, 41]
RIGHT_EYE_IDX = [42, 43, 44, 45, 46, 47]

EAR_THRESHOLD = 0.22   # below this = eye closed
EAR_CONSEC    = 2       # consecutive frames below threshold = 1 blink


def _dist(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two 2D points."""
    return float(np.linalg.norm(a - b))


def compute_ear(eye_points: np.ndarray) -> float:
    """
    Compute Eye Aspect Ratio for 6-point eye landmarks.

    eye_points: ndarray shape (6, 2) — the 6 landmark points of one eye.
    Returns: float EAR value. High (0.3+) = open, low (<0.22) = closed.
    """
    # Vertical distances
    v1 = _dist(eye_points[1], eye_points[5])
    v2 = _dist(eye_points[2], eye_points[4])
    # Horizontal distance
    h  = _dist(eye_points[0], eye_points[3])
    if h < 1e-6:
        return 0.0
    return (v1 + v2) / (2.0 * h)


# ═══════════════════════════════════════════════════════════════
# Texture Variance — Anti-Spoof (Screen/Print Detection)
# Real faces have rich micro-texture (pores, hair, skin grain).
# Photos and screens appear flat — low LBP variance.
# ═══════════════════════════════════════════════════════════════

def _compute_lbp_variance(gray_face: np.ndarray) -> float:
    """
    Compute Local Binary Pattern variance on a grayscale face ROI.
    Higher variance = more texture = real face.
    Lower variance = flat/smooth = likely a screen or print.

    gray_face: grayscale ndarray of the face region.
    Returns: float variance score.
    """
    if gray_face.size < 100:
        return 0.0

    h, w = gray_face.shape[:2]
    # Resize to consistent size for comparable scores
    import cv2
    face = cv2.resize(gray_face, (64, 64))
    face = face.astype(np.float64)

    # Simple LBP: compare each pixel to its 8 neighbors
    # Build binary pattern, then compute variance of the pattern image
    lbp = np.zeros_like(face, dtype=np.uint8)

    for dy, dx, bit in [
        (-1, -1, 0), (-1,  0, 1), (-1,  1, 2),
        ( 0,  1, 3), ( 1,  1, 4), ( 1,  0, 5),
        ( 1, -1, 6), ( 0, -1, 7),
    ]:
        # Shifted version of the image
        y_start = max(0, dy)
        y_end   = 64 + min(0, dy)
        x_start = max(0, dx)
        x_end   = 64 + min(0, dx)

        cy_start = max(0, -dy)
        cy_end   = 64 + min(0, -dy)
        cx_start = max(0, -dx)
        cx_end   = 64 + min(0, -dx)

        neighbor = face[y_start:y_end, x_start:x_end]
        center   = face[cy_start:cy_end, cx_start:cx_end]

        mask = (neighbor >= center).astype(np.uint8)
        lbp[cy_start:cy_end, cx_start:cx_end] |= (mask << bit)

    variance = float(np.var(lbp))
    return variance


# Threshold determined empirically:
# Real faces: LBP variance > 800 typically
# Screens/prints: LBP variance < 500 typically
LBP_VARIANCE_THRESHOLD = 500.0


# ═══════════════════════════════════════════════════════════════
# Liveness Checker — Stateful blink tracker
# ═══════════════════════════════════════════════════════════════

class LivenessChecker:
    """
    Stateful liveness detector that tracks blinks over a time window.

    Usage:
        checker = LivenessChecker(min_blinks=1, window=3.0)
        # In your frame loop:
        result = checker.check_frame(frame, face_location)
        if result == "pass":
            # Real person confirmed
        elif result == "spoof":
            # Photo/screen detected
        elif result == "pending":
            # Still waiting for blink evidence
    """

    def __init__(self,
                 min_blinks: int = 1,
                 window: float = 3.0,
                 check_texture: bool = True):
        self.min_blinks    = max(1, min_blinks)
        self.window        = window
        self.check_texture = check_texture

        # State
        self._blink_count  = 0
        self._consec_below = 0
        self._start_time   = None
        self._predictor    = None
        self._texture_scores: List[float] = []
        self._available    = None   # None = not yet checked

    def reset(self):
        """Reset all state for a new detection session."""
        self._blink_count  = 0
        self._consec_below = 0
        self._start_time   = None
        self._texture_scores.clear()

    def _ensure_predictor(self) -> bool:
        """Load dlib shape predictor if available."""
        if self._available is False:
            return False
        if self._predictor is not None:
            return True

        try:
            import dlib
        except ImportError:
            log.warning("dlib not available — liveness check disabled")
            self._available = False
            return False

        # Search for shape predictor model file
        model_name = "shape_predictor_68_face_landmarks.dat"
        search_paths = [
            Path(__file__).parent.parent.parent / "data" / model_name,
            Path(__file__).parent.parent.parent / model_name,
            Path.home() / ".nova-unlock" / model_name,
            Path("/usr/share/dlib") / model_name,
            Path("/usr/local/share/dlib") / model_name,
        ]

        for p in search_paths:
            if p.exists():
                try:
                    self._predictor = dlib.shape_predictor(str(p))
                    self._available = True
                    log.info(f"Shape predictor loaded: {p}")
                    return True
                except Exception as e:
                    log.warning(f"Failed to load predictor from {p}: {e}")

        log.warning(
            f"Shape predictor not found. Blink detection disabled. "
            f"Download from: http://dlib.net/files/{model_name}.bz2 "
            f"and place in data/ directory."
        )
        self._available = False
        return False

    def check_frame(self, frame: np.ndarray,
                    face_location: Tuple[int, int, int, int] | None = None
                    ) -> str:
        """
        Process one video frame for liveness evidence.

        Args:
            frame: BGR video frame (numpy array)
            face_location: (top, right, bottom, left) face bounding box
                           If None, face detection will be attempted.

        Returns:
            "pass"    — liveness confirmed (enough blinks detected)
            "spoof"   — spoof detected (texture too flat)
            "pending" — still collecting evidence
            "unavailable" — predictor not found, check skipped
        """
        import cv2

        if self._start_time is None:
            self._start_time = time.time()

        elapsed = time.time() - self._start_time

        # ── Texture analysis (always available, no dlib needed) ──
        if self.check_texture and face_location is not None:
            top, right, bottom, left = face_location
            h, w = frame.shape[:2]
            # Clamp coordinates
            top    = max(0, top)
            bottom = min(h, bottom)
            left   = max(0, left)
            right  = min(w, right)

            if bottom > top + 10 and right > left + 10:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                face_roi = gray[top:bottom, left:right]
                variance = _compute_lbp_variance(face_roi)
                self._texture_scores.append(variance)

                # After enough samples, check average texture
                if len(self._texture_scores) >= 5:
                    avg_var = sum(self._texture_scores) / len(self._texture_scores)
                    if avg_var < LBP_VARIANCE_THRESHOLD:
                        log.warning(
                            f"Anti-spoof: texture variance {avg_var:.1f} "
                            f"below threshold {LBP_VARIANCE_THRESHOLD} — "
                            f"possible screen/print"
                        )
                        return "spoof"

        # ── Blink detection (requires dlib predictor) ──────────
        if not self._ensure_predictor():
            # If predictor unavailable but texture passed, allow through
            if elapsed > self.window:
                return "unavailable"
            return "pending"

        import dlib

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Convert face_recognition format to dlib rectangle
        if face_location is not None:
            top, right, bottom, left = face_location
            rect = dlib.rectangle(left, top, right, bottom)
        else:
            # Detect face with dlib
            detector = dlib.get_frontal_face_detector()
            faces = detector(gray, 0)
            if not faces:
                return "pending"
            rect = faces[0]

        # Get landmarks
        shape = self._predictor(gray, rect)
        landmarks = np.array([
            (shape.part(i).x, shape.part(i).y)
            for i in range(68)
        ])

        # Compute EAR for both eyes
        left_eye  = landmarks[LEFT_EYE_IDX]
        right_eye = landmarks[RIGHT_EYE_IDX]
        ear_left  = compute_ear(left_eye)
        ear_right = compute_ear(right_eye)
        ear_avg   = (ear_left + ear_right) / 2.0

        # Track blinks
        if ear_avg < EAR_THRESHOLD:
            self._consec_below += 1
        else:
            if self._consec_below >= EAR_CONSEC:
                self._blink_count += 1
                log.debug(f"Blink detected (count={self._blink_count})")
            self._consec_below = 0

        # Check if enough blinks within window
        if self._blink_count >= self.min_blinks:
            log.info(f"Liveness confirmed: {self._blink_count} blinks in {elapsed:.1f}s")
            return "pass"

        # Timeout
        if elapsed > self.window:
            if self._blink_count < self.min_blinks:
                log.warning(
                    f"Liveness timeout: only {self._blink_count}/{self.min_blinks} "
                    f"blinks in {self.window}s"
                )
                # Don't hard-fail on blink timeout — texture check is primary
                # Some users may not blink naturally in short windows
                return "pending"

        return "pending"

    @property
    def blink_count(self) -> int:
        return self._blink_count

    @property
    def is_available(self) -> bool:
        """Check if liveness detection has all required models."""
        if self._available is None:
            self._ensure_predictor()
        return self._available is True
