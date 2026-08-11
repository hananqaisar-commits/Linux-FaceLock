#!/usr/bin/env python3
"""
Nova Charging Plugin
Uses OS default notifications for charging events.
"""
from __future__ import annotations
import subprocess
import time
from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
from nova_unlock.plugins.base import NovaPlugin


class BatteryMonitor(QThread):
    plugged   = pyqtSignal(int)
    unplugged = pyqtSignal(int)
    full      = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.running       = True
        self._was_charging = None
        self._was_full     = False

    def stop(self): self.running = False

    def run(self):
        while self.running:
            try:
                pct, charging, is_full = self._read()
                if self._was_charging is None:
                    self._was_charging = charging
                    self._was_full     = is_full
                    time.sleep(2)
                    continue

                if charging and not self._was_charging:
                    self.plugged.emit(pct)
                elif not charging and self._was_charging:
                    self.unplugged.emit(pct)
                elif is_full and not self._was_full and charging:
                    self.full.emit(pct)

                self._was_charging = charging
                self._was_full     = is_full
            except:
                pass
            time.sleep(3)

    def _read(self):
        import platform as _pl
        if _pl.system().lower() == "linux":
            return self._read_linux()
        elif _pl.system().lower() == "windows":
            return self._read_windows()
        return 50, False, False

    def _read_linux(self):
        try:
            out = subprocess.run(
                ["upower", "-i",
                 "/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True, text=True, timeout=2).stdout
            pct = 50; charging = False; full = False
            for line in out.splitlines():
                l = line.strip()
                if l.startswith("percentage:"):
                    pct = int(l.split()[-1].rstrip("%"))
                elif l.startswith("state:"):
                    charging = "charging" in l
                    full     = "fully-charged" in l
            return pct, charging, full
        except:
            pass
        try:
            pct = int(Path(
                "/sys/class/power_supply/BAT0/capacity"
            ).read_text().strip())
            st  = Path(
                "/sys/class/power_supply/BAT0/status"
            ).read_text().strip().lower()
            return pct, "charging" in st, "full" in st
        except:
            return 50, False, False

    def _read_windows(self):
        try:
            import psutil
            b = psutil.sensors_battery()
            if b:
                return int(b.percent), b.power_plugged,                        (b.percent >= 99 and b.power_plugged)
        except:
            pass
        return 50, False, False


def _notify(summary, body="", urgency="normal"):
    try:
        cmd = ["notify-send", "--urgency", urgency, summary]
        if body:
            cmd.append(body)
        subprocess.Popen(cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[Nova/charging] notify-send failed: {e}")


class ChargingPlugin(NovaPlugin):

    name     = "charging"
    display  = "Charging Notifications"
    version  = "2.0.0"
    platform = ["linux", "windows"]

    def setup(self) -> bool:
        try:
            self._monitor = BatteryMonitor()
            self._monitor.plugged.connect(self._on_plug)
            self._monitor.unplugged.connect(self._on_unplug)
            self._monitor.full.connect(self._on_full)
            self._monitor.start()
            print(f"[Nova/{self.name}] Battery monitor ready")
            return True
        except Exception as e:
            print(f"[Nova/{self.name}] Setup failed: {e}")
            return False

    def _on_plug(self, pct):
        print(f"[Nova/{self.name}] Plugged in — {pct}%")
        _notify("Charging", f"Battery at {pct}%", "normal")

    def _on_unplug(self, pct):
        print(f"[Nova/{self.name}] Unplugged — {pct}%")
        _notify("Unplugged", f"Battery at {pct}%", "normal")

    def _on_full(self, pct):
        print(f"[Nova/{self.name}] Fully charged")
        _notify("Fully Charged", f"Battery at {pct}%", "normal")

    def on_notification(self, notif):
        pass

    def teardown(self):
        try:
            self._monitor.stop()
            self._monitor.wait(1000)
        except:
            pass
