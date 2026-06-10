#!/usr/bin/env python3
"""

# ── Auto Theme ───────────────────────────────────────────────
try:
    from nova_unlock.ui.theme_manager import get_theme
    _theme = get_theme()
    _theme.apply_to_app(__import__('PyQt5.QtWidgets', fromlist=['QApplication']).QApplication.instance() or __import__('PyQt5.QtWidgets', fromlist=['QApplication']).QApplication([]))
    _theme.start_watching(interval_ms=6000)
except Exception as _te:
    import logging; logging.getLogger(__name__).warning("Theme auto-apply failed: %s", _te)

╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   N O V A   ·   G R E E T E R                                    ║
║                                                                  ║
║   The first three seconds.                                       ║
║   A moment of stillness before everything begins.                ║
║                                                                  ║
║   Like turning on a Leica.                                       ║
║   Like opening a Patek Philippe.                                 ║
║   Like the first frame of a Kubrick film.                        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import math
import os
import sys
import time
import random
import subprocess
from typing import Optional

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont, QCursor,
                              QRadialGradient, QLinearGradient,
                              QConicalGradient, QBrush, QPainterPath,
                              QFontMetrics)


# ════════════════════════════════════════════════════════════════
#  ENV
# ════════════════════════════════════════════════════════════════
def detect_dark():
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
            capture_output=True, text=True, timeout=1.5)
        if "dark" in r.stdout.lower(): return True
        if "light" in r.stdout.lower(): return False
    except: pass
    try:
        r = subprocess.run(
            ["xfconf-query", "-c", "xsettings", "-p", "/Net/ThemeName"],
            capture_output=True, text=True, timeout=1.5)
        return "dark" in r.stdout.lower()
    except:
        return True


# ════════════════════════════════════════════════════════════════
#  MOTION
# ════════════════════════════════════════════════════════════════
def ease_out_quint(t):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 1 - pow(1 - t, 5)


def ease_in_out_cubic(t):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


def ease_in_quint(t):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return t * t * t * t * t


def ease_out_expo(t):
    if t <= 0: return 0.0
    if t >= 1: return 1.0
    return 1 - pow(2, -10 * t)


# ════════════════════════════════════════════════════════════════
#  GREETER
# ════════════════════════════════════════════════════════════════
class Greeter(QWidget):
    """
    The ceremonial reveal.
    Plays once at startup, then signals 'finished' to caller.
    """

    finished = pyqtSignal()

    W = 540
    H = 760

    def __init__(self, appearance="auto", duration=2.8, parent=None):
        super().__init__(parent)

        if appearance == "auto":
            self.dark = detect_dark()
        else:
            self.dark = (appearance == "dark")

        self.duration = duration

        # Timing
        self.t_start = time.time()
        self.t_last = self.t_start

        # Animation milestones (seconds)
        # Carefully choreographed
        self.tm = {
            "spark":        (0.30, 0.50),   # Single point of light
            "expand":       (0.55, 0.65),   # Expands to ring
            "ring_form":    (0.80, 0.80),   # Ring solidifies + rotates
            "hero":         (1.00, 1.00),   # Face materializes
            "wordmark":     (1.50, 0.55),   # "NOVA" fades in
            "tagline":      (1.85, 0.55),   # "Face ID" tagline
            "hold":         (2.30, 0.30),   # Brief stillness
            "dissolve":     (2.55, 0.45),   # Everything fades out
        }
        self.progress = {k: 0.0 for k in self.tm}

        self.global_opacity = 0.0
        self.spark_radius = 0.0
        self.ring_form_progress = 0.0
        self.ring_rotation = 0.0
        self.hero_materialize = 0.0
        self.hero_breath = 0.0
        self.particle_emission = 0.0

        # ── Living face state ──
        self.eye_blink = 1.0           # 1.0 = open, 0.0 = closed
        self.eye_look_x = 0.0          # -1 to +1 (left/right gaze)
        self.eye_look_y = 0.0          # -1 to +1 (up/down gaze)
        self.smile_intensity = 0.0     # 0 = neutral, 1 = full smile
        self.head_tilt = 0.0           # subtle tilt
        self._next_blink_t = time.time() + 3.5
        self._next_look_t = time.time() + 2.0
        self._look_target_x = 0.0
        self._look_target_y = 0.0
        self._smile_emerging = False

        # Particle system (subtle sparks during reveal)
        self.particles = []
        self.last_particle_time = 0

        # Window setup — FRAMELESS for cinematic feel
        self.setWindowTitle("Nova")
        self.setFixedSize(self.W, self.H)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        # ── Cursor tracking (for face awareness) ──
        self.setMouseTracking(True)
        self.cursor_x = self.W / 2     # default center
        self.cursor_y = self.H * 0.42  # default at face level
        self.cursor_active = False     # has cursor been moved yet?
        self._last_cursor_time = 0     # to detect idle

        bg = QColor(0, 0, 0) if self.dark else QColor(248, 250, 254)
        self.setStyleSheet(
            f"background-color: rgb({bg.red()},{bg.green()},{bg.blue()});"
        )

        # 60fps timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)

        # Auto-finish
        QTimer.singleShot(int(duration * 1000), self._emit_finished)

    def _emit_finished(self):
        self.finished.emit()
        QTimer.singleShot(50, self.close)

    # ────────────────────────────────────────────────────────
    # TICK
    # ────────────────────────────────────────────────────────
    def _tick(self):
        now = time.time()
        dt = min(now - self.t_last, 0.05)
        self.t_last = now
        t = now - self.t_start

        # Update milestone progresses
        for key, (start, dur) in self.tm.items():
            if t >= start:
                local = min((t - start) / dur, 1.0)
                if key == "dissolve":
                    self.progress[key] = ease_in_quint(local)
                elif key == "spark":
                    self.progress[key] = ease_out_expo(local)
                else:
                    self.progress[key] = ease_out_quint(local)

        # Global opacity (fade in initially, fade out at end)
        # Fade in quickly at start
        if t < 0.15:
            self.global_opacity = t / 0.15
        # Fade out at dissolve
        elif self.progress["dissolve"] > 0:
            self.global_opacity = 1.0 - self.progress["dissolve"]
        else:
            self.global_opacity = 1.0

        # Spark grows
        self.spark_radius = self.progress["spark"] * 14

        # Ring forms
        self.ring_form_progress = self.progress["ring_form"]

        # Ring rotates (subtle, slow)
        self.ring_rotation = (t * 20) % 360

        # Hero materializes
        self.hero_materialize = self.progress["hero"]

        # Hero breathing (after fully formed)
        if self.hero_materialize > 0.9:
            self.hero_breath = math.sin(t * 1.2) * 0.5

        # Particle emission during ring formation
        if 0.6 < t < 1.4:
            self.particle_emission = math.sin((t - 0.6) / 0.8 * math.pi)
            if now - self.last_particle_time > 0.04:
                self._spawn_particle()
                self.last_particle_time = now

        # Update particles
        self.particles = [p for p in self.particles if p['life'] < 1.0]
        for p in self.particles:
            p['life'] += dt / p['lifetime']
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            p['vy'] += 30 * dt  # gravity

        # ── LIVING FACE — Global cursor tracking ──
        if self.hero_materialize > 0.8:
            # Blinking
            if now >= self._next_blink_t:
                bt = now - self._next_blink_t
                if bt < 0.08:
                    self.eye_blink = 1.0 - (bt / 0.08)
                elif bt < 0.16:
                    self.eye_blink = 0.0
                elif bt < 0.28:
                    self.eye_blink = (bt - 0.16) / 0.12
                else:
                    self.eye_blink = 1.0
                    self._next_blink_t = now + random.uniform(3.0, 6.0)
            else:
                self.eye_blink = 1.0

            # Face center in global screen coordinates
            face_cx_global = self.x() + self.W / 2
            face_cy_global = self.y() + self.H * 0.42

            # Global cursor
            cursor_global = QCursor.pos()
            cgx, cgy = cursor_global.x(), cursor_global.y()

            dx = cgx - face_cx_global
            dy = cgy - face_cy_global
            dist = math.sqrt(dx*dx + dy*dy)
            max_dist = self.W * 1.5

            if dist > 8:
                influence = min(1.0, dist / max_dist)
                influence_eased = pow(influence, 0.6)
                dir_x = dx / dist
                dir_y = dy / dist

                MAX_GAZE_X = 0.85
                MAX_GAZE_Y = 0.55

                self._look_target_x = dir_x * MAX_GAZE_X * influence_eased
                self._look_target_y = dir_y * MAX_GAZE_Y * influence_eased

                target_tilt = dir_x * 0.10 * influence_eased
                self.head_tilt += (target_tilt - self.head_tilt) * dt * 4.0
            else:
                self._look_target_x = 0
                self._look_target_y = 0
                self.head_tilt += (0 - self.head_tilt) * dt * 4.0

            # Physics-based response
            self.eye_look_x += (self._look_target_x - self.eye_look_x) * dt * 14.0
            self.eye_look_y += (self._look_target_y - self.eye_look_y) * dt * 14.0

            # Gentle smile (emerges over time)
            if self.smile_intensity < 1.0:
                self.smile_intensity += dt * 0.4
            self.smile_intensity = min(1.0, self.smile_intensity)

        self.update()

    def _spawn_particle(self):
        cx = self.W / 2
        cy = self.H * 0.42
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(60, 140)
        self.particles.append({
            'x': cx + math.cos(angle) * 40,
            'y': cy + math.sin(angle) * 40,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed * 0.5,
            'life': 0.0,
            'lifetime': random.uniform(0.8, 1.4),
            'size': random.uniform(1.0, 2.5),
        })

    # ────────────────────────────────────────────────────────
    # PAINT
    # ────────────────────────────────────────────────────────
    def paintEvent(self, _e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)
        P.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try: P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except: pass

        # Background
        self._paint_bg(P)

        # Apply global opacity for fade
        P.setOpacity(self.global_opacity)

        # Center of action
        cx = self.W / 2
        cy = self.H * 0.42

        # Layer by layer reveal
        self._paint_spark(P, cx, cy)
        self._paint_ring(P, cx, cy)
        self._paint_particles(P)
        self._paint_hero(P, cx, cy)
        self._paint_wordmark(P)
        self._paint_tagline(P)

        P.setOpacity(1.0)
        P.end()

    # ────────────────────────────────────────────────────────
    # BACKGROUND
    # ────────────────────────────────────────────────────────
    def _paint_bg(self, P):
        if self.dark:
            bg = QRadialGradient(self.W/2, self.H * 0.42, self.W * 0.9)
            bg.setColorAt(0.0, QColor(15, 18, 28))
            bg.setColorAt(0.5, QColor(5, 6, 10))
            bg.setColorAt(1.0, QColor(0, 0, 0))
        else:
            bg = QRadialGradient(self.W/2, self.H * 0.42, self.W * 0.9)
            bg.setColorAt(0.0, QColor(253, 254, 255))
            bg.setColorAt(0.7, QColor(245, 248, 252))
            bg.setColorAt(1.0, QColor(235, 240, 248))

        P.setBrush(QBrush(bg))
        P.setPen(Qt.NoPen)
        P.drawRect(self.rect())

        # Subtle vignette
        v = QRadialGradient(self.W/2, self.H/2, max(self.W, self.H) * 0.7)
        v.setColorAt(0.0, QColor(0, 0, 0, 0))
        v.setColorAt(0.7, QColor(0, 0, 0, 0))
        v.setColorAt(1.0, QColor(0, 0, 0, 80))
        P.setBrush(QBrush(v))
        P.drawRect(self.rect())

    # ────────────────────────────────────────────────────────
    # SPARK — The first point of light
    # ────────────────────────────────────────────────────────
    def _paint_spark(self, P, cx, cy):
        sp = self.progress["spark"]
        if sp < 0.01: return
        # Fade out as ring takes over
        fade_out = 1.0 - self.ring_form_progress
        if fade_out < 0.01: return

        blue = QColor(10, 132, 255)

        # Outer glow halos
        for layer_r, alpha in [(40, 0.06), (25, 0.12),
                                (15, 0.22), (8, 0.40)]:
            r = layer_r * sp
            g = QRadialGradient(cx, cy, r)
            a = int(255 * alpha * fade_out)
            g.setColorAt(0.0, QColor(blue.red(), blue.green(), blue.blue(), a))
            g.setColorAt(0.6, QColor(blue.red(), blue.green(), blue.blue(), a // 3))
            g.setColorAt(1.0, QColor(blue.red(), blue.green(), blue.blue(), 0))
            P.setBrush(QBrush(g))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), r, r)

        # Core point
        core_r = self.spark_radius * fade_out
        if core_r > 0.5:
            # White center
            P.setBrush(QBrush(QColor(255, 255, 255, int(255 * fade_out))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), core_r, core_r)

    # ────────────────────────────────────────────────────────
    # RING — Expands and forms
    # ────────────────────────────────────────────────────────
    def _paint_ring(self, P, cx, cy):
        ex = self.progress["expand"]
        rf = self.ring_form_progress
        if ex < 0.01: return

        blue = QColor(10, 132, 255)
        blue_hi = QColor(64, 156, 255)

        # Target ring radius
        target_r = 95

        # Current ring radius (animates from spark to full)
        current_r = self.spark_radius + (target_r - self.spark_radius) * ex

        # Ring opacity (fades in)
        ring_alpha = ex

        # ── Outer glow ──
        for layer_mult, alpha in [(1.6, 0.08), (1.3, 0.18), (1.15, 0.30)]:
            layer_r = current_r * layer_mult
            g = QRadialGradient(cx, cy, layer_r)
            a = int(255 * alpha * ring_alpha)
            g.setColorAt(0.0, QColor(blue.red(), blue.green(), blue.blue(), 0))
            g.setColorAt(0.85, QColor(blue.red(), blue.green(), blue.blue(), a))
            g.setColorAt(1.0, QColor(blue.red(), blue.green(), blue.blue(), 0))
            P.setBrush(QBrush(g))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), layer_r, layer_r)

        # ── Main ring with conical sweep ──
        # Once formed, use conical gradient
        if rf > 0.3:
            conical = QConicalGradient(cx, cy, -self.ring_rotation)
            for i in range(17):
                t = i / 16.0
                brightness = pow(0.5 + 0.5 * math.cos(t * 2 * math.pi), 2.0)
                a = int(255 * brightness * ring_alpha * 0.9)
                conical.setColorAt(t, QColor(blue_hi.red(), blue_hi.green(),
                                              blue_hi.blue(), a))

            # Soft glow ring
            P.setOpacity(self.global_opacity * 0.5)
            P.setPen(QPen(QBrush(conical), 5.0, Qt.SolidLine, Qt.RoundCap))
            P.setBrush(Qt.NoBrush)
            P.drawEllipse(QPointF(cx, cy), current_r, current_r)
            P.setOpacity(self.global_opacity)

            # Sharp inner ring
            P.setPen(QPen(QBrush(conical), 2.0, Qt.SolidLine, Qt.RoundCap))
            P.drawEllipse(QPointF(cx, cy), current_r, current_r)
        else:
            # Before fully formed — simple stroke
            P.setBrush(Qt.NoBrush)
            P.setPen(QPen(QColor(blue.red(), blue.green(), blue.blue(),
                                   int(220 * ring_alpha)),
                          2.0, Qt.SolidLine, Qt.RoundCap))
            P.drawEllipse(QPointF(cx, cy), current_r, current_r)

    # ────────────────────────────────────────────────────────
    # PARTICLES — Subtle sparks during reveal
    # ────────────────────────────────────────────────────────
    def _paint_particles(self, P):
        if not self.particles: return

        for p in self.particles:
            life_t = p['life']
            if life_t >= 1.0: continue

            # Fade out
            alpha = int(255 * (1 - life_t) * 0.7)
            size = p['size'] * (1 - life_t * 0.5)

            # White-blue glow
            P.setBrush(QBrush(QColor(120, 180, 255, alpha // 3)))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(p['x'], p['y']), size * 2, size * 2)

            P.setBrush(QBrush(QColor(220, 240, 255, alpha)))
            P.drawEllipse(QPointF(p['x'], p['y']), size, size)

    # ────────────────────────────────────────────────────────
    # HERO — Face materializes inside ring
    # ────────────────────────────────────────────────────────
    def _paint_hero(self, P, cx, cy):
        m = self.hero_materialize
        if m < 0.01: return

        r = 75 * m * (1.0 + self.hero_breath * 0.012)

        # Inner sphere surface
        surface = QRadialGradient(cx - r * 0.35, cy - r * 0.40, r * 2.2)
        if self.dark:
            surface.setColorAt(0.00, QColor(70, 78, 96))
            surface.setColorAt(0.40, QColor(40, 44, 56))
            surface.setColorAt(1.00, QColor(16, 18, 26))
        else:
            surface.setColorAt(0.00, QColor(255, 255, 255))
            surface.setColorAt(0.50, QColor(245, 247, 252))
            surface.setColorAt(1.00, QColor(220, 226, 238))

        P.setBrush(QBrush(surface))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r, r)

        # Bottom shadow
        if m > 0.3:
            clip = QPainterPath()
            clip.addEllipse(QPointF(cx, cy), r, r)
            P.setClipPath(clip)
            bs = QRadialGradient(cx, cy + r * 0.7, r * 1.2)
            bs.setColorAt(0.0, QColor(0, 0, 0, int(50 * m)))
            bs.setColorAt(1.0, QColor(0, 0, 0, 0))
            P.setBrush(QBrush(bs))
            P.drawEllipse(QPointF(cx, cy + r * 0.4), r * 1.4, r * 0.8)
            P.setClipping(False)

        # Rim light
        if m > 0.4:
            rim = QRadialGradient(cx, cy, r * 1.01)
            rim.setColorAt(0.92, QColor(255, 255, 255, 0))
            rim.setColorAt(0.97, QColor(255, 255, 255, int(60 * m)))
            rim.setColorAt(1.00, QColor(255, 255, 255, 0))
            P.setBrush(QBrush(rim))
            P.drawEllipse(QPointF(cx, cy), r, r)

        # ── LIVING face features ──
        if m > 0.6:
            feature_alpha = (m - 0.6) / 0.4
            color = QColor(255, 255, 255) if self.dark else QColor(0, 0, 0)
            color.setAlpha(int(255 * feature_alpha))

            # Apply subtle head tilt
            P.save()
            P.translate(cx, cy)
            P.rotate(self.head_tilt * 57.3)  # rad to deg
            P.translate(-cx, -cy)

            # ── Eyes (with blink + gaze) ──
            eye_y = cy - r * 0.20
            eye_dx = r * 0.32
            eye_base_h = r * 0.20
            eye_h = eye_base_h * self.eye_blink  # blink scales height
            eye_w = max(2.5, r * 0.06)

            # Gaze offset (eyes shift slightly based on look direction)
            gaze_x = self.eye_look_x * r * 0.04
            gaze_y = self.eye_look_y * r * 0.03

            P.setPen(QPen(color, eye_w * 1.8, Qt.SolidLine, Qt.RoundCap))
            P.setBrush(Qt.NoBrush)

            # Left eye
            lx = cx - eye_dx + gaze_x
            ly = eye_y + gaze_y
            if self.eye_blink > 0.05:
                P.drawLine(QPointF(lx, ly - eye_h/2),
                           QPointF(lx, ly + eye_h/2))
            else:
                # Closed eye — horizontal line
                P.drawLine(QPointF(lx - eye_w * 0.8, ly),
                           QPointF(lx + eye_w * 0.8, ly))

            # Right eye
            rx = cx + eye_dx + gaze_x
            ry = eye_y + gaze_y
            if self.eye_blink > 0.05:
                P.drawLine(QPointF(rx, ry - eye_h/2),
                           QPointF(rx, ry + eye_h/2))
            else:
                P.drawLine(QPointF(rx - eye_w * 0.8, ry),
                           QPointF(rx + eye_w * 0.8, ry))

            # ── Smile (intensity-based) ──
            si = self.smile_intensity
            smile_y = cy + r * (0.16 + si * 0.02)
            smile_w = r * (0.40 + si * 0.06)
            smile_h = r * (0.22 + si * 0.06)
            P.setPen(QPen(color, max(2.5, r * 0.05),
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.setBrush(Qt.NoBrush)

            # Smile arc opens more as intensity grows
            arc_start = 205 * 16
            arc_span = int((100 + si * 30) * 16)
            P.drawArc(QRectF(cx - smile_w/2, smile_y - smile_h/2,
                              smile_w, smile_h), arc_start, arc_span)

            P.restore()

        # Specular highlight
        if m > 0.5:
            spec = QRadialGradient(cx - r * 0.32, cy - r * 0.45, r * 0.5)
            spec.setColorAt(0.0, QColor(255, 255, 255, int(50 * m)))
            spec.setColorAt(1.0, QColor(255, 255, 255, 0))
            P.setBrush(QBrush(spec))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx - r * 0.32, cy - r * 0.45),
                          r * 0.5, r * 0.42)

    # ────────────────────────────────────────────────────────
    # WORDMARK — "NOVA"
    # ────────────────────────────────────────────────────────
    def _paint_wordmark(self, P):
        wp = self.progress["wordmark"]
        if wp < 0.01: return

        # Slide up subtly + fade
        offset_y = (1.0 - wp) * 12

        font = QFont("SF Pro Display, -apple-system, Inter, Helvetica Neue, Arial")
        font.setPixelSize(38)
        font.setWeight(QFont.Bold)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 5.0)  # Wide tracking
        P.setFont(font)

        color = QColor(255, 255, 255) if self.dark else QColor(10, 14, 22)
        color.setAlpha(int(255 * wp))
        P.setPen(QPen(color))

        text = "NOVA"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        y = self.H * 0.42 + 145 + offset_y
        P.drawText(int(self.W/2 - tw/2), int(y), text)

    # ────────────────────────────────────────────────────────
    # TAGLINE — "Face ID"
    # ────────────────────────────────────────────────────────
    def _paint_tagline(self, P):
        tp = self.progress["tagline"]
        if tp < 0.01: return

        offset_y = (1.0 - tp) * 8

        font = QFont("SF Pro Text, -apple-system, Inter, Helvetica Neue, Arial")
        font.setPixelSize(14)
        font.setWeight(QFont.Medium)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2.5)
        P.setFont(font)

        color_dim = QColor(170, 180, 200) if self.dark else QColor(80, 90, 110)
        color_dim.setAlpha(int(255 * tp * 0.85))
        P.setPen(QPen(color_dim))

        text = "FACE ID"
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(text)
        y = self.H * 0.42 + 178 + offset_y
        P.drawText(int(self.W/2 - tw/2), int(y), text)

    def mouseMoveEvent(self, e):
        """Track cursor for face awareness"""
        self.cursor_x = e.x()
        self.cursor_y = e.y()
        self.cursor_active = True
        self._last_cursor_time = time.time()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.finished.emit()
            self.close()


# ════════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ════════════════════════════════════════════════════════════════
def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except: pass

    app = QApplication(sys.argv)

    greeter = Greeter(appearance="auto", duration=2.8)

    scr = app.primaryScreen().geometry()
    greeter.move((scr.width() - greeter.W) // 2,
                  (scr.height() - greeter.H) // 2)

    def on_done():
        print("[Nova] Greeter complete — ready for splash")
        QTimer.singleShot(200, app.quit)

    greeter.finished.connect(on_done)

    greeter.show()
    greeter.raise_()
    greeter.activateWindow()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
