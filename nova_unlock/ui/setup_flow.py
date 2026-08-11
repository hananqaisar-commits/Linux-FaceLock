#!/usr/bin/env python3
"""
nova_unlock/ui/setup_flow.py

Production-grade setup flow.
Single window, scene replacement (no overlap).
Smooth transitions with GT-R inspired audio.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
import random
import subprocess
import tempfile
import wave
import struct
from pathlib import Path
from typing import Optional
from enum import Enum

from PyQt5.QtWidgets import (QApplication, QWidget, QStackedWidget,
                              QVBoxLayout)
from PyQt5.QtCore    import (Qt, QTimer, pyqtSignal, QObject,
                              QPropertyAnimation, QEasingCurve)
from PyQt5.QtGui     import QPainter, QColor

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ════════════════════════════════════════════════════════════════
#  AUDIO  ·  Nissan GT-R inspired sound design
# ════════════════════════════════════════════════════════════════
SDIR = tempfile.mkdtemp(prefix="nova_audio_")


def _wav(name, samples, rate=44100):
    path = os.path.join(SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h', max(-32767, min(32767, int(s)))))
    return path


def _refined_startup(duration=2.4, rate=44100):
    """
    Elite startup — single sustained crystal tone with slow swell.
    Like a Patek Philippe chime, or the first note of a Stradivarius.
    Sub-bass undertone gives weight without being mechanical.
    """
    n = int(rate * duration)
    out = [0.0] * n

    # Crystalline frequencies — pure intervals
    f_root  = 220.00   # A3 — warm foundation
    f_5th   = 329.63   # E4 — perfect fifth
    f_oct   = 440.00   # A4 — octave
    f_bell  = 880.00   # A5 — high sparkle

    for i in range(n):
        t = i / rate

        # ── Slow swell envelope (no attack — fades in like dawn) ──
        if t < 0.6:
            swell = (t / 0.6) ** 2   # gradual fade-in
        elif t < 1.4:
            swell = 1.0
        else:
            swell = max(0, 1.0 - (t - 1.4) / 1.0)   # fade-out

        # ── Crystal harmonic stack (additive synthesis) ──
        # Each harmonic adds shimmer
        s = math.sin(2 * math.pi * f_root * t) * 0.18
        s += math.sin(2 * math.pi * f_5th  * t) * 0.12
        s += math.sin(2 * math.pi * f_oct  * t) * 0.10
        s += math.sin(2 * math.pi * f_bell * t) * 0.05

        # ── Subtle inharmonic shimmer (bell-like ringing) ──
        s += math.sin(2 * math.pi * (f_bell * 1.41) * t) * 0.02
        s += math.sin(2 * math.pi * (f_bell * 2.83) * t) * 0.01

        # ── Sub-bass foundation (felt, not heard) ──
        s += math.sin(2 * math.pi * 55 * t) * 0.08 * swell

        out[i] = 32767 * s * swell * 0.55

    peak = max(abs(x) for x in out) if out else 1
    if peak > 30000:
        out = [x * 30000 / peak for x in out]
    return out


def _transition_breath(duration=0.55, rate=44100):
    """
    Transition sound — like silk being drawn through air.
    Soft frequency rise, no harshness.
    """
    n = int(rate * duration)
    out = []
    prev = 0.0
    for i in range(n):
        t = i / rate

        # Filtered pink noise (warmer than white)
        noise = (random.random() - 0.5) * 2
        prev = prev * 0.96 + noise * 0.04   # heavy low-pass

        # Gentle harmonic tone
        freq = 600 + 800 * (t / duration)
        tone = math.sin(2 * math.pi * freq * t) * 0.08

        # Soft bell envelope (no sharp edges)
        env_in  = min(1.0, t / 0.10)        # smooth fade-in
        env_out = min(1.0, (duration - t) / 0.20)  # smooth fade-out
        env = env_in * env_out * 0.45

        out.append(32767 * (tone + prev * 0.4) * env)
    return out


def _refined_click(duration=0.12, rate=44100):
    """
    Tap sound — like a fingernail on fine crystal.
    Single bright impulse with quick decay. No metallic harshness.
    """
    n = int(rate * duration)
    out = []
    for i in range(n):
        t = i / rate

        # Bright fundamental — two pure tones (interval)
        s = math.sin(2 * math.pi * 1760 * t) * 0.32   # A6
        s += math.sin(2 * math.pi * 2637 * t) * 0.18  # E7

        # Exponential decay (bell-like)
        env = math.exp(-t * 45)
        out.append(32767 * s * env * 0.45)
    return out


def _success_revelation(duration=1.6, rate=44100):
    """
    Success — slow ascending revelation.
    Three notes rising, each held longer than the last.
    Final note resonates and decays gracefully.
    """
    n = int(rate * duration)
    out = [0.0] * n

    # Major triad ascending — C, E, G (then sustained chord)
    notes = [
        (523.25, 0.00, 0.30, 0.30),   # C5
        (659.25, 0.18, 0.28, 0.50),   # E5
        (783.99, 0.40, 0.32, 1.10),   # G5 (held longest)
    ]

    for freq, start_t, vol, decay_dur in notes:
        start_i = int(rate * start_t)
        note_n = int(rate * decay_dur)
        for i in range(min(note_n, n - start_i)):
            t = i / rate

            # Bell decay envelope
            env = math.exp(-t * 2.2) * vol

            # Fundamental + harmonics
            s = math.sin(2 * math.pi * freq * t) * 1.0
            s += math.sin(2 * math.pi * freq * 2 * t) * 0.30
            s += math.sin(2 * math.pi * freq * 3 * t) * 0.12
            s += math.sin(2 * math.pi * freq * 4 * t) * 0.05

            # Slight inharmonic for bell timbre
            s += math.sin(2 * math.pi * freq * 2.76 * t) * 0.04

            if start_i + i < n:
                out[start_i + i] += 32767 * env * s

    peak = max(abs(x) for x in out) if out else 1
    if peak > 30000:
        out = [x * 30000 / peak for x in out]
    return out


# Generate refined sounds
SND_STARTUP    = _wav("startup.wav",    _refined_startup())
SND_TRANSITION = _wav("transition.wav", _transition_breath())
SND_CLICK      = _wav("click.wav",      _refined_click())
SND_SUCCESS    = _wav("success.wav",    _success_revelation())


def play(path: str):
    """Play sound asynchronously"""
    try:
        subprocess.Popen(
            ["paplay", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ}
        )
    except Exception:
        try:
            subprocess.Popen(
                ["aplay", "-q", path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
#  SCENE ENUM
# ════════════════════════════════════════════════════════════════
class Scene(Enum):
    GREETER = "greeter"
    SPLASH  = "splash"
    WIZARD  = "wizard"
    NONE    = "none"




# ════════════════════════════════════════════════════════════════
#  ENROLLMENT STATUS
# ════════════════════════════════════════════════════════════════
def check_enrollment_status(username: str) -> dict:
    """
    Check if user is already enrolled.
    Returns: {
        "enrolled": bool,
        "user": str,
        "samples": int,
        "data_path": Path | None,
    }
    """
    result = {
        "enrolled": False,
        "user": username,
        "samples": 0,
        "data_path": None,
    }

    try:
        nova_root = Path.home() / "NovaUnlock"
        faces_dir = nova_root / "data" / "faces"
        meta_file = faces_dir / "users_meta.json"
        face_file = faces_dir / f"{username}.npy"

        if face_file.exists():
            result["enrolled"] = True
            result["data_path"] = face_file

            # Read metadata
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text())
                    if username in meta:
                        result["samples"] = meta[username].get("samples", 0)
                except Exception:
                    pass
    except Exception as e:
        print(f"[Nova] Enrollment check error: {e}")

    return result


# ════════════════════════════════════════════════════════════════
#  SETUP FLOW MANAGER
# ════════════════════════════════════════════════════════════════
class SetupFlow(QObject):
    """
    Manages scene transitions in a way that:
    - Only ONE scene visible at a time
    - Window stays at same position
    - Smooth fade-out → swap → fade-in transitions
    - Audio cues for major events
    """

    finished = pyqtSignal(bool, str)

    def __init__(self, app: QApplication, username: Optional[str] = None,
                 samples: int = 10, appearance: str = "auto",
                 force_setup: bool = False, mode: str = "auto"):
        super().__init__()
        self.app = app
        self.username = username or os.environ.get("USER", "user")
        self.samples = samples
        self.appearance = appearance
        self.force_setup = force_setup
        self.mode = mode  # "auto", "enroll", "reenroll"

        self.current_widget: Optional[QWidget] = None
        self.current_scene: Scene = Scene.NONE
        self.window_pos: Optional[tuple] = None

        self.success = False

        # Check enrollment status
        self.status = check_enrollment_status(self.username)
        print(f"[Nova] Enrollment status: {self.status}")

    def start(self):
        """Smart entry — decide what to show based on state"""
        # CRITICAL: Prevent Qt from auto-quitting when widgets close
        # We control the lifecycle manually
        self.app.setQuitOnLastWindowClosed(False)

        play(SND_STARTUP)

        if self.mode == "reenroll":
            # Re-enrollment: skip greeter+splash, go straight to wizard
            print("[Nova] Re-enrollment mode → wizard directly")
            self._start_timer = QTimer()
            self._start_timer.setSingleShot(True)
            self._start_timer.timeout.connect(self._show_wizard)
            self._start_timer.start(300)
            return

        if self.mode == "enroll":
            # Forced enrollment: full flow
            print("[Nova] Full setup flow")
            self._show_greeter()
            return

        # AUTO mode — smart routing
        if self.status["enrolled"] and not self.force_setup:
            # Already enrolled — show greeter + already-enrolled screen
            samples = self.status["samples"]
            print(f"[Nova] User already enrolled ({samples} samples)")
            self._show_greeter()
            # Will route to "already enrolled" after greeter
            self._next_after_greeter = "already_enrolled"
        else:
            # Fresh setup
            print("[Nova] First-time setup")
            self._show_greeter()
            self._next_after_greeter = "splash"

    # ────────────────────────────────────────────────────────
    # SCENE SHOWERS
    # ────────────────────────────────────────────────────────
    def _show_greeter(self):
        """Show greeter scene"""
        from nova_unlock.ui.greeter import Greeter

        self._close_current()

        widget = Greeter(appearance=self.appearance, duration=2.8)
        widget.finished.connect(self._on_greeter_done)

        self._show_widget(widget, Scene.GREETER)

    def _show_splash(self):
        """Show splash scene"""
        from nova_unlock.ui.onboarding_splash import OnboardingSplash

        self._close_current()
        play(SND_TRANSITION)

        widget = OnboardingSplash(appearance=self.appearance)
        widget.get_started_clicked.connect(self._on_continue)
        widget.skip_clicked.connect(self._on_skip)
        widget.settings_clicked.connect(self._on_settings)

        self._show_widget(widget, Scene.SPLASH)

    def _show_wizard(self):
        """Show enrollment wizard with full error handling"""
        print("[Nova] ▶ Opening wizard...")

        try:
            from nova_unlock.ui.enrollment_wizard import EnrollmentWizard
            print("[Nova]   ✓ Import OK")

            self._close_current()
            print("[Nova]   ✓ Previous scene closed")

            play(SND_TRANSITION)

            print(f"[Nova]   Creating wizard: user={self.username}, samples={self.samples}")
            widget = EnrollmentWizard(
                username=self.username,
                samples=self.samples
            )
            print("[Nova]   ✓ Wizard created")

            widget.finished_signal.connect(self._on_wizard_done)
            print("[Nova]   ✓ Signal connected")

            self._show_widget(widget, Scene.WIZARD)
            print("[Nova]   ✓ Wizard shown")

        except Exception as e:
            import traceback
            print("[Nova] ✗ WIZARD ERROR:")
            traceback.print_exc()
            print(f"[Nova]   Error: {e}")
            self.success = False
            self.finished.emit(False, self.username)
            QTimer.singleShot(500, self.app.quit)

    # ────────────────────────────────────────────────────────
    # CORE SCENE MANAGEMENT
    # ────────────────────────────────────────────────────────
    def _show_widget(self, widget: QWidget, scene: Scene):
        """Show widget at remembered window position"""
        self.current_widget = widget
        self.current_scene = scene

        # Set position
        if self.window_pos is not None:
            widget.move(*self.window_pos)
        else:
            # First time — center on screen
            scr = self.app.primaryScreen().geometry()
            x = (scr.width() - widget.width()) // 2
            y = (scr.height() - widget.height()) // 2
            widget.move(x, y)
            self.window_pos = (x, y)

        widget.show()
        widget.raise_()
        widget.activateWindow()

    def _close_current(self):
        """Close current widget but remember its position"""
        if self.current_widget is not None:
            try:
                self.window_pos = (self.current_widget.x(),
                                   self.current_widget.y())
                print(f"[Nova]   Saved position: {self.window_pos}")
            except Exception as e:
                print(f"[Nova]   Position save error: {e}")

            try:
                self.current_widget.close()
                self.current_widget.deleteLater()
                print("[Nova]   Widget closed")
            except Exception as e:
                print(f"[Nova]   Close error: {e}")

            self.current_widget = None

    # ────────────────────────────────────────────────────────
    # EVENT HANDLERS
    # ────────────────────────────────────────────────────────
    def _on_greeter_done(self):
        """Greeter finished — route based on state"""
        next_screen = getattr(self, "_next_after_greeter", "splash")
        self._greeter_timer = QTimer()
        self._greeter_timer.setSingleShot(True)
        if next_screen == "already_enrolled":
            self._greeter_timer.timeout.connect(self._show_already_enrolled)
        else:
            self._greeter_timer.timeout.connect(self._show_splash)
        self._greeter_timer.start(100)

    def _show_already_enrolled(self):
        """Show 'already enrolled' screen with re-enroll option"""
        samples = self.status["samples"]
        print(f"[Nova] ✅ Face ID already set up for: {self.username}")
        print(f"[Nova]    Samples: {samples}")
        print(f"[Nova]    To re-enroll: --mode reenroll")
        self.success = True
        self._enrolled_timer = QTimer()
        self._enrolled_timer.setSingleShot(True)
        self._enrolled_timer.timeout.connect(self.app.quit)
        self._enrolled_timer.start(500)

    def _on_continue(self):
        """User clicked Continue — show wizard"""
        print("[Nova] ▶ Continue clicked")
        play(SND_CLICK)

        # CRITICAL: Don't let splash close before we transition
        # Create a timer owned by self (SetupFlow), not splash
        self._continue_timer = QTimer()
        self._continue_timer.setSingleShot(True)
        self._continue_timer.timeout.connect(self._show_wizard)
        self._continue_timer.start(200)
        print("[Nova]   Timer started → wizard in 200ms")

    def _on_skip(self):
        """User skipped"""
        play(SND_CLICK)
        print("[Nova] Setup skipped")
        self.success = False
        self._close_current()
        self._exit_timer = QTimer()
        self._exit_timer.setSingleShot(True)
        self._exit_timer.timeout.connect(self.app.quit)
        self._exit_timer.start(200)

    def _on_settings(self):
        """Settings clicked — placeholder"""
        play(SND_CLICK)
        print("[Nova] Settings (TODO)")

    def _on_wizard_done(self, success, username):
        """Wizard finished"""
        if success:
            play(SND_SUCCESS)
            print(f"[Nova] ✅ Face ID enrolled: {username}")
        else:
            print(f"[Nova] ⚠️  Enrollment cancelled/failed")

        self.success = success
        self.finished.emit(success, username)
        self._done_timer = QTimer()
        self._done_timer.setSingleShot(True)
        self._done_timer.timeout.connect(self.app.quit)
        self._done_timer.start(800 if success else 300)


# ════════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════════
def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Nova · Face ID Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Auto mode (smart routing):
    setup_flow.py --user hanan

  First-time enrollment (full flow):
    setup_flow.py --user hanan --mode enroll

  Re-enrollment (skip greeter/splash):
    setup_flow.py --user hanan --mode reenroll

  Force setup even if already enrolled:
    setup_flow.py --user hanan --force
""")
    ap.add_argument("--user", default=None, help="Username")
    ap.add_argument("--samples", type=int, default=16,
                    help="Number of samples (default: 10)")
    ap.add_argument("--theme", default="auto",
                    choices=["auto", "dark", "light"])
    ap.add_argument("--mode", default="auto",
                    choices=["auto", "enroll", "reenroll"],
                    help="Setup mode")
    ap.add_argument("--force", action="store_true",
                    help="Force re-enrollment even if already enrolled")
    args = ap.parse_args()

    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)

    flow = SetupFlow(
        app,
        username=args.user,
        samples=args.samples,
        appearance=args.theme,
        force_setup=args.force,
        mode=args.mode,
    )
    flow.start()

    rc = app.exec_()
    sys.exit(0 if flow.success else 1)


if __name__ == "__main__":
    main()
