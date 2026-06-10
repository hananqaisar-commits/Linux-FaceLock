#!/usr/bin/env python3
"""
NovaUnlock — Liveness Detection v5.2
Anti-Spoof Blink Detection using:
  PRIMARY  : dlib 68-point facial landmarks (EAR method)
  FALLBACK : MediaPipe Tasks API  (mediapipe >= 0.10)
  FALLBACK2: OpenCV Haar + basic blink heuristic

Rejects:
  - Printed photos
  - Phone / tablet screen replays
  - Static masks
"""

import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

# ── EAR Constants ──────────────────────────────────────────────
EAR_THRESHOLD   = 0.0   # 0.0 = auto-calibrate from first frames   # below this = eye closed
BLINK_FRAMES    = 1      # consecutive frames eye must be closed
REQUIRED_BLINKS = 1      # blinks needed to pass liveness
CHALLENGE_SECS  = 6.0    # seconds user has to blink

# ── dlib 68-point landmark eye indices ────────────────────────
# Left eye  : 36-41   Right eye : 42-47
DLIB_LEFT_EYE  = list(range(36, 42))
DLIB_RIGHT_EYE = list(range(42, 48))

# ── MediaPipe 478-point mesh eye indices ──────────────────────
MP_LEFT_EYE  = [362, 385, 387, 263, 373, 380]
MP_RIGHT_EYE = [33,  160, 158, 133, 153, 144]


# ─────────────────────────────────────────────────────────────
# EAR helper
# ─────────────────────────────────────────────────────────────
def _ear_from_points(pts: np.ndarray) -> float:
    """
    Compute Eye Aspect Ratio from 6 (x,y) points.
    pts[0]=left_corner, pts[3]=right_corner,
    pts[1],pts[5]=top, pts[2],pts[4]=bottom.
    """
    A = np.linalg.norm(pts[1] - pts[5])
    B = np.linalg.norm(pts[2] - pts[4])
    C = np.linalg.norm(pts[0] - pts[3])
    return float((A + B) / (2.0 * C + 1e-6))


def _ear(landmarks, eye_idx: list, w: int, h: int) -> float:
    """Compute EAR from MediaPipe-style landmark objects."""
    pts = np.array(
        [[landmarks[i].x * w, landmarks[i].y * h] for i in eye_idx],
        dtype=np.float64,
    )
    return _ear_from_points(pts)


# ─────────────────────────────────────────────────────────────
# Backend detection
# ─────────────────────────────────────────────────────────────
def _detect_backend() -> str:
    """
    Detect best available landmark backend.
    Returns: 'dlib' | 'mediapipe' | 'opencv' | 'none'
    """
    # ── Try dlib (preferred — already installed via face_recognition) ──
    try:
        import dlib
        model_candidates = [
            "shape_predictor_68_face_landmarks.dat",
            "/usr/share/dlib/shape_predictor_68_face_landmarks.dat",
            "/usr/local/share/dlib/shape_predictor_68_face_landmarks.dat",
        ]
        import os, glob
        # Also search in common pip cache / site-packages paths
        import site
        for sp in site.getsitepackages():
            model_candidates += glob.glob(
                os.path.join(sp, "**", "shape_predictor_68*.dat"),
                recursive=True
            )

        for p in model_candidates:
            if os.path.isfile(p):
                logger.info("Liveness backend: dlib (%s)", p)
                return 'dlib'
        logger.debug("dlib available but model file not found — trying mediapipe")
    except ImportError:
        pass

    # ── Try MediaPipe new Tasks API (>= 0.10) ──
    try:
        import mediapipe as mp
        # New API check
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        logger.info("Liveness backend: mediapipe tasks API")
        return 'mediapipe'
    except (ImportError, AttributeError):
        pass

    # ── Try MediaPipe legacy API (< 0.10) ──
    try:
        import mediapipe as mp
        _ = mp.solutions.face_mesh
        logger.info("Liveness backend: mediapipe legacy")
        return 'mediapipe_legacy'
    except (ImportError, AttributeError):
        pass

    # ── OpenCV Haar fallback ──
    try:
        import cv2
        clf = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_eye.xml"
        )
        if not clf.empty():
            logger.info("Liveness backend: opencv haar")
            return 'opencv'
    except Exception:
        pass

    logger.warning("No liveness backend found — liveness disabled")
    return 'none'


# ─────────────────────────────────────────────────────────────
# LivenessDetector
# ─────────────────────────────────────────────────────────────
class LivenessDetector:
    """
    Anti-spoof liveness checker using blink challenge.

    Backends (auto-detected, in priority order):
      1. dlib 68-point landmarks
      2. MediaPipe Tasks API (>= 0.10)
      3. MediaPipe legacy   (< 0.10)
      4. OpenCV Haar eye detector (basic)
    """

    def __init__(self,
                 required_blinks: int   = REQUIRED_BLINKS,
                 challenge_secs: float  = CHALLENGE_SECS,
                 ear_threshold: float   = EAR_THRESHOLD):

        self.required_blinks = required_blinks
        self.challenge_secs  = challenge_secs
        self.ear_threshold   = ear_threshold

        self._blink_count    = 0
        self._consec_closed  = 0
        self._start_time     = None
        self._passed         = False
        self._failed         = False

        # ── Adaptive threshold calibration ────────────────────
        # Collect open-eye EAR samples first, then set threshold
        # dynamically as open_avg * BLINK_RATIO
        self._calib_samples   = []
        self._calib_done      = False
        self._calib_frames    = 30        # frames to collect for calibration
        self._blink_ratio     = 0.88      # tuned for narrow EAR range      # threshold = open_avg * ratio
        self._adaptive_thresh = ear_threshold if ear_threshold > 0 else None
        self._open_ear_avg    = 0.0

        # Backend objects
        self._backend        = _detect_backend()
        self._dlib_detector  = None
        self._dlib_predictor = None
        self._mp_face_mesh   = None
        self._mp_mesh_obj    = None
        self._haar_eye       = None
        self._haar_face      = None

        self._init_backend()

    # ── Init backend ──────────────────────────────────────────
    def _init_backend(self):
        if self._backend == 'dlib':
            self._init_dlib()
        elif self._backend == 'mediapipe':
            self._init_mediapipe_tasks()
        elif self._backend == 'mediapipe_legacy':
            self._init_mediapipe_legacy()
        elif self._backend == 'opencv':
            self._init_opencv()

    def _init_dlib(self):
        try:
            import dlib, os, glob, site

            self._dlib_detector = dlib.get_frontal_face_detector()

            # Find model file
            candidates = [
                "shape_predictor_68_face_landmarks.dat",
                "/usr/share/dlib/shape_predictor_68_face_landmarks.dat",
                "/usr/local/share/dlib/shape_predictor_68_face_landmarks.dat",
            ]
            for sp in site.getsitepackages():
                candidates += glob.glob(
                    os.path.join(sp, "**", "shape_predictor_68*.dat"),
                    recursive=True
                )

            model_path = None
            for p in candidates:
                if os.path.isfile(p):
                    model_path = p
                    break

            if model_path:
                self._dlib_predictor = dlib.shape_predictor(model_path)
                logger.info("dlib predictor loaded: %s", model_path)
            else:
                logger.warning("dlib model not found — downloading now")
                self._download_dlib_model()

        except Exception as e:
            logger.error("dlib init failed: %s — falling back", e)
            self._backend = 'opencv'
            self._init_opencv()

    def _download_dlib_model(self):
        """Download dlib shape predictor model if not present."""
        import subprocess, os
        try:
            url  = ("http://dlib.net/files/"
                    "shape_predictor_68_face_landmarks.dat.bz2")
            dest = "shape_predictor_68_face_landmarks.dat.bz2"
            logger.info("Downloading dlib model...")
            subprocess.run(["wget", "-q", url, "-O", dest],
                           timeout=120, check=True)
            subprocess.run(["bunzip2", dest], timeout=60, check=True)
            if os.path.isfile("shape_predictor_68_face_landmarks.dat"):
                import dlib
                self._dlib_predictor = dlib.shape_predictor(
                    "shape_predictor_68_face_landmarks.dat"
                )
                logger.info("dlib model downloaded and loaded")
            else:
                raise FileNotFoundError("bz2 extract failed")
        except Exception as e:
            logger.error("dlib model download failed: %s", e)
            self._dlib_predictor = None
            self._backend = 'opencv'
            self._init_opencv()

    def _init_mediapipe_tasks(self):
        """MediaPipe >= 0.10 Tasks API."""
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            base_opts = mp_python.BaseOptions(
                model_asset_path=self._get_mp_model_path()
            )
            opts = mp_vision.FaceLandmarkerOptions(
                base_options=base_opts,
                running_mode=mp_vision.RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self._mp_face_mesh = mp_vision.FaceLandmarker.create_from_options(opts)
            self._mp_ts = 0
            logger.info("MediaPipe Tasks FaceLandmarker loaded")
        except Exception as e:
            logger.error("MediaPipe Tasks init failed: %s", e)
            self._backend = 'opencv'
            self._init_opencv()

    def _get_mp_model_path(self) -> str:
        import os, urllib.request
        path = "face_landmarker.task"
        if not os.path.isfile(path):
            url = ("https://storage.googleapis.com/mediapipe-models/"
                   "face_landmarker/face_landmarker/float16/1/face_landmarker.task")
            logger.info("Downloading MediaPipe face_landmarker.task...")
            urllib.request.urlretrieve(url, path)
        return path

    def _init_mediapipe_legacy(self):
        """MediaPipe < 0.10 legacy solutions API."""
        try:
            import mediapipe as mp
            self._mp_face_mesh = mp.solutions.face_mesh
            self._mp_mesh_obj  = self._mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            logger.info("MediaPipe legacy FaceMesh loaded")
        except Exception as e:
            logger.error("MediaPipe legacy init failed: %s", e)
            self._backend = 'opencv'
            self._init_opencv()

    def _init_opencv(self):
        """OpenCV Haar cascades basic fallback."""
        try:
            self._haar_face = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            self._haar_eye  = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_eye.xml"
            )
            self._backend = 'opencv'
            logger.info("OpenCV Haar backend loaded")
        except Exception as e:
            logger.error("OpenCV init failed: %s", e)
            self._backend = 'none'

    # ── Reset ─────────────────────────────────────────────────
    def reset(self):
        self._blink_count     = 0
        self._consec_closed   = 0
        self._start_time      = None
        self._passed          = False
        self._failed          = False
        # Reset adaptive calibration for new session
        self._calib_samples   = []
        self._calib_done      = False
        self._adaptive_thresh = None
        self._open_ear_avg    = 0.0

    # ── Main update ───────────────────────────────────────────
    def update(self, frame: np.ndarray) -> dict:
        """
        Process one BGR frame.
        Returns dict with keys:
          status, blinks, required, seconds_left, ear, message
        """
        result = {
            "status"      : "waiting",
            "blinks"      : self._blink_count,
            "required"    : self.required_blinks,
            "seconds_left": self.challenge_secs,
            "ear"         : 0.0,
            "message"     : "Please blink naturally",
        }

        if self._backend == 'none':
            result.update(status="disabled",
                          message="Liveness disabled (no backend)")
            return result

        if self._passed:
            result.update(status="passed",
                          message="✅ Liveness passed — real face confirmed")
            return result

        if self._failed:
            result.update(status="failed",
                          message="❌ No blink detected — spoof rejected")
            return result

        # Start timer
        if self._start_time is None:
            self._start_time = time.time()

        elapsed      = time.time() - self._start_time
        seconds_left = max(0.0, self.challenge_secs - elapsed)
        result["seconds_left"] = round(seconds_left, 1)

        # Timeout
        if elapsed > self.challenge_secs:
            self._failed     = True
            result["status"] = "failed"
            result["message"] = "❌ No blink detected — spoof rejected"
            logger.warning("Liveness FAILED — timeout %.1fs", elapsed)
            return result

        # ── Dispatch to backend ──
        if self._backend == 'dlib':
            avg_ear = self._process_dlib(frame)
        elif self._backend == 'mediapipe':
            avg_ear = self._process_mp_tasks(frame, elapsed)
        elif self._backend == 'mediapipe_legacy':
            avg_ear = self._process_mp_legacy(frame)
        elif self._backend == 'opencv':
            avg_ear = self._process_opencv(frame)
        else:
            avg_ear = -1.0

        if avg_ear < 0:
            result["status"]  = "no_face"
            result["message"] = "👁 No face detected"
            return result

        result["ear"] = round(avg_ear, 3)

        # ── Adaptive calibration phase ────────────────────────
        # Collect open-eye EAR samples before starting blink detection
        if not self._calib_done:
            # Only add clearly-open samples (avoid collecting during blink)
            if avg_ear > 0.20:
                self._calib_samples.append(avg_ear)

            if len(self._calib_samples) >= self._calib_frames:
                # Sort and use median of top 60% (ignore outlier blinks)
                sorted_s = sorted(self._calib_samples)
                top      = sorted_s[int(len(sorted_s) * 0.4):]
                self._open_ear_avg    = float(sum(top) / len(top))
                self._adaptive_thresh = round(
                    self._open_ear_avg * self._blink_ratio, 4
                )
                self._calib_done      = True
                logger.info(
                    "EAR calibrated: open_avg=%.3f threshold=%.3f",
                    self._open_ear_avg, self._adaptive_thresh
                )

            # During calibration show progress
            prog = len(self._calib_samples)
            result["message"] = (
                f"👁 Calibrating... ({prog}/{self._calib_frames})"
            )
            result["status"]  = "waiting"
            return result

        # ── Use adaptive threshold ────────────────────────────
        effective_thresh = self._adaptive_thresh or self.ear_threshold

        # ── Blink logic ───────────────────────────────────────
        if avg_ear < effective_thresh:
            self._consec_closed += 1
        else:
            if self._consec_closed >= BLINK_FRAMES:
                self._blink_count += 1
                logger.debug(
                    "Blink #%d EAR=%.3f thresh=%.3f",
                    self._blink_count, avg_ear, effective_thresh
                )
            self._consec_closed = 0

        result["blinks"] = self._blink_count
        result["ear"]    = round(avg_ear, 3)

        if self._blink_count >= self.required_blinks:
            self._passed     = True
            result["status"] = "passed"
            result["message"] = "✅ Liveness passed — real face confirmed"
            logger.info("Liveness PASSED (%d blinks)", self._blink_count)
        else:
            rem = self.required_blinks - self._blink_count
            result["message"] = (
                f"👁 Blink {rem}x naturally ({seconds_left:.0f}s)  "
                f"[thr:{effective_thresh:.3f}]"
            )

        return result

    # ── dlib processing ───────────────────────────────────────
    def _process_dlib(self, frame: np.ndarray) -> float:
        if self._dlib_detector is None or self._dlib_predictor is None:
            return -1.0
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = None

            # Strategy 1: upsample=1 (best for webcam distance)
            r = self._dlib_detector(gray, 1)
            if r:
                rects = r

            # Strategy 2: histogram equalization
            if not rects:
                eq = cv2.equalizeHist(gray)
                r  = self._dlib_detector(eq, 1)
                if r:
                    rects = r
                    gray  = eq

            # Strategy 3: CLAHE adaptive contrast
            if not rects:
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                cl    = clahe.apply(gray)
                r     = self._dlib_detector(cl, 1)
                if r:
                    rects = r
                    gray  = cl

            # Strategy 4: resize + upsample=2
            if not rects:
                h, w  = gray.shape[:2]
                scale = 480.0 / max(h, w)
                if scale < 1.0:
                    small = cv2.resize(gray, (int(w * scale), int(h * scale)))
                    r     = self._dlib_detector(small, 2)
                    if r:
                        import dlib as _dlib
                        rects = _dlib.rectangles()
                        for rect in r:
                            rects.append(_dlib.rectangle(
                                int(rect.left()   / scale),
                                int(rect.top()    / scale),
                                int(rect.right()  / scale),
                                int(rect.bottom() / scale),
                            ))

            # Strategy 5: OpenCV Haar face → dlib landmarks
            if not rects:
                haar = cv2.CascadeClassifier(
                    cv2.data.haarcascades +
                    "haarcascade_frontalface_default.xml"
                )
                hf = haar.detectMultiScale(gray, 1.05, 4, minSize=(60, 60))
                if len(hf) > 0:
                    import dlib as _dlib
                    x, y, fw, fh = hf[0]
                    pad   = int(max(fw, fh) * 0.1)
                    x     = max(0, x - pad)
                    y     = max(0, y - pad)
                    fw    = min(gray.shape[1] - x, fw + 2 * pad)
                    fh    = min(gray.shape[0] - y, fh + 2 * pad)
                    rects = [_dlib.rectangle(x, y, x + fw, y + fh)]

            if not rects:
                return -1.0

            shape = self._dlib_predictor(gray, rects[0])
            pts   = np.array(
                [[shape.part(i).x, shape.part(i).y] for i in range(68)],
                dtype=np.float64,
            )
            l_ear = _ear_from_points(pts[DLIB_LEFT_EYE])
            r_ear = _ear_from_points(pts[DLIB_RIGHT_EYE])
            return (l_ear + r_ear) / 2.0

        except Exception as e:
            logger.debug("dlib process error: %s", e)
            return -1.0

    # ── MediaPipe Tasks processing ────────────────────────────
    def _process_mp_tasks(self, frame: np.ndarray, elapsed: float) -> float:
        try:
            import mediapipe as mp
            from mediapipe.tasks.python.vision import RunningMode
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )
            self._mp_ts += 33
            result = self._mp_face_mesh.detect_for_video(
                mp_image, self._mp_ts
            )
            if not result.face_landmarks:
                return -1.0
            lm = result.face_landmarks[0]
            h, w = frame.shape[:2]

            class _LM:
                def __init__(self, x, y): self.x = x; self.y = y

            lm_dict = {i: _LM(lm[i].x, lm[i].y) for i in
                       MP_LEFT_EYE + MP_RIGHT_EYE}
            l_ear = _ear(lm_dict, MP_LEFT_EYE,  w, h)
            r_ear = _ear(lm_dict, MP_RIGHT_EYE, w, h)
            return (l_ear + r_ear) / 2.0
        except Exception as e:
            logger.debug("MP Tasks error: %s", e)
            return -1.0

    # ── MediaPipe legacy processing ───────────────────────────
    def _process_mp_legacy(self, frame: np.ndarray) -> float:
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False
            res = self._mp_mesh_obj.process(rgb)
            rgb.flags.writeable = True
            if not res.multi_face_landmarks:
                return -1.0
            lm   = res.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            l_ear = _ear(lm, MP_LEFT_EYE,  w, h)
            r_ear = _ear(lm, MP_RIGHT_EYE, w, h)
            return (l_ear + r_ear) / 2.0
        except Exception as e:
            logger.debug("MP legacy error: %s", e)
            return -1.0

    # ── OpenCV Haar processing ────────────────────────────────
    def _process_opencv(self, frame: np.ndarray) -> float:
        """
        Basic eye presence heuristic:
          2 eyes visible → EAR=0.30 (open)
          0 eyes visible → EAR=0.15 (closed/blink)
        """
        try:
            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._haar_face.detectMultiScale(
                gray, 1.1, 5, minSize=(80, 80)
            )
            if len(faces) == 0:
                return -1.0
            x, y, fw, fh = faces[0]
            roi   = gray[y:y+fh, x:x+fw]
            eyes  = self._haar_eye.detectMultiScale(roi, 1.05, 3)
            # Simulate EAR: 2 eyes = open, 0 = closed
            if len(eyes) >= 2:
                return 0.30
            elif len(eyes) == 1:
                return 0.22
            else:
                return 0.10
        except Exception as e:
            logger.debug("OpenCV haar error: %s", e)
            return -1.0

    # ── Draw overlay ──────────────────────────────────────────
    def draw_overlay(self, frame: np.ndarray, result: dict) -> np.ndarray:
        status = result["status"]
        msg    = result["message"]
        ear    = result.get("ear",  0.0)
        secs   = result.get("seconds_left", 0.0)
        blinks = result.get("blinks", 0)
        req    = result.get("required", 1)

        color_map = {
            "passed"  : (0,   220,  80),
            "failed"  : (0,    60, 255),
            "waiting" : (255, 200,   0),
            "no_face" : (120, 120, 120),
            "disabled": (180, 180, 180),
        }
        color = color_map.get(status, (255, 255, 255))

        cv2.putText(frame, msg,
                    (20, 40), cv2.FONT_HERSHEY_DUPLEX,
                    0.7, color, 2, cv2.LINE_AA)
        cv2.putText(
            frame,
            f"EAR:{ear:.3f}  Blinks:{blinks}/{req}  "
            f"Backend:{self._backend}  {secs:.0f}s",
            (20, 70), cv2.FONT_HERSHEY_SIMPLEX,
            0.48, color, 1, cv2.LINE_AA
        )
        return frame

    # ── Properties ────────────────────────────────────────────
    def is_passed(self)   -> bool: return self._passed
    def is_failed(self)   -> bool: return self._failed
    def blink_count(self) -> int:  return self._blink_count

    @property
    def adaptive_threshold(self) -> float:
        """Current adaptive threshold (0.0 if not yet calibrated)."""
        return self._adaptive_thresh or 0.0

    @property
    def open_ear_avg(self) -> float:
        return self._open_ear_avg

    @property
    def backend(self) -> str:
        return self._backend


    def debug_ear_live(self, duration: int = 15) -> None:
        """
        Opens camera and prints real-time EAR values.
        Use to diagnose detection issues.
        """
        import cv2 as _cv2
        cap = _cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Camera unavailable")
            return

        cap.set(_cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(_cv2.CAP_PROP_FRAME_HEIGHT, 480)

        import time as _time
        start = _time.time()
        print(f"  EAR debug — {duration}s | backend={self._backend} | adaptive_thresh={self.adaptive_threshold:.3f}")
        print("  Look at camera. Open eyes wide, then blink.")
        print("  (Values printed every 0.5s)")
        print()

        last_print = 0
        while _time.time() - start < duration:
            ret, frame = cap.read()
            if not ret:
                break

            if self._backend == 'dlib':
                ear = self._process_dlib(frame)
            elif self._backend == 'opencv':
                ear = self._process_opencv(frame)
            else:
                ear = -1.0

            now = _time.time()
            if now - last_print >= 0.5:
                elapsed = now - start
                if ear < 0:
                    print(f"  [{elapsed:4.1f}s]  NO FACE DETECTED")
                elif ear < self.ear_threshold:
                    print(f"  [{elapsed:4.1f}s]  EAR={ear:.4f}  👁 CLOSED")
                else:
                    print(f"  [{elapsed:4.1f}s]  EAR={ear:.4f}  👁 OPEN")
                last_print = now

            if _cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        print()
        print("  EAR debug complete")

    def __del__(self):
        for obj in (self._mp_mesh_obj, self._mp_face_mesh):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    import sys
    print(f"Backend: {_detect_backend()}")
    det = LivenessDetector(required_blinks=2, challenge_secs=10)
    print(f"Using  : {det.backend}")
    cap = cv2.VideoCapture(0)
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        res = det.update(frame)
        det.draw_overlay(frame, res)
        cv2.imshow("Liveness Test", frame)
        if res["status"] in ("passed", "failed"):
            print(f"Result : {res['status']} — {res['message']}")
            time.sleep(2)
            break
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    cap.release()
    cv2.destroyAllWindows()
