#!/usr/bin/env python3
"""
Nova Icon Loader
Finds real app icons from system — works for any app.
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Optional, Dict
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QSize

# Cache — avoid repeated disk lookups
_cache: Dict[str, Optional[QPixmap]] = {}

# Icon search sizes (prefer larger)
SIZES = [48, 64, 32, 128, 256, 24, 16]

# Icon theme dirs
ICON_DIRS = [
    "/usr/share/icons/hicolor",
    "/usr/share/icons/Adwaita",
    "/usr/share/icons/Flat-Remix-Blue-Dark",
    "/usr/share/icons",
    "/usr/share/pixmaps",
    os.path.expanduser("~/.local/share/icons"),
    os.path.expanduser("~/.icons"),
]

# App name → icon name mapping
APP_ICON_MAP = {
    "telegram":           "telegram",
    "telegram-desktop":   "telegram",
    "org.telegram":       "telegram",
    "spotify":            "spotify",
    "whatsapp":           "whatsapp",
    "discord":            "discord",
    "slack":              "slack",
    "firefox":            "firefox",
    "firefox-esr":        "firefox-esr",
    "chrome":             "google-chrome",
    "google-chrome":      "google-chrome",
    "chromium":           "chromium",
    "thunderbird":        "thunderbird",
    "signal":             "signal-desktop",
    "gmail":              "google-gmail",
    "mail":               "evolution",
    "geary":              "geary",
    "evolution":          "evolution",
    "instagram":          "instagram",
    "facebook":           "facebook",
    "twitter":            "twitter",
    "youtube":            "youtube",
    "vlc":                "vlc",
    "rhythmbox":          "rhythmbox",
    "clementine":         "clementine",
    "audacious":          "audacious",
    "gimp":               "gimp",
    "inkscape":           "inkscape",
    "code":               "com.visualstudio.code",
    "vscode":             "com.visualstudio.code",
    "terminal":           "utilities-terminal",
    "bash":               "utilities-terminal",
    "system":             "preferences-system",
    "battery":            "battery",
    "power":              "battery",
    "network":            "network-wireless",
    "bluetooth":          "bluetooth",
    "camera":             "camera-photo",
    "calendar":           "gnome-calendar",
    "clock":              "gnome-clocks",
    "files":              "system-file-manager",
    "nautilus":           "system-file-manager",
    "thunar":             "thunar",
    "notify-send":        "dialog-information",
    "dunst":              "dialog-information",
    "xfce4-power-manager":"xfpm-ac-adapter",
    "xfce":               "xfce4-logo",
}


def _find_desktop_icon(app_name: str) -> Optional[str]:
    """Find icon name from .desktop file."""
    search = app_name.lower().strip()
    dirs = [
        "/usr/share/applications",
        os.path.expanduser("~/.local/share/applications"),
        "/usr/local/share/applications",
    ]
    for d in dirs:
        try:
            for f in Path(d).glob("*.desktop"):
                name = f.stem.lower()
                if search in name or name in search:
                    for line in f.read_text(errors='ignore').splitlines():
                        if line.startswith("Icon="):
                            return line.split("=",1)[1].strip()
        except: pass
    return None


def _find_icon_file(icon_name: str) -> Optional[str]:
    """Find actual icon file path."""
    if not icon_name: return None

    # Already absolute path
    if icon_name.startswith("/") and Path(icon_name).exists():
        return icon_name

    # Check pixmaps first
    for ext in ["png","svg","xpm"]:
        p = f"/usr/share/pixmaps/{icon_name}.{ext}"
        if Path(p).exists(): return p

    # Search icon dirs by size
    for size in SIZES:
        for base in ICON_DIRS:
            for subdir in [
                f"{base}/{size}x{size}/apps",
                f"{base}/apps/{size}",
                f"{base}/apps",
                f"{base}/{size}x{size}/status",
                f"{base}",
            ]:
                for ext in ["png","svg","xpm"]:
                    p = f"{subdir}/{icon_name}.{ext}"
                    if Path(p).exists(): return p

    # Recursive search
    for base in ICON_DIRS:
        try:
            result = subprocess.run(
                ["find", base, "-name", f"{icon_name}.*",
                 "-type", "f", "-size", "+1k"],
                capture_output=True, text=True, timeout=1.0)
            files = [l for l in result.stdout.strip().split("\n")
                     if l and any(l.endswith(e)
                                  for e in [".png",".svg",".xpm"])]
            if files:
                # Prefer 48px
                for f in files:
                    if "48" in f: return f
                return files[0]
        except: pass

    return None


def get_icon_from_hint(app_icon: str, size: int = 42) -> Optional[QPixmap]:
    """Load icon directly from app_icon D-Bus hint."""
    if not app_icon: return None
    key = f"hint:{app_icon}:{size}"
    if key in _cache: return _cache[key]
    # Try as file path
    pm = _load_pixmap(app_icon, size)
    if pm:
        _cache[key] = pm
        return pm
    # Try as icon name
    f = _find_icon_file(app_icon)
    if f:
        pm = _load_pixmap(f, size)
        if pm:
            _cache[key] = pm
            return pm
    _cache[key] = None
    return None


def _load_pixmap(path: str, size: int) -> Optional[QPixmap]:
    try:
        pm = QPixmap(path)
        if not pm.isNull():
            return pm.scaled(size, size,
                             Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
    except: pass
    return None


def get_icon(app_name: str, size: int = 42) -> Optional[QPixmap]:
    """
    Get app icon as QPixmap.
    Returns None if not found — caller uses letter fallback.
    """
    key = f"{app_name.lower()}:{size}"
    if key in _cache:
        return _cache[key]

    app_lower = app_name.lower().strip()

    # Step 1: Check our map
    icon_name = None
    for k, v in APP_ICON_MAP.items():
        if k in app_lower or app_lower in k:
            icon_name = v
            break

    # Step 2: Try desktop file
    if not icon_name:
        icon_name = _find_desktop_icon(app_lower)

    # Step 3: Use app name directly
    if not icon_name:
        icon_name = app_lower.replace(" ","_").replace("-","_")

    # Step 4: Find file
    icon_file = _find_icon_file(icon_name)

    # Step 5: Try Qt's built-in theme
    if not icon_file:
        try:
            qt_icon = QIcon.fromTheme(icon_name)
            if not qt_icon.isNull():
                pm = qt_icon.pixmap(QSize(size, size))
                if not pm.isNull():
                    _cache[key] = pm
                    return pm
        except: pass

    # Step 6: Load file
    if icon_file:
        try:
            pm = QPixmap(icon_file)
            if not pm.isNull():
                pm = pm.scaled(size, size,
                               Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
                _cache[key] = pm
                return pm
        except: pass

    _cache[key] = None
    return None
