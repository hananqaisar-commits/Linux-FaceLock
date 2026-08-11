#!/usr/bin/env python3
"""
NovaUnlock — GTK Theme Manager v1.32
Auto-detects system GTK dark/light theme and applies
matching palette to all NovaUnlock Qt windows.
"""

import subprocess
import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

ThemeMode = Literal["dark", "light"]

# ── Color Palettes ────────────────────────────────────────────
PALETTES = {
    "dark": {
        "bg_primary"    : "#0d0d0d",
        "bg_secondary"  : "#1a1a1a",
        "bg_card"       : "#1e1e1e",
        "accent"        : "#00d4ff",
        "accent_glow"   : "rgba(0, 212, 255, 0.3)",
        "text_primary"  : "#ffffff",
        "text_secondary": "#aaaaaa",
        "success"       : "#00ff88",
        "error"         : "#ff4444",
        "warning"       : "#ffaa00",
        "border"        : "#2a2a2a",
        "overlay_alpha" : 210,
    },
    "light": {
        "bg_primary"    : "#f5f5f5",
        "bg_secondary"  : "#ffffff",
        "bg_card"       : "#ebebeb",
        "accent"        : "#0077cc",
        "accent_glow"   : "rgba(0, 119, 204, 0.2)",
        "text_primary"  : "#111111",
        "text_secondary": "#555555",
        "success"       : "#008844",
        "error"         : "#cc1111",
        "warning"       : "#cc7700",
        "border"        : "#cccccc",
        "overlay_alpha" : 230,
    },
}


class ThemeManager:
    """
    Detects system GTK theme (dark/light) and
    provides Qt stylesheet + color palette.
    Watches for runtime theme changes via DBus.
    """

    def __init__(self):
        self._mode: ThemeMode = "dark"
        self._callbacks = []
        self._detect_theme()

    # ── Detection ─────────────────────────────────────────────
    def _detect_theme(self) -> ThemeMode:
        mode = self._try_gsettings()
        if mode is None:
            mode = self._try_gtk_theme_name()
        if mode is None:
            mode = self._try_xfconf()
        if mode is None:
            mode = self._try_env()
        self._mode = mode or "dark"
        logger.info("ThemeManager: detected mode = %s", self._mode)
        return self._mode

    def _try_gsettings(self):
        try:
            out = subprocess.check_output(
                ["gsettings", "get",
                 "org.gnome.desktop.interface", "color-scheme"],
                stderr=subprocess.DEVNULL, timeout=2,
            ).decode().strip().strip("'")
            if "dark" in out.lower():
                return "dark"
            if "light" in out.lower() or "default" in out.lower():
                return "light"
        except Exception:
            pass
        try:
            out = subprocess.check_output(
                ["gsettings", "get",
                 "org.gnome.desktop.interface", "gtk-theme"],
                stderr=subprocess.DEVNULL, timeout=2,
            ).decode().strip().strip("'").lower()
            if "dark" in out:
                return "dark"
        except Exception:
            pass
        return None

    def _try_gtk_theme_name(self):
        paths = [
            os.path.expanduser("~/.config/gtk-3.0/settings.ini"),
            os.path.expanduser("~/.config/gtk-4.0/settings.ini"),
            "/etc/gtk-3.0/settings.ini",
        ]
        for p in paths:
            if os.path.isfile(p):
                try:
                    txt = open(p).read().lower()
                    if "gtk-application-prefer-dark-theme=1" in txt or \
                       "gtk-application-prefer-dark-theme=true" in txt:
                        return "dark"
                    for line in txt.splitlines():
                        if line.startswith("gtk-theme-name"):
                            if "dark" in line:
                                return "dark"
                            return "light"
                except Exception:
                    pass
        return None

    def _try_xfconf(self):
        try:
            out = subprocess.check_output(
                ["xfconf-query", "-c", "xsettings",
                 "-p", "/Net/ThemeName"],
                stderr=subprocess.DEVNULL, timeout=2,
            ).decode().strip().lower()
            return "dark" if "dark" in out else "light"
        except Exception:
            return None

    def _try_env(self):
        env_theme = os.environ.get("GTK_THEME", "").lower()
        if env_theme:
            return "dark" if "dark" in env_theme else "light"
        return None

    # ── Public API ────────────────────────────────────────────
    @property
    def mode(self) -> ThemeMode:
        return self._mode

    @property
    def palette(self) -> dict:
        return PALETTES[self._mode]

    def is_dark(self)  -> bool: return self._mode == "dark"
    def is_light(self) -> bool: return self._mode == "light"

    def refresh(self) -> ThemeMode:
        old = self._mode
        self._detect_theme()
        if old != self._mode:
            logger.info("ThemeManager: theme changed %s → %s", old, self._mode)
            for cb in self._callbacks:
                try:
                    cb(self._mode)
                except Exception as e:
                    logger.warning("Theme callback error: %s", e)
        return self._mode

    def on_change(self, callback):
        """Register callback(mode: str) called when theme changes."""
        self._callbacks.append(callback)

    # ── Qt Stylesheet ─────────────────────────────────────────
    def qt_stylesheet(self) -> str:
        p = self.palette
        return f"""
        QWidget {{
            background-color: {p['bg_primary']};
            color: {p['text_primary']};
            font-family: 'Segoe UI', 'Noto Sans', sans-serif;
        }}
        QLabel {{
            color: {p['text_primary']};
            background: transparent;
        }}
        QLabel#subtitle {{
            color: {p['text_secondary']};
        }}
        QPushButton {{
            background-color: {p['accent']};
            color: {p['bg_primary']};
            border: none;
            border-radius: 8px;
            padding: 8px 20px;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton:hover {{
            background-color: {p['text_primary']};
        }}
        QPushButton:pressed {{
            background-color: {p['text_secondary']};
        }}
        QPushButton#danger {{
            background-color: {p['error']};
            color: #ffffff;
        }}
        QLineEdit {{
            background-color: {p['bg_card']};
            color: {p['text_primary']};
            border: 1px solid {p['border']};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {p['accent']};
        }}
        QFrame {{
            border: 1px solid {p['border']};
            border-radius: 10px;
            background-color: {p['bg_card']};
        }}
        QScrollBar:vertical {{
            background: {p['bg_secondary']};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {p['border']};
            border-radius: 4px;
            min-height: 20px;
        }}
        QProgressBar {{
            background-color: {p['bg_card']};
            border: 1px solid {p['border']};
            border-radius: 5px;
            text-align: center;
            color: {p['text_primary']};
        }}
        QProgressBar::chunk {{
            background-color: {p['accent']};
            border-radius: 5px;
        }}
        """

    # ── Apply to QApplication ─────────────────────────────────
    def apply_to_app(self, app) -> None:
        app.setStyleSheet(self.qt_stylesheet())
        logger.info("ThemeManager: stylesheet applied (%s mode)", self._mode)

    # ── Watch DBus for runtime theme changes ──────────────────
    def start_watching(self, interval_ms: int = 5000) -> None:
        """Poll for GTK theme changes every interval_ms milliseconds."""
        try:
            from PyQt5.QtCore import QTimer
            self._timer = QTimer()
            self._timer.timeout.connect(self.refresh)
            self._timer.start(interval_ms)
            logger.info("ThemeManager: watching for theme changes every %dms", interval_ms)
        except Exception as e:
            logger.warning("ThemeManager: cannot start watcher — %s", e)


# ── Singleton ─────────────────────────────────────────────────
_instance: ThemeManager | None = None

def get_theme() -> ThemeManager:
    global _instance
    if _instance is None:
        _instance = ThemeManager()
    return _instance


# ── Standalone test ───────────────────────────────────────────
if __name__ == "__main__":
    t = ThemeManager()
    print(f"Detected mode : {t.mode}")
    print(f"Is dark       : {t.is_dark()}")
    print(f"Accent color  : {t.palette['accent']}")
    print(f"Stylesheet len: {len(t.qt_stylesheet())} chars")
    print("✅ ThemeManager OK")
