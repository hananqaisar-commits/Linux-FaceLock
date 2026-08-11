#!/usr/bin/env python3
"""
Liquid Glass renderer — pure QPainter, zero deps.
Import and call draw_glass_pill() / draw_glass_card() anywhere.
"""
from __future__ import annotations
import math
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore    import QRectF, QPointF, Qt
from PyQt5.QtGui     import (QPainter, QColor, QPen, QBrush,
                              QLinearGradient, QRadialGradient,
                              QPainterPath, QConicalGradient)


def draw_glass_pill(P: QPainter, x, y, w, h,
                    tint: QColor = None,
                    border_alpha: int = 40,
                    fill_alpha: int = 18,
                    shadow: bool = True,
                    glow: bool = False,
                    glow_color: QColor = None):
    """
    iPhone-style liquid glass pill.

    Layers (bottom to top):
      1. Drop shadow
      2. Base fill — ultra-thin translucent dark
      3. Refraction layer — subtle blue-shift at edges
      4. Top specular sheen — bright stripe across top third
      5. Inner rim highlight — thin bright edge all around
      6. Border — 0.5px translucent white stroke
      7. Optional glow halo underneath
    """
    r = h / 2
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)

    # ── 0. Glow halo (optional — for active/hover state) ──
    if glow and glow_color:
        for spread, alpha in [(14, 18), (9, 30), (5, 45)]:
            glow_path = QPainterPath()
            glow_path.addRoundedRect(
                QRectF(x - spread/2, y - spread/2 + 2,
                       w + spread, h + spread),
                r + spread/2, r + spread/2)
            gc = QColor(glow_color)
            gc.setAlpha(alpha)
            P.setBrush(QBrush(gc))
            P.setPen(Qt.NoPen)
            P.drawPath(glow_path)

    # ── 1. Drop shadow ──
    if shadow:
        for dy, blur, alpha in [(2, 6, 28), (5, 12, 18), (10, 20, 10)]:
            shadow_path = QPainterPath()
            shadow_path.addRoundedRect(
                QRectF(x - blur/2, y + dy - blur/2,
                       w + blur, h + blur),
                r + blur/2, r + blur/2)
            P.setBrush(QBrush(QColor(0, 0, 0, alpha)))
            P.setPen(Qt.NoPen)
            P.drawPath(shadow_path)

    # ── 2. Base fill — frosted dark glass ──
    base = QLinearGradient(x, y, x, y + h)
    if tint:
        base.setColorAt(0.0, QColor(
            min(255, tint.red()   + 8),
            min(255, tint.green() + 8),
            min(255, tint.blue()  + 12),
            fill_alpha + 8))
        base.setColorAt(1.0, QColor(
            tint.red(), tint.green(), tint.blue(),
            fill_alpha))
    else:
        base.setColorAt(0.0, QColor(255, 255, 255, fill_alpha + 6))
        base.setColorAt(1.0, QColor(200, 210, 230, fill_alpha))
    P.setBrush(QBrush(base))
    P.setPen(Qt.NoPen)
    P.drawPath(path)

    # ── 3. Refraction layer — subtle prismatic edge ──
    refract = QRadialGradient(x + w * 0.3, y + h * 0.2, w * 0.8)
    refract.setColorAt(0.0, QColor(120, 160, 255, 0))
    refract.setColorAt(0.7, QColor(100, 140, 255, 6))
    refract.setColorAt(1.0, QColor(80,  120, 255, 14))
    P.setBrush(QBrush(refract))
    P.drawPath(path)

    # ── 4. Top specular sheen — bright streak ──
    sheen_h = h * 0.42
    sheen_path = QPainterPath()
    sheen_path.addRoundedRect(QRectF(x + 1, y + 1, w - 2, sheen_h),
                               r - 1, r - 1)
    sheen_path = sheen_path.intersected(path)

    sheen = QLinearGradient(x, y, x, y + sheen_h)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 55))
    sheen.setColorAt(0.5, QColor(255, 255, 255, 18))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    P.setBrush(QBrush(sheen))
    P.drawPath(sheen_path)

    # ── 5. Inner rim highlight ──
    rim = QLinearGradient(x, y, x, y + h)
    rim.setColorAt(0.0,  QColor(255, 255, 255, border_alpha + 20))
    rim.setColorAt(0.08, QColor(255, 255, 255, border_alpha // 2))
    rim.setColorAt(0.92, QColor(255, 255, 255, 0))
    rim.setColorAt(1.0,  QColor(255, 255, 255, border_alpha // 3))
    P.setBrush(Qt.NoBrush)
    P.setPen(QPen(QBrush(rim), 0.8))
    inner = QPainterPath()
    inner.addRoundedRect(QRectF(x + 0.4, y + 0.4,
                                 w - 0.8, h - 0.8),
                          r - 0.4, r - 0.4)
    P.drawPath(inner)

    # ── 6. Outer border — crisp 0.5px ──
    P.setBrush(Qt.NoBrush)
    P.setPen(QPen(QColor(255, 255, 255, border_alpha), 0.5))
    P.drawPath(path)


def draw_glass_card(P: QPainter, x, y, w, h,
                    radius: float = 18,
                    tint: QColor = None,
                    hover: bool = False):
    """
    Frosted glass card — used for feature cards in splash.
    """
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), radius, radius)

    # Shadow
    for dy, blur, alpha in [(2, 5, 20), (6, 14, 12), (14, 28, 7)]:
        sp = QPainterPath()
        sp.addRoundedRect(
            QRectF(x - blur/2, y + dy - blur/2,
                   w + blur, h + blur),
            radius + blur/2, radius + blur/2)
        P.setBrush(QBrush(QColor(0, 0, 0, alpha)))
        P.setPen(Qt.NoPen)
        P.drawPath(sp)

    # Base
    hover_boost = 8 if hover else 0
    base = QLinearGradient(x, y, x, y + h)
    if tint:
        base.setColorAt(0.0, QColor(tint.red(), tint.green(),
                                     tint.blue(), 32 + hover_boost))
        base.setColorAt(1.0, QColor(tint.red(), tint.green(),
                                     tint.blue(), 18 + hover_boost))
    else:
        base.setColorAt(0.0, QColor(255, 255, 255, 22 + hover_boost))
        base.setColorAt(1.0, QColor(220, 228, 245, 12 + hover_boost))
    P.setBrush(QBrush(base))
    P.setPen(Qt.NoPen)
    P.drawPath(path)

    # Top sheen
    sheen = QLinearGradient(x, y, x, y + h * 0.4)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 28 + hover_boost))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    P.setBrush(QBrush(sheen))
    P.drawPath(path)

    # Side caustic — light bending at left edge
    caustic = QLinearGradient(x, y, x + w * 0.12, y)
    caustic.setColorAt(0.0, QColor(180, 200, 255, 20))
    caustic.setColorAt(1.0, QColor(180, 200, 255, 0))
    P.setBrush(QBrush(caustic))
    P.drawPath(path)

    # Border
    P.setBrush(Qt.NoBrush)
    P.setPen(QPen(QColor(255, 255, 255,
                          38 if hover else 26), 0.6))
    P.drawPath(path)

    # Hover inner glow
    if hover:
        inner_glow = QRadialGradient(x + w/2, y + h/2, max(w, h) * 0.6)
        inner_glow.setColorAt(0.0, QColor(255, 255, 255, 8))
        inner_glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(inner_glow))
        P.drawPath(path)


def draw_glass_button(P: QPainter, x, y, w, h,
                      color: QColor,
                      hover: bool = False,
                      pressed: bool = False):
    """
    Primary action button — solid color with glass overlay.
    """
    r    = h / 2
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)

    scale = 0.97 if pressed else (1.0 if not hover else 1.0)

    # Shadow
    if not pressed:
        for dy, blur, alpha in [(2, 4, 30), (5, 10, 18)]:
            sp = QPainterPath()
            sp.addRoundedRect(
                QRectF(x - blur/2, y + dy, w + blur, h + blur/2),
                r + blur/2, r + blur/2)
            sc = QColor(color)
            sc.setAlpha(alpha)
            P.setBrush(QBrush(sc))
            P.setPen(Qt.NoPen)
            P.drawPath(sp)

    # Base fill
    boost = -15 if pressed else (10 if hover else 0)
    base = QLinearGradient(x, y, x, y + h)
    base.setColorAt(0.0, QColor(
        min(255, color.red()   + 25 + boost),
        min(255, color.green() + 20 + boost),
        min(255, color.blue()  + 10 + boost)))
    base.setColorAt(1.0, QColor(
        max(0, color.red()   - 10 + boost),
        max(0, color.green() - 8  + boost),
        max(0, color.blue()  - 5  + boost)))
    P.setBrush(QBrush(base))
    P.setPen(Qt.NoPen)
    P.drawPath(path)

    # Glass sheen over button
    sheen = QLinearGradient(x, y, x, y + h * 0.5)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 45))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    P.setBrush(QBrush(sheen))
    P.drawPath(path)

    # Border
    P.setBrush(Qt.NoBrush)
    P.setPen(QPen(QColor(255, 255, 255, 50), 0.6))
    P.drawPath(path)
