#!/usr/bin/env python3
"""
Nova License Dialog — shown on trial expiry.
Progressive delay + purchase reminder.
"""
from __future__ import annotations

import sys
import time
import subprocess
import platform
from pathlib import Path

from PyQt5.QtCore    import Qt, QTimer, QRectF, pyqtSignal
from PyQt5.QtGui     import (QPainter, QColor, QFont, QPen,
                              QBrush, QLinearGradient, QPainterPath,
                              QGuiApplication)
from PyQt5.QtWidgets import QApplication, QWidget


PURCHASE_EMAIL = "hananqaisar316@gmail.com"
DEFAULT_DELAY  = 3.0    # Base seconds user must wait


def _copy_to_clipboard(text: str) -> bool:
    """Cross-platform clipboard copy."""
    try:
        cb = QGuiApplication.clipboard()
        cb.setText(text)
        return True
    except Exception:
        return False


def _open_email(hw_id: str) -> bool:
    """Open email client with pre-filled purchase request."""
    subject = "NovaUnlock License Purchase Request"
    body    = (f"Hi,\n\n"
               f"I would like to purchase a NovaUnlock license.\n\n"
               f"My Hardware ID: {hw_id}\n\n"
               f"Please send me payment details.\n\n"
               f"Thanks.")

    mailto = (f"mailto:{PURCHASE_EMAIL}?"
              f"subject={subject.replace(' ', '%20')}&"
              f"body={body.replace(chr(10), '%0A').replace(' ', '%20')}")

    try:
        system = platform.system().lower()
        if system == "linux":
            subprocess.Popen(["xdg-open", mailto],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        elif system == "darwin":
            subprocess.Popen(["open", mailto],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        elif system == "windows":
            import os
            os.startfile(mailto)
        return True
    except Exception:
        return False


class LicenseDialog(QWidget):
    """
    Purchase reminder dialog with progressive delay.
    User must wait N seconds before "Continue" enables.

    Days over expiry → longer delay (3s → 15s over 30 days).
    """

    continued = pyqtSignal()

    W = 520
    H = 380

    def __init__(self,
                 hw_id: str,
                 days_expired: int = 0,
                 status_text: str = "Trial Expired",
                 parent=None):
        super().__init__(parent,
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.X11BypassWindowManagerHint)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.hw_id        = hw_id
        self.days_expired = max(0, days_expired)
        self.status_text  = status_text

        # Progressive delay: 3s base, +0.4s per expired day, cap 15s
        self.delay_total  = min(15.0, DEFAULT_DELAY + self.days_expired * 0.4)
        self.t_start      = time.time()

        # Hover states
        self.hover_purchase = False
        self.hover_copy     = False
        self.hover_continue = False
        self.hover_email    = False

        # Position center of primary screen
        self.setFixedSize(self.W, self.H)
        scr = QApplication.primaryScreen().geometry()
        self.move((scr.width()  - self.W) // 2,
                  (scr.height() - self.H) // 2)

        self.setMouseTracking(True)

        # Tick for countdown redraw
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self.update)
        self._tmr.start(50)

    def _elapsed(self) -> float:
        return time.time() - self.t_start

    def _seconds_left(self) -> float:
        return max(0.0, self.delay_total - self._elapsed())

    def _can_continue(self) -> bool:
        return self._seconds_left() <= 0.01

    # ────────────────────────────────────────────────
    def paintEvent(self, _):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)
        try: P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except Exception: pass

        W, H = self.W, self.H
        r    = 22

        # ── Card background (dark glass) ──
        card = QPainterPath()
        card.addRoundedRect(QRectF(0, 0, W, H), r, r)

        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0.0, QColor(28, 28, 32, 250))
        bg.setColorAt(1.0, QColor(18, 18, 22, 250))
        P.setBrush(QBrush(bg))
        P.setPen(Qt.NoPen)
        P.drawPath(card)

        # ── Border ──
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(255, 255, 255, 30), 1))
        P.drawPath(card)

        # ── Warning icon (orange lock) ──
        icon_y = 34
        P.setBrush(QBrush(QColor(255, 149, 10, 40)))
        P.setPen(Qt.NoPen)
        P.drawEllipse(int(W/2 - 26), icon_y, 52, 52)
        P.setBrush(QBrush(QColor(255, 149, 10, 255)))
        P.drawEllipse(int(W/2 - 18), icon_y + 8, 36, 36)
        # Lock shape inside
        P.setPen(QPen(QColor(255, 255, 255), 2.4,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        # Shackle
        lock_cx = W / 2
        lock_cy = icon_y + 26
        shackle = QPainterPath()
        shackle.moveTo(lock_cx - 6, lock_cy - 2)
        shackle.lineTo(lock_cx - 6, lock_cy - 7)
        shackle.cubicTo(lock_cx - 6, lock_cy - 13,
                        lock_cx + 6, lock_cy - 13,
                        lock_cx + 6, lock_cy - 7)
        shackle.lineTo(lock_cx + 6, lock_cy - 2)
        P.drawPath(shackle)
        # Body
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(QColor(255, 255, 255)))
        body = QPainterPath()
        body.addRoundedRect(QRectF(lock_cx - 8, lock_cy - 2, 16, 11), 2, 2)
        P.drawPath(body)

        # ── Title ──
        f_title = QFont("SF Pro Display, Inter, Arial")
        f_title.setPixelSize(22)
        f_title.setWeight(QFont.Bold)
        P.setFont(f_title)
        P.setPen(QPen(QColor(255, 255, 255)))
        title = self.status_text
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(title)
        P.drawText(int(W/2 - tw/2), icon_y + 90, title)

        # ── Message ──
        f_msg = QFont("SF Pro Text, Inter, Arial")
        f_msg.setPixelSize(13)
        P.setFont(f_msg)
        P.setPen(QPen(QColor(190, 195, 210)))

        if self.days_expired > 0:
            msg = f"Your trial expired {self.days_expired} day(s) ago."
        else:
            msg = "Your 30-day trial has ended."
        fm = P.fontMetrics()
        mw = fm.horizontalAdvance(msg)
        P.drawText(int(W/2 - mw/2), icon_y + 116, msg)

        msg2 = "Purchase a license to remove reminders."
        mw2 = fm.horizontalAdvance(msg2)
        P.drawText(int(W/2 - mw2/2), icon_y + 134, msg2)

        # ── Hardware ID box ──
        hw_box_y = icon_y + 156
        hw_box_h = 46
        hw_box_w = W - 60
        hw_box_x = 30

        hw_bg = QPainterPath()
        hw_bg.addRoundedRect(
            QRectF(hw_box_x, hw_box_y, hw_box_w, hw_box_h),
            10, 10)
        P.setBrush(QBrush(QColor(255, 255, 255, 12)))
        P.setPen(QPen(QColor(255, 255, 255, 25), 1))
        P.drawPath(hw_bg)

        # HW ID label
        f_lbl = QFont("SF Pro Text, Inter, Arial")
        f_lbl.setPixelSize(10)
        f_lbl.setWeight(QFont.Medium)
        P.setFont(f_lbl)
        P.setPen(QPen(QColor(155, 160, 175)))
        P.drawText(hw_box_x + 14, hw_box_y + 15, "HARDWARE ID")

        # HW ID value (monospace)
        f_hw = QFont("Menlo, Consolas, Monaco, monospace")
        f_hw.setPixelSize(14)
        f_hw.setWeight(QFont.Bold)
        P.setFont(f_hw)
        P.setPen(QPen(QColor(255, 255, 255)))
        P.drawText(hw_box_x + 14, hw_box_y + 34, self.hw_id)

        # Copy button (right side of HW box)
        copy_x = hw_box_x + hw_box_w - 68
        copy_y = hw_box_y + 10
        copy_w = 54
        copy_h = 26
        self._copy_rect = (copy_x, copy_y, copy_w, copy_h)

        copy_grad = QLinearGradient(copy_x, copy_y, copy_x, copy_y + copy_h)
        if self.hover_copy:
            copy_grad.setColorAt(0.0, QColor(60, 160, 255))
            copy_grad.setColorAt(1.0, QColor(0,  120, 235))
        else:
            copy_grad.setColorAt(0.0, QColor(30, 140, 255))
            copy_grad.setColorAt(1.0, QColor(0,  110, 225))
        P.setBrush(QBrush(copy_grad))
        P.setPen(Qt.NoPen)
        copy_path = QPainterPath()
        copy_path.addRoundedRect(
            QRectF(copy_x, copy_y, copy_w, copy_h), 6, 6)
        P.drawPath(copy_path)

        # Gloss
        cgloss = QLinearGradient(copy_x, copy_y, copy_x, copy_y + copy_h * 0.5)
        cgloss.setColorAt(0.0, QColor(255, 255, 255, 40))
        cgloss.setColorAt(1.0, QColor(255, 255, 255,  0))
        P.setBrush(QBrush(cgloss))
        P.drawPath(copy_path)

        f_btn = QFont("SF Pro Text, Inter, Arial")
        f_btn.setPixelSize(11)
        f_btn.setWeight(QFont.DemiBold)
        P.setFont(f_btn)
        P.setPen(QPen(QColor(255, 255, 255)))
        fm = P.fontMetrics()
        ct = "Copy"
        cw = fm.horizontalAdvance(ct)
        P.drawText(int(copy_x + copy_w/2 - cw/2),
                   int(copy_y + copy_h/2 + 4), ct)

        # ── Buttons row ──
        btn_y   = H - 88
        btn_h   = 44
        gap     = 12

        # Purchase (blue, primary)
        p_w = 200
        p_x = int(W/2 - p_w - gap/2)
        self._purchase_rect = (p_x, btn_y, p_w, btn_h)

        # Hover lift effect
        p_y_offset = -1 if self.hover_purchase else 0
        p_actual_y = btn_y + p_y_offset

        # Hover shadow
        if self.hover_purchase:
            sh = QPainterPath()
            sh.addRoundedRect(
                QRectF(p_x, btn_y + 3, p_w, btn_h), 10, 10)
            P.setBrush(QBrush(QColor(10, 132, 255, 60)))
            P.setPen(Qt.NoPen)
            P.drawPath(sh)

        # Button gradient
        p_grad = QLinearGradient(p_x, p_actual_y, p_x, p_actual_y + btn_h)
        if self.hover_purchase:
            p_grad.setColorAt(0.0, QColor(60, 160, 255))
            p_grad.setColorAt(1.0, QColor(0,  120, 255))
        else:
            p_grad.setColorAt(0.0, QColor(30, 140, 255))
            p_grad.setColorAt(1.0, QColor(0,  110, 235))
        P.setBrush(QBrush(p_grad))
        P.setPen(Qt.NoPen)
        p_path = QPainterPath()
        p_path.addRoundedRect(
            QRectF(p_x, p_actual_y, p_w, btn_h), 10, 10)
        P.drawPath(p_path)

        # Subtle top gloss
        gloss = QLinearGradient(p_x, p_actual_y, p_x, p_actual_y + btn_h * 0.5)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 30))
        gloss.setColorAt(1.0, QColor(255, 255, 255,  0))
        P.setBrush(QBrush(gloss))
        P.drawPath(p_path)

        f_btn = QFont("SF Pro Text, Inter, Arial")
        f_btn.setPixelSize(14)
        f_btn.setWeight(QFont.DemiBold)
        P.setFont(f_btn)
        P.setPen(QPen(QColor(255, 255, 255)))
        pt = "📧 Purchase License"
        fm = P.fontMetrics()
        pw = fm.horizontalAdvance(pt)
        P.drawText(int(p_x + p_w/2 - pw/2),
                   int(p_actual_y + btn_h/2 + 5), pt)

        # Continue (grey, secondary — disabled until delay done)
        c_w = 200
        c_x = int(W/2 + gap/2)
        self._continue_rect = (c_x, btn_y, c_w, btn_h)

        can_continue = self._can_continue()
        secs = self._seconds_left()

        c_y_offset = -1 if (can_continue and self.hover_continue) else 0
        c_actual_y = btn_y + c_y_offset

        # Hover shadow (only when enabled + hovered)
        if can_continue and self.hover_continue:
            sh = QPainterPath()
            sh.addRoundedRect(
                QRectF(c_x, btn_y + 3, c_w, btn_h), 10, 10)
            P.setBrush(QBrush(QColor(255, 255, 255, 20)))
            P.setPen(Qt.NoPen)
            P.drawPath(sh)

        # Button gradient
        c_grad = QLinearGradient(c_x, c_actual_y, c_x, c_actual_y + btn_h)
        if can_continue:
            if self.hover_continue:
                c_grad.setColorAt(0.0, QColor(85, 85, 92))
                c_grad.setColorAt(1.0, QColor(55, 55, 62))
            else:
                c_grad.setColorAt(0.0, QColor(65, 65, 72))
                c_grad.setColorAt(1.0, QColor(45, 45, 52))
            c_text_col = QColor(255, 255, 255)
        else:
            c_grad.setColorAt(0.0, QColor(40, 40, 45, 180))
            c_grad.setColorAt(1.0, QColor(30, 30, 35, 180))
            c_text_col = QColor(140, 140, 150)

        P.setBrush(QBrush(c_grad))
        P.setPen(QPen(QColor(255, 255, 255, 30), 1))
        c_path = QPainterPath()
        c_path.addRoundedRect(
            QRectF(c_x, c_actual_y, c_w, btn_h), 10, 10)
        P.drawPath(c_path)

        # Gloss on top
        if can_continue:
            gloss2 = QLinearGradient(c_x, c_actual_y, c_x, c_actual_y + btn_h * 0.5)
            gloss2.setColorAt(0.0, QColor(255, 255, 255, 20))
            gloss2.setColorAt(1.0, QColor(255, 255, 255,  0))
            P.setBrush(QBrush(gloss2))
            P.setPen(Qt.NoPen)
            P.drawPath(c_path)

        P.setPen(QPen(c_text_col))
        if can_continue:
            ct = "Continue"
        else:
            ct = f"Continue ({int(secs) + 1}s)"
        fm = P.fontMetrics()
        cw = fm.horizontalAdvance(ct)
        P.drawText(int(c_x + c_w/2 - cw/2),
                   int(c_actual_y + btn_h/2 + 5), ct)

        # Email footer — clickable with hover
        f_ft = QFont("SF Pro Text, Inter, Arial")
        f_ft.setPixelSize(12)
        f_ft.setWeight(QFont.Medium)
        P.setFont(f_ft)

        if self.hover_email:
            P.setPen(QPen(QColor(10, 132, 255)))   # iOS blue on hover
        else:
            P.setPen(QPen(QColor(155, 160, 175)))

        ft = f"Contact: {PURCHASE_EMAIL}"
        fm = P.fontMetrics()
        fw = fm.horizontalAdvance(ft)
        ft_x = int(W/2 - fw/2)
        ft_y = H - 22
        P.drawText(ft_x, ft_y, ft)

        # Store rect for click handling
        self._email_rect = (ft_x - 8, ft_y - 16, fw + 16, 22)

        # Underline on hover
        if self.hover_email:
            P.setPen(QPen(QColor(10, 132, 255), 1.2))
            P.drawLine(ft_x, ft_y + 3, ft_x + fw, ft_y + 3)

        P.end()

    # ────────────────────────────────────────────────
    def _in_rect(self, x, y, rect):
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def mouseMoveEvent(self, e):
        x, y = e.x(), e.y()
        self.hover_purchase = self._in_rect(x, y, getattr(self, "_purchase_rect", (0,0,0,0)))
        self.hover_copy     = self._in_rect(x, y, getattr(self, "_copy_rect", (0,0,0,0)))
        self.hover_email    = self._in_rect(x, y, getattr(self, "_email_rect", (0,0,0,0)))
        self.hover_continue = self._can_continue() and \
                              self._in_rect(x, y, getattr(self, "_continue_rect", (0,0,0,0)))
        if (self.hover_purchase or self.hover_copy or
                self.hover_continue or self.hover_email):
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        self.update()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        x, y = e.x(), e.y()

        if self._in_rect(x, y, self._copy_rect):
            _copy_to_clipboard(self.hw_id)
            # Flash indicator? Just visual feedback via redraw
            self.update()

        elif self._in_rect(x, y, self._purchase_rect):
            _open_email(self.hw_id)

        elif self._in_rect(x, y, getattr(self, "_email_rect", (0,0,0,0))):
            _open_email(self.hw_id)

        elif self._in_rect(x, y, self._continue_rect):
            if self._can_continue():
                self._tmr.stop()
                try: self.continued.emit()
                except Exception: pass
                self.close()

    def keyPressEvent(self, e):
        # Escape does NOT close (must wait for delay + continue)
        # Enter/Space triggers Continue if enabled
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if self._can_continue():
                self._tmr.stop()
                try: self.continued.emit()
                except Exception: pass
                self.close()


def show_license_dialog(hw_id: str,
                        days_expired: int = 0,
                        status_text: str = "Trial Expired",
                        on_continue=None) -> LicenseDialog:
    """
    Public API — show blocking-ish license dialog.
    User must wait N seconds before Continue enables.
    """
    dlg = LicenseDialog(hw_id, days_expired, status_text)
    if on_continue:
        try: dlg.continued.connect(on_continue)
        except Exception: pass
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    return dlg


# ─── Standalone test ─────────────────────────────────────
def main():
    """Standalone test — uses REAL hardware ID from this machine."""
    app = QApplication(sys.argv)

    # Get actual hardware ID (not hardcoded)
    try:
        from nova_unlock.licensing.hardware_id import get_short_hw_id
        real_hw = get_short_hw_id()
    except Exception:
        real_hw = "TEST-HW-ID"

    dlg = show_license_dialog(
        hw_id=real_hw,
        days_expired=5,
        status_text="Trial Expired",
        on_continue=app.quit)
    app._nova_dlg = dlg
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
