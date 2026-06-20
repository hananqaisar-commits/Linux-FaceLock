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

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject, QThread)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont,
                              QRadialGradient, QLinearGradient,
                              QBrush, QPainterPath, QImage)

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
    """Auto-detect: dark or light"""
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
#  SPRING
# ════════════════════════════════════════════════════════════════
class Spring:
    __slots__ = ('omega', 'x', 'v')
    def __init__(self, freq=5.0):
        self.omega = 2.0 * math.pi * freq
        self.x = 0.0
        self.v = 0.0
    def update(self, dt, target):
        f = 1.0 + 2.0 * dt * self.omega
        oo = self.omega * self.omega
        hoo = dt * oo
        hhoo = dt * hoo
        det_inv = 1.0 / (f + hhoo)
        det_x = f * self.x + dt * self.v + hhoo * target
        det_v = self.v + hoo * (target - self.x)
        self.x = det_x * det_inv
        self.v = det_v * det_inv
        return self.x


def ease_out_quint(t):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 1 - pow(1 - t, 5)


# ════════════════════════════════════════════════════════════════
#  ARC SEGMENT (16 segments around circle)
# ════════════════════════════════════════════════════════════════
N_SEGMENTS = 16


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
        for idx in range(3):
            try:
                c = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    c.set(cv2.CAP_PROP_FPS, 30)
                    for _ in range(5): c.grab()
                    ok, _ = c.read()
                    if ok:
                        cap = c
                        break
                c.release()
            except: pass

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

        self.username = username or os.environ.get("USER", "user")
        # Samples = number of arc segments (16)
        self.samples_needed = N_SEGMENTS

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
        self.phase = 0  # 0=appearing, 1=scanning, 2=success, 3=failed

        # Arc activation timestamps (when each segment lit up)
        self.arc_activated_t = [0.0] * N_SEGMENTS  # 0 = not yet active

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

        # Worker
        self.signals = WorkerSignals()
        self.signals.frame_ready.connect(self._on_frame)
        self.signals.sample_captured.connect(self._on_sample)
        self.signals.face_detected.connect(self._on_face)
        self.signals.finished.connect(self._on_finished)

        self.worker = EnrollmentWorker(
            self.signals, self.username, self.samples_needed)

        # Window
        self.setWindowTitle("Nova · Face ID")
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        bg = self.p.bg if hasattr(self.p, 'bg') else self.p.bg_btm
        self.setStyleSheet(
            f"background-color: rgb({bg.red()},{bg.green()},{bg.blue()});")

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        QTimer.singleShot(900, self._start_worker)

    def _start_worker(self):
        if self.phase != 0: return
        self.phase = 1
        self.worker.start()

    # ────────────────────────────────────────────────────────
    def _on_frame(self, rgb_frame):
        try:
            h, w, ch = rgb_frame.shape
            qimg = QImage(rgb_frame.data, w, h, ch * w, QImage.Format_RGB888)
            self.current_frame = qimg.copy()
        except: pass

    def _on_sample(self, count):
        """Each sample activates one arc segment"""
        self.samples_done = count
        # Activate this segment (index = count-1)
        idx = count - 1
        if 0 <= idx < N_SEGMENTS:
            self.arc_activated_t[idx] = time.time()
        # Capture flash
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

        self._paint_bg(P)
        self._paint_pill(P)
        self._paint_camera(P)
        self._paint_arc_segments(P)  # The 16 arcs around face
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
        prog = self.progress["pill"]
        if prog < 0.01: return

        w = 200 * (0.85 + 0.15 * prog)
        h = 34 * (0.85 + 0.15 * prog)
        x = (self.W - w) / 2
        y = 26
        r = h / 2

        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), r, r)

        # Shadow
        for dy, alpha in [(2, 30), (4, 18), (8, 10)]:
            P.save()
            P.translate(0, dy)
            P.setBrush(QBrush(QColor(0, 0, 0, int(alpha * prog))))
            P.setPen(Qt.NoPen)
            P.drawPath(path)
            P.restore()

        # Body
        P.setBrush(QBrush(self.p.pill))
        P.setPen(Qt.NoPen)
        P.drawPath(path)

        # Sheen
        sheen = QLinearGradient(x, y, x, y + h * 0.6)
        sheen.setColorAt(0, QColor(255, 255, 255, 22))
        sheen.setColorAt(1, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(sheen))
        P.drawPath(path)

        # Border
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(self.p.pill_border, 0.6))
        P.drawPath(path)

        # Content
        if prog > 0.5:
            ca = (prog - 0.5) / 0.5
            P.setOpacity(ca)
            cy = y + h / 2

            # Lock
            self._draw_lock(P, x + h * 0.65, cy, 13,
                            QColor(255, 255, 255, 240))

            # Brand
            font = Type.font(Type.BRAND)
            P.setFont(font)
            P.setPen(QPen(QColor(255, 255, 255, 245)))
            fm = P.fontMetrics()
            text = "FACE ID"
            tw = fm.horizontalAdvance(text)
            P.drawText(int(x + w/2 - tw/2), int(cy + 4), text)

            # Camera dot
            pulse = math.sin(time.time() * 3) * 0.5 + 0.5
            dot_x = x + w - h * 0.65
            blue = self.p.blue
            P.setBrush(QBrush(QColor(blue.red(), blue.green(), blue.blue(),
                                       int(30 + 60 * pulse))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(dot_x, cy), 7, 7)
            P.setBrush(QBrush(blue))
            P.drawEllipse(QPointF(dot_x, cy), 3, 3)

            P.setOpacity(1.0)

    # ────────────────────────────────────────────────────────
    def _paint_camera(self, P):
        """Live camera in clean circle"""
        prog = self.progress["circle"]
        if prog < 0.01: return

        cx = self.W / 2
        cy = 240
        r = 95 * prog   # camera circle radius

        if r < 5: return

        # ── Clip + draw ──
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), r, r)
        P.setClipPath(clip)

        # Dark base
        P.setBrush(QBrush(self.p.camera_bg))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r, r)

        # Live frame
        if self.current_frame is not None:
            try:
                src = self.current_frame
                side = min(src.width(), src.height())
                sx_c = (src.width() - side) // 2
                sy_c = (src.height() - side) // 2
                target = int(r * 2)
                cropped = src.copy(sx_c, sy_c, side, side)
                scaled = cropped.scaled(target, target,
                                        Qt.KeepAspectRatio,
                                        Qt.SmoothTransformation)
                scaled = scaled.mirrored(True, False)
                P.drawImage(QPointF(cx - r, cy - r), scaled)
            except: pass

        # Flash on capture
        if self.flash_alpha > 0.005:
            P.setBrush(QBrush(QColor(255, 255, 255,
                                       int(150 * self.flash_alpha))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), r, r)

        P.setClipping(False)

        # Inner rim highlight
        rim = QRadialGradient(cx, cy, r * 1.01)
        rim.setColorAt(0.92, QColor(255, 255, 255, 0))
        rim.setColorAt(0.97, QColor(255, 255, 255, int(40 * prog)))
        rim.setColorAt(1.00, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(rim))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r, r)

    # ────────────────────────────────────────────────────────
    def _paint_arc_segments(self, P):
        """
        Authentic iPhone Face ID style:
        16 arc segments around the face circle.
        Each turns from gray to green as samples are captured.
        """
        prog = self.progress["circle"]
        if prog < 0.01: return

        cx = self.W / 2
        cy = 240
        # Arc radius — outside the camera circle
        arc_r = 95 * prog + 14

        # Each arc is 360/16 = 22.5 degrees
        # With a small gap between them (visual separation)
        SEGMENT_ANGLE = 360.0 / N_SEGMENTS  # 22.5°
        GAP_ANGLE = 4.0                      # 4° gap
        ARC_LENGTH = SEGMENT_ANGLE - GAP_ANGLE  # 18.5° per arc

        # Arc thickness (varies for active/inactive look)
        STROKE_INACTIVE = 2.0
        STROKE_ACTIVE = 3.5

        rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
        now = time.time()

        for i in range(N_SEGMENTS):
            # Start angle for this segment
            # Start from top (-90°) and go clockwise
            # Qt arc: 0° = 3 o'clock, positive = counter-clockwise
            # So we convert: top (-90° in screen) = 90° in Qt
            start_angle_qt = 90 - (i * SEGMENT_ANGLE) - (GAP_ANGLE / 2)

            # Qt drawArc uses 1/16 degree units
            start_qt = int(start_angle_qt * 16)
            span_qt = int(-ARC_LENGTH * 16)  # negative = clockwise

            # Is this segment activated?
            activated_t = self.arc_activated_t[i]
            is_active = activated_t > 0

            if is_active:
                # Bloom animation when freshly activated
                age = now - activated_t
                if age < 0.4:
                    # Bloom-in: scale and brighten
                    bloom_t = age / 0.4
                    eased = ease_out_quint(bloom_t)
                    stroke = STROKE_INACTIVE + (STROKE_ACTIVE - STROKE_INACTIVE) * eased
                    color = QColor(self.p.arc_active)
                    # Slight brightness boost during bloom
                    boost = int(40 * (1 - bloom_t))
                    color.setRgb(
                        min(255, color.red() + boost),
                        min(255, color.green() + boost),
                        min(255, color.blue() + boost),
                        255
                    )

                    # Glow halo during bloom
                    glow_alpha = int(120 * (1 - bloom_t))
                    if glow_alpha > 5:
                        glow_color = QColor(self.p.arc_active)
                        glow_color.setAlpha(glow_alpha)
                        P.setPen(QPen(glow_color, stroke + 4,
                                      Qt.SolidLine, Qt.RoundCap))
                        P.setBrush(Qt.NoBrush)
                        P.drawArc(rect, start_qt, span_qt)
                else:
                    stroke = STROKE_ACTIVE
                    color = QColor(self.p.arc_active)
            else:
                stroke = STROKE_INACTIVE
                color = QColor(self.p.arc_inactive)

            # Apply opacity for appearance progress
            color.setAlpha(int(color.alpha() * prog))

            # Draw the arc
            P.setPen(QPen(color, stroke,
                          Qt.SolidLine, Qt.RoundCap))
            P.setBrush(Qt.NoBrush)
            P.drawArc(rect, start_qt, span_qt)

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
            elif not self.face_detected and self.samples_done == 0:
                text = "Position your face"
            else:
                text = "Hold still"

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
            elif not self.face_detected:
                sub = "Look at the camera"
            else:
                sub = f"Capturing your face"

            fm = P.fontMetrics()
            tw = fm.horizontalAdvance(sub)
            P.drawText(int(self.W/2 - tw/2), int(432 + offset_y), sub)

    # ────────────────────────────────────────────────────────
    def _paint_button(self, P):
        """iOS-style text button (Cancel)"""
        prog = self.progress["button"]
        if prog < 0.01: return

        scale = self.cancel_spring.x if self.cancel_spring.x > 0.01 else 1.0

        font = Type.font(Type.BUTTON)
        P.setFont(font)
        P.setOpacity(prog)

        # iOS blue text button
        color = self.p.blue if not self.cancel_press else self.p.text_quiet

        P.setPen(QPen(color))
        text = "Cancel"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)

        # Apply scale via font size variation
        y = 640
        x = self.W/2 - tw/2

        P.drawText(int(x), int(y), text)

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
    # INTERACTIONS
    # ────────────────────────────────────────────────────────
    def _in_cancel(self, x, y):
        return 200 <= x <= 280 and 620 <= y <= 658

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        self.cancel_hover = self._in_cancel(x, y)
        if self.cancel_hover:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._in_cancel(e.x(), e.y()):
            self.cancel_press = True

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton: return
        was = self.cancel_press
        self.cancel_press = False
        if was and self._in_cancel(e.x(), e.y()):
            self._cancel()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._cancel()

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
    ap.add_argument("--user", default=os.environ.get("USER", "user"))
    ap.add_argument("--samples", type=int, default=N_SEGMENTS)
    ap.add_argument("--theme", default="auto",
                    choices=["auto", "dark", "light", "pure_black"])
    args = ap.parse_args()

    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except: pass

    app = QApplication(sys.argv)
    wizard = EnrollmentWizard(args.user, args.samples, theme=args.theme)

    def on_done(success, username):
        print(f"[Nova] {'✅' if success else '❌'} {username}")
        QTimer.singleShot(200, app.quit)

    wizard.finished_signal.connect(on_done)

    scr = app.primaryScreen().geometry()
    wizard.move((scr.width() - wizard.W) // 2,
                (scr.height() - wizard.H) // 2)

    wizard.show()
    wizard.raise_()
    wizard.activateWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
