#!/usr/bin/env python3
"""
nova_unlock/ui/error_dialogs.py
═══════════════════════════════════════════════════════════
GUI Error Dialogs for NovaUnlock

All error conditions shown as premium dark-themed PyQt5 popups.
No terminal output — clean user-facing error experience.
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QApplication, QGraphicsDropShadowEffect, QWidget,
)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QSize
from PyQt5.QtGui import QFont, QColor, QIcon, QPalette, QPainter, QPixmap


# ═══════════════════════════════════════════════════════════════
# Shared Dark Stylesheet
# ═══════════════════════════════════════════════════════════════

DARK_STYLE = """
QDialog {
    background-color: #0a0a0e;
    border: 1px solid #1a1a2e;
    border-radius: 16px;
}
QLabel {
    color: #e0e0e8;
    background: transparent;
}
QLabel#title {
    font-size: 20px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: 0.5px;
}
QLabel#subtitle {
    font-size: 13px;
    color: #8888a0;
    letter-spacing: 0.3px;
}
QLabel#icon {
    font-size: 48px;
}
QPushButton {
    background-color: #1e1e3a;
    color: #d0d0e0;
    border: 1px solid #2a2a4e;
    border-radius: 10px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 500;
    min-width: 100px;
}
QPushButton:hover {
    background-color: #2a2a52;
    border: 1px solid #3a3a6e;
}
QPushButton:pressed {
    background-color: #16162e;
}
QPushButton#primary {
    background-color: #1a4fd8;
    color: #ffffff;
    border: 1px solid #2a5fe8;
}
QPushButton#primary:hover {
    background-color: #2460e8;
}
QPushButton#primary:pressed {
    background-color: #1240b0;
}
QPushButton#danger {
    background-color: #5a1a1a;
    color: #ff8888;
    border: 1px solid #7a2a2a;
}
QPushButton#danger:hover {
    background-color: #6a2a2a;
}
"""


class _BaseNovaDialog(QDialog):
    """Base class for all NovaUnlock error dialogs."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Dialog
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet(DARK_STYLE)
        self.setMinimumWidth(400)
        self.setMaximumWidth(520)

        # Main container with shadow
        self._container = QWidget(self)
        self._container.setObjectName("container")
        self._container.setStyleSheet("""
            QWidget#container {
                background-color: #0a0a0e;
                border: 1px solid #1a1a2e;
                border-radius: 16px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 8)
        self._container.setGraphicsEffect(shadow)

    def _build_layout(self, icon_text: str, icon_color: str,
                      title: str, subtitle: str,
                      buttons: list[tuple[str, str, object]]):
        """
        Build the standard dialog layout.

        buttons: list of (text, object_name, callback) tuples.
                 object_name: 'primary', 'danger', or '' for default.
        """
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(8)

        # Icon
        icon_label = QLabel(icon_text)
        icon_label.setObjectName("icon")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"color: {icon_color}; font-size: 48px;")
        layout.addWidget(icon_label)
        layout.addSpacing(8)

        # Title
        title_label = QLabel(title)
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addSpacing(4)

        # Subtitle
        sub_label = QLabel(subtitle)
        sub_label.setObjectName("subtitle")
        sub_label.setAlignment(Qt.AlignCenter)
        sub_label.setWordWrap(True)
        layout.addWidget(sub_label)
        layout.addSpacing(20)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        for text, obj_name, callback in buttons:
            btn = QPushButton(text)
            if obj_name:
                btn.setObjectName(obj_name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(callback)
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

        # Container fills dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.addWidget(self._container)

    def showEvent(self, event):
        """Center on screen when shown."""
        super().showEvent(event)
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                geo = screen.geometry()
                x = (geo.width() - self.width()) // 2
                y = (geo.height() - self.height()) // 2
                self.move(x, y)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


# ═══════════════════════════════════════════════════════════════
# Camera Not Found Dialog
# ═══════════════════════════════════════════════════════════════

class NoCameraDialog(_BaseNovaDialog):
    """
    Displayed when no camera is detected.
    Offers retry and close options.
    """

    def __init__(self, parent: QWidget | None = None,
                 on_retry: object = None):
        super().__init__(parent)
        self._on_retry = on_retry
        self.setWindowTitle("No camera detected")

        self._build_layout(
            icon_text="CAM",
            icon_color="#ff6b6b",
            title="No camera detected",
            subtitle=(
                "NovaUnlock could not find a working camera.\n\n"
                "- Check that your webcam is connected\n"
                "- Ensure no other application is using the camera\n"
                "- Try unplugging and reconnecting the device"
            ),
            buttons=[
                ("Close", "", self.close),
                ("Retry", "primary", self._retry),
            ],
        )

    def _retry(self):
        self.close()
        if self._on_retry:
            self._on_retry()


# ═══════════════════════════════════════════════════════════════
# Face Not Enrolled Dialog
# ═══════════════════════════════════════════════════════════════

class NotEnrolledDialog(_BaseNovaDialog):
    """
    Displayed when no face data is enrolled for the current user.
    """

    def __init__(self, parent: QWidget | None = None,
                 username: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Please enroll your face first")

        user_text = f" for '{username}'" if username else ""

        self._build_layout(
            icon_text="USER",
            icon_color="#ffa940",
            title="Please enroll your face first",
            subtitle=(
                f"No face data found{user_text}.\n\n"
                "Run the enrollment wizard to register your face:\n\n"
                "  python3 scripts/enroll_gui.py\n\n"
                "Or use the CLI:\n\n"
                "  python3 scripts/enroll.py"
            ),
            buttons=[
                ("Close", "", self.close),
            ],
        )


# ═══════════════════════════════════════════════════════════════
# Low Light Warning Dialog
# ═══════════════════════════════════════════════════════════════

class LowLightDialog(_BaseNovaDialog):
    """
    Displayed when poor lighting conditions are detected.
    Non-blocking warning — user can continue or retry.
    """

    def __init__(self, parent: QWidget | None = None,
                 on_continue: object = None):
        super().__init__(parent)
        self._on_continue = on_continue
        self.setWindowTitle("Poor lighting conditions")

        self._build_layout(
            icon_text="LIGHT",
            icon_color="#ffd666",
            title="Poor lighting conditions",
            subtitle=(
                "The camera image is too dark for reliable face recognition.\n\n"
                "Tips for better results:\n"
                "- Turn on a desk lamp or overhead light\n"
                "- Face towards the light source\n"
                "- Avoid strong backlighting\n"
                "- Increase screen brightness"
            ),
            buttons=[
                ("Cancel", "", self.close),
                ("Continue Anyway", "primary", self._continue),
            ],
        )

    def _continue(self):
        self.close()
        if self._on_continue:
            self._on_continue()


# ═══════════════════════════════════════════════════════════════
# Anti-Spoof Detection Dialog
# ═══════════════════════════════════════════════════════════════

class SpoofDetectedDialog(_BaseNovaDialog):
    """
    Displayed when a spoofing attempt is detected
    (photo or screen presented instead of real face).
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Spoof Detected")

        self._build_layout(
            icon_text="SEC",
            icon_color="#ff4d4f",
            title="Spoofing Attempt Detected",
            subtitle=(
                "NovaUnlock detected a photo or screen\n"
                "instead of a real face.\n\n"
                "For security, this attempt has been blocked.\n"
                "Please present your actual face to the camera."
            ),
            buttons=[
                ("Close", "danger", self.close),
            ],
        )


# ═══════════════════════════════════════════════════════════════
# Generic Error Dialog
# ═══════════════════════════════════════════════════════════════

class NovaErrorDialog(_BaseNovaDialog):
    """
    Generic error dialog for unexpected errors.
    Shows error message with technical details.
    """

    def __init__(self, parent: QWidget | None = None,
                 title: str = "Error",
                 message: str = "",
                 details: str = ""):
        super().__init__(parent)
        self.setWindowTitle(title)

        subtitle = message
        if details:
            subtitle += f"\n\nDetails:\n{details}"

        self._build_layout(
            icon_text="!",
            icon_color="#ff7875",
            title=title,
            subtitle=subtitle,
            buttons=[
                ("Close", "", self.close),
            ],
        )


# ═══════════════════════════════════════════════════════════════
# Light Level Detection Utility
# ═══════════════════════════════════════════════════════════════

def check_light_level(frame) -> str:
    """
    Analyze a camera frame for lighting quality.

    Returns:
        "good"    — adequate lighting for face recognition
        "low"     — poor lighting, may affect accuracy
        "very_low" — too dark, recognition will likely fail
    """
    import cv2
    import numpy as np

    if frame is None or frame.size == 0:
        return "very_low"

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = float(np.mean(gray))

    if mean_brightness < 40:
        return "very_low"
    elif mean_brightness < 80:
        return "low"
    return "good"


# ═══════════════════════════════════════════════════════════════
# Convenience — Show dialog and block
# ═══════════════════════════════════════════════════════════════

def show_error(dialog_class, **kwargs):
    """
    Show an error dialog, creating QApplication if needed.
    Blocks until dialog is closed.
    """
    app = QApplication.instance()
    created = False
    if app is None:
        app = QApplication(sys.argv)
        created = True

    dlg = dialog_class(**kwargs)
    dlg.exec_()

    if created:
        app.quit()
