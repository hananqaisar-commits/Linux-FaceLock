#!/usr/bin/env python3
"""
Nova Platform Manager
Detects OS/DE only. Does NOT kill any daemon.
"""
from __future__ import annotations
import os
import platform as _platform
from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path


@dataclass
class PlatformInfo:
    os:           str = ""
    distro:       str = ""
    distro_like:  str = ""
    de:           str = ""
    session:      str = ""
    notif_daemon: str = ""
    notif_pid:    int = 0
    win_version:  str = ""


class PlatformManager:

    def __init__(self, config_path: Optional[Path] = None):
        self.info = PlatformInfo()
        self._log: List[str] = []

    def detect(self) -> PlatformInfo:
        p = _platform.system().lower()
        if p == "linux":
            self.info.os = "linux"
            self._detect_linux()
        elif p == "windows":
            self.info.os = "windows"
            self.info.de = "windows"
        else:
            self.info.os = "linux"
        return self.info

    def _detect_linux(self):
        try:
            txt = Path("/etc/os-release").read_text()
            for line in txt.splitlines():
                if line.startswith("ID="):
                    self.info.distro = (line.split("=",1)[1]
                                        .strip().strip('"').lower())
                elif line.startswith("ID_LIKE="):
                    self.info.distro_like = (line.split("=",1)[1]
                                             .strip().strip('"').lower())
        except:
            pass

        de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if not de:
            de = os.environ.get("DESKTOP_SESSION", "").lower()
        self.info.de = de.split(":")[0] if ":" in de else de
        self.info.session = os.environ.get(
            "XDG_SESSION_TYPE", "x11").lower()

    def stop_original_daemon(self) -> bool:
        """No-op — OS daemon untouched."""
        print("[Nova] OS notification daemon untouched")
        return True

    def install_autostart(self, entry_script: Path) -> bool:
        return True

    def get_notif_position(self):
        de = self.info.de
        positions = {
            "xfce":     ("top",    "right"),
            "gnome":    ("top",    "center"),
            "kde":      ("top",    "right"),
            "cinnamon": ("bottom", "right"),
            "mate":     ("top",    "right"),
            "windows":  ("bottom", "right"),
        }
        for key, pos in positions.items():
            if key in de:
                return pos
        return ("top", "right")

    @property
    def log(self) -> List[str]:
        return self._log
