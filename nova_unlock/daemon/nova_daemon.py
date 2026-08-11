#!/usr/bin/env python3
"""
Nova Daemon — Plugin Host
Manages plugins. OS notification daemon untouched.
"""
from __future__ import annotations

import os
import sys
import time
import signal
import argparse
from pathlib import Path
from typing import List, Dict

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore    import QObject

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from nova_unlock.daemon.os_platform import PlatformManager, PlatformInfo
from nova_unlock.plugins.base       import NovaPlugin


class NovaDaemon(QObject):

    def __init__(self, app: QApplication,
                 config: Dict = None,
                 debug: bool = False):
        super().__init__()
        self.app     = app
        self.config  = config or {}
        self.debug   = debug
        self.platform: PlatformInfo = None
        self.plugins:  List[NovaPlugin] = []

    def start(self):
        print("[Nova Daemon] Starting...")

        # Detect platform (info only — no daemon kill)
        pm = PlatformManager()
        self.platform = pm.detect()
        print(f"[Nova Daemon] Platform: {self.platform.os}/"
              f"{self.platform.de}")

        # Load plugins
        self._load_plugins()
        print("[Nova Daemon] Ready")

    def _load_plugins(self):
        from nova_unlock.plugins.notifications import NotificationPlugin
        self._register(NotificationPlugin(self))

        from nova_unlock.plugins.charging import ChargingPlugin
        self._register(ChargingPlugin(self))

    def _register(self, plugin: NovaPlugin):
        if ("all" not in plugin.platform and
                self.platform.os not in plugin.platform):
            print(f"[Nova Daemon] Skip {plugin.name} "
                  f"(not supported on {self.platform.os})")
            return
        ok = plugin.setup()
        if ok:
            self.plugins.append(plugin)
            plugin.running = True
            print(f"[Nova Daemon] Plugin loaded: {plugin.display}")
        else:
            print(f"[Nova Daemon] Plugin failed: {plugin.name}")

    def shutdown(self):
        print("[Nova Daemon] Shutting down...")
        for plugin in self.plugins:
            try: plugin.teardown()
            except: pass
        print("[Nova Daemon] Done")


def main():
    parser = argparse.ArgumentParser(description="Nova Daemon")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    try:
        QApplication.setAttribute(QApplication.AA_EnableHighDpiScaling)
        QApplication.setAttribute(QApplication.AA_UseHighDpiPixmaps)
    except: pass

    app    = QApplication(sys.argv)
    daemon = NovaDaemon(app, debug=args.debug)
    daemon.start()

    def _sig(*_): daemon.shutdown(); app.quit()
    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT,  _sig)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
