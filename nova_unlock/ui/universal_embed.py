#!/usr/bin/env python3
"""
NovaUnlock — Universal Lock Screen Embedder v4.5
Supports: GNOME, XFCE, KDE, Cinnamon, Mint, LightDM, SDDM, GDM
"""

import os
import sys
import subprocess
from pathlib import Path


def _run(cmd, timeout=2):
    try:
        r = subprocess.run(
            cmd, capture_output=True,
            text=True, timeout=timeout
        )
        return r.stdout.strip()
    except Exception:
        return ""


# ══════════════════════════════════════════════
# DESKTOP ENVIRONMENT DETECTION
# ══════════════════════════════════════════════

def detect_desktop():
    """Detect current desktop environment"""
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session = os.environ.get("DESKTOP_SESSION", "").lower()
    gdmsession = os.environ.get("GDMSESSION", "").lower()

    combined = f"{de} {session} {gdmsession}"

    if any(x in combined for x in ["gnome", "ubuntu", "pop"]):
        return "gnome"
    elif any(x in combined for x in ["xfce", "xubuntu"]):
        return "xfce"
    elif any(x in combined for x in ["kde", "plasma", "kubuntu"]):
        return "kde"
    elif any(x in combined for x in ["cinnamon", "mint"]):
        return "cinnamon"
    elif any(x in combined for x in ["mate"]):
        return "mate"
    elif any(x in combined for x in ["lxde", "lxqt"]):
        return "lxde"
    elif any(x in combined for x in ["budgie"]):
        return "budgie"

    # Fallback: check running processes
    procs = _run(["ps", "aux"])
    if "gnome-shell" in procs:
        return "gnome"
    elif "xfce4-session" in procs:
        return "xfce"
    elif "plasmashell" in procs:
        return "kde"
    elif "cinnamon" in procs:
        return "cinnamon"
    elif "mate-session" in procs:
        return "mate"

    return "unknown"


def detect_display_manager():
    """Detect display manager / greeter"""
    procs = _run(["ps", "aux"])

    if "gdm" in procs:
        return "gdm"
    elif "lightdm" in procs:
        return "lightdm"
    elif "sddm" in procs:
        return "sddm"
    elif "lxdm" in procs:
        return "lxdm"
    elif "slim" in procs:
        return "slim"

    # Check systemd
    for dm in ["gdm", "gdm3", "lightdm", "sddm", "lxdm"]:
        r = _run(["systemctl", "is-active", dm])
        if r == "active":
            return dm

    return "unknown"


# ══════════════════════════════════════════════
# LOCK SCREEN WINDOW FINDER
# ══════════════════════════════════════════════

LOCK_CLASSES = {
    "gnome": [
        "gnome-shell",
        "GNOME Shell",
        "org.gnome.Shell",
        "gnome-screensaver",
        "Gjs",
        "mutter",
        "unlock-dialog",
    ],
    "xfce": [
        "xfce4-screensaver",
        "xfce4-screensaver-dialog",
        "Xfce4-screensaver",
    ],
    "kde": [
        "kscreenlocker_greet",
        "kscreensaver",
        "org.kde.kscreenlocker",
    ],
    "cinnamon": [
        "cinnamon-screensaver",
        "Cinnamon-screensaver",
    ],
    "mate": [
        "mate-screensaver",
        "Mate-screensaver",
    ],
    "lxde": [
        "i3lock",
        "xscreensaver",
        "slock",
    ],
    "budgie": [
        "gnome-screensaver",
        "budgie-screensaver",
    ],
}

LOCK_NAMES = [
    "Screen Saver",
    "screensaver",
    "Lock Screen",
    "lockscreen",
    "Unlock",
    "unlock-dialog",
    "Login Window",
    "i3lock",
]


def find_lock_window(desktop=None):
    """Find lock screen window ID universally"""
    if desktop is None:
        desktop = detect_desktop()

    ids = []

    # Get classes for this desktop
    classes = LOCK_CLASSES.get(desktop, [])

    # Also check all desktops (fallback)
    all_classes = []
    for v in LOCK_CLASSES.values():
        all_classes.extend(v)

    search_classes = list(dict.fromkeys(classes + all_classes))

    # Search by class
    for cls in search_classes:
        for cmd in [
            ["xdotool", "search", "--class", cls],
            ["xdotool", "search", "--classname", cls],
        ]:
            out = _run(cmd)
            if out:
                for line in out.splitlines():
                    line = line.strip()
                    if line.isdigit():
                        ids.append(int(line))

    # Search by name
    for name in LOCK_NAMES:
        out = _run(["xdotool", "search", "--name", name])
        if out:
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    ids.append(int(line))

    # Remove duplicates
    ids = list(dict.fromkeys(ids))

    if not ids:
        return None

    # Find best window (largest visible)
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
        if best_id:
            return best_id
    except Exception:
        pass

    return ids[0] if ids else None


# ══════════════════════════════════════════════
# XLIB EMBED TRICK (CIPHER Technology)
# ══════════════════════════════════════════════

def embed_widget(widget, parent_id=None, y_pos=50, desktop=None):
    """
    Embed Qt widget into lock screen window.
    Uses CIPHER's Xlib reparenting trick.
    Works on: GNOME, XFCE, KDE, Cinnamon, MATE
    """
    try:
        from Xlib import display, X

        if parent_id is None:
            parent_id = find_lock_window(desktop)

        if not parent_id:
            return False

        child_id = int(widget.winId())
        d = display.Display()
        screen = d.screen()

        parent = d.create_resource_object("window", parent_id)
        child = d.create_resource_object("window", child_id)

        # Center horizontally
        x = max(0, (screen.width_in_pixels - widget.width()) // 2)
        y = max(0, y_pos)

        # Override redirect — bypass WM
        try:
            child.change_attributes(override_redirect=1)
        except Exception:
            pass

        # Reparent into lock screen
        try:
            child.reparent(parent, x, y)
        except Exception:
            pass

        # Configure position + size
        try:
            child.configure(
                x=x, y=y,
                width=widget.width(),
                height=widget.height(),
                border_width=0,
                stack_mode=X.Above,
            )
        except Exception:
            pass

        # Map (show) the window
        try:
            child.map()
        except Exception:
            pass

        # Raise parent too
        try:
            parent.configure(stack_mode=X.Above)
        except Exception:
            pass

        d.sync()
        d.close()
        set_xprop_hints(widget)
        gnome_set_window_above(widget)
        return True

    except Exception as e:
        return False


def raise_embedded(widget, parent_id=None, y_pos=50, desktop=None):
    """Re-raise embedded widget to top (always visible even without lock parent)."""
    if parent_id is None:
        parent_id = find_lock_window(desktop)

    if not parent_id:
        return ensure_on_top(widget, y_pos=y_pos, desktop=desktop)

    try:
        from Xlib import display, X

        child_id = int(widget.winId())
        d = display.Display()
        screen = d.screen()
        child = d.create_resource_object("window", child_id)

        x = max(0, (screen.width_in_pixels - widget.width()) // 2)
        y = max(0, y_pos)

        child.configure(
            x=x, y=y,
            width=widget.width(),
            height=widget.height(),
            border_width=0,
            stack_mode=X.Above,
        )
        child.map()
        d.sync()
        d.close()
    except Exception:
        pass

    return ensure_on_top(widget, y_pos=y_pos, desktop=desktop)


# ══════════════════════════════════════════════
# GNOME SHELL SPECIFIC (Overlay)
# ══════════════════════════════════════════════

def _window_id_hex(widget) -> str:
    return hex(int(widget.winId()))


def gnome_set_window_above(widget=None):
    """Use wmctrl to pin the face-lock UI above the desktop/lock screen."""
    try:
        if widget is not None:
            wid = str(int(widget.winId()))
            subprocess.run(
                ["wmctrl", "-i", "-r", wid, "-b",
                 "add,above,sticky,skip_taskbar,skip_pager"],
                capture_output=True, timeout=2,
            )
        else:
            subprocess.run(
                ["wmctrl", "-r", ":ACTIVE:",
                 "-b", "add,above,sticky,skip_taskbar"],
                capture_output=True, timeout=2,
            )
    except Exception:
        pass


def set_xprop_hints(widget):
    """Set X11 hints so the widget stays above lock screen and desktop."""
    try:
        wid = _window_id_hex(widget)
        hints = [
            ([
                "xprop", "-id", wid,
                "-f", "_NET_WM_WINDOW_TYPE", "32a",
                "-set", "_NET_WM_WINDOW_TYPE",
                "_NET_WM_WINDOW_TYPE_DOCK,_NET_WM_WINDOW_TYPE_UTILITY",
            ], 2),
            ([
                "xprop", "-id", wid,
                "-f", "_NET_WM_STATE", "32a",
                "-set", "_NET_WM_STATE",
                "_NET_WM_STATE_ABOVE,_NET_WM_STATE_STICKY,"
                "_NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_SKIP_PAGER",
            ], 2),
            ([
                "xprop", "-id", wid,
                "-f", "_NET_WM_WINDOW_OPACITY", "32c",
                "-set", "_NET_WM_WINDOW_OPACITY", "0xffffffff",
            ], 2),
        ]
        for cmd, timeout in hints:
            subprocess.run(cmd, capture_output=True, timeout=timeout)
    except Exception:
        pass


def ensure_on_top(widget, y_pos=50, desktop=None):
    """
    Force the face-lock widget to remain visible above desktop/lock screen.
    Called repeatedly while the lock screen is active.
    """
    try:
        from PyQt5.QtCore import Qt

        widget.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.X11BypassWindowManagerHint
            | Qt.Tool
        )
        widget.setAttribute(Qt.WA_ShowWithoutActivating, True)
        widget.show()

        # Center on active screen
        try:
            screen = widget.screen().availableGeometry()
        except Exception:
            from PyQt5.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + max(0, (screen.width() - widget.width()) // 2)
        y = screen.y() + max(0, y_pos)
        widget.move(x, y)
        widget.raise_()

        set_xprop_hints(widget)
        gnome_set_window_above(widget)

        wid = int(widget.winId())
        subprocess.run(
            ["xdotool", "windowraise", str(wid)],
            capture_output=True, timeout=2,
        )
        subprocess.run(
            ["xdotool", "windowactivate", "--sync", str(wid)],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass

    # Re-embed when lock parent exists (XFCE/KDE/Cinnamon)
    if desktop is None:
        desktop = detect_desktop()
    parent_id = find_lock_window(desktop)
    if parent_id:
        embed_widget(widget, parent_id=parent_id, y_pos=y_pos, desktop=desktop)
    return True


if __name__ == "__main__":
    desktop = detect_desktop()
    dm = detect_display_manager()
    print(f"Desktop: {desktop}")
    print(f"Display Manager: {dm}")
    lock_id = find_lock_window(desktop)
    print(f"Lock Window ID: {lock_id}")


# ══════════════════════════════════════════════
# GNOME SHELL SPECIFIC OVERLAY
# ══════════════════════════════════════════════

def embed_gnome_shell(widget) -> bool:
    """
    GNOME Shell lock screen — special approach
    Uses fullscreen overlay instead of reparent
    Because GNOME Shell is sandboxed
    """
    try:
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QDesktopWidget

        # Get screen geometry
        screen = QDesktopWidget().screenGeometry()

        # Position on top of lock screen
        widget.setWindowFlags(
            Qt.FramelessWindowHint        |
            Qt.WindowStaysOnTopHint       |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )

        # Center on screen
        x = (screen.width() - widget.width()) // 2
        y = 50
        widget.move(x, y)

        # Set window type to DOCK
        # This makes it visible above lock screen
        try:
            import subprocess
            wid = hex(int(widget.winId()))
            subprocess.run([
                "xprop", "-id", wid,
                "-f", "_NET_WM_WINDOW_TYPE", "32a",
                "-set", "_NET_WM_WINDOW_TYPE",
                "_NET_WM_WINDOW_TYPE_DOCK"
            ], capture_output=True, timeout=2)
            subprocess.run([
                "xprop", "-id", wid,
                "-f", "_NET_WM_STATE", "32a",
                "-set", "_NET_WM_STATE",
                "_NET_WM_STATE_ABOVE"
            ], capture_output=True, timeout=2)
        except Exception:
            pass

        ensure_on_top(widget, y_pos=y)
        return True

    except Exception:
        return False


def smart_embed(widget, y_pos=50) -> bool:
    """
    Smart embed — tries best method for current desktop
    """
    desktop = detect_desktop()
    dm = detect_display_manager()

    # GNOME / Ubuntu / GDM: overlay above shell (reparent rarely works)
    if desktop == "gnome" or dm in ("gdm", "gdm3"):
        if embed_gnome_shell(widget):
            return True
        success = embed_widget(widget, y_pos=y_pos, desktop=desktop)
        ensure_on_top(widget, y_pos=y_pos, desktop=desktop)
        return success

    success = embed_widget(widget, y_pos=y_pos, desktop=desktop)
    if not success:
        embed_gnome_shell(widget)
    ensure_on_top(widget, y_pos=y_pos, desktop=desktop)
    return True
