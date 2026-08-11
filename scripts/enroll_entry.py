#!/usr/bin/env python3
"""NovaUnlock — Enrollment Entry Point (GUI first, CLI fallback)"""

import os
import sys
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent
PY = sys.executable

def has_display():
    display = os.environ.get("DISPLAY", "")
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    ssh = os.environ.get("SSH_TTY", "")
    return bool((display or wayland) and not ssh)

def run_script(name):
    p = BASE / name
    if not p.exists():
        return 127
    result = subprocess.run(
        [PY, str(p)] + sys.argv[1:],
        env=os.environ.copy()
    )
    return result.returncode

def auto_detect_display():
    """Auto detect DISPLAY and XAUTHORITY"""
    import subprocess as sp

    # Try display from who command
    try:
        out = sp.check_output(['who'], text=True)
        for line in out.splitlines():
            if '(:' in line:
                d = line.split('(')[1].rstrip(')')
                os.environ['DISPLAY'] = d
                break
    except:
        pass

    if 'DISPLAY' not in os.environ:
        os.environ['DISPLAY'] = ':1'

    # XAUTHORITY
    uid = os.getuid()
    for xauth in [
        f'/run/user/{uid}/gdm/Xauthority',
        os.path.expanduser('~/.Xauthority'),
        f'/run/user/1000/gdm/Xauthority',
    ]:
        if os.path.exists(xauth):
            os.environ['XAUTHORITY'] = xauth
            break

    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    os.environ.pop('WAYLAND_DISPLAY', None)

if __name__ == '__main__':
    auto_detect_display()

    if has_display():
        print("→  Trying GUI enrollment...")
        rc = run_script("enroll_gui.pyc")
        if rc == 0:
            sys.exit(0)
        if rc == 130:
            # User cancelled the GUI (Esc) — do NOT fall back to the CLI.
            print("→  Enrollment cancelled.")
            sys.exit(130)
        print("⚠️  GUI failed — switching to CLI enrollment...")
    else:
        print("→  No display detected — using CLI enrollment...")

    rc = run_script("enroll.pyc")
    sys.exit(rc)
