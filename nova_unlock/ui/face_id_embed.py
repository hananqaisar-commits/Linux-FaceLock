#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

from nova_unlock.ui.face_unlock_widget import Sig, FaceUnlockWidget, FaceWorker

def _run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    except Exception:
        return ""

def _find_xfce_lock_window():
    ids = []

    for cmd in [
        ["xdotool", "search", "--class", "xfce4-screensaver"],
        ["xdotool", "search", "--name", "xfce4-screensaver"],
        ["xdotool", "search", "--name", "Screen Saver"],
        ["xdotool", "search", "--class", "Xfce4-screensaver"],
    ]:
        out = _run(cmd)
        if out:
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))

    ids = list(dict.fromkeys(ids))
    if not ids:
        return None

    try:
        from Xlib import display, X
        d = display.Display()
        best_id = None
        best_area = -1

        for wid in ids:
            try:
                w = d.create_resource_object("window", wid)
                g = w.get_geometry()
                attrs = w.get_attributes()
                area = g.width * g.height
                if attrs.map_state == X.IsViewable and area > best_area:
                    best_area = area
                    best_id = wid
            except Exception:
                pass

        d.close()
        return best_id
    except Exception:
        return ids[0] if ids else None

def _embed_widget(widget, y_pos=50):
    try:
        from Xlib import display, X

        parent_id = _find_xfce_lock_window()
        if not parent_id:
            return False

        child_id = int(widget.winId())

        d = display.Display()
        screen = d.screen()
        parent = d.create_resource_object("window", parent_id)
        child = d.create_resource_object("window", child_id)

        x = max(0, (screen.width_in_pixels - widget.width()) // 2)
        y = max(0, y_pos)

        try:
            child.change_attributes(override_redirect=1)
        except Exception:
            pass

        try:
            child.reparent(parent, x, y)
        except Exception:
            pass

        try:
            child.configure(
                x=x,
                y=y,
                width=widget.width(),
                height=widget.height(),
                border_width=0,
                stack_mode=X.Above,
            )
        except Exception:
            pass

        try:
            child.map()
        except Exception:
            pass

        try:
            parent.configure(stack_mode=X.Above)
        except Exception:
            pass

        d.sync()
        d.close()
        return True

    except Exception:
        return False

def _raise_embedded(widget, y_pos=50):
    try:
        from Xlib import display, X

        parent_id = _find_xfce_lock_window()
        if not parent_id:
            return False

        child_id = int(widget.winId())

        d = display.Display()
        screen = d.screen()
        child = d.create_resource_object("window", child_id)

        x = max(0, (screen.width_in_pixels - widget.width()) // 2)
        y = max(0, y_pos)

        child.configure(
            x=x,
            y=y,
            width=widget.width(),
            height=widget.height(),
            border_width=0,
            stack_mode=X.Above,
        )
        child.map()
        d.sync()
        d.close()
        return True
    except Exception:
        return False

class FaceIDLoginApp:
    def __init__(self):
        self.result = None

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()
        w = FaceUnlockWidget(sig, demo_mode=False)

        w.show()
        app.processEvents()

        # pehle top-level dikhao
        try:
            w.raise_()
            w.activateWindow()
        except Exception:
            pass

        # phir lock window ke andar embed karo
        QTimer.singleShot(150, lambda: _embed_widget(w, 50))
        QTimer.singleShot(400, lambda: _embed_widget(w, 50))
        QTimer.singleShot(800, lambda: _embed_widget(w, 50))
        QTimer.singleShot(1200, lambda: _embed_widget(w, 50))

        keep_top = QTimer()
        keep_top.timeout.connect(lambda: _raise_embedded(w, 50))
        keep_top.start(250)

        wk = FaceWorker(sig)

        def done(name):
            self.result = name
            keep_top.stop()
            QTimer.singleShot(2800, app.quit)

        sig.ok.connect(done)
        wk.start()
        app.exec_()
        wk.stop()
        wk.wait(2000)
        return self.result
