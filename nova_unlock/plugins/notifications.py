#!/usr/bin/env python3
"""
Nova Notification Plugin
Routes notifications to OS default (notify-send).
"""
from __future__ import annotations
import subprocess
from nova_unlock.plugins.base import NovaPlugin


class NotificationPlugin(NovaPlugin):

    name     = "notifications"
    display  = "System Notifications"
    version  = "1.0.0"
    platform = ["linux", "windows", "macos"]

    def setup(self) -> bool:
        print(f"[Nova/{self.name}] Using OS default notifications")
        return True

    def on_notification(self, notif: dict):
        app     = notif.get("app", "Nova")
        summary = notif.get("summary", "")
        body    = notif.get("body", "")
        urgency = notif.get("urgency", 1)

        if not summary: return

        urgency_map = {0: "low", 1: "normal", 2: "critical"}
        urg_str = urgency_map.get(urgency, "normal")

        try:
            cmd = ["notify-send",
                   "--app-name", app,
                   "--urgency", urg_str,
                   summary]
            if body:
                cmd.append(body)
            subprocess.Popen(cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Nova/{self.name}] notify-send failed: {e}")

    def on_close(self, nid: int):
        pass

    def teardown(self):
        pass
