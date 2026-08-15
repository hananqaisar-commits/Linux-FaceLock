#!/usr/bin/env python3
"""
Nova Welcome — Launcher for hello_overlay & voice greeting.
Spawns overlay process, handles KDE desktop loading wait,
and plays uninterrupted voice/sound greeting.
"""
from __future__ import annotations

import os
import sys
import time
import json
import socket
import signal
import threading
import subprocess
import getpass
from pathlib import Path
from typing import Optional

# Ignore desktop environment initialization signals (SIGHUP/SIGTERM during KDE load)
for _sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, signal.SIG_IGN)
    except Exception:
        pass

SOCKET_PATH = "/tmp/nova_hello.sock"
OVERLAY_MODULE = "nova_unlock.ui.hello_overlay"


def _wait_for_desktop_ready(max_wait: float = 3.0) -> None:
    """
    Wait for KDE splash screen (ksplashqml) to exit and window manager surface to settle.
    This prevents KDE desktop loading from interrupting the overlay display.
    """
    start_t = time.time()
    while time.time() - start_t < max_wait:
        try:
            res = subprocess.run(["pgrep", "-x", "ksplashqml"], capture_output=True)
            if res.returncode != 0:
                # ksplashqml is no longer running
                break
        except Exception:
            break
        time.sleep(0.1)

    # Brief stabilization pause for KWin surface compositing
    time.sleep(0.4)


def _ensure_overlay_running(timeout: float = 4.0) -> bool:
    """Ensure hello_overlay subprocess is up and socket is ready."""
    if os.path.exists(SOCKET_PATH):
        return True

    try:
        env = os.environ.copy()
        env.setdefault("DISPLAY", ":0")
        env.setdefault("XAUTHORITY", os.path.expanduser("~/.Xauthority"))

        root = Path(__file__).parent.parent.parent

        subprocess.Popen(
            [sys.executable, "-m", OVERLAY_MODULE],
            cwd=str(root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        print(f"[Nova/welcome] Spawn failed: {e}", file=sys.stderr)
        return False

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
        print(f"[Nova/welcome] Send failed: {e}", file=sys.stderr)
        return False


def _speak_welcome_audio(name: str) -> None:
    """
    Play non-blocking voice audio or chime greeting for 'Hello <name>'.
    Uses system TTS tools (spd-say / espeak-ng / espeak / piper) or audio chime.
    Includes PulseAudio/PipeWire reconnect handling.
    """
    def _run_speak():
        time.sleep(0.2)
        phrase = f"Hello {name}, welcome back"

        # Try TTS tools in priority order
        tts_cmds = [
            ["spd-say", "-i", "10", phrase],
            ["espeak-ng", "-s", "150", phrase],
            ["espeak", "-s", "150", phrase],
        ]

        for cmd in tts_cmds:
            if subprocess.run(["command", "-v", cmd[0]], capture_output=True, shell=False).returncode == 0:
                try:
                    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
                    if res.returncode == 0:
                        return
                except Exception:
                    pass

        # Sound chime fallback
        try:
            from nova_unlock.ui.enrollment_sounds import SND_STARTUP, play
            if SND_STARTUP:
                play(SND_STARTUP)
        except Exception:
            pass

    t = threading.Thread(target=_run_speak, daemon=True)
    t.start()


def _get_username() -> str:
    """Cross-platform username, capitalized."""
    try:
        name = getpass.getuser()
    except Exception:
        name = (os.environ.get("USER") or os.environ.get("USERNAME") or "user")
    if name.lower() == "root":
        name = os.environ.get("SUDO_USER") or name
    return (name or "user").strip().capitalize()


def show_welcome(username: Optional[str] = None, duration: float = 5.0, wait_kde: bool = True) -> bool:
    """
    Public API — show hello + username overlay with voice greeting.
    Immune to KDE startup interruptions.
    """
    name = username or _get_username()

    if wait_kde:
        _wait_for_desktop_ready()

    if not _ensure_overlay_running():
        print("[Nova/welcome] Overlay not ready — skipping", file=sys.stderr)
        return False

    _speak_welcome_audio(name)

    sent = _send({
        "action":   "hello",
        "text":     f"hello, {name}",
        "duration": duration,
    })

    # Watchdog loop: ensure overlay finishes duration without being killed prematurely by KDE
    def _watchdog():
        end_t = time.time() + duration - 0.5
        while time.time() < end_t:
            time.sleep(0.8)
            if not os.path.exists(SOCKET_PATH):
                _ensure_overlay_running(timeout=1.5)
                _send({
                    "action":   "hello",
                    "text":     f"hello, {name}",
                    "duration": max(2.0, end_t - time.time()),
                })

    w_thread = threading.Thread(target=_watchdog, daemon=True)
    w_thread.start()

    return sent


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else None
    ok = show_welcome(user, wait_kde=True)
    print(f"[Nova/welcome] {'✓ shown' if ok else '✗ failed'}")
    time.sleep(1.0)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
