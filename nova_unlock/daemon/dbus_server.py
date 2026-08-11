#!/usr/bin/env python3
"""
Nova D-Bus Notification Server
Owns org.freedesktop.Notifications fully.
"""
from __future__ import annotations
import threading
from typing import Callable


class NovaDBusServer:

    def __init__(self, on_notify: Callable, on_close: Callable):
        self.on_notify  = on_notify
        self.on_close   = on_close
        self._next_id   = 1
        self._running   = False
        self._thread    = None
        # Keep references alive — prevents GC killing the connection
        self._seen      = {}   # dedup
        self._lock      = __import__('threading').Lock()
        self._bus       = None
        self._name      = None
        self._svc       = None
        self._loop      = None

    def start(self) -> bool:
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib
            ok = self._start_dbus()
            if ok:
                print("[Nova] D-Bus server active — monitor disabled")
                return True
            # Only use monitor if dbus failed
            print("[Nova] D-Bus failed — falling back to monitor")
            return self._start_monitor()
        except ImportError:
            print("[Nova] dbus-python missing — using monitor")
            return self._start_monitor()

    def _start_dbus(self) -> bool:
        try:
            import dbus
            import dbus.service
            from dbus.mainloop.glib import DBusGMainLoop
            from gi.repository import GLib

            # Must set default BEFORE creating bus
            DBusGMainLoop(set_as_default=True)

            self._bus  = dbus.SessionBus()
            self._name = dbus.service.BusName(
                "org.freedesktop.Notifications",
                self._bus,
                replace_existing=True,
                allow_replacement=True,
                do_not_queue=True)

            server = self

            class _Svc(dbus.service.Object):

                @dbus.service.method(
                    "org.freedesktop.Notifications",
                    in_signature="susssasa{sv}i",
                    out_signature="u")
                def Notify(self, app_name, replaces_id,
                           app_icon, summary, body,
                           actions, hints, expire_timeout):
                    import time as _t
                    urgency = 1
                    try:
                        if "urgency" in hints:
                            urgency = int(hints["urgency"])
                    except: pass

                    # Threading lock — GLib calls Notify twice
                    if not server._lock.acquire(blocking=False):
                        return dbus.UInt32(server._next_id-1)
                    try:
                        pass  # lock acquired
                    finally:
                        import threading
                        threading.Timer(0.5, server._lock.release).start()

                    # replaces_id > 0 means update
                    if replaces_id > 0:
                        return dbus.UInt32(replaces_id)

                    # Dedup by (app, summary) within 1.5s
                    _a=str(app_name).strip()
                    _s=str(summary).strip()
                    key = f"{_a}||{_s}"
                    now = _t.time()
                    if now - server._seen.get(key, 0) < 1.5:
                        nid = server._next_id - 1
                        return dbus.UInt32(max(1, nid))
                    server._seen[key] = now
                    # Prune
                    server._seen = {
                        k:v for k,v in server._seen.items()
                        if now-v < 10}

                    nid = server._next_id
                    server._next_id += 1

                    _b=str(body); _u=urgency; _n=nid
                    _e=int(expire_timeout)
                    _i=str(app_icon) if app_icon else ""

                    # Direct call — no QTimer to avoid double dispatch
                    try:
                        server.on_notify(_n,_a,_s,_b,_u,_e,_i)
                    except Exception as e:
                        print(f"[Nova] notify error: {e}")

                    return dbus.UInt32(nid)

                @dbus.service.method(
                    "org.freedesktop.Notifications",
                    in_signature="u")
                def CloseNotification(self, nid):
                    from PyQt5.QtCore import QTimer
                    _n=int(nid)
                    QTimer.singleShot(0, lambda:
                        server.on_close(_n))

                @dbus.service.method(
                    "org.freedesktop.Notifications",
                    out_signature="as")
                def GetCapabilities(self):
                    return ["body","body-markup","actions",
                            "icon-static","persistence"]

                @dbus.service.method(
                    "org.freedesktop.Notifications",
                    out_signature="ssss")
                def GetServerInformation(self):
                    return ("Nova","NovaUnlock","5.4","1.2")

            self._svc  = _Svc(
                self._bus,
                "/org/freedesktop/Notifications")

            self._loop = GLib.MainLoop()
            self._running = True

            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="nova-glib")
            self._thread.start()

            print("[Nova] ✓ D-Bus server owns "
                  "org.freedesktop.Notifications")
            return True

        except Exception as e:
            print(f"[Nova] D-Bus error: {e}")
            return False

    def _run_loop(self):
        """Run GLib loop — keeps D-Bus name alive."""
        try:
            self._loop.run()
        except Exception as e:
            print(f"[Nova] GLib loop: {e}")

    def _start_monitor(self) -> bool:
        """Fallback — passive dbus-monitor."""
        import subprocess
        import time as _time

        _seen = {}
        DEDUP  = 2.0

        def _listen():
            nonlocal _seen
            try:
                proc = subprocess.Popen(
                    ["dbus-monitor",
                     "interface='org.freedesktop.Notifications',"
                     "member='Notify'"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True, bufsize=1)

                app=summary=body=""
                urgency=1; si=0; buf=[]; in_c=False

                while self._running:
                    line = proc.stdout.readline()
                    if not line: break
                    line = line.rstrip()

                    if "member=Notify" in line:
                        if "method return" in line.lower():
                            continue
                        in_c=True; buf=[]
                        app=summary=body=""
                        urgency=1; si=0

                    if not in_c: continue
                    buf.append(line)

                    s = line.strip()
                    if s.startswith('string "'):
                        v = s[8:].rstrip('"')
                        if si==0:   app=v
                        elif si==3: summary=v
                        elif si==4: body=v
                        si+=1

                    if "byte" in s:
                        ctx = "".join(buf[-8:]).lower()
                        if "urgency" in ctx:
                            try:
                                urgency=min(int(s.split()[-1]),2)
                            except: pass

                    if in_c and si>=4 and app and summary:
                        key = (app.strip(), summary.strip())
                        now = _time.time()
                        if now - _seen.get(key,0) > DEDUP:
                            _seen[key] = now
                            _seen = {k:v for k,v in _seen.items()
                                     if now-v < DEDUP*3}
                            nid=self._next_id; self._next_id+=1
                            from PyQt5.QtCore import QTimer
                            _a=app; _s=summary; _b=body
                            _u=urgency; _n=nid
                            QTimer.singleShot(0, lambda:
                                self.on_notify(_n,_a,_s,_b,_u,-1,""))
                        in_c=False; app=summary=body=""
                        urgency=1; buf=[]; si=0

                proc.terminate()
            except Exception as e:
                print(f"[Nova] monitor: {e}")

        self._running = True
        self._thread  = threading.Thread(
            target=_listen, daemon=True, name="nova-monitor")
        self._thread.start()
        print("[Nova] ✓ D-Bus monitor active")
        return True

    def stop(self):
        self._running = False
        if self._loop:
            try: self._loop.quit()
            except: pass

