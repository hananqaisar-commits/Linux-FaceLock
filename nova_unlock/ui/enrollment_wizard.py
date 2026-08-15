#!/usr/bin/env python3
"""
Nova Face ID Enrollment — Authentic iPhone style.
16 arc segments around face circle, turn green as samples capture.
"""
from __future__ import annotations

import math
import os
import sys
import time
import subprocess
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from PyQt5.QtWidgets import QApplication, QWidget, QLineEdit
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject, QThread)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont,
                              QRadialGradient, QLinearGradient,
                              QBrush, QPainterPath, QImage, QCursor)
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).parent.parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
from nova_unlock.ui.glass import draw_glass_pill, draw_glass_button

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

log = logging.getLogger("nova.enroll")


# ════════════════════════════════════════════════════════════════
#  THREE THEMES
# ════════════════════════════════════════════════════════════════
class Theme:
    class PureBlack:
        """iPhone Face ID style — pure black"""
        bg          = QColor(0, 0, 0)
        bg_top      = QColor(0, 0, 0)
        bg_btm      = QColor(0, 0, 0)
        text        = QColor(255, 255, 255)
        text_dim    = QColor(180, 180, 185)
        text_quiet  = QColor(120, 120, 125)
        pill        = QColor(20, 20, 22)
        pill_border = QColor(255, 255, 255, 30)
        arc_inactive = QColor(60, 60, 65)
        arc_active   = QColor(48, 209, 88)        # iOS green
        arc_glow     = QColor(48, 209, 88, 80)
        blue        = QColor(10, 132, 255)
        green       = QColor(48, 209, 88)
        red         = QColor(255, 69, 58)
        camera_bg   = QColor(20, 20, 25)

    class Dark:
        bg_top      = QColor(18, 20, 28)
        bg_btm      = QColor(6, 7, 12)
        text        = QColor(255, 255, 255)
        text_dim    = QColor(170, 180, 200)
        text_quiet  = QColor(110, 120, 140)
        pill        = QColor(8, 9, 14)
        pill_border = QColor(255, 255, 255, 28)
        arc_inactive = QColor(60, 70, 90)
        arc_active   = QColor(48, 209, 88)
        arc_glow     = QColor(48, 209, 88, 90)
        blue        = QColor(10, 132, 255)
        green       = QColor(48, 209, 88)
        red         = QColor(255, 69, 58)
        camera_bg   = QColor(20, 22, 28)

    class Light:
        bg_top      = QColor(248, 250, 254)
        bg_btm      = QColor(235, 240, 248)
        text        = QColor(10, 14, 22)
        text_dim    = QColor(60, 70, 90)
        text_quiet  = QColor(130, 140, 155)
        pill        = QColor(15, 15, 20)
        pill_border = QColor(255, 255, 255, 40)
        arc_inactive = QColor(200, 205, 215)
        arc_active   = QColor(52, 199, 89)
        arc_glow     = QColor(52, 199, 89, 70)
        blue        = QColor(0, 122, 255)
        green       = QColor(52, 199, 89)
        red         = QColor(255, 59, 48)
        camera_bg   = QColor(225, 230, 240)


def detect_theme() -> str:
    """Auto-detect: dark or light (Windows + Linux)"""
    import platform
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if val == 1 else "dark"
        except Exception:
            return "dark"
    # Linux / macOS
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=1.5)
        if "dark" in r.stdout.lower(): return "dark"
        if "light" in r.stdout.lower(): return "light"
    except: pass
    try:
        r = subprocess.run(
            ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
            capture_output=True, text=True, timeout=1.5)
        return "dark" if "dark" in r.stdout.lower() else "light"
    except:
        return "dark"


def get_palette(theme_name: str):
    """Return palette class for theme name"""
    if theme_name == "auto":
        theme_name = detect_theme()
    if theme_name == "pure_black":
        return Theme.PureBlack
    if theme_name == "light":
        return Theme.Light
    return Theme.Dark


# ════════════════════════════════════════════════════════════════
#  TYPOGRAPHY
# ════════════════════════════════════════════════════════════════
class Type:
    FAMILY = "SF Pro Display, -apple-system, Inter, Helvetica Neue, Arial"
    FAMILY_TEXT = "SF Pro Text, -apple-system, Inter, Helvetica Neue, Arial"

    HERO    = (26, QFont.Bold,     -0.014)
    BODY    = (15, QFont.Normal,    0.002)
    CALLOUT = (14, QFont.Medium,    0.004)
    BUTTON  = (15, QFont.DemiBold,  0.000)
    BRAND   = (10, QFont.Bold,      0.180)
    MICRO   = (11, QFont.Medium,    0.020)

    @staticmethod
    def font(style, text=False):
        size, weight, tracking = style
        family = Type.FAMILY_TEXT if (text or size < 15) else Type.FAMILY
        f = QFont(family)
        f.setPixelSize(size)
        f.setWeight(weight)
        f.setLetterSpacing(QFont.AbsoluteSpacing, tracking * size)
        f.setHintingPreference(QFont.PreferFullHinting)
        f.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        return f


# ════════════════════════════════════════════════════════════════
#  SPRING PHYSICS — Optimized for 60fps+ smoothness
#  Uses critically-damped spring with adaptive timestep handling
# ════════════════════════════════════════════════════════════════
class Spring:
    __slots__ = ('k', 'd', 'x', 'v', '_eps')
    def __init__(self, freq=5.5, damping=0.85):
        # Critically damped spring: k = (2πf)², d = 2ζ√k
        # ζ=0.85 gives smooth overshoot-free settling
        self.k = (2.0 * math.pi * freq) ** 2
        self.d = 2.0 * damping * math.sqrt(self.k)
        self.x = 0.0
        self.v = 0.0
        self._eps = 1e-4

    def update(self, dt: float, target: float) -> float:
        # Clamp dt for stability (handles frame drops gracefully)
        dt = min(dt, 0.033)  # max ~30fps equivalent step

        # Implicit Euler integration (unconditionally stable)
        # x' = v
        # v' = -k*(x-target) - d*v
        # Solve: (1 + dt*d)*v_new + dt*k*x_new = v + dt*k*target
        #         x_new = x + dt*v_new

        a = 1.0 + dt * self.d + dt * dt * self.k
        v_new = (self.v + dt * self.k * (target - self.x)) / a
        self.x = self.x + dt * v_new
        self.v = v_new

        # Snap to target when very close (prevents endless micro-oscillation)
        if abs(self.x - target) < self._eps and abs(self.v) < self._eps:
            self.x = target
            self.v = 0.0
        return self.x

    def set_value(self, x: float):
        """Instantly set spring position (for phase transitions)"""
        self.x = x
        self.v = 0.0


# ════════════════════════════════════════════════════════════════
#  EASING — Perceptually-tuned curves for UI motion
# ════════════════════════════════════════════════════════════════
def ease_out_quint(t: float) -> float:
    """Quintic ease-out — iOS standard for decelerating motion"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 1.0 - (1.0 - t) ** 5


def ease_out_expo(t: float) -> float:
    """Exponential ease-out — for quick snappy appearances"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 1.0 - pow(2.0, -10.0 * t)


def ease_out_circ(t: float) -> float:
    """Circular ease-out — natural arc deceleration"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return math.sqrt(1.0 - (t - 1.0) ** 2)


def ease_in_out_cubic(t: float) -> float:
    """Cubic ease-in-out — symmetric acceleration/deceleration"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 4.0 * t ** 3 if t < 0.5 else 1.0 - pow(-2.0 * t + 2.0, 3) / 2.0


def smoothstep(t: float) -> float:
    """Smoothstep — C1 continuous, used for crossfades"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return t * t * (3.0 - 2.0 * t)


def smootherstep(t: float) -> float:
    """Smootherstep — C2 continuous, even smoother"""
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


# ════════════════════════════════════════════════════════════════
#  SYSTEM USER DETECTION + PASSWORD VERIFICATION
# ════════════════════════════════════════════════════════════════
def detect_system_users() -> list:
    """Detect all real system users. Called fresh every wizard launch."""
    try:
        import pwd
        users = []
        for p in pwd.getpwall():
            if (p.pw_dir.startswith("/home") and
                    os.path.exists(p.pw_dir) and
                    p.pw_uid >= 1000):
                users.append({
                    "username": p.pw_name,
                    "uid":      p.pw_uid,
                    "home":     p.pw_dir,
                    "fullname": (p.pw_gecos.split(",")[0] if p.pw_gecos else p.pw_name),
                })
        return users
    except ImportError:
        uname = os.environ.get("USER", "user")
        return [{"username": uname, "uid": 1000,
                 "home": str(Path.home()), "fullname": uname}]


def check_enrolled(username: str) -> bool:
    """Check if a user already has a face profile enrolled."""
    try:
        from nova_unlock.vision.face_recognizer import is_enrolled
        return is_enrolled(username)
    except Exception:
        return False


def verify_password(username: str, password: str) -> bool:
    """Verify user password via su (PAM-backed)."""
    try:
        proc = subprocess.Popen(
            ["su", "-", username, "-c", "exit 0"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate(input=(password + "\n").encode(), timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════
#  ARC SEGMENT (16 segments around circle)
# ════════════════════════════════════════════════════════════════
N_SEGMENTS = 32  # iOS Face ID exact


# ════════════════════════════════════════════════════════════════
#  WORKER
# ════════════════════════════════════════════════════════════════
class WorkerSignals(QObject):
    frame_ready     = pyqtSignal(object)
    sample_captured = pyqtSignal(int)
    face_detected   = pyqtSignal(bool)
    finished        = pyqtSignal(bool, str)


class EnrollmentWorker(QThread):
    def __init__(self, signals, username, samples_needed=16):
        super().__init__()
        self.signals = signals
        self.username = username
        self.samples_needed = samples_needed
        self.running = True

    def stop(self):
        self.running = False

    def run(self):
        try:
            import cv2
            import face_recognition
        except ImportError as e:
            self.signals.finished.emit(False, f"Missing: {e}")
            return

        try:
            from nova_unlock.vision.face_recognizer import save_face
        except Exception as e:
            self.signals.finished.emit(False, f"Vision: {e}")
            return

        cap = None
        import platform as _platform
        _is_windows = _platform.system() == "Windows"
        # Windows supports DirectShow (DSHOW) and Media Foundation (MSMF).
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
            cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Warm-up time for permission prompts and hardware initialization
            if _is_windows:
                time.sleep(1.0)
                
            for _ in range(10): cap.grab()
            ok, _ = cap.read()
            
            if not ok:
                if _is_windows:
                    time.sleep(0.5)
                    for _ in range(5): cap.grab()
                    ok, _ = cap.read()
                
                if not ok:
                    cap.release()
                    cap = None
        else:
            cap.release()
            cap = None
        if not cap:
            self.signals.finished.emit(False, "Camera unavailable")
            return

        embeddings = []
        last_capture = time.time()
        CAPTURE_INTERVAL = 0.35

        while self.running and len(embeddings) < self.samples_needed:
            try:
                cap.grab()
                ok, frame = cap.retrieve()
                if not ok:
                    time.sleep(0.05); continue

                rgb_preview = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.signals.frame_ready.emit(rgb_preview)

                now = time.time()
                if now - last_capture < CAPTURE_INTERVAL:
                    time.sleep(0.06); continue

                small = cv2.resize(frame, (160, 120))
                rgb_small = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb_small, model="hog")

                if not locs:
                    self.signals.face_detected.emit(False)
                    time.sleep(0.06); continue

                self.signals.face_detected.emit(True)

                sx = frame.shape[1] / 160
                sy = frame.shape[0] / 120
                scaled = [(int(t*sy), int(rt*sx),
                           int(b*sy), int(l*sx))
                          for (t, rt, b, l) in locs]
                rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                try:
                    encs = face_recognition.face_encodings(rgb_full, scaled)
                    if encs:
                        embeddings.append(encs[0])
                        last_capture = now
                        self.signals.sample_captured.emit(len(embeddings))
                except: pass

                time.sleep(0.06)
            except Exception as e:
                log.error(f"Loop: {e}")
                time.sleep(0.1)

        try: cap.release()
        except: pass

        if not self.running: return

        if len(embeddings) < 3:
            self.signals.finished.emit(False, "Not enough samples")
            return

        try:
            avg = np.mean(embeddings, axis=0)
            ok = save_face(self.username, avg)
            if ok:
                self.signals.finished.emit(True, "Enrollment complete")
            else:
                self.signals.finished.emit(False, "Save failed")
        except Exception as e:
            self.signals.finished.emit(False, str(e))


# ════════════════════════════════════════════════════════════════
#  WIZARD — Authentic iPhone Face ID
# ════════════════════════════════════════════════════════════════
class EnrollmentWizard(QWidget):

    finished_signal = pyqtSignal(bool, str)

    W = 480
    H = 720

    def __init__(self, username: Optional[str] = None,
                 samples: int = N_SEGMENTS,
                 theme: str = "auto", parent=None):
        super().__init__(parent)

        self._direct_user = username
        self.username = username or ""
        self.samples_needed = N_SEGMENTS

        # Detect system users fresh every launch
        self.system_users = detect_system_users()
        for u in self.system_users:
            u["enrolled"] = check_enrolled(u["username"])

        self.theme_name = theme
        self.p = get_palette(theme)
        self.is_pure_black = (self.p == Theme.PureBlack)
        self.is_dark = (self.p in (Theme.PureBlack, Theme.Dark))

        # Time
        self.t_start = time.time()
        self.t_last = self.t_start

        # Camera
        self.current_frame: Optional[QImage] = None

        # State
        self.samples_done = 0
        self.face_detected = False
        self.complete = False
        self.success = False
        self.error_msg = ""
        # Phases: -2=user_select, -1=password, 0=appearing, 1=scanning,
        #         2=success, 3=failed
        self.phase = 0 if self._direct_user else -2

        # ── User selection state (phase -2) ──
        self.user_hovered_idx = -1
        self.user_select_t = 0.0
        self.user_card_springs = [Spring(7.0) for _ in self.system_users]

        # ── Password verification state (phase -1) ──
        self.pwd_error = False
        self.pwd_error_t = 0.0
        self.pwd_error_msg = ""
        self.pwd_verify_hover = False
        self.pwd_verify_press = False
        self.pwd_back_hover = False
        self.pwd_appear_t = 0.0
        self.pwd_verifying = False
        self.pwd_btn_spring = Spring(7.0)

        # Arc activation timestamps (when each segment lit up)
        self.arc_activated_t = [0.0] * N_SEGMENTS

        # Appearance
        self.appear_t = 0.0
        self.appear_prog = 0.0

        # Choreography
        self.cg = {
            "pill":     (0.00, 0.55),
            "circle":   (0.20, 0.80),
            "title":    (0.55, 0.55),
            "subtitle": (0.70, 0.50),
            "button":   (0.90, 0.45),
        }
        self.progress = {k: 0.0 for k in self.cg}

        # Capture flash
        self.flash_alpha = 0.0

        # Success animation
        self.success_t = 0
        self.success_scale = 0.0
        self._finished_emitted = False

        # Cancel button
        self.cancel_hover = False
        self.cancel_press = False
        self.cancel_spring = Spring(7.0)

        # Worker (created when user confirmed)
        self.signals = WorkerSignals()
        self.signals.frame_ready.connect(self._on_frame)
        self.signals.sample_captured.connect(self._on_sample)
        self.signals.face_detected.connect(self._on_face)
        self.signals.finished.connect(self._on_finished)
        self.worker = None

        # Window
        self.setWindowTitle("Nova · Face ID")
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        bg = self.p.bg if hasattr(self.p, 'bg') else self.p.bg_btm
        self.setStyleSheet(
            f"background-color: rgb({bg.red()},{bg.green()},{bg.blue()});")

        # ── Password input (styled, hidden until phase -1) ──
        self.pwd_input = QLineEdit(self)
        self.pwd_input.setEchoMode(QLineEdit.Password)
        self.pwd_input.setPlaceholderText("Password")
        self.pwd_input.setAlignment(Qt.AlignCenter)
        self.pwd_input.setFixedSize(320, 46)
        self.pwd_input.move((self.W - 320) // 2, 370)
        self.pwd_input.hide()
        self.pwd_input.returnPressed.connect(self._verify_password)
        self._style_pwd_input()

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        if self.phase == 0:
            QTimer.singleShot(900, self._start_worker)

    # ────────────────────────────────────────────────────────
    def _style_pwd_input(self):
        if self.is_dark or self.is_pure_black:
            self.pwd_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(255,255,255,10);
                    border: 1px solid rgba(255,255,255,18);
                    border-radius: 12px;
                    color: #ffffff;
                    font-size: 15px;
                    font-family: 'Inter','Helvetica Neue',Arial,sans-serif;
                    padding: 10px 20px;
                }
                QLineEdit:focus {
                    border: 1.5px solid rgba(10,132,255,160);
                    background-color: rgba(255,255,255,14);
                }
            """)
        else:
            self.pwd_input.setStyleSheet("""
                QLineEdit {
                    background-color: rgba(0,0,0,5);
                    border: 1px solid rgba(0,0,0,10);
                    border-radius: 12px;
                    color: #0a0e16;
                    font-size: 15px;
                    font-family: 'Inter','Helvetica Neue',Arial,sans-serif;
                    padding: 10px 20px;
                }
                QLineEdit:focus {
                    border: 1.5px solid rgba(0,122,255,140);
                }
            """)

    def _select_user(self, idx):
        """User selected a card — move to password phase."""
        if 0 <= idx < len(self.system_users):
            self.username = self.system_users[idx]["username"]
            self.phase = -1
            self.pwd_appear_t = 0.0
            self.pwd_error = False
            self.pwd_error_msg = ""
            self.pwd_input.clear()
            self.pwd_input.show()
            self.pwd_input.setFocus()

    def _verify_password(self):
        """Verify the entered password for selected user."""
        pwd_text = self.pwd_input.text()
        if not pwd_text or self.pwd_verifying:
            return
        self.pwd_verifying = True
        self.pwd_error = False
        self.update()
        # Run in background to avoid blocking UI
        QTimer.singleShot(50, lambda: self._do_verify(pwd_text))

    def _do_verify(self, pwd_text):
        ok = verify_password(self.username, pwd_text)
        self.pwd_verifying = False
        if ok:
            self.pwd_input.hide()
            self.phase = 0
            self.t_start = time.time()
            self.t_last = self.t_start
            self.appear_t = 0.0
            QTimer.singleShot(900, self._start_worker)
        else:
            self.pwd_error = True
            self.pwd_error_t = time.time()
            self.pwd_error_msg = "Incorrect password"
            self.pwd_input.selectAll()
            self.pwd_input.setFocus()
        self.update()

    def _go_back_to_select(self):
        """Return from password screen to user selection."""
        self.pwd_input.hide()
        self.pwd_input.clear()
        self.phase = -2
        self.user_select_t = 0.0
        self.username = ""

    def _start_worker(self):
        if self.phase != 0:
            return
        self.phase = 1
        self.worker = EnrollmentWorker(
            self.signals, self.username, self.samples_needed)
        self.worker.start()

    # ────────────────────────────────────────────────────────
    def _on_frame(self, rgb_frame):
        try:
            h, w, ch = rgb_frame.shape
            qimg = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
            self.current_frame = qimg.copy()
        except: pass

    def _on_sample(self, count):
        """Each sample activates 1 arc segment (iOS exact)"""
        self.samples_done = count
        idx = count - 1
        if 0 <= idx < N_SEGMENTS:
            self.arc_activated_t[idx] = time.time()
        self.flash_alpha = 0.6

    def _on_face(self, detected):
        self.face_detected = detected

    def _on_finished(self, success, msg):
        self.complete = True
        self.success = success
        self.error_msg = msg
        if success:
            self.phase = 2
            self.success_t = time.time()
        else:
            self.phase = 3

    # ────────────────────────────────────────────────────────
    def _tick(self):
        now = time.time()
        dt = min(now - self.t_last, 0.05)
        self.t_last = now

        # ── Phase -2: User Selection ──
        if self.phase == -2:
            self.user_select_t += dt
            for i, spr in enumerate(self.user_card_springs):
                target = 1.02 if i == self.user_hovered_idx else 1.0
                spr.update(dt, target)
            self.update()
            return

        # ── Phase -1: Password ──
        if self.phase == -1:
            self.pwd_appear_t += dt
            t_btn = 1.02 if self.pwd_verify_hover else 1.0
            if self.pwd_verify_press: t_btn = 0.97
            self.pwd_btn_spring.update(dt, t_btn)
            self.update()
            return

        # ── Existing phases 0–3 ──
        # Appear
        self.appear_t += dt
        T = 0.55
        self.appear_prog = ease_out_quint(min(self.appear_t / T, 1.0))

        # Choreography
        if self.phase <= 1:
            for key, (start, dur) in self.cg.items():
                if self.appear_t >= start:
                    p = min((self.appear_t - start) / dur, 1.0)
                    self.progress[key] = ease_out_quint(p)

        # Flash decay
        self.flash_alpha *= pow(0.01, dt * 3)
        if self.flash_alpha < 0.005: self.flash_alpha = 0.0

        # Cancel hover
        target = 1.025 if self.cancel_hover else 1.0
        if self.cancel_press: target = 0.98
        self.cancel_spring.update(dt, target)

        # Success
        if self.phase == 2:
            t_s = now - self.success_t
            if t_s > 0.1:
                local = min((t_s - 0.1) / 0.5, 1.0)
                self.success_scale = ease_out_quint(local)
            if t_s > 2.2 and not self._finished_emitted:
                self._finished_emitted = True
                self.finished_signal.emit(True, self.username)

        if self.phase == 3 and not self._finished_emitted:
            self._finished_emitted = True
            QTimer.singleShot(1500,
                lambda: self.finished_signal.emit(False, self.username))

        self.update()

    # ────────────────────────────────────────────────────────
    # PAINT
    # ────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)
        P.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try: P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except: pass

        if self.phase == -2:
            self._paint_bg(P)
            self._paint_user_select(P)
        elif self.phase == -1:
            self._paint_bg(P)
            self._paint_password_screen(P)
        else:
            self._paint_bg(P)
            self._paint_pill(P)
            self._paint_camera(P)
            self._paint_arc_segments(P)
            self._paint_text(P)
            self._paint_button(P)
            if self.phase == 2:
                self._paint_success(P)

        P.end()

    # ────────────────────────────────────────────────────────
    def _paint_bg(self, P):
        if self.is_pure_black:
            # Pure black — no gradient
            P.fillRect(self.rect(), self.p.bg)
        else:
            bg = QLinearGradient(0, 0, 0, self.H)
            bg.setColorAt(0.0, self.p.bg_top)
            bg.setColorAt(1.0, self.p.bg_btm)
            P.setBrush(QBrush(bg))
            P.setPen(Qt.NoPen)
            P.drawRect(self.rect())

            # Subtle vignette
            v = QRadialGradient(self.W/2, self.H/2, max(self.W, self.H) * 0.8)
            v.setColorAt(0.0, QColor(0, 0, 0, 0))
            v.setColorAt(1.0, QColor(0, 0, 0, 60))
            P.setBrush(QBrush(v))
            P.drawRect(self.rect())

    # ────────────────────────────────────────────────────────
    def _paint_pill(self, P):
        return  # pill hidden — iOS Face ID has no top pill
        prog = self.progress["pill"]
        if prog < 0.01: return

        w = 200 * (0.88 + 0.12 * prog)
        h = 34 * (0.88 + 0.12 * prog)
        x = (self.W - w) / 2
        y = 26
        r = h / 2

        P.setOpacity(prog)
        draw_glass_pill(P, x, y, w, h,
                        border_alpha=36,
                        fill_alpha=20,
                        shadow=True)

        if prog > 0.5:
            ca = (prog - 0.5) / 0.5
            P.setOpacity(ca * prog)
            cy_ = y + h / 2

            self._draw_lock(P, x + h * 0.65, cy_, 13,
                            QColor(255, 255, 255, 240))

            font = Type.font(Type.BRAND)
            P.setFont(font)
            P.setPen(QPen(QColor(255, 255, 255, 245)))
            fm = P.fontMetrics()
            text = "FACE ID"
            tw = fm.horizontalAdvance(text)
            P.drawText(int(x + w/2 - tw/2), int(cy_ + 4), text)

            pulse = math.sin(time.time() * 3) * 0.5 + 0.5
            dot_x = x + w - h * 0.65
            blue = self.p.blue
            P.setBrush(QBrush(QColor(blue.red(), blue.green(),
                                       blue.blue(), int(30+55*pulse))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(dot_x, cy_), 7, 7)
            P.setBrush(QBrush(blue))
            P.drawEllipse(QPointF(dot_x, cy_), 3, 3)

        P.setOpacity(1.0)

    def _paint_camera(self, P):
        """
        Live camera feed — circular clipped, mirrored.
        iOS Face ID style: pure camera, no overlays.
        """
        prog = self.progress["circle"]
        if prog < 0.01: return

        cx = self.W / 2
        cy = 240
        r  = 95 * prog
        if r < 5: return

        # ── Dark circle background (fallback if no frame) ──
        bg = QRadialGradient(cx, cy - r*0.15, r*1.1)
        bg.setColorAt(0.0, QColor(16, 18, 26))
        bg.setColorAt(1.0, QColor(8,  10, 18))
        P.setBrush(QBrush(bg))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r, r)

        # ── Draw live camera feed inside circle ──
        if self.current_frame is not None:
            P.save()

            # Clip to circle
            clip = QPainterPath()
            clip.addEllipse(QPointF(cx, cy), r, r)
            P.setClipPath(clip)

            img = self.current_frame
            iw = img.width()
            ih = img.height()

            # Center-crop to square
            side = min(iw, ih)
            sx = (iw - side) // 2
            sy = (ih - side) // 2
            square = img.copy(sx, sy, side, side)

            # Scale to circle diameter
            d = int(r * 2)
            scaled = square.scaled(
                d, d,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation)

            # Mirror horizontally (selfie view)
            from PyQt5.QtGui import QTransform
            mirrored = scaled.transformed(
                QTransform().scale(-1, 1),
                Qt.SmoothTransformation)

            # Draw centered
            P.drawImage(
                int(cx - r), int(cy - r),
                mirrored)

            P.setClipping(False)
            P.restore()

        # ── Inner rim ──
        rim = QRadialGradient(cx, cy, r * 1.01)
        rim.setColorAt(0.92, QColor(255, 255, 255, 0))
        rim.setColorAt(0.97, QColor(255, 255, 255, int(30 * prog)))
        rim.setColorAt(1.00, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(rim)); P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r, r)

    # ────────────────────────────────────────────────────────
    def _paint_arc_segments(self, P):
        """
        iPhone Face ID — radial spoke marks (not arcs).
        Each mark is a straight line pointing outward from circle center,
        like spokes of a wheel. Turns green as samples are captured.
        """
        prog = self.progress["circle"]
        if prog < 0.01: return

        import math as _m
        from PyQt5.QtCore import QLineF

        cx = self.W / 2
        cy = 240

        # Circle radius (matches _paint_camera)
        circle_r = 95 * prog

        # Spoke geometry — starts just outside circle, extends outward
        inner_r = circle_r + 6           # start position
        outer_r = circle_r + 20          # end position (spoke length = 14px)

        # Line thickness
        STROKE_INACTIVE = 2.0
        STROKE_ACTIVE   = 2.6

        now = time.time()

        for i in range(N_SEGMENTS):
            # Angle for this spoke — start from top (-90°), go clockwise
            # Convert to radians for math functions
            angle_deg = -90.0 + (i * 360.0 / N_SEGMENTS)
            angle_rad = _m.radians(angle_deg)

            cos_a = _m.cos(angle_rad)
            sin_a = _m.sin(angle_rad)

            # Inner and outer points of the spoke
            x1 = cx + inner_r * cos_a
            y1 = cy + inner_r * sin_a
            x2 = cx + outer_r * cos_a
            y2 = cy + outer_r * sin_a

            # Is this spoke activated?
            activated_t = self.arc_activated_t[i]
            is_active   = activated_t > 0

            if is_active:
                age = now - activated_t
                if age < 0.4:
                    # Bloom-in: interpolate stroke + brightness
                    bloom_t = age / 0.4
                    eased   = ease_out_quint(bloom_t)
                    stroke  = STROKE_INACTIVE + (
                        STROKE_ACTIVE - STROKE_INACTIVE) * eased

                    color = QColor(self.p.arc_active)
                    boost = int(40 * (1 - bloom_t))
                    color.setRgb(
                        min(255, color.red()   + boost),
                        min(255, color.green() + boost),
                        min(255, color.blue()  + boost),
                        255)

                    # Extend spoke outward slightly during bloom (pop effect)
                    extend = 3.0 * (1 - bloom_t)
                    x2_bloom = cx + (outer_r + extend) * cos_a
                    y2_bloom = cy + (outer_r + extend) * sin_a

                    # Glow halo (thicker faded line beneath)
                    glow_alpha = int(140 * (1 - bloom_t))
                    if glow_alpha > 5:
                        glow_color = QColor(self.p.arc_active)
                        glow_color.setAlpha(glow_alpha)
                        P.setPen(QPen(glow_color, stroke + 3.5,
                                      Qt.SolidLine, Qt.RoundCap))
                        P.drawLine(QLineF(x1, y1, x2_bloom, y2_bloom))

                    x2, y2 = x2_bloom, y2_bloom
                else:
                    stroke = STROKE_ACTIVE
                    color  = QColor(self.p.arc_active)
            else:
                stroke = STROKE_INACTIVE
                color  = QColor(self.p.arc_inactive)

            # Fade in with appearance progress
            color.setAlpha(int(color.alpha() * prog))

            # Draw the spoke line
            P.setPen(QPen(color, stroke,
                          Qt.SolidLine, Qt.RoundCap))
            P.drawLine(QLineF(x1, y1, x2, y2))


    # ────────────────────────────────────────────────────────
    def _paint_text(self, P):
        # Title
        tp = self.progress["title"]
        if tp > 0.01:
            offset_y = (1.0 - tp) * 14

            font = Type.font(Type.HERO)
            P.setFont(font)
            color = QColor(self.p.text)
            color.setAlpha(int(color.alpha() * tp))
            P.setPen(QPen(color))

            if self.complete and self.success:
                text = "Face ID is set up"
            elif self.complete:
                text = "Setup failed"
            else:
                text = ""  # no title during scanning

            fm = P.fontMetrics()
            tw = fm.horizontalAdvance(text)
            y = 400 + offset_y
            P.drawText(int(self.W/2 - tw/2), int(y), text)

        # Subtitle
        sp = self.progress["subtitle"]
        if sp > 0.01:
            offset_y = (1.0 - sp) * 10

            font = Type.font(Type.BODY, text=True)
            P.setFont(font)
            color = QColor(self.p.text_dim)
            color.setAlpha(int(color.alpha() * sp))
            P.setPen(QPen(color))

            if self.complete and self.success:
                sub = "You can now unlock with your face"
            elif self.complete:
                sub = self.error_msg or "Please try again"
            else:
                sub = "Move your head slowly\nto complete the circle."

            fm = P.fontMetrics()
            lines = sub.split("\n")
            line_h = fm.height() + 2
            base_y = 400 + offset_y
            for li, line in enumerate(lines):
                tw = fm.horizontalAdvance(line)
                P.drawText(int(self.W/2 - tw/2),
                           int(base_y + li * line_h), line)

    # ────────────────────────────────────────────────────────
    def _paint_button(self, P):
        """iOS-style Cancel button (top-left) + Accessibility bottom"""
        prog = self.progress["button"]
        if prog < 0.01: return

        P.setOpacity(prog)

        # ── Cancel (top-left) ──
        font = Type.font(Type.BUTTON)
        font.setUnderline(self.cancel_hover)
        P.setFont(font)
        if self.cancel_hover:
            color = self.p.red
        else:
            color = self.p.blue if not self.cancel_press else self.p.text_quiet
        P.setPen(QPen(color))
        P.drawText(28, 52, "Cancel")

        # ── Accessibility Options (bottom-center, glass pill) ──
        acc_text = "Accessibility Options"
        acc_font = Type.font(Type.CALLOUT)
        P.setFont(acc_font)
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(acc_text)
        
        btn_w = tw + 40
        btn_h = 36
        btn_x = (self.W - btn_w) / 2
        btn_y = 645
        
        # Determine hover state (accessible from mouse position)
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        is_hover = btn_x <= cursor_pos.x() <= btn_x + btn_w and btn_y <= cursor_pos.y() <= btn_y + btn_h
        
        tint = QColor(255, 255, 255, 15) if self.is_dark else QColor(0, 0, 0, 10)
        if is_hover:
            tint = QColor(10, 132, 255, 40)
            
        draw_glass_pill(P, btn_x, btn_y, btn_w, btn_h, 
                        tint=tint, border_alpha=30, fill_alpha=20, shadow=True)
                        
        P.setPen(QPen(self.p.blue))
        P.drawText(int(btn_x + btn_w/2 - tw/2), int(btn_y + btn_h/2 + 4), acc_text)

        P.setOpacity(1.0)

    # ────────────────────────────────────────────────────────
    def _paint_success(self, P):
        """Success state — green checkmark in center of camera"""
        if self.success_scale < 0.01: return

        cx = self.W / 2
        cy = 240
        r = 95

        # Green tint overlay
        green = self.p.green
        sphere = QRadialGradient(cx, cy, r * 1.3 * self.success_scale)
        a = int(180 * self.success_scale)
        sphere.setColorAt(0.0, QColor(green.red(), green.green(),
                                        green.blue(), a))
        sphere.setColorAt(0.6, QColor(green.red(), green.green(),
                                        green.blue(), a // 2))
        sphere.setColorAt(1.0, QColor(green.red(), green.green(),
                                        green.blue(), 0))
        P.setBrush(QBrush(sphere))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy),
                      r * 1.3 * self.success_scale,
                      r * 1.3 * self.success_scale)

        # Big checkmark
        if self.success_scale > 0.5:
            ct = (self.success_scale - 0.5) / 0.5
            cc = QColor(255, 255, 255, int(255 * ct))
            P.setPen(QPen(cc, 6 * ct,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.setBrush(Qt.NoBrush)
            check = QPainterPath()
            check.moveTo(cx - 26 * ct, cy + 0)
            check.lineTo(cx - 6 * ct, cy + 18 * ct)
            check.lineTo(cx + 28 * ct, cy - 18 * ct)
            P.drawPath(check)

    # ────────────────────────────────────────────────────────
    def _draw_lock(self, P, cx, cy, size, color):
        s = size / 24.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        shackle = QPainterPath()
        shackle.moveTo(-5, -2)
        shackle.lineTo(-5, -7)
        shackle.cubicTo(-5, -12, 5, -12, 5, -7)
        shackle.lineTo(5, -2)
        P.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawPath(shackle)
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(color))
        body = QPainterPath()
        body.addRoundedRect(QRectF(-7, -2, 14, 10), 2, 2)
        P.drawPath(body)
        P.restore()

    # ────────────────────────────────────────────────────────
    # NEW PHASES (USER SELECT & PASSWORD)
    # ────────────────────────────────────────────────────────
    def _paint_user_select(self, P):
        """Phase -2: Dynamic User Selection Screen"""
        # Cancel button top-left
        self.progress["button"] = 1.0  # Force button opacity
        self._paint_button(P)

        # Entrance animation
        t = self.user_select_t
        prog = ease_out_quint(min(t / 0.6, 1.0))
        if prog < 0.01: return

        # Title
        font = Type.font(Type.HERO)
        P.setFont(font)
        color = QColor(self.p.text)
        color.setAlpha(int(255 * prog))
        P.setPen(QPen(color))
        text = "Choose Account"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        y = 120 + (1.0 - prog) * 20
        P.drawText(int(self.W/2 - tw/2), int(y), text)

        # Subtitle
        font = Type.font(Type.BODY, text=True)
        P.setFont(font)
        color = QColor(self.p.text_dim)
        color.setAlpha(int(255 * prog))
        P.setPen(QPen(color))
        sub = "Select a user to set up Face ID"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(sub)
        P.drawText(int(self.W/2 - tw/2), int(y + 30), sub)

        # User Cards
        card_w = 340
        card_h = 76
        start_y = 220
        spacing = 16

        for i, user in enumerate(self.system_users):
            cx = (self.W - card_w) / 2
            cy = start_y + i * (card_h + spacing)
            
            # Staggered entrance
            delay = 0.1 + i * 0.08
            local_t = max(0, t - delay)
            cprog = ease_out_quint(min(local_t / 0.5, 1.0))
            if cprog < 0.01: continue
            
            cy += (1.0 - cprog) * 30
            P.setOpacity(cprog)
            
            # Draw Glass Card
            scale = self.user_card_springs[i].x
            
            P.save()
            P.translate(cx + card_w/2, cy + card_h/2)
            P.scale(scale, scale)
            P.translate(-(cx + card_w/2), -(cy + card_h/2))
            
            is_hover = (i == self.user_hovered_idx)
            tint = None
            if is_hover:
                tint = QColor(255, 255, 255, 10) if self.is_dark else QColor(0, 0, 0, 10)
                
            draw_glass_pill(P, cx, cy, card_w, card_h, 
                            tint=tint, border_alpha=30, fill_alpha=20, shadow=True)
            
            # Avatar Circle
            ar = 24
            ax = cx + 20 + ar
            ay = cy + card_h/2
            
            avatar_grad = QLinearGradient(ax - ar, ay - ar, ax + ar, ay + ar)
            avatar_grad.setColorAt(0.0, QColor(40, 145, 255))
            avatar_grad.setColorAt(1.0, QColor(0, 100, 220))
            P.setBrush(QBrush(avatar_grad))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(ax, ay), ar, ar)
            
            # Avatar Initial
            initial = user["fullname"][0].upper() if user["fullname"] else user["username"][0].upper()
            P.setFont(Type.font((20, QFont.Bold, 0.0)))
            P.setPen(QPen(QColor(255, 255, 255)))
            fm = P.fontMetrics()
            tw = fm.horizontalAdvance(initial)
            P.drawText(int(ax - tw/2), int(ay + fm.height()/3), initial)
            
            # Names
            text_x = ax + ar + 16
            
            P.setFont(Type.font(Type.BUTTON))
            P.setPen(QPen(self.p.text))
            fm = P.fontMetrics()
            P.drawText(int(text_x), int(cy + card_h/2 - 4), user["fullname"] or user["username"])
            
            P.setFont(Type.font(Type.MICRO))
            P.setPen(QPen(self.p.text_dim))
            P.drawText(int(text_x), int(cy + card_h/2 + 16), "@" + user["username"])
            
            # Enrolled Badge
            if user.get("enrolled"):
                bx = cx + card_w - 24
                # Professional badge (not dreamy): simple green text + check
                P.setFont(Type.font((11, QFont.DemiBold, 0.0)))
                P.setPen(QPen(self.p.green))
                badge_txt = "Enrolled  ✓"
                fm = P.fontMetrics()
                bw = fm.horizontalAdvance(badge_txt)
                P.drawText(int(bx - bw), int(cy + card_h/2 + 5), badge_txt)
            
            P.restore()
        
        P.setOpacity(1.0)


    def _paint_password_screen(self, P):
        """Phase -1: Password Verification Screen"""
        t = self.pwd_appear_t
        prog = ease_out_quint(min(t / 0.5, 1.0))
        if prog < 0.01: return

        P.setOpacity(prog)

        # Back button top-left
        font = Type.font(Type.BUTTON)
        font.setUnderline(self.pwd_back_hover)
        P.setFont(font)
        if self.pwd_back_hover:
            color = self.p.red
        else:
            color = self.p.blue if not self.cancel_press else self.p.text_quiet
        P.setPen(QPen(color))
        P.drawText(28, 52, "Back")

        y_offset = (1.0 - prog) * 20

        # Lock Icon
        icon_y = 120 + y_offset
        self._draw_lock(P, self.W/2, icon_y, 48, self.p.text)

        # Title
        font = Type.font(Type.HERO)
        P.setFont(font)
        P.setPen(QPen(self.p.text))
        text = "Enter Password"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        P.drawText(int(self.W/2 - tw/2), int(icon_y + 60), text)

        # Subtitle
        font = Type.font(Type.BODY, text=True)
        P.setFont(font)
        P.setPen(QPen(self.p.text_dim))
        sub = f"Verify your identity for @{self.username}"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(sub)
        P.drawText(int(self.W/2 - tw/2), int(icon_y + 90), sub)

        # Error Message (if any)
        if self.pwd_error:
            # Shake animation
            shake_t = time.time() - self.pwd_error_t
            shake_x = 0
            if shake_t < 0.4:
                shake_x = math.sin(shake_t * 40) * (8 * (1.0 - shake_t/0.4))
            
            # Adjust input box position if shaking
            self.pwd_input.move(int((self.W - 320) // 2 + shake_x), 370)
            
            P.setFont(Type.font(Type.MICRO))
            P.setPen(QPen(self.p.red))
            fm = P.fontMetrics()
            tw = fm.horizontalAdvance(self.pwd_error_msg)
            P.drawText(int(self.W/2 - tw/2), 440, self.pwd_error_msg)
        else:
            self.pwd_input.move((self.W - 320) // 2, 370)

        # Verify Button
        btn_w = 320
        btn_h = 48
        btn_x = (self.W - btn_w) / 2
        btn_y = 460
        
        scale = self.pwd_btn_spring.x
        
        P.save()
        P.translate(btn_x + btn_w/2, btn_y + btn_h/2)
        P.scale(scale, scale)
        P.translate(-(btn_x + btn_w/2), -(btn_y + btn_h/2))
        
        draw_glass_button(P, btn_x, btn_y, btn_w, btn_h, 
                          self.p.blue, hover=self.pwd_verify_hover, pressed=self.pwd_verify_press)
        
        P.setFont(Type.font(Type.BUTTON))
        P.setPen(QPen(QColor(255, 255, 255)))
        fm = P.fontMetrics()
        btn_txt = "Verifying..." if self.pwd_verifying else "Continue"
        tw = fm.horizontalAdvance(btn_txt)
        P.drawText(int(btn_x + btn_w/2 - tw/2), int(btn_y + btn_h/2 + 5), btn_txt)
        
        P.restore()

        P.setOpacity(1.0)

    # ────────────────────────────────────────────────────────
    # INTERACTIONS
    # ────────────────────────────────────────────────────────
    def _in_cancel(self, x, y):
        return 20 <= x <= 90 and 32 <= y <= 68

    def _in_accessibility(self, x, y):
        return (self.W/2 - 110) <= x <= (self.W/2 + 110) and 640 <= y <= 680

    def _get_hovered_user_card(self, x, y):
        if self.phase != -2: return -1
        card_w, card_h, spacing = 340, 76, 16
        start_y = 220
        cx = (self.W - card_w) / 2
        for i in range(len(self.system_users)):
            cy = start_y + i * (card_h + spacing)
            if cx <= x <= cx + card_w and cy <= y <= cy + card_h:
                return i
        return -1

    def _in_verify_btn(self, x, y):
        if self.phase != -1: return False
        btn_w, btn_h = 320, 48
        btn_x, btn_y = (self.W - btn_w) / 2, 460
        return btn_x <= x <= btn_x + btn_w and btn_y <= y <= btn_y + btn_h

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        self.cancel_hover = self._in_cancel(x, y)
        self.user_hovered_idx = self._get_hovered_user_card(x, y)
        self.pwd_verify_hover = self._in_verify_btn(x, y)
        self.pwd_back_hover = self.cancel_hover if self.phase == -1 else False

        if self.cancel_hover or self.pwd_verify_hover or self.user_hovered_idx >= 0 or (self.phase >= 0 and self._in_accessibility(x, y)):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton: return
        x, y = e.x(), e.y()
        if self._in_cancel(x, y):
            self.cancel_press = True
            self.pwd_verify_press = False
        elif self._in_verify_btn(x, y):
            self.pwd_verify_press = True
            self.cancel_press = False

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton: return
        x, y = e.x(), e.y()
        
        was_cancel = self.cancel_press
        was_verify = self.pwd_verify_press
        self.cancel_press = False
        self.pwd_verify_press = False

        if was_cancel and self._in_cancel(x, y):
            if self.phase == -1:
                self._go_back_to_select()
            else:
                self._cancel()
            return
            
        if self.phase == -2:
            idx = self._get_hovered_user_card(x, y)
            if idx >= 0:
                if self.system_users[idx].get("enrolled"):
                    # Show warning if re-enrolling
                    from PyQt5.QtWidgets import QMessageBox
                    box = QMessageBox(self)
                    box.setWindowTitle("Already Enrolled")
                    box.setText(f"Face ID is already set up for {self.system_users[idx]['username']}.")
                    box.setInformativeText("Do you want to overwrite the existing face profile?")
                    box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
                    box.setDefaultButton(QMessageBox.Cancel)
                    # Apply professional dark styling
                    box.setStyleSheet("QMessageBox { background-color: #1c1c1e; color: #fff; } QMessageBox QLabel { color: #fff; } QPushButton { background-color: #0a84ff; color: white; padding: 6px 14px; border-radius: 6px; }")
                    if box.exec_() != QMessageBox.Yes:
                        return
                self._select_user(idx)
            return

        if self.phase == -1 and was_verify and self._in_verify_btn(x, y):
            self._verify_password()
            return

        if self.phase >= 0 and self._in_accessibility(x, y):
            self._show_accessibility()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            if self.phase == -1:
                self._go_back_to_select()
            else:
                self._cancel()

    def _show_accessibility(self):
        """
        Friendly accessibility dialog with professional custom UI.
        Explains options in plain language for new users.
        """
        from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
        from PyQt5.QtCore import Qt
        from PyQt5.QtGui import QPainter, QColor, QPainterPath

        class PremiumDialog(QDialog):
            def __init__(self, parent_widget, is_dark):
                super().__init__(parent_widget)
                self.is_dark = is_dark
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
                self.setAttribute(Qt.WA_TranslucentBackground)
                
                # Setup layout
                layout = QVBoxLayout(self)
                layout.setContentsMargins(24, 28, 24, 24)
                layout.setSpacing(16)
                
                # Title
                title = QLabel("Having trouble moving your head?")
                title.setFont(Type.font((18, QFont.Bold, -0.01)))
                title.setStyleSheet("color: white;" if is_dark else "color: black;")
                title.setWordWrap(True)
                layout.addWidget(title)
                
                # Body
                body_text = (
                    "Normally you rotate your head slowly to capture your face from different angles.\n\n"
                    "If that's difficult, we can set up Face ID with fewer samples — just hold your face still and look at the camera. "
                    "You can always redo setup later."
                )
                body = QLabel(body_text)
                body.setFont(Type.font(Type.BODY, text=True))
                body.setStyleSheet("color: rgba(255,255,255,180);" if is_dark else "color: rgba(0,0,0,180);")
                body.setWordWrap(True)
                layout.addWidget(body)
                
                layout.addSpacing(10)
                
                # Buttons
                btn_layout = QHBoxLayout()
                btn_layout.setSpacing(12)
                
                self.btn_normal = QPushButton("Keep Normal Setup")
                self.btn_normal.setCursor(Qt.PointingHandCursor)
                self.btn_normal.setFont(Type.font(Type.BUTTON))
                self.btn_normal.setFixedHeight(42)
                
                self.btn_quick = QPushButton("Use Quick Setup")
                self.btn_quick.setCursor(Qt.PointingHandCursor)
                self.btn_quick.setFont(Type.font(Type.BUTTON))
                self.btn_quick.setFixedHeight(42)
                
                # Button Styling
                if is_dark:
                    self.btn_normal.setStyleSheet("""
                        QPushButton { background-color: rgba(255,255,255,20); color: white; border-radius: 10px; }
                        QPushButton:hover { background-color: rgba(255,255,255,30); }
                    """)
                else:
                    self.btn_normal.setStyleSheet("""
                        QPushButton { background-color: rgba(0,0,0,10); color: black; border-radius: 10px; }
                        QPushButton:hover { background-color: rgba(0,0,0,20); }
                    """)
                    
                self.btn_quick.setStyleSheet("""
                    QPushButton { background-color: #0a84ff; color: white; border-radius: 10px; }
                    QPushButton:hover { background-color: #409cff; }
                """)
                
                self.btn_normal.clicked.connect(self.reject)
                self.btn_quick.clicked.connect(self.accept)
                
                btn_layout.addWidget(self.btn_normal)
                btn_layout.addWidget(self.btn_quick)
                layout.addLayout(btn_layout)
                
                self.setFixedSize(360, 240)

            def paintEvent(self, e):
                P = QPainter(self)
                P.setRenderHint(QPainter.Antialiasing)
                path = QPainterPath()
                path.addRoundedRect(self.rect(), 16, 16)
                
                # Premium Drop Shadow & Border
                P.setPen(Qt.NoPen)
                P.setBrush(QColor(0, 0, 0, 60))
                P.drawRoundedRect(self.rect().adjusted(2, 6, -2, -2), 16, 16)
                
                # Background
                bg_color = QColor(28, 28, 30, 245) if self.is_dark else QColor(250, 250, 250, 245)
                P.setBrush(bg_color)
                
                # Thin Border
                border_color = QColor(255, 255, 255, 30) if self.is_dark else QColor(0, 0, 0, 30)
                P.setPen(QPen(border_color, 1))
                P.drawPath(path)

        dialog = PremiumDialog(self, self.is_dark)
        
        # Center dialog over the wizard
        pos = self.mapToGlobal(self.rect().center())
        dialog.move(pos.x() - dialog.width() // 2, pos.y() - dialog.height() // 2)

        if dialog.exec_() == QDialog.Accepted:
            # Quick setup
            try:
                new_count = 8
                self.worker.samples_needed = new_count
                print(f"[Nova] Quick Setup: {new_count} samples")
            except Exception as e:
                print(f"[Nova] Quick setup failed: {e}")

    def _cancel(self):
        try:
            self.worker.stop()
            self.worker.wait(1000)
        except: pass
        self.finished_signal.emit(False, self.username)

    def closeEvent(self, e):
        try:
            self.worker.stop()
            self.worker.wait(1000)
        except: pass
        e.accept()


# ════════════════════════════════════════════════════════════════
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=None, help="Skip selection and enroll specific user")
    ap.add_argument("--samples", type=int, default=N_SEGMENTS)
    ap.add_argument("--theme", default="auto",
                    choices=["auto", "dark", "light", "pure_black"])
    ap.add_argument("--skip-splash", action="store_true",
                    help="Skip onboarding splash and go directly to enrollment")
    args = ap.parse_args()

    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except: pass

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    def launch_wizard():
        """Create and show the enrollment wizard."""
        wizard = EnrollmentWizard(args.user, args.samples, theme=args.theme)

        def on_done(success, username):
            icon = '\u2705' if success else '\u274c'
            print(f"[Nova] {icon} {username}")
            if not success:
                from PyQt5.QtWidgets import QMessageBox
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("NovaUnlock Error")
                msg.setText("Camera Unavailable")
                msg.setInformativeText("The camera could not be started. It might be blocked by privacy settings, antivirus, or used by another app.")
                msg.exec_()
            QTimer.singleShot(200, app.quit)

        wizard.finished_signal.connect(on_done)

        scr = app.primaryScreen().geometry()
        wizard.move((scr.width() - wizard.W) // 2,
                    (scr.height() - wizard.H) // 2)

        wizard.show()
        wizard.raise_()
        wizard.activateWindow()
        # prevent garbage collection
        app._nova_wizard = wizard

    if args.skip_splash:
        launch_wizard()
    else:
        # Show the onboarding greeting splash first
        try:
            from nova_unlock.ui.onboarding_splash import OnboardingSplash
            splash = OnboardingSplash(appearance="auto")

            scr = app.primaryScreen().geometry()
            splash.move((scr.width() - splash.W) // 2,
                        (scr.height() - splash.H) // 2)

            def on_get_started():
                splash.close()
                QTimer.singleShot(200, launch_wizard)

            def on_skip():
                print("[Nova] Enrollment skipped by user")
                QTimer.singleShot(100, app.quit)

            splash.get_started_clicked.connect(on_get_started)
            splash.skip_clicked.connect(on_skip)

            splash.show()
            splash.raise_()
            splash.activateWindow()
            # prevent garbage collection
            app._nova_splash = splash
        except Exception as e:
            log.warning(f"Onboarding splash failed: {e}, going directly to enrollment")
            launch_wizard()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()