#!/usr/bin/env python3
"""
Nova Welcome — Launcher for hello_overlay.
Spawns overlay process, sends hello via Unix socket.
Instant display after face unlock.
"""
from __future__ import annotations

import os
import sys
import time
import json
import socket
import subprocess
import getpass
from pathlib import Path
from typing import Optional


SOCKET_PATH = "/tmp/nova_hello.sock"
OVERLAY_MODULE = "nova_unlock.ui.hello_overlay"


def _ensure_overlay_running(timeout: float = 3.0) -> bool:
    """Ensure hello_overlay subprocess is up and socket is ready."""
    if os.path.exists(SOCKET_PATH):
        return True

    try:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XAUTHORITY",
                       os.path.expanduser("~/.Xauthority"))

        # Find nova root
        root = Path(__file__).parent.parent.parent

        subprocess.Popen(
            [sys.executable, "-m", OVERLAY_MODULE],
            cwd=str(root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True)
    except Exception as e:
        print(f"[Nova/welcome] Spawn failed: {e}",
              file=sys.stderr)
        return False

    # Wait for socket up to `timeout` seconds
    steps = int(timeout / 0.1)
    for _ in range(steps):
        if os.path.exists(SOCKET_PATH):
            return True
        time.sleep(0.1)

    return os.path.exists(SOCKET_PATH)


def _send(payload: dict, timeout: float = 1.5) -> bool:
    """Send JSON payload to overlay socket."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        s.connect(SOCKET_PATH)
        data = (json.dumps(payload) + "\n").encode()
        s.sendall(data)
        s.close()
        return True
    except Exception as e:
        print(f"[Nova/welcome] Send failed: {e}",
              file=sys.stderr)
        return False


def _get_username() -> str:
    """Cross-platform username, capitalized."""
    try:
        name = getpass.getuser()
    except Exception:
        name = (os.environ.get("USER")
                or os.environ.get("USERNAME")
                or "user")
    if name.lower() == "root":
        # Fall back to SUDO_USER when running under sudo
        name = os.environ.get("SUDO_USER") or name
    return (name or "user").strip().capitalize()


def show_welcome(username: Optional[str] = None,
                 duration: float = 4.5) -> bool:
    """
    Public API — show hello + username overlay.
    Non-blocking. Instant.
    """
    name = username or _get_username()

    if not _ensure_overlay_running():
        print("[Nova/welcome] Overlay not ready — skipping",
              file=sys.stderr)
        return False

    return _send({
        "action":   "hello",
        "text":     f"hello, {name}",
        "duration": duration,
    })


# ─── Standalone test ─────────────────────────────────────
def main():
    user = sys.argv[1] if len(sys.argv) > 1 else None
    ok = show_welcome(user)
    print(f"[Nova/welcome] {'✓ shown' if ok else '✗ failed'}")
    # Keep alive briefly so subprocess can finish rendering
    time.sleep(0.3)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
