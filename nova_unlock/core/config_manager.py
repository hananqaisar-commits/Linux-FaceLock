#!/usr/bin/env python3
"""
nova_unlock/core/config_manager.py
═══════════════════════════════════════════════════════════
NovaUnlock Configuration Manager

Singleton config loader with typed getters and defaults.
Reads from config/nova.conf relative to project root.
All modules import NovaConfig instead of raw configparser.
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import configparser
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("nova.config")

# ── Defaults — used when config file or key is missing ──────
DEFAULTS = {
    "recognition": {
        "threshold":    "0.5",
        "timeout":      "10",
        "max_attempts": "5",
        "angles":       "5",
    },
    "ui": {
        "theme":                "dark",
        "show_camera_preview":  "true",
        "animation":            "true",
    },
    "audio": {
        "success_sound": "true",
        "fail_sound":    "true",
    },
    "security": {
        "liveness_check":  "true",
        "anti_spoof":      "true",
        "min_blinks":      "1",
        "liveness_window": "3.0",
    },
}


class NovaConfig:
    """
    Centralized configuration for NovaUnlock.

    Usage:
        from nova_unlock.core.config_manager import NovaConfig
        cfg = NovaConfig()
        print(cfg.threshold)        # float
        print(cfg.timeout)          # int
        print(cfg.liveness_check)   # bool
    """

    _instance: NovaConfig | None = None

    def __new__(cls, config_path: str | Path | None = None) -> NovaConfig:
        if cls._instance is not None:
            return cls._instance
        inst = super().__new__(cls)
        cls._instance = inst
        return inst

    def __init__(self, config_path: str | Path | None = None):
        if hasattr(self, "_loaded"):
            return
        self._loaded = True
        self._parser = configparser.ConfigParser()

        # Apply defaults first
        for section, values in DEFAULTS.items():
            if not self._parser.has_section(section):
                self._parser.add_section(section)
            for key, val in values.items():
                self._parser.set(section, key, val)

        # Find and load config file
        if config_path is None:
            config_path = self._find_config()

        if config_path and Path(config_path).exists():
            self._parser.read(str(config_path))
            self._config_path = Path(config_path)
            log.info(f"Config loaded: {config_path}")
        else:
            self._config_path = None
            log.info("Using default config (no nova.conf found)")

    def _find_config(self) -> Path | None:
        """Locate nova.conf using the same logic as system_detect.find_nova_root()."""
        import os

        # Method 1: NOVA_ROOT environment variable
        nova_root = os.environ.get("NOVA_ROOT")
        if nova_root:
            p = Path(nova_root) / "config" / "nova.conf"
            if p.exists():
                return p

        # Method 2: Relative to this file (development layout)
        project_root = Path(__file__).parent.parent.parent
        p = project_root / "config" / "nova.conf"
        if p.exists():
            return p

        # Method 3: Standard install locations
        import pwd
        try:
            user = os.environ.get("SUDO_USER", os.environ.get("USER", ""))
            if not user or user == "root":
                user = pwd.getpwuid(os.getuid()).pw_name
        except Exception:
            user = "user"

        for base in [
            Path(f"/home/{user}/.local/share/nova-unlock"),
            Path("/opt/nova-unlock"),
            Path("/usr/local/share/nova-unlock"),
        ]:
            p = base / "config" / "nova.conf"
            if p.exists():
                return p

        return None

    # ── Typed property accessors ────────────────────────────

    def _get(self, section: str, key: str, fallback: str = "") -> str:
        return self._parser.get(section, key, fallback=fallback)

    def _get_bool(self, section: str, key: str, fallback: bool = False) -> bool:
        try:
            return self._parser.getboolean(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    def _get_float(self, section: str, key: str, fallback: float = 0.0) -> float:
        try:
            return self._parser.getfloat(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    def _get_int(self, section: str, key: str, fallback: int = 0) -> int:
        try:
            return self._parser.getint(section, key, fallback=fallback)
        except (ValueError, configparser.Error):
            return fallback

    # ── Recognition ─────────────────────────────────────────

    @property
    def threshold(self) -> float:
        return self._get_float("recognition", "threshold", 0.42)

    @property
    def timeout(self) -> int:
        return self._get_int("recognition", "timeout", 10)

    @property
    def max_attempts(self) -> int:
        return self._get_int("recognition", "max_attempts", 5)

    @property
    def angles(self) -> int:
        return self._get_int("recognition", "angles", 5)

    # ── UI ──────────────────────────────────────────────────

    @property
    def theme(self) -> str:
        return self._get("ui", "theme", "dark")

    @property
    def show_camera_preview(self) -> bool:
        return self._get_bool("ui", "show_camera_preview", True)

    @property
    def animation(self) -> bool:
        return self._get_bool("ui", "animation", True)

    # ── Audio ───────────────────────────────────────────────

    @property
    def success_sound(self) -> bool:
        return self._get_bool("audio", "success_sound", True)

    @property
    def fail_sound(self) -> bool:
        return self._get_bool("audio", "fail_sound", True)

    # ── Security ────────────────────────────────────────────

    @property
    def liveness_check(self) -> bool:
        return self._get_bool("security", "liveness_check", True)

    @property
    def anti_spoof(self) -> bool:
        return self._get_bool("security", "anti_spoof", True)

    @property
    def min_blinks(self) -> int:
        return self._get_int("security", "min_blinks", 1)

    @property
    def liveness_window(self) -> float:
        return self._get_float("security", "liveness_window", 3.0)

    # ── Utility ─────────────────────────────────────────────

    def reload(self):
        """Force reload from disk."""
        self._loaded = False
        NovaConfig._instance = None
        self.__init__()

    def as_dict(self) -> dict:
        """Return all config as a flat dictionary."""
        result = {}
        for section in self._parser.sections():
            for key, value in self._parser.items(section):
                result[f"{section}.{key}"] = value
        return result

    def __repr__(self) -> str:
        src = str(self._config_path) if self._config_path else "defaults"
        return f"<NovaConfig src={src}>"
