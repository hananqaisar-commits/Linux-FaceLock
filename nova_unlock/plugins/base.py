#!/usr/bin/env python3
"""
Nova Plugin Base — every plugin inherits this.
Future plugins: charging, cricket, spotify, youtube, etc.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class NovaPlugin(ABC):
    """
    Base class for all Nova plugins.

    Lifecycle:
        __init__ → setup() → [running] → teardown()

    Every plugin gets:
        - name:        unique id  e.g. "notifications"
        - display:     human name e.g. "System Notifications"
        - version:     semver     e.g. "1.0.0"
        - platform:    list of supported platforms
                       ["linux", "windows", "macos", "all"]
    """
    name:     str = "base"
    display:  str = "Base Plugin"
    version:  str = "1.0.0"
    platform: list = ["all"]

    def __init__(self, host):
        """
        host = NovaDaemon instance
        Gives plugin access to:
            host.show(widget)      — show a glass card
            host.dismiss(widget)   — dismiss a glass card
            host.config            — plugin config dict
            host.platform          — PlatformInfo
        """
        self.host    = host
        self.config  = host.config.get(self.name, {})
        self.running = False

    @abstractmethod
    def setup(self) -> bool:
        """
        Initialize the plugin.
        Return True if setup succeeded, False to disable plugin.
        """

    @abstractmethod
    def teardown(self):
        """Clean up resources."""

    def on_platform_ready(self):
        """Called after OS-level hooks are installed."""

    def __repr__(self):
        return f"<NovaPlugin {self.name} v{self.version}>"
