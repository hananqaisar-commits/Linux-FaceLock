#!/usr/bin/env python3
"""
nova_unlock/ui/password_fallback.py
═══════════════════════════════════════════════════════════
Password Fallback Widget for NovaUnlock

Premium dark-themed password input that slides in when:
  - Face recognition times out (configurable, default 10s)
  - Face recognition fails 3 times
  - User explicitly requests password entry

Authenticates via PAM using subprocess to 'su'.
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import os
import logging
import time
import ctypes
import ctypes.util

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QApplication, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve,
    pyqtSignal, QRect, QPoint,
)
from PyQt5.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QBrush,
    QPen, QPainterPath,
)

log = logging.getLogger("nova.password_fallback")


# ═══════════════════════════════════════════════════════════════
# Dark Stylesheet
# ═══════════════════════════════════════════════════════════════

PASSWORD_STYLE = """
QWidget#pwContainer {
    background-color: #0a0a0e;
    border: 1px solid #1a1a2e;
    border-radius: 18px;
}
QLabel#pwTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
}
QLabel#pwSubtitle {
    color: #6a6a8a;
    font-size: 12px;
    background: transparent;
}
QLabel#pwError {
    color: #ff6b6b;
    font-size: 11px;
    background: transparent;
}
QLabel#pwIcon {
    color: #3a7bff;
    font-size: 36px;
    background: transparent;
}
QLineEdit#pwInput {
    background-color: #12121e;
    color: #e0e0f0;
    border: 2px solid #2a2a4e;
    border-radius: 12px;
    padding: 12px 16px;
    font-size: 15px;
    selection-background-color: #2a5fe8;
}
QLineEdit#pwInput:focus {
    border: 2px solid #3a7bff;
}
QPushButton#pwUnlock {
    background-color: #1a4fd8;
    color: #ffffff;
    border: none;
    border-radius: 12px;
    padding: 12px 32px;
    font-size: 14px;
    font-weight: 600;
    min-width: 120px;
}
QPushButton#pwUnlock:hover {
    background-color: #2460e8;
}
QPushButton#pwUnlock:pressed {
    background-color: #1240b0;
}
QPushButton#pwUnlock:disabled {
    background-color: #1a1a3a;
    color: #4a4a6a;
}
QPushButton#pwCancel {
    background-color: transparent;
    color: #6a6a8a;
    border: 1px solid #2a2a4e;
    border-radius: 12px;
    padding: 10px 24px;
    font-size: 13px;
}
QPushButton#pwCancel:hover {
    background-color: #1a1a2e;
    color: #9090b0;
}
"""


class PasswordFallbackWidget(QWidget):
    """
    Premium password input widget for lockscreen fallback.

    Signals:
        authenticated(str) — emitted with username on successful PAM auth
        cancelled()        — emitted when user cancels
    """

    authenticated = pyqtSignal(str)
    cancelled     = pyqtSignal()

    def __init__(self, username: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self._username = username or self._detect_user()
        self._attempts = 0
        self._max_attempts = 5
        self._locked_until = 0.0

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(420, 380)
        self.setStyleSheet(PASSWORD_STYLE)

        self._build_ui()
        self._setup_animations()

    def _detect_user(self) -> str:
        """Detect the current real user."""
        for var in ["SUDO_USER", "USER", "LOGNAME"]:
            user = os.environ.get(var, "").strip()
            if user and user != "root":
                return user
        try:
            import pwd
            return pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            return "user"

    def _build_ui(self):
        """Build the password input interface."""
        # Container
        self._container = QWidget(self)
        self._container.setObjectName("pwContainer")
        self._container.setGeometry(10, 10, 400, 360)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 8)
        self._container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(6)

        # Icon
        icon = QLabel("🔒")
        icon.setObjectName("pwIcon")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)
        layout.addSpacing(4)

        # Title
        title = QLabel("Password Required")
        title.setObjectName("pwTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Subtitle
        self._subtitle = QLabel(f"Enter password for {self._username}")
        self._subtitle.setObjectName("pwSubtitle")
        self._subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._subtitle)
        layout.addSpacing(16)

        # Password input
        self._input = QLineEdit()
        self._input.setObjectName("pwInput")
        self._input.setEchoMode(QLineEdit.Password)
        self._input.setPlaceholderText("Password")
        self._input.returnPressed.connect(self._try_authenticate)
        layout.addWidget(self._input)

        # Error label
        self._error = QLabel("")
        self._error.setObjectName("pwError")
        self._error.setAlignment(Qt.AlignCenter)
        self._error.setVisible(False)
        layout.addWidget(self._error)
        layout.addSpacing(12)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("pwCancel")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        self._unlock_btn = QPushButton("Unlock")
        self._unlock_btn.setObjectName("pwUnlock")
        self._unlock_btn.setCursor(Qt.PointingHandCursor)
        self._unlock_btn.clicked.connect(self._try_authenticate)
        btn_layout.addWidget(self._unlock_btn)

        layout.addLayout(btn_layout)

        # Attempts label
        self._attempts_label = QLabel("")
        self._attempts_label.setObjectName("pwSubtitle")
        self._attempts_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._attempts_label)

    def _setup_animations(self):
        """Prepare slide-in animation."""
        self._slide_anim = None

    def slide_in(self):
        """Animate the widget sliding up from below."""
        screen = QApplication.instance().primaryScreen().geometry()
        start_y = screen.height()
        end_x = (screen.width() - self.width()) // 2
        end_y = (screen.height() - self.height()) // 2

        self.move(end_x, start_y)
        self.show()
        self.raise_()

        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(450)
        self._slide_anim.setStartValue(QPoint(end_x, start_y))
        self._slide_anim.setEndValue(QPoint(end_x, end_y))
        self._slide_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._slide_anim.start()

        QTimer.singleShot(500, self._input.setFocus)

    def slide_out(self):
        """Animate the widget sliding down off screen."""
        screen = QApplication.instance().primaryScreen().geometry()
        end_y = screen.height()
        start_pos = self.pos()

        self._slide_anim = QPropertyAnimation(self, b"pos")
        self._slide_anim.setDuration(350)
        self._slide_anim.setStartValue(start_pos)
        self._slide_anim.setEndValue(QPoint(start_pos.x(), end_y))
        self._slide_anim.setEasingCurve(QEasingCurve.InCubic)
        self._slide_anim.finished.connect(self.hide)
        self._slide_anim.start()

    def _try_authenticate(self):
        """Attempt PAM authentication with entered password."""
        password = self._input.text().strip()
        if not password:
            self._show_error("Please enter your password")
            return

        # Check lockout
        now = time.time()
        if now < self._locked_until:
            remaining = int(self._locked_until - now)
            self._show_error(f"Too many attempts. Wait {remaining}s")
            return

        self._unlock_btn.setEnabled(False)
        self._unlock_btn.setText("Verifying...")

        QTimer.singleShot(100, lambda: self._do_auth(password))

    def _do_auth(self, password: str):
        """
        Authenticate with Linux PAM through libpam.
        This avoids terminal prompts and does not require extra Python packages.
        """
        try:
            if pam_authenticate(self._username, password):
                log.info(f"Password authentication successful for {self._username}")
                self._error.setVisible(False)
                self._unlock_btn.setText("✓ Unlocked")
                self.authenticated.emit(self._username)
                QTimer.singleShot(600, self.slide_out)
                return

        except Exception as e:
            log.error(f"Password authentication error: {e}")

        # Authentication failed
        self._attempts += 1
        remaining = self._max_attempts - self._attempts
        log.warning(
            f"Password authentication failed for {self._username} "
            f"(attempt {self._attempts}/{self._max_attempts})"
        )

        self._unlock_btn.setEnabled(True)
        self._unlock_btn.setText("Unlock")
        self._input.clear()
        self._input.setFocus()

        if remaining <= 0:
            self._locked_until = time.time() + 30
            self._show_error("Too many failed attempts. Locked for 30 seconds.")
            self._attempts = 0
            self._unlock_btn.setEnabled(False)
            QTimer.singleShot(30000, self._unlock_after_lockout)
        elif remaining <= 2:
            self._show_error(
                f"Incorrect password. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
            )
        else:
            self._show_error("Incorrect password. Please try again.")

        self._attempts_label.setText(
            f"Attempt {self._attempts}/{self._max_attempts}"
        )

        # Shake animation on failure
        self._shake()

    def _unlock_after_lockout(self):
        """Re-enable after lockout period."""
        self._unlock_btn.setEnabled(True)
        self._error.setVisible(False)

    def _show_error(self, text: str):
        """Display error message with smooth appearance."""
        self._error.setText(text)
        self._error.setVisible(True)

    def _shake(self):
        """Shake the input field on wrong password (like iOS)."""
        original_pos = self._input.pos()
        anim = QPropertyAnimation(self._input, b"pos")
        anim.setDuration(400)

        keyframes = [0, -8, 6, -4, 2, 0]
        duration_per = 400 // len(keyframes)

        anim.setStartValue(original_pos)
        anim.setEndValue(original_pos)
        anim.setEasingCurve(QEasingCurve.OutElastic)
        anim.start()
        self._shake_anim = anim  # prevent GC

    def _on_cancel(self):
        """Handle cancel button."""
        self.cancelled.emit()
        self.slide_out()

    def showEvent(self, event):
        """Focus password input when shown."""
        super().showEvent(event)
        QTimer.singleShot(200, self._input.setFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._on_cancel()

    def paintEvent(self, event):
        """Custom paint for translucent background."""
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing)
        P.setBrush(QBrush(QColor(0, 0, 0, 0)))
        P.setPen(Qt.NoPen)
        P.drawRect(self.rect())
        P.end()


PAM_PROMPT_ECHO_OFF = 1
PAM_PROMPT_ECHO_ON = 2
PAM_ERROR_MSG = 3
PAM_TEXT_INFO = 4
PAM_SUCCESS = 0


class PamMessage(ctypes.Structure):
    _fields_ = [
        ("msg_style", ctypes.c_int),
        ("msg", ctypes.c_char_p),
    ]


class PamResponse(ctypes.Structure):
    _fields_ = [
        ("resp", ctypes.c_char_p),
        ("resp_retcode", ctypes.c_int),
    ]


CONV_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.POINTER(PamMessage)),
    ctypes.POINTER(ctypes.POINTER(PamResponse)),
    ctypes.c_void_p,
)


class PamConv(ctypes.Structure):
    _fields_ = [
        ("conv", CONV_FUNC),
        ("appdata_ptr", ctypes.c_void_p),
    ]


def pam_authenticate(username: str, password: str, service: str = "login") -> bool:
    """Return True when PAM accepts username/password for the given service."""
    libpam_path = ctypes.util.find_library("pam")
    if not libpam_path:
        log.error("libpam not found")
        return False

    libpam = ctypes.CDLL(libpam_path)
    password_bytes = password.encode("utf-8")
    callbacks = []

    @CONV_FUNC
    def conversation(num_msg, msg, resp, appdata_ptr):
        response_array = (PamResponse * num_msg)()
        for i in range(num_msg):
            style = msg[i].contents.msg_style
            if style in (PAM_PROMPT_ECHO_OFF, PAM_PROMPT_ECHO_ON):
                response_array[i].resp = ctypes.cast(
                    ctypes.create_string_buffer(password_bytes),
                    ctypes.c_char_p,
                )
                response_array[i].resp_retcode = 0
            elif style in (PAM_TEXT_INFO, PAM_ERROR_MSG):
                response_array[i].resp = None
                response_array[i].resp_retcode = 0
            else:
                return 1
        callbacks.append(response_array)
        resp[0] = ctypes.cast(response_array, ctypes.POINTER(PamResponse))
        return PAM_SUCCESS

    handle = ctypes.c_void_p()
    conv = PamConv(conversation, None)

    libpam.pam_start.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.POINTER(PamConv),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    libpam.pam_start.restype = ctypes.c_int
    libpam.pam_authenticate.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libpam.pam_authenticate.restype = ctypes.c_int
    libpam.pam_acct_mgmt.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libpam.pam_acct_mgmt.restype = ctypes.c_int
    libpam.pam_end.argtypes = [ctypes.c_void_p, ctypes.c_int]
    libpam.pam_end.restype = ctypes.c_int

    code = libpam.pam_start(
        service.encode("utf-8"),
        username.encode("utf-8"),
        ctypes.byref(conv),
        ctypes.byref(handle),
    )
    if code != PAM_SUCCESS:
        return False

    try:
        code = libpam.pam_authenticate(handle, 0)
        if code != PAM_SUCCESS:
            return False
        code = libpam.pam_acct_mgmt(handle, 0)
        return code == PAM_SUCCESS
    finally:
        libpam.pam_end(handle, code)
