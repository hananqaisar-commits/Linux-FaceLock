#!/usr/bin/env python3
"""
Nova · Face ID Onboarding
Premium splash — clean, restrained, beautiful.
"""
from __future__ import annotations

import math
import os
import sys
import time
import random
import subprocess
from typing import Optional, List, Tuple

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont,
                              QRadialGradient, QLinearGradient,
                              QConicalGradient, QBrush, QPainterPath,
                              QFontMetrics, QPixmap, QImage, QTransform, QCursor)
import sys as _sys
from pathlib import Path as _Path
_ROOT = _Path(__file__).parent.parent.parent
if str(_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_ROOT))
from nova_unlock.ui.glass import draw_glass_pill, draw_glass_card, draw_glass_button


# ════════════════════════════════════════════════════════════════
#  ENV
# ════════════════════════════════════════════════════════════════
class Env:
    @staticmethod
    def is_dark():
        try:
            r = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True, text=True, timeout=1.5)
            if "dark" in r.stdout.lower(): return True
            if "light" in r.stdout.lower(): return False
        except Exception: pass
        try:
            r = subprocess.run(
                ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
                capture_output=True, text=True, timeout=1.5)
            return "dark" in r.stdout.lower()
        except Exception:
            return True


# ════════════════════════════════════════════════════════════════
#  COLORS
# ════════════════════════════════════════════════════════════════
class Palette:
    class Dark:
        bg_top     = QColor(12, 14, 22)
        bg_mid     = QColor(6, 7, 12)
        bg_btm     = QColor(0, 0, 4)

        # Cards — properly visible
        card       = QColor(28, 30, 38)
        card_hi    = QColor(38, 42, 52)
        card_border= QColor(255, 255, 255, 22)

        # Pill (very dark, distinct)
        pill       = QColor(8, 9, 14)
        pill_border= QColor(255, 255, 255, 28)

        # Text
        text       = QColor(255, 255, 255)
        text_dim   = QColor(170, 180, 200)
        text_quiet = QColor(110, 120, 140)

        # Accents
        blue       = QColor(10, 132, 255)
        blue_hi    = QColor(64, 156, 255)
        green      = QColor(48, 209, 88)
        purple     = QColor(175, 122, 255)

    class Light:
        bg_top     = QColor(248, 250, 254)
        bg_mid     = QColor(242, 245, 250)
        bg_btm     = QColor(235, 240, 248)

        card       = QColor(255, 255, 255)
        card_hi    = QColor(252, 253, 255)
        card_border= QColor(0, 0, 0, 28)

        pill       = QColor(15, 15, 20)
        pill_border= QColor(255, 255, 255, 40)

        text       = QColor(10, 14, 22)
        text_dim   = QColor(60, 70, 90)
        text_quiet = QColor(130, 140, 155)

        blue       = QColor(0, 122, 255)
        blue_hi    = QColor(40, 145, 255)
        green      = QColor(52, 199, 89)
        purple     = QColor(155, 100, 220)


# ════════════════════════════════════════════════════════════════
#  TYPOGRAPHY
# ════════════════════════════════════════════════════════════════
class Type:
    FAMILY = "SF Pro Display, -apple-system, Inter, Helvetica Neue, Arial"
    FAMILY_TEXT = "SF Pro Text, -apple-system, Inter, Helvetica Neue, Arial"

    HERO        = (42, QFont.Bold,     -0.022)
    TITLE       = (28, QFont.Bold,     -0.014)
    HEADLINE    = (16, QFont.DemiBold, -0.002)
    BODY        = (14, QFont.Normal,    0.001)
    CALLOUT     = (13, QFont.Normal,    0.004)
    BRAND       = (11, QFont.Bold,      0.180)
    MICRO       = (10, QFont.Medium,    0.030)

    @staticmethod
    def font(style: tuple, text: bool = False) -> QFont:
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
#  GLYPHS
# ════════════════════════════════════════════════════════════════
class Glyph:
    @staticmethod
    def lock(P, cx, cy, size, color):
        s = size / 24.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        # Shackle
        shackle = QPainterPath()
        shackle.moveTo(-5, -2)
        shackle.lineTo(-5, -7)
        shackle.cubicTo(-5, -12, 5, -12, 5, -7)
        shackle.lineTo(5, -2)
        P.setPen(QPen(color, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawPath(shackle)
        # Body
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(color))
        body = QPainterPath()
        body.addRoundedRect(QRectF(-7, -2, 14, 10), 2, 2)
        P.drawPath(body)
        P.restore()

    @staticmethod
    def shield(P, cx, cy, size, color):
        s = size / 32.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        shield = QPainterPath()
        shield.moveTo(0, -14)
        shield.cubicTo(-9, -14, -12, -11, -12, -6)
        shield.lineTo(-12, 4)
        shield.cubicTo(-12, 10, -6, 14, 0, 16)
        shield.cubicTo(6, 14, 12, 10, 12, 4)
        shield.lineTo(12, -6)
        shield.cubicTo(12, -11, 9, -14, 0, -14)
        shield.closeSubpath()
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(color))
        P.drawPath(shield)
        # Check
        check = QPainterPath()
        check.moveTo(-5, 0)
        check.lineTo(-1, 4)
        check.lineTo(5, -3)
        P.setPen(QPen(QColor(255, 255, 255), 2.5,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawPath(check)
        P.restore()

    @staticmethod
    def bolt(P, cx, cy, size, color):
        s = size / 32.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        bolt = QPainterPath()
        bolt.moveTo(3, -14)
        bolt.lineTo(-7, 2)
        bolt.lineTo(-1, 2)
        bolt.lineTo(-3, 14)
        bolt.lineTo(7, -2)
        bolt.lineTo(1, -2)
        bolt.lineTo(3, -14)
        bolt.closeSubpath()
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(color))
        P.drawPath(bolt)
        P.restore()

    @staticmethod
    def viewfinder(P, cx, cy, size, color):
        s = size / 32.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        P.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        L = 5; D = 11
        for sx, sy in [(-1,-1), (1,-1), (-1,1), (1,1)]:
            P.drawLine(QPointF(sx*D, sy*D), QPointF(sx*D, sy*(D-L)))
            P.drawLine(QPointF(sx*D, sy*D), QPointF(sx*(D-L), sy*D))
        P.setBrush(QBrush(color))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(0, 0), 1.5, 1.5)
        P.restore()

    @staticmethod
    def gear(P, cx, cy, size, color, rotation=0.0):
        """
        Production-grade gear icon.
        - 6 perfectly proportioned teeth
        - Smooth rounded corners on each tooth
        - Optical center hole (slightly larger appearance)
        - Anti-aliased path union
        - Inspired by SF Symbols 'gearshape.fill'
        """
        s = size / 24.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        P.rotate(rotation)

        # ── Geometry constants (carefully tuned) ──
        OUTER_R       = 11.0    # outer body radius
        INNER_R       = 7.2     # where teeth start
        TOOTH_LEN     = 2.8     # how far teeth extend beyond OUTER_R
        TOOTH_W_BASE  = 3.2     # tooth width at base
        TOOTH_W_TIP   = 2.4     # tooth width at tip (tapered)
        TOOTH_CORNER  = 0.8     # rounded corner radius on teeth
        CENTER_HOLE_R = 3.6     # center hole

        # ── Build gear via path union ──
        gear_path = QPainterPath()

        # Body circle
        gear_path.addEllipse(QPointF(0, 0), OUTER_R, OUTER_R)

        # 6 teeth — tapered with rounded corners
        for i in range(6):
            angle_deg = i * 60
            tx = QTransform()
            tx.rotate(angle_deg)

            # Trapezoidal tooth (wider at base, narrower at tip)
            tooth = QPainterPath()
            # Build as polygon path
            half_base = TOOTH_W_BASE / 2
            half_tip  = TOOTH_W_TIP / 2
            base_y    = -OUTER_R + 0.5      # slightly inside body
            tip_y     = -OUTER_R - TOOTH_LEN  # extends outward

            # Tooth polygon points
            poly = QPainterPath()
            poly.moveTo(-half_base, base_y)
            # Round corners via small arcs
            poly.lineTo(-half_tip, tip_y + TOOTH_CORNER)
            poly.quadTo(-half_tip, tip_y, -half_tip + TOOTH_CORNER, tip_y)
            poly.lineTo(half_tip - TOOTH_CORNER, tip_y)
            poly.quadTo(half_tip, tip_y, half_tip, tip_y + TOOTH_CORNER)
            poly.lineTo(half_base, base_y)
            poly.closeSubpath()

            gear_path = gear_path.united(tx.map(poly))

        # ── Subtract center hole ──
        center = QPainterPath()
        center.addEllipse(QPointF(0, 0), CENTER_HOLE_R, CENTER_HOLE_R)
        gear_final = gear_path.subtracted(center)

        # ── Render ──
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(color))
        P.drawPath(gear_final)

        P.restore()


    @staticmethod
    def chevron(P, cx, cy, size, color):
        s = size / 16.0
        P.save()
        P.translate(cx, cy)
        P.scale(s, s)
        P.setPen(QPen(color, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawLine(QPointF(-3, -5), QPointF(3, 0))
        P.drawLine(QPointF(3, 0), QPointF(-3, 5))
        P.restore()


# ════════════════════════════════════════════════════════════════
#  HERO MARK — Clean, balanced face icon
# ════════════════════════════════════════════════════════════════
class HeroMark:
    @staticmethod
    def render(P, cx, cy, size, palette, dark,
               scale=1.0, rotation=0.0, breath=0.0, blink=1.0,
               look_x=0.0, look_y=0.0, head_tilt=0.0):
        if scale < 0.01: return

        r = size * scale
        blue = palette.blue
        blue_hi = palette.blue_hi

        # ── Outer halos ──
        for layer_r, alpha in [(r*3.5, 0.04), (r*2.5, 0.08),
                                (r*1.8, 0.14), (r*1.4, 0.20)]:
            halo = QRadialGradient(cx, cy, layer_r)
            a = int(255 * alpha * scale)
            halo.setColorAt(0.0, QColor(blue.red(), blue.green(), blue.blue(), a))
            halo.setColorAt(0.6, QColor(blue.red(), blue.green(), blue.blue(), a // 3))
            halo.setColorAt(1.0, QColor(blue.red(), blue.green(), blue.blue(), 0))
            P.setBrush(QBrush(halo))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), layer_r, layer_r)

        # ── Rotating ring ──
        ring_r = r * 1.16
        conical = QConicalGradient(cx, cy, -rotation)
        for i in range(17):
            t = i / 16.0
            brightness = pow(0.5 + 0.5 * math.cos(t * 2 * math.pi), 2.0)
            a = int(255 * brightness * scale * 0.9)
            conical.setColorAt(t, QColor(blue_hi.red(), blue_hi.green(),
                                          blue_hi.blue(), a))
        # Soft glow ring
        P.setOpacity(0.45)
        P.setPen(QPen(QBrush(conical), 4.5, Qt.SolidLine, Qt.RoundCap))
        P.setBrush(Qt.NoBrush)
        P.drawEllipse(QPointF(cx, cy), ring_r, ring_r)
        P.setOpacity(1.0)
        # Sharp ring
        P.setPen(QPen(QBrush(conical), 2.0, Qt.SolidLine, Qt.RoundCap))
        P.drawEllipse(QPointF(cx, cy), ring_r, ring_r)

        # ── Sphere surface ──
        breath_r = r * (1.0 + breath * 0.012)
        surface = QRadialGradient(cx - r * 0.35, cy - r * 0.40, r * 2.2)
        if dark:
            surface.setColorAt(0.00, QColor(70, 78, 96))
            surface.setColorAt(0.40, QColor(40, 44, 56))
            surface.setColorAt(1.00, QColor(16, 18, 26))
        else:
            surface.setColorAt(0.00, QColor(255, 255, 255))
            surface.setColorAt(0.50, QColor(245, 247, 252))
            surface.setColorAt(1.00, QColor(220, 226, 238))

        P.setBrush(QBrush(surface))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), breath_r, breath_r)

        # ── Bottom inner shadow ──
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), breath_r, breath_r)
        P.setClipPath(clip)
        bottom = QRadialGradient(cx, cy + r * 0.7, r * 1.2)
        bottom.setColorAt(0.0, QColor(0, 0, 0, int(50 * scale)))
        bottom.setColorAt(1.0, QColor(0, 0, 0, 0))
        P.setBrush(QBrush(bottom))
        P.drawEllipse(QPointF(cx, cy + r * 0.4), r * 1.4, r * 0.8)
        P.setClipping(False)

        # ── Rim light ──
        rim = QRadialGradient(cx, cy, breath_r * 1.01)
        rim.setColorAt(0.92, QColor(255, 255, 255, 0))
        rim.setColorAt(0.97, QColor(255, 255, 255, int(60 * scale)))
        rim.setColorAt(1.00, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(rim))
        P.drawEllipse(QPointF(cx, cy), breath_r, breath_r)

        # ── LIVING face features with cursor awareness ──
        feature_color = QColor(palette.text)
        feature_color.setAlpha(int(255 * scale))

        # Apply head tilt (rotate around face center)
        P.save()
        P.translate(cx, cy)
        P.rotate(head_tilt * 57.3)  # rad to deg
        P.translate(-cx, -cy)

        # ── Eyes with gaze offset ──
        eye_y = cy - r * 0.20
        eye_dx = r * 0.32
        eye_base_h = r * 0.20
        eye_h = eye_base_h * blink
        eye_w = max(2.5, r * 0.06)

        # Gaze translation
        gaze_dx = look_x * r * 0.045
        gaze_dy = look_y * r * 0.035

        P.setPen(QPen(feature_color, eye_w * 1.8,
                      Qt.SolidLine, Qt.RoundCap))
        P.setBrush(Qt.NoBrush)

        # Left eye
        lx = cx - eye_dx + gaze_dx
        ly = eye_y + gaze_dy
        if blink > 0.05:
            P.drawLine(QPointF(lx, ly - eye_h/2),
                       QPointF(lx, ly + eye_h/2))
        else:
            P.drawLine(QPointF(lx - eye_w * 0.8, ly),
                       QPointF(lx + eye_w * 0.8, ly))

        # Right eye
        rx = cx + eye_dx + gaze_dx
        ry = eye_y + gaze_dy
        if blink > 0.05:
            P.drawLine(QPointF(rx, ry - eye_h/2),
                       QPointF(rx, ry + eye_h/2))
        else:
            P.drawLine(QPointF(rx - eye_w * 0.8, ry),
                       QPointF(rx + eye_w * 0.8, ry))

        # Smile
        smile_y = cy + r * 0.18
        smile_w = r * 0.46
        smile_h = r * 0.28
        P.setPen(QPen(feature_color, max(2.5, r * 0.05),
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawArc(QRectF(cx - smile_w/2, smile_y - smile_h/2,
                          smile_w, smile_h), 205 * 16, 130 * 16)

        P.restore()

        # ── Top specular ──
        spec = QRadialGradient(cx - r * 0.32, cy - r * 0.45, r * 0.5)
        spec.setColorAt(0.0, QColor(255, 255, 255, int(50 * scale)))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(spec))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx - r * 0.32, cy - r * 0.45),
                      r * 0.5, r * 0.42)


# ════════════════════════════════════════════════════════════════
#  SPLASH SCREEN
# ════════════════════════════════════════════════════════════════
class OnboardingSplash(QWidget):
    get_started_clicked = pyqtSignal()
    skip_clicked = pyqtSignal()
    settings_clicked = pyqtSignal()

    # PROPER CANVAS — no overlaps
    W = 540
    H = 760

    def __init__(self, appearance="auto", parent=None):
        super().__init__(parent)

        if appearance == "auto":
            appearance = "dark" if Env.is_dark() else "light"
        self.dark = (appearance == "dark")
        self.p = Palette.Dark if self.dark else Palette.Light

        self.t_start = time.time()
        self.t_last = self.t_start

        # Springs
        self.cta_scale = Spring(7.0)
        self.cta_lift = Spring(6.0)
        self.cta_glow = Spring(4.0)
        self.skip_alpha = Spring(4.0)
        self.skip_underline = Spring(5.0)
        self.gear_rotation = Spring(3.5)
        self.gear_scale = Spring(6.0)
        self.gear_alpha = Spring(4.0)
        self.card_springs = [
            {"scale": Spring(7.0), "lift": Spring(6.0),
             "icon_scale": Spring(8.0)} for _ in range(3)
        ]
        self.card_hovered = [False] * 3

        # Hero state — living face with cursor awareness
        self.hero_progress = 0.0
        self.hero_breath = 0.0
        self.hero_rotation = 0.0
        self.hero_blink = 1.0
        self._next_blink = time.time() + random.uniform(4.0, 7.0)
        self.eye_look_x = 0.0
        self.eye_look_y = 0.0
        self._look_target_x = 0.0
        self._look_target_y = 0.0
        self._next_look_t = time.time() + 2.5
        self.head_tilt = 0.0
        # Cursor tracking
        self.cursor_x = self.W / 2
        self.cursor_y = 190  # face center y
        self._last_cursor_time = 0

        # Choreography
        self.cg = {
            "pill":     (0.00, 0.55),
            "gear":     (0.30, 0.45),
            "hero":     (0.10, 1.00),
            "title":    (0.65, 0.55),
            "subtitle": (0.85, 0.55),
            "card_0":   (1.05, 0.55),
            "card_1":   (1.18, 0.55),
            "card_2":   (1.31, 0.55),
            "cta":      (1.55, 0.55),
            "skip":     (1.75, 0.50),
        }
        self.progress = {k: 0.0 for k in self.cg}

        # Interaction
        self.cta_hover = False
        self.cta_press = False
        self.skip_hover = False
        self.gear_hover = False

        self.setWindowTitle("Nova")
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        bg = self.p.bg_btm
        self.setStyleSheet(
            f"background-color: rgb({bg.red()},{bg.green()},{bg.blue()});")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

    def _tick(self):
        now = time.time()
        dt = min(now - self.t_last, 0.05)
        self.t_last = now
        t = now - self.t_start

        for key, (start, dur) in self.cg.items():
            if t >= start:
                local = min((t - start) / dur, 1.0)
                self.progress[key] = ease_out_quint(local)

        hs, hd = self.cg["hero"]
        if t >= hs:
            local = min((t - hs) / hd, 1.0)
            self.hero_progress = ease_out_quint(local)

        self.hero_breath = math.sin(t * 1.4) * 0.5
        self.hero_rotation = (t * 16) % 360

        # Blinking
        if now >= self._next_blink and self.hero_progress > 0.8:
            bt = now - self._next_blink
            if bt < 0.10: self.hero_blink = 1.0 - bt / 0.10
            elif bt < 0.18: self.hero_blink = 0.0
            elif bt < 0.30: self.hero_blink = (bt - 0.18) / 0.12
            else:
                self.hero_blink = 1.0
                self._next_blink = now + random.uniform(4.0, 7.0)

        # ── PROPER FACE TRACKING — Global cursor position ──
        if self.hero_progress > 0.9:
            # Get cursor position relative to FACE in screen coords
            face_cx_global = self.x() + self.W / 2
            face_cy_global = self.y() + 190  # hero y position

            # Global cursor position
            cursor_global = QCursor.pos()
            cgx, cgy = cursor_global.x(), cursor_global.y()

            # Vector from face to cursor (in screen pixels)
            dx = cgx - face_cx_global
            dy = cgy - face_cy_global
            dist = math.sqrt(dx*dx + dy*dy)

            # Effective tracking range (1.5x window width)
            max_dist = self.W * 1.5

            if dist > 8:
                # Influence based on distance (full effect within window range)
                influence = min(1.0, dist / max_dist)

                # Apply slight curve for natural feel
                # (eyes saturate quickly, not linear)
                influence_eased = pow(influence, 0.6)

                # Direction vector
                dir_x = dx / dist
                dir_y = dy / dist

                # Max gaze angles (in normalized -1 to +1)
                MAX_GAZE_X = 0.85   # horizontal (more freedom)
                MAX_GAZE_Y = 0.55   # vertical (less, anatomically)

                self._look_target_x = dir_x * MAX_GAZE_X * influence_eased
                self._look_target_y = dir_y * MAX_GAZE_Y * influence_eased

                # Head tilts slightly in direction of gaze (15% of eye amount)
                # Only horizontal tilt — head rarely tilts vertically for eye tracking
                target_tilt = dir_x * 0.10 * influence_eased
                self.head_tilt += (target_tilt - self.head_tilt) * dt * 4.0
            else:
                # Cursor directly on face — look forward
                self._look_target_x = 0
                self._look_target_y = 0
                self.head_tilt += (0 - self.head_tilt) * dt * 4.0

            # ── Physics-based eye movement ──
            # Eyes have high frequency (snap to position quickly)
            # but with slight overshoot for organic feel
            eye_response = 14.0   # Very responsive
            self.eye_look_x += (self._look_target_x - self.eye_look_x) * dt * eye_response
            self.eye_look_y += (self._look_target_y - self.eye_look_y) * dt * eye_response

        # Spring updates
        ts = 1.025 if self.cta_hover else 1.0
        tl = -3.0 if (self.cta_hover and not self.cta_press) else 0.0
        tg = 1.0 if self.cta_hover else 0.0
        if self.cta_press: ts = 0.98; tl = 1.0
        self.cta_scale.update(dt, ts)
        self.cta_lift.update(dt, tl)
        self.cta_glow.update(dt, tg)

        self.skip_underline.update(dt, 1.0 if self.skip_hover else 0.0)
        self.skip_alpha.update(dt, 1.0 if self.skip_hover else 0.75)

        self.gear_rotation.update(dt, 60.0 if self.gear_hover else 0.0)
        self.gear_scale.update(dt, 1.10 if self.gear_hover else 1.0)
        self.gear_alpha.update(dt, 1.0 if self.gear_hover else 0.85)

        for i, spr in enumerate(self.card_springs):
            spr["scale"].update(dt, 1.018 if self.card_hovered[i] else 1.0)
            spr["lift"].update(dt, -2.0 if self.card_hovered[i] else 0.0)
            spr["icon_scale"].update(dt, 1.10 if self.card_hovered[i] else 1.0)

        self.update()

    def paintEvent(self, _e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)
        P.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try: P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except: pass

        self._paint_bg(P)
        self._paint_pill(P)
        self._paint_gear(P)
        self._paint_hero(P)
        self._paint_text(P)
        self._paint_cards(P)
        self._paint_cta(P)
        self._paint_skip(P)

        P.end()

    def _paint_bg(self, P):
        bg = QLinearGradient(0, 0, 0, self.H)
        bg.setColorAt(0.0, self.p.bg_top)
        bg.setColorAt(0.5, self.p.bg_mid)
        bg.setColorAt(1.0, self.p.bg_btm)
        P.setBrush(QBrush(bg))
        P.setPen(Qt.NoPen)
        P.drawRect(self.rect())

        # Subtle vignette
        v = QRadialGradient(self.W/2, self.H/2, max(self.W, self.H) * 0.8)
        v.setColorAt(0.0, QColor(0, 0, 0, 0))
        v.setColorAt(0.7, QColor(0, 0, 0, 0))
        v.setColorAt(1.0, QColor(0, 0, 0, 60))
        P.setBrush(QBrush(v))
        P.drawRect(self.rect())

    def _paint_pill(self, P):
        prog = self.progress["pill"]
        if prog < 0.01: return

        w = 230 * (0.88 + 0.12 * prog)
        h = 36 * (0.88 + 0.12 * prog)
        x = (self.W - w) / 2
        y = 28
        r = h / 2

        P.setOpacity(prog)
        draw_glass_pill(P, x, y, w, h,
                        border_alpha=38,
                        fill_alpha=22,
                        shadow=True)

        if prog > 0.5:
            ca = (prog - 0.5) / 0.5
            P.setOpacity(ca * prog)
            cy_ = y + h / 2

            Glyph.lock(P, x + h * 0.65, cy_, 14,
                       QColor(255, 255, 255, 240))

            font = Type.font(Type.BRAND)
            P.setFont(font)
            P.setPen(QPen(QColor(255, 255, 255, 245)))
            fm = P.fontMetrics()
            text = "NOVA"
            tw = fm.horizontalAdvance(text)
            P.drawText(int(x + w/2 - tw/2), int(cy_ + 4), text)

            pulse = math.sin(time.time() * 2.5) * 0.5 + 0.5
            dot_x = x + w - h * 0.65
            blue = self.p.blue
            P.setBrush(QBrush(QColor(blue.red(), blue.green(),
                                       blue.blue(), int(28 + 45*pulse))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(dot_x, cy_), 7, 7)
            P.setBrush(QBrush(blue))
            P.drawEllipse(QPointF(dot_x, cy_), 3, 3)

        P.setOpacity(1.0)

    def _paint_gear(self, P):
        prog = self.progress["gear"]
        if prog < 0.01: return

        cx = self.W - 36
        cy = 46

        a = prog * self.gear_alpha.x
        P.setOpacity(a)

        if self.gear_hover:
            P.setBrush(QBrush(QColor(255, 255, 255, 18)))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), 20, 20)

        color = self.p.blue if self.gear_hover else self.p.text_dim
        scale = self.gear_scale.x if self.gear_scale.x > 0.01 else 1.0
        Glyph.gear(P, cx, cy, 18 * scale, color, rotation=self.gear_rotation.x)

        P.setOpacity(1.0)

    def _paint_hero(self, P):
        if self.hero_progress < 0.01: return

        cx = self.W / 2
        cy = 190
        size = 72

        HeroMark.render(P, cx, cy, size, self.p, self.dark,
                        scale=self.hero_progress,
                        rotation=self.hero_rotation,
                        breath=self.hero_breath,
                        blink=self.hero_blink,
                        look_x=self.eye_look_x,
                        look_y=self.eye_look_y,
                        head_tilt=self.head_tilt)

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

            text = "Face ID"
            fm = P.fontMetrics()
            tw = fm.horizontalAdvance(text)
            y = 335 + offset_y
            P.drawText(int(self.W/2 - tw/2), int(y), text)

        # Subtitle
        sp = self.progress["subtitle"]
        if sp > 0.01:
            offset_y = (1.0 - sp) * 10

            font = Type.font(Type.CALLOUT, text=True)
            P.setFont(font)
            color = QColor(self.p.text_dim)
            color.setAlpha(int(color.alpha() * sp))
            P.setPen(QPen(color))

            fm = P.fontMetrics()
            y = 368 + offset_y
            lines = ["A faster, more secure way",
                     "to unlock your device."]
            for line in lines:
                tw = fm.horizontalAdvance(line)
                P.drawText(int(self.W/2 - tw/2), int(y), line)
                y += 22

    def _paint_cards(self, P):
        cards = [
            ("Private",  "Your face data stays on this device",
             Glyph.shield, self.p.green),
            ("Instant",  "Unlocks in under 200 milliseconds",
             Glyph.bolt, self.p.blue),
            ("Precise",  "Accurate even in low light",
             Glyph.viewfinder, self.p.purple),
        ]

        card_w = 400
        card_h = 60
        card_x = (self.W - card_w) / 2
        gap = 10
        start_y = 440

        for i, (title, desc, icon_fn, accent) in enumerate(cards):
            prog = self.progress[f"card_{i}"]
            if prog < 0.01: continue

            offset_y = (1.0 - prog) * 16
            spr = self.card_springs[i]
            scale = spr["scale"].x if spr["scale"].x > 0.01 else 1.0
            lift = spr["lift"].x

            y = start_y + i * (card_h + gap) + offset_y + lift
            x = card_x

            P.save()
            P.setOpacity(prog)

            if scale != 1.0:
                P.translate(x + card_w/2, y + card_h/2)
                P.scale(scale, scale)
                P.translate(-(x + card_w/2), -(y + card_h/2))

            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, card_w, card_h), 14, 14)

            # Shadow
            for dy, alpha in [(2, 25), (5, 15), (10, 8)]:
                P.save()
                P.translate(0, dy)
                P.setBrush(QBrush(QColor(0, 0, 0, int(alpha * prog))))
                P.setPen(Qt.NoPen)
                P.drawPath(path)
                P.restore()

            # Card body — DEFINITELY VISIBLE
            card_color = self.p.card_hi if self.card_hovered[i] else self.p.card
            P.setBrush(QBrush(card_color))
            P.setPen(Qt.NoPen)
            P.drawPath(path)

            # Top sheen
            sheen = QLinearGradient(x, y, x, y + card_h * 0.5)
            sheen.setColorAt(0, QColor(255, 255, 255, 12))
            sheen.setColorAt(1, QColor(255, 255, 255, 0))
            P.setBrush(QBrush(sheen))
            P.drawPath(path)

            # Border
            P.setBrush(Qt.NoBrush)
            P.setPen(QPen(self.p.card_border, 0.8))
            P.drawPath(path)

            # Icon tile
            tile_size = 38
            tile_x = x + 14
            tile_y = y + (card_h - tile_size) / 2

            tile_path = QPainterPath()
            tile_path.addRoundedRect(
                QRectF(tile_x, tile_y, tile_size, tile_size), 11, 11)

            tile_grad = QLinearGradient(tile_x, tile_y, tile_x, tile_y + tile_size)
            tile_grad.setColorAt(0.0, QColor(accent.red(), accent.green(),
                                              accent.blue(), 100))
            tile_grad.setColorAt(1.0, QColor(accent.red(), accent.green(),
                                              accent.blue(), 45))
            P.setBrush(QBrush(tile_grad))
            P.setPen(Qt.NoPen)
            P.drawPath(tile_path)

            # Tile border
            P.setBrush(Qt.NoBrush)
            P.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(),
                                   100), 0.7))
            P.drawPath(tile_path)

            # Icon
            icon_scale = spr["icon_scale"].x if spr["icon_scale"].x > 0.01 else 1.0
            icon_fn(P, tile_x + tile_size/2, tile_y + tile_size/2,
                     22 * icon_scale, accent)

            # Text
            text_x = tile_x + tile_size + 16

            font_t = Type.font(Type.HEADLINE)
            P.setFont(font_t)
            P.setPen(QPen(self.p.text))
            P.drawText(int(text_x), int(y + 25), title)

            font_d = Type.font(Type.CALLOUT, text=True)
            P.setFont(font_d)
            P.setPen(QPen(self.p.text_dim))
            P.drawText(int(text_x), int(y + 44), desc)

            # Chevron on hover
            if self.card_hovered[i]:
                Glyph.chevron(P, x + card_w - 22, y + card_h/2,
                               10, self.p.text_quiet)

            P.setOpacity(1.0)
            P.restore()

    def _paint_cta(self, P):
        prog = self.progress["cta"]
        if prog < 0.01: return

        offset_y = (1.0 - prog) * 20
        scale = self.cta_scale.x if self.cta_scale.x > 0.01 else 1.0
        lift = self.cta_lift.x
        glow = self.cta_glow.x

        btn_w = 360 * scale
        btn_h = 54 * scale
        btn_x = (self.W - btn_w) / 2
        # PROPERLY POSITIONED — below cards (ends at ~660)
        btn_y = 660 + offset_y + lift

        P.setOpacity(prog)

        path = QPainterPath()
        path.addRoundedRect(QRectF(btn_x, btn_y, btn_w, btn_h),
                              btn_h/2, btn_h/2)

        # Colored shadow
        blue = self.p.blue
        for dy, alpha in [(3, 50), (8, 35), (16, 20)]:
            P.save()
            P.translate(0, dy)
            sa = int(alpha * (1 + glow * 0.4))
            if self.cta_press: sa = int(sa * 0.5)
            P.setBrush(QBrush(QColor(blue.red(), blue.green(), blue.blue(), sa)))
            P.setPen(Qt.NoPen)
            P.drawPath(path)
            P.restore()

        # Button gradient
        grad = QLinearGradient(btn_x, btn_y, btn_x, btn_y + btn_h)
        if self.cta_press:
            grad.setColorAt(0.0, QColor(max(0, blue.red() - 20),
                                          max(0, blue.green() - 15),
                                          max(0, blue.blue() - 10)))
            grad.setColorAt(1.0, QColor(max(0, blue.red() - 40),
                                          max(0, blue.green() - 28),
                                          max(0, blue.blue() - 18)))
        else:
            boost = 30 + int(glow * 12)
            grad.setColorAt(0.0, QColor(min(255, blue.red() + boost),
                                          min(255, blue.green() + boost - 5),
                                          min(255, blue.blue() + boost - 10)))
            grad.setColorAt(1.0, blue)

        P.setBrush(QBrush(grad))
        P.setPen(Qt.NoPen)
        P.drawPath(path)

        # Top scrim
        scrim = QLinearGradient(btn_x, btn_y, btn_x, btn_y + btn_h * 0.5)
        scrim.setColorAt(0, QColor(255, 255, 255, 70))
        scrim.setColorAt(1, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(scrim))
        P.drawPath(path)

        # Rim
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(255, 255, 255, 35), 0.6))
        P.drawPath(path)

        # Label
        font = Type.font(Type.HEADLINE)
        P.setFont(font)
        P.setPen(QPen(QColor(255, 255, 255)))
        text = "Continue"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        text_x = btn_x + btn_w/2 - tw/2 - 8
        text_y = btn_y + btn_h/2 + 5
        P.drawText(int(text_x), int(text_y), text)

        # Chevron
        chev_offset = 5 if self.cta_hover else 0
        Glyph.chevron(P, text_x + tw + 14 + chev_offset,
                       btn_y + btn_h/2, 13, QColor(255, 255, 255))

        P.setOpacity(1.0)

    def _paint_skip(self, P):
        prog = self.progress["skip"]
        if prog < 0.01: return

        opacity = prog * self.skip_alpha.x
        P.setOpacity(opacity)

        font = Type.font(Type.CALLOUT)
        P.setFont(font)

        color = self.p.blue if self.skip_hover else self.p.text_quiet
        P.setPen(QPen(color))

        text = "Not Now"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        # WELL BELOW CTA (CTA ends at 660+54=714, skip at 738)
        y = 745
        x = self.W/2 - tw/2
        P.drawText(int(x), int(y), text)

        underline = self.skip_underline.x
        if underline > 0.01:
            P.setPen(QPen(color, 1.2))
            line_y = y + 3
            half = (tw / 2) * underline
            P.drawLine(QPointF(self.W/2 - half, line_y),
                       QPointF(self.W/2 + half, line_y))

        P.setOpacity(1.0)

    # ────────────────────────────────────────────────────────
    def _in_cta(self, x, y):
        return (90 <= x <= 450) and (660 <= y <= 714)

    def _in_skip(self, x, y):
        return (220 <= x <= 320) and (732 <= y <= 758)

    def _in_gear(self, x, y):
        return abs(x - (self.W - 36)) <= 20 and abs(y - 46) <= 20

    def _in_card(self, x, y, idx):
        card_w = 400
        card_h = 60
        card_x = (self.W - card_w) / 2
        gap = 10
        start_y = 440
        cy = start_y + idx * (card_h + gap)
        return card_x <= x <= card_x + card_w and cy <= y <= cy + card_h

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        # Track cursor for face awareness
        self.cursor_x = x
        self.cursor_y = y
        self._last_cursor_time = time.time()

        self.cta_hover = self._in_cta(x, y)
        self.skip_hover = self._in_skip(x, y)
        self.gear_hover = self._in_gear(x, y)
        for i in range(3):
            self.card_hovered[i] = self._in_card(x, y, i)

        if (self.cta_hover or self.skip_hover or self.gear_hover or
            any(self.card_hovered)):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._in_cta(e.x(), e.y()):
            self.cta_press = True

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton: return
        x, y = e.x(), e.y()
        was = self.cta_press
        self.cta_press = False
        if was and self._in_cta(x, y):
            self.get_started_clicked.emit()
            QTimer.singleShot(120, self.close)
        elif self._in_skip(x, y):
            self.skip_clicked.emit()
            QTimer.singleShot(100, self.close)
        elif self._in_gear(x, y):
            self.settings_clicked.emit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.skip_clicked.emit()
            self.close()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.get_started_clicked.emit()
            QTimer.singleShot(120, self.close)


def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except: pass

    app = QApplication(sys.argv)
    splash = OnboardingSplash(appearance="auto")

    scr = app.primaryScreen().geometry()
    splash.move((scr.width() - splash.W) // 2,
                (scr.height() - splash.H) // 2)

    splash.get_started_clicked.connect(lambda: print("[Nova] Continue"))
    splash.skip_clicked.connect(lambda: print("[Nova] Not now"))
    splash.settings_clicked.connect(lambda: print("[Nova] Settings"))

    splash.show()
    splash.raise_()
    splash.activateWindow()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()