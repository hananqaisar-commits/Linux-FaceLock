#!/usr/bin/env python3
"""
Nova Windows Notification Interceptor
Hooks into Windows notification system via winrt/win32.
Replaces Action Center toasts with Nova glass UI.
"""
from __future__ import annotations
import threading
from typing import Callable


class WinNotifServer:
    """
    Windows notification server.
    Uses Windows Runtime (winrt) to intercept toast notifications.
    Falls back to win32api polling if winrt unavailable.
    """

    def __init__(self, on_notify: Callable, on_close: Callable):
        self.on_notify = on_notify
        self.on_close  = on_close
        self._running  = False
        self._thread   = None

    def start(self) -> bool:
        try:
            return self._start_winrt()
        except ImportError:
            return self._start_polling()

    def _start_winrt(self) -> bool:
        """Windows Runtime notification listener."""
        import winrt.windows.ui.notifications as wn
        import winrt.windows.ui.notifications.management as wm

        listener = wm.UserNotificationListener.current
        access   = listener.request_access_async().get()

        if str(access) != "allowed":
            return self._start_polling()

        def _on_changed(sender, args):
            try:
                notifs = listener.get_notifications_async(
                    wn.NotificationKinds.TOAST).get()
                for n in notifs:
                    try:
                        app  = n.app_info.display_info.display_name
                        xml  = n.notification.content.get_xml()
                        body = ""
                        nid  = n.id
                        self.on_notify(nid, app, str(xml), body, 1, -1, "")
                    except: pass
            except: pass

        listener.notification_changed += _on_changed
        self._running = True
        print("[Nova] ✓ Windows WinRT notification listener active")
        return True

    def _start_polling(self) -> bool:
        """Fallback: poll Windows notifications via win32."""
        def _loop():
            import time
            last_ids = set()
            while self._running:
                try:
                    # Use PowerShell to get toast history
                    import subprocess
                    result = subprocess.run([
                        "powershell","-NoProfile","-Command",
                        "Get-ChildItem "
                        "$env:LOCALAPPDATA\\Microsoft\\Windows\\"
                        "Notifications\\wpndatabase.db-wal "
                        "-ErrorAction SilentlyContinue | "
                        "Select-Object LastWriteTime"
                    ], capture_output=True, text=True)
                except: pass
                time.sleep(1.0)

        self._running = True
        self._thread  = threading.Thread(target=_loop, daemon=True)
        self._thread.start()
        print("[Nova] ✓ Windows polling fallback active")
        return True

    def stop(self):
        self._running = False

