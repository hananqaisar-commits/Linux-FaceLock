#!/usr/bin/env python3
"""
NovaUnlock Face Unlock UI — PyQt5
iOS-equivalent animations:
  - CABasicAnimation     → QTimer + arc rotation (scanning ring)
  - CAKeyframeAnimation  → keyframe array shake on fail
  - CAShapeLayer/strokeEnd → arc spanAngle 0→360 (checkmark draw-on)
  - CASpringAnimation    → spring ODE: mass/stiffness/damping
  - Metal particles/blur → QPainter radial gradient particle system
  - UIViewPropertyAnimator → spring timing unlock→home transition
"""
import sys, math, time, struct, wave, tempfile, os, subprocess, random
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject, QThread)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont,
                              QRadialGradient, QLinearGradient,
                              QBrush, QPainterPath, QConicalGradient)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ══════════════════════════════════════════════════════════════
# SOUND SYNTHESIS
# ══════════════════════════════════════════════════════════════
SDIR = tempfile.mkdtemp(prefix="nova_snd_")

def _wav(name, samples, rate=44100):
    path = os.path.join(SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h', max(-32767, min(32767, int(s)))))
    return path

def _sin(freq, dur, vol=0.5, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t   = i / rate
        env = min(1, min(t * 30, (dur - t) * 20))
        out.append(32767 * vol * env * math.sin(2 * math.pi * freq * t))
    return out

def _silence(dur, rate=44100):
    return [0] * int(rate * dur)

def _sin_layered(freqs, dur, vols, rate=44100):
    """Mix multiple sine waves for rich tone."""
    n = int(rate * dur); out = [0.0] * n
    for freq, vol in zip(freqs, vols):
        for i in range(n):
            t   = i / rate
            env = min(1, min(t * 40, (dur - t) * 25))
            out[i] += 32767 * vol * env * math.sin(2 * math.pi * freq * t)
    return out

def _bell(freq, dur, vol=0.4, rate=44100):
    """Bell-like tone with exponential decay (iOS notification style)."""
    n = int(rate * dur); out = []
    for i in range(n):
        t   = i / rate
        # Exponential decay envelope (bell shape)
        env = math.exp(-t * 4.5) * vol
        # Fundamental + harmonics for bell timbre
        s   = math.sin(2 * math.pi * freq * t) * 1.0
        s  += math.sin(2 * math.pi * freq * 2.0 * t) * 0.3
        s  += math.sin(2 * math.pi * freq * 3.0 * t) * 0.15
        s  += math.sin(2 * math.pi * freq * 4.0 * t) * 0.08
        out.append(32767 * env * s * 0.5)
    return out

def _whoosh(start_f, end_f, dur, vol=0.3, rate=44100):
    """Filtered noise whoosh (Dynamic Island expand sound)."""
    import random
    n = int(rate * dur); out = []
    prev = 0.0
    for i in range(n):
        t      = i / rate
        # Frequency sweep
        freq   = start_f + (end_f - start_f) * (t / dur)
        # Low-pass filtered noise
        noise  = random.uniform(-1, 1)
        prev   = prev * 0.85 + noise * 0.15
        # Envelope: quick attack, slow decay
        env    = min(1, t * 30) * math.exp(-t * 3) * vol
        # Mix tonal + noise
        tone   = math.sin(2 * math.pi * freq * t) * 0.5
        out.append(32767 * env * (tone + prev * 0.4))
    return out

def mk_pop():
    """iOS Dynamic Island POP sound - subtle expand whoosh."""
    s = _whoosh(180, 800, 0.18, vol=0.18)
    s2 = _sin_layered([1200, 1800], 0.08, [0.025, 0.015])
    for i in range(min(len(s), len(s2))):
        s[i] += s2[i]
    return _wav("pop.wav", s)

def mk_scan():
    """
    iOS Face ID scan sound — barely audible soft click.
    Real iPhone scan is almost silent, just a subtle cue.
    """
    rate = 44100
    s = []
    dur = 0.12
    for i in range(int(rate * dur)):
        t = i / rate
        # Very soft, quick-decay click at 1200Hz
        freq = 1200
        env = math.exp(-t * 25) * 0.10
        val = math.sin(2 * math.pi * freq * t)
        val += math.sin(2 * math.pi * freq * 2 * t) * 0.3
        s.append(32767 * env * val)
    return _wav("scan.wav", s)

def _pluck(freq, dur, vol=0.4, rate=44100):
    """Karplus-Strong style pluck (real iOS unlock pluck)."""
    import random
    n = int(rate * dur)
    delay = max(1, int(rate / freq))
    buf = [random.uniform(-1, 1) * vol for _ in range(delay)]
    out = []
    for i in range(n):
        idx = i % delay
        # Smooth average for damping
        nxt = (buf[idx] + buf[(idx + 1) % delay]) * 0.498
        buf[idx] = nxt
        # Decay envelope
        t = i / rate
        env = math.exp(-t * 3.5)
        out.append(32767 * nxt * env)
    return out

def _sub_thump(freq, dur, vol=0.5, rate=44100):
    """Sub-bass thump (warm low frequency body)."""
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        # Pitch envelope: slight downward pitch bend
        f = freq * (1 + 0.3 * math.exp(-t * 15))
        # Amplitude envelope: punch + decay
        env = (1 - math.exp(-t * 80)) * math.exp(-t * 5.5) * vol
        s = math.sin(2 * math.pi * f * t)
        s += math.sin(2 * math.pi * f * 0.5 * t) * 0.4   # sub octave
        out.append(32767 * env * s)
    return out

def _sparkle(rate=44100):
    """High frequency shimmer (iOS unlock sparkle layer)."""
    out = []
    notes = [
        (2349.3, 0.0,  0.04),   # D7
        (2793.8, 0.04, 0.04),   # F7
        (3520.0, 0.08, 0.05),   # A7
        (4186.0, 0.12, 0.06),   # C8
    ]
    total_dur = 0.40
    n = int(rate * total_dur)
    out = [0.0] * n
    for freq, start_t, vol in notes:
        start_i = int(rate * start_t)
        for i in range(n - start_i):
            t = i / rate
            env = math.exp(-t * 6) * vol
            val = math.sin(2 * math.pi * freq * t)
            if start_i + i < n:
                out[start_i + i] += 32767 * env * val
    return out

def mk_ok():
    """
    Real iOS Face ID unlock sound — 3-layer synthesis:
      L1: Soft attack synth (C6 fundamental, warm)
      L2: Sub-bass thump (punch + body)  
      L3: Shimmer cascade (D7→A7 sparkle)
    Total duration: ~0.6s (matches real iPhone)
    """
    rate = 44100

    # ── Layer 1: Warm synth pluck at C6 (1046.5 Hz) ──
    # Real iOS unlock has a soft but bright pluck as lead
    lead = _pluck(1046.5, 0.60, vol=0.50)

    # Blend in perfect 5th (G6) for fullness
    fifth = _pluck(1568.0, 0.45, vol=0.22)
    for i in range(min(len(lead), len(fifth))):
        lead[i] += fifth[i]

    # ── Layer 2: Sub-bass thump (warm body) ──
    # Short punch — fades in 150ms
    thump = _sub_thump(82, 0.35, vol=0.38)

    # ── Layer 3: Sparkle shimmer ──
    # High cascade that "opens up" the sound
    sparkle = _sparkle()

    # ── Mix ──
    max_len = max(len(lead), len(thump), len(sparkle))
    out = [0.0] * max_len

    for i in range(len(lead)):
        out[i] += lead[i]
    for i in range(len(thump)):
        out[i] += thump[i] * 0.65
    for i in range(min(len(sparkle), len(out))):
        out[i] += sparkle[i] * 0.55

    # Soft limiter (prevent clipping)
    peak = max(abs(x) for x in out) if out else 1
    if peak > 30000:
        out = [x * 30000 / peak for x in out]

    return _wav("ok.wav", out)

def mk_fail():
    """iOS-style failure - descending soft 'thunk' with bass."""
    rate = 44100
    s = []

    # Descending bell tones
    s += _bell(440, 0.15, 0.25)
    s += _silence(0.02)
    s += _bell(330, 0.20, 0.28)

    # Low bass thud
    bass = []
    dur = 0.25
    for i in range(int(rate * dur)):
        t   = i / rate
        env = math.exp(-t * 8) * 0.4
        val = math.sin(2 * math.pi * 80 * t)
        val += math.sin(2 * math.pi * 55 * t) * 0.6
        bass.append(32767 * env * val)

    # Mix bass with bells
    offset = int(rate * 0.05)
    for i in range(len(bass)):
        idx = offset + i
        if idx < len(s):
            s[idx] += bass[i]
        else:
            s.append(bass[i])

    return _wav("fail.wav", s)

def mk_collapse():
    """Dynamic Island collapse - reverse pop."""
    s = _whoosh(800, 180, 0.15, vol=0.15)
    return _wav("collapse.wav", s)

SND_POP      = mk_pop()
SND_SCAN     = mk_scan()
SND_OK       = mk_ok()
SND_FAIL     = mk_fail()
SND_COLLAPSE = mk_collapse()

def play(path):
    try:
        subprocess.Popen(["aplay", "-q", path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except: pass

# ══════════════════════════════════════════════════════════════
# SPRING PHYSICS — UISpringTimingParameters equivalent
# mass, stiffness, damping ODE solver
# ══════════════════════════════════════════════════════════════
class Spring:
    """
    RK4 spring solver — same accuracy as Core Animation.
    Solves: m*x'' + d*x' + k*x = 0
    RK4 never drifts even at variable frame rates.
    """
    def __init__(self, mass=1.0, stiffness=180.0, damping=18.0):
        self.m  = mass
        self.k  = stiffness
        self.d  = damping
        self.x  = 0.0
        self.v  = 0.0

    def reset(self, x=1.0, v=0.0):
        self.x = x
        self.v = v

    def _derivatives(self, x, v):
        """Spring ODE: returns (dx/dt, dv/dt)"""
        ax = (-self.k * x - self.d * v) / self.m
        return v, ax

    def step(self, dt=0.016):
        """4th-order Runge-Kutta integration — zero drift."""
        x, v = self.x, self.v

        # RK4 stages
        dx1, dv1 = self._derivatives(x,              v             )
        dx2, dv2 = self._derivatives(x + dx1*dt*0.5, v + dv1*dt*0.5)
        dx3, dv3 = self._derivatives(x + dx2*dt*0.5, v + dv2*dt*0.5)
        dx4, dv4 = self._derivatives(x + dx3*dt,     v + dv3*dt    )

        self.x += (dt / 6.0) * (dx1 + 2*dx2 + 2*dx3 + dx4)
        self.v += (dt / 6.0) * (dv1 + 2*dv2 + 2*dv3 + dv4)
        return self.x

    @property
    def settled(self):
        return abs(self.x) < 0.0008 and abs(self.v) < 0.0008

# ══════════════════════════════════════════════════════════════
# PARTICLE SYSTEM — Metal/CAEmitterLayer equivalent
# GPU-like per-frame particle update in QPainter
# ══════════════════════════════════════════════════════════════
def _curl_noise(x, y, t, scale=0.008):
    """
    Curl noise field — same technique as Metal particle shaders.
    Creates swirling, organic turbulence (not random jitter).
    """
    # Two Perlin-like sine waves offset by 90 degrees
    # gives a divergence-free (curl) vector field
    nx  = math.sin(x * scale + t * 1.1) * math.cos(y * scale * 0.7 + t * 0.9)
    ny  = math.cos(x * scale * 0.8 + t * 0.7) * math.sin(y * scale + t * 1.3)
    # Curl: rotate gradient 90 degrees
    return ny * 0.6, -nx * 0.6

class Particle:
    __slots__ = ['x','y','vx','vy','life','max_life',
                 'r','g','b','size','alpha','spin','spin_v']

    def __init__(self, cx, cy, color):
        angle         = random.uniform(0, 2 * math.pi)
        speed         = random.uniform(0.3, 1.8)
        self.x        = cx + random.uniform(-6, 6)
        self.y        = cy + random.uniform(-6, 6)
        self.vx       = math.cos(angle) * speed
        self.vy       = math.sin(angle) * speed
        self.life     = 0.0
        self.max_life = random.uniform(0.7, 1.6)
        self.r, self.g, self.b = color
        self.size     = random.uniform(1.2, 3.8)
        self.alpha    = 1.0
        self.spin     = random.uniform(0, math.pi * 2)
        self.spin_v   = random.uniform(-2.0, 2.0)

    def update(self, dt, now=0.0):
        # ── Curl noise turbulence ──
        cx_n, cy_n = _curl_noise(self.x, self.y, now)
        self.vx += cx_n * dt * 18.0
        self.vy += cy_n * dt * 18.0

        # ── Gentle gravity + drag ──
        self.vy  += 0.018              # soft gravity
        self.vx  *= pow(0.965, dt*60)  # frame-rate independent drag
        self.vy  *= pow(0.965, dt*60)

        self.x   += self.vx * dt * 60
        self.y   += self.vy * dt * 60
        self.spin += self.spin_v * dt

        self.life += dt
        t          = self.life / self.max_life

        # ── Smooth fade: fast fade-in, slow fade-out ──
        if t < 0.15:
            self.alpha = t / 0.15          # quick appear
        else:
            # Cubic ease-out fade
            t2 = (t - 0.15) / 0.85
            self.alpha = max(0.0, 1.0 - t2 * t2 * t2)

        # Size shrinks smoothly
        self.size = max(0.3, self.size * pow(0.988, dt*60))

    @property
    def alive(self):
        return self.life < self.max_life

class ParticleSystem:
    def __init__(self):
        self.particles = []
        self._now      = 0.0

    def burst(self, cx, cy, color, n=25):
        for _ in range(n):
            self.particles.append(Particle(cx, cy, color))

    def update(self, dt):
        import time
        self._now += dt
        self.particles = [p for p in self.particles if p.alive]
        for p in self.particles:
            p.update(dt, self._now)

    def draw(self, painter):
        for p in self.particles:
            a = int(255 * p.alpha)
            if a < 5: continue
            painter.save()
            painter.setPen(Qt.NoPen)

            # Glow only for big particles (performance)
            if p.size > 2.5 and a > 40:
                glow_c = QColor(p.r, p.g, p.b, max(0, a // 5))
                painter.setBrush(QBrush(glow_c))
                painter.drawEllipse(QPointF(p.x, p.y),
                                    p.size * 1.6, p.size * 1.6)

            # Core particle
            painter.setBrush(QBrush(QColor(p.r, p.g, p.b, a)))
            painter.drawEllipse(QPointF(p.x, p.y), p.size, p.size)
            painter.restore()

# ══════════════════════════════════════════════════════════════
# KEYFRAME SHAKE — CAKeyframeAnimation equivalent
# kCAMediaTimingFunctionEaseInEaseOut shake values
# ══════════════════════════════════════════════════════════════
# Exact keyframe values from iOS Human Interface Guidelines shake
SHAKE_KEYFRAMES = [0, -12, 10, -8, 6, -4, 2, 0]

def ease_in_out(t):
    """kCAMediaTimingFunctionEaseInEaseOut"""
    return t * t * (3 - 2 * t)

def shake_at(t, duration=0.5):
    """
    CAKeyframeAnimation with kCAMediaTimingFunctionEaseInEaseOut
    Returns pixel offset at time t (0..duration)
    """
    if t <= 0 or t >= duration:
        return 0
    n      = len(SHAKE_KEYFRAMES) - 1
    seg_t  = (t / duration) * n
    idx    = int(seg_t)
    idx    = min(idx, n - 1)
    local  = seg_t - idx
    local  = ease_in_out(local)
    a      = SHAKE_KEYFRAMES[idx]
    b      = SHAKE_KEYFRAMES[idx + 1]
    return a + (b - a) * local

# ══════════════════════════════════════════════════════════════
# SIGNALS
# ══════════════════════════════════════════════════════════════
class Sig(QObject):
    ok   = pyqtSignal(str)
    fail = pyqtSignal()

# ══════════════════════════════════════════════════════════════
# MAIN WIDGET
# ══════════════════════════════════════════════════════════════
class FaceUnlockWidget(QWidget):
    IDLE = 0
    SCAN = 1
    OK   = 2
    FAIL = 3

    W  = 420         # widget width (laptop Dynamic Island)
    H  = 480         # widget height
    CX = 210         # center X
    CY = 200         # center Y (icon position when expanded)
    R  = 65          # main scanning radius
    N  = 52          # number of dots
    DS = 2.8         # dot size

    def __init__(self, sig, demo_mode=False):
        super().__init__()
        self.sig       = sig
        self.demo_mode = demo_mode
        self.sig.ok.connect(self._on_ok)
        self.sig.fail.connect(self._on_fail)

        # State
        self.ph         = self.IDLE
        self.t0         = time.time()
        self.nm         = ""
        self._fail_count= 0
        self._last_tick = time.time()

        # Springs (CASpringAnimation equivalent)
        # ── Premium springs: higher damping = no rattle ──
        self.spring_scale  = Spring(mass=1.0,  stiffness=140.0, damping=24.0)
        self.spring_opacity= Spring(mass=0.9,  stiffness=110.0, damping=20.0)
        self.spring_ring   = Spring(mass=1.2,  stiffness=130.0, damping=18.0)
        self.spring_icon   = Spring(mass=1.0,  stiffness=160.0, damping=22.0)

        # Particles (Metal/CAEmitterLayer equivalent)
        self.particles = ParticleSystem()

        # Scanning ring — CABasicAnimation rotation
        self.ring_angle   = 0.0      # current rotation
        self.ring_speed   = 0.0      # deg/frame (accelerates)
        self.ring_arc     = 0.0      # CAShapeLayer strokeEnd 0→1
        self.ring_alpha   = 0.0
        self.ring_color   = [255, 255, 255]

        # Checkmark — CAShapeLayer strokeEnd
        self.check_stroke = 0.0      # 0→1 draw-on progress
        self.check_alpha  = 0.0
        self.check_spring = Spring(mass=0.9, stiffness=180.0, damping=26.0)
        # ── Scanning ring state ──
        self.ring_progress    = 0.0
        self.ring_rot         = 0.0
        self.ring_seg_alpha   = 0.0
        self.ring_to_check    = 0.0
        self.ring_speed_ok    = 4.5
        self._ring_spring     = Spring(mass=0.8, stiffness=220.0, damping=24.0)
        self._check_draw_t    = 0.0
        self._success_phase   = 0

        # X mark
        self.x_stroke     = 0.0
        self.x_alpha      = 0.0

        # Face ring dots
        self.dot_a        = [0.7] * self.N
        self.dot_sz       = [self.DS] * self.N
        self.dot_rot      = 0.0

        # Face eye / glow
        self.face_alpha   = 0.0
        self.face_scale   = 0.55
        self.eye_alpha    = 0.0
        self.glow_alpha   = 0.0
        self.glow_color   = [100, 100, 100]
        self.face_color   = [255, 255, 255]

        # Text
        self.txt          = ""
        self.txt_alpha    = 0.0
        self.txt_color    = [255, 255, 255]

        # Ripple (CASpringAnimation pop-in equivalent)
        self.ripple_r     = 0.0
        self.ripple_alpha = 0.0

        # ── iOS/HyperOS Scanning extras ──────────────────
        # Multi-ring (HyperOS dual ring)
        self.ring2_angle  = 0.0      # counter-rotating ring
        self.ring2_alpha  = 0.0
        self.ring3_angle  = 0.0      # slow outer ring
        self.ring3_alpha  = 0.0

        # Conical gradient trail (iOS FaceID arc glow)
        self.trail_rot    = 0.0

        # Breathing pulse (HyperOS inner glow)
        self.pulse_r      = 0.0
        self.pulse_alpha  = 0.0

        # Scan line sweep (HyperOS IR sweep)
        self.scan_y       = 0.0      # -R to +R
        self.scan_dir     = 1
        self.scan_alpha   = 0.0

        # Dot wave (sequential size wave)
        self.wave_phase   = 0.0

        # Grid mesh (iOS depth sensor pattern)
        self.grid_alpha   = 0.0
        self.grid_phase   = 0.0

        # Corner brackets (HyperOS face frame)
        self.bracket_alpha= 0.0
        self.bracket_scale= 0.0

        # ── iPhone Face ID scanning mesh ──────────────────
        self.mesh_lines     = []
        self.mesh_t         = 0.0
        self.mesh_spawn_t   = 0.0
        self.mesh_alpha     = 0.0

        # ── Face direction (head turn animation) ─────────
        # face_dir: 0.0 = front, -1.0 = full left, +1.0 = full right
        self.face_dir       = 0.0
        self.target_dir     = 0.0
        # Bracket visibility (only during left-look phase)
        self.bracket_show   = 0.0     # 0 → 1 fade in/out

        # ── Scan phase sequence ───────────────────────────
        # 0 = RECTANGLE front view (brackets visible, face straight)
        # 1 = RECTANGLE look RIGHT (brackets stay, face turns right)
        # 2 = RECTANGLE look LEFT  (brackets stay, face turns left)
        # 3 = MORPH: brackets fade out, return front, rectangle→circle
        # 4 = CIRCLE + WINK animation
        # 5 = complete (trigger success)
        self.scan_step      = 0
        self.scan_step_t    = 0.0

        # ── Shape morph: 0.0 = rectangle/brackets, 1.0 = circle ──
        self.shape_morph    = 0.0   # interpolation factor
        self.target_morph   = 0.0

        # Wink animation
        self.wink_t         = -1.0
        self.left_eye_open  = 1.0
        self.right_eye_open = 1.0

        # Flash effect
        self.flash_alpha    = 0.0

        # Scan completion trigger
        self._wink_triggered = False

        # Global
        self.widget_fade  = 1.0
        self.shake_t      = -1.0
        self.ell          = 0
        self.demo_cy      = 0

        # ── Dynamic Island state ─────────────────────────
        # Phases:
        #   0 = pill appearance (subtle entry)
        #   1 = expanding from pill to full
        #   2 = fully expanded (running)
        #   3 = collapsing back
        self.island_phase    = 0
        self.island_t        = 0.0
        self.island_progress = 0.0
        # Premium spring: snappy + bouncy (iOS Dynamic Island feel)
        self.island_spring   = Spring(mass=1.2, stiffness=160.0, damping=22.0)
        self._pop_played     = False
        self._scan_started   = False

        # Pill dimensions (laptop notch)
        self.PILL_W = 200     # wider pill
        self.PILL_H = 42      # taller pill
        self.PILL_Y = 12      # margin from top
        self.PILL_FADE_IN = 0.35   # pill appear time

        # Window setup
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground,    True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint        |
            Qt.WindowStaysOnTopHint       |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )
        self.setFixedSize(self.W, self.H)

        # 60fps tick
        self._tmr = QTimer()
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        # Ellipsis timer
        self._etmr = QTimer()
        self._etmr.timeout.connect(lambda: setattr(self, 'ell', (self.ell % 3) + 1))
        self._etmr.start(380)

    # ── State transitions ──────────────────────────────────
    def _on_ok(self, n):
        if self.ph == self.OK: return
        self.ph = self.OK; self.t0 = time.time(); self.nm = n
        # Particle burst — Metal emitter equivalent
        self.particles.burst(self.CX, self.CY, [0, 230, 118], n=60)
        # Spring pop-in for checkmark
        self.check_spring.reset(x=1.4, v=0.0)
        play(SND_OK)

    def _on_fail(self):
        if self.ph == self.OK: return
        self.ph = self.FAIL; self.t0 = time.time()
        self.shake_t = 0.0
        # Particle burst red
        self.particles.burst(self.CX, self.CY, [255, 74, 74], n=25)
        self._fail_count += 1
        if self._fail_count >= 3:
            QTimer.singleShot(1800, self.close)
        play(SND_FAIL)

    # ── Main tick — all animations advance here ────────────
    def _tick(self):
        now = time.time()
        raw_dt = now - self._last_tick
        self._last_tick = now

        # ── Smooth dt: blend 20% actual + 80% previous ──
        # Stable timing without heavy math
        raw_dt = min(raw_dt, 0.040)
        if not hasattr(self, "_sdt"):
            self._sdt = 0.016
        self._sdt = self._sdt * 0.80 + raw_dt * 0.20
        dt = max(0.006, self._sdt)
        p   = now - self.t0

        # ── Dynamic Island animation ──────────────────────
        self.island_t += dt

        if self.island_phase == 0:
            # ── Pill rests at top, user notices it (0.85s) ──
            if self.island_t > 0.55:
                self.island_phase = 1
                self.island_t     = 0.0
                if not self._pop_played:
                    play(SND_POP)
                    self._pop_played = True

        elif self.island_phase == 1:
            # ── Expand: slow luxurious spring (0.72s) ──
            # Gentle single overshoot — premium iOS feel
            T = 0.48
            if self.island_t >= T:
                self.island_progress = 1.0
                self.island_phase    = 2
                self.island_t        = 0.0
                if not self._scan_started:
                    play(SND_SCAN)
                    self._scan_started = True
            else:
                t = self.island_t / T
                # Smooth quintic ease-out (no harsh overshoot)
                ease = 1 - pow(1 - t, 5)
                # Subtle single overshoot at 75% progress
                bump = math.sin(t * math.pi) * 0.055 * math.exp(-t * 3.5)
                self.island_progress = min(1.055, ease + bump)

        elif self.island_phase == 2:
            # ── Fully expanded — breathe slightly ──
            breathe = 0.008 * math.sin(self.island_t * 2.2)
            self.island_progress = 1.0 + breathe

        elif self.island_phase == 3:
            # ── Collapse: smooth cubic ease-in (0.55s) ──
            T = 0.55
            if self.island_t >= T:
                self.close()
            else:
                t = self.island_t / T
                # Ease-in-out collapse
                if t < 0.5:
                    ease = 4 * t * t * t
                else:
                    ease = 1 - pow(-2 * t + 2, 3) / 2
                self.island_progress = 1.0 - ease

        # Particle update (Metal per-frame equivalent)
        self.particles.update(dt)

        # Shake advance
        if self.shake_t >= 0:
            self.shake_t += dt
            if self.shake_t > 0.5:
                self.shake_t = -1.0

        if self.ph == self.IDLE:
            self._tick_idle(p, dt)
        elif self.ph == self.SCAN:
            self._tick_scan(p, dt)
        elif self.ph == self.OK:
            self._tick_ok(p, dt)
        elif self.ph == self.FAIL:
            self._tick_fail(p, dt)

        self.update()

    # ── IDLE ───────────────────────────────────────────────
    def _tick_idle(self, p, dt):
        # Spring scale intro (CASpringAnimation pop-in)
        if p < 0.01:
            self.spring_scale.reset(x=0.45, v=0.0)
            self.spring_opacity.reset(x=-1.0, v=0.0)

        # ── Smooth cubic ease-in-out face pop-in ──
        if p < 0.80:
            # Cubic ease: slow start, smooth end
            t = min(p / 0.80, 1.0)
            ease = t * t * (3.0 - 2.0 * t)   # smoothstep
            self.face_scale = 0.50 + 0.50 * ease
            self.face_alpha = ease
        else:
            self.face_scale = 1.0
            self.face_alpha = 1.0

        # Eyes fade in after face (staggered)
        self.eye_alpha   = min(max(0, (p - 0.35) * 2.2), 0.6)
        self.face_color  = [255, 255, 255]

        # Glow: very subtle, breathes softly
        self.glow_alpha  = 0.012 + 0.008 * math.sin(p * 1.8)
        self.glow_color  = [120, 120, 140]

        self.ring_alpha  = min(max(0, (p - 0.40) * 1.8), 0.055)
        self.ring_color  = [255, 255, 255]
        self.ring_arc    = 0.0
        self.dot_rot     = 0.0
        self.ring_speed  = 0.0

        # Dots stagger in with smooth delay
        for i in range(self.N):
            delay          = i * 0.022
            dt2            = max(0, p - delay)
            t2             = min(dt2 / 0.28, 1.0)
            self.dot_a[i]  = 0.65 * t2 * t2 * (3 - 2 * t2)   # smoothstep
            self.dot_sz[i] = self.DS

        self.txt         = "Face Unlock"
        # ── Synchronized idle cascade ──
        # Face → Dots → Ring → Text (staggered but synced)
        # Each starts exactly when previous is 60% done
        t_txt = min(max(0, (p - 0.42) / 0.30), 1.0)
        t_txt = t_txt * t_txt * (3 - 2 * t_txt)   # smoothstep
        self.txt_alpha   = 0.42 * t_txt
        self.txt_color   = [255, 255, 255]
        self.check_stroke= 0.0
        self.check_alpha = 0.0
        self.x_stroke    = 0.0
        self.x_alpha     = 0.0
        self.widget_fade = 1.0

        if p > 0.65:
            self.ph = self.SCAN; self.t0 = time.time()

    # ── SCAN — iPhone Face ID: rectangle→circle→wink ─────
    def _tick_scan(self, p, dt):
        import math, time, random
        now = time.time()

        self.face_alpha = 1.0
        self.face_scale = 1.0
        self.eye_alpha  = 0.6

        # ── Subtle background ring ───────────────────────
        target_speed = 1.2
        if p < 0.4:
            self.ring_speed = (p / 0.4) * target_speed
        else:
            self.ring_speed = target_speed
        self.dot_rot  += self.ring_speed
        self.trail_rot = self.dot_rot
        self.ring_arc   = min(p / 0.5, 1.0)
        self.ring_alpha = min(p / 0.4, 0.12)

        self.ring2_alpha = 0.0
        self.ring3_alpha = (0.05 + 0.03 *
                            math.sin(now * 1.8)) * min(p / 0.8, 1.0)

        for i in range(self.N):
            self.dot_a[i]  = 0.10
            self.dot_sz[i] = self.DS * 0.65

        # ── Breathing pulse ──────────────────────────────
        breath           = (math.sin(now * 2.2) + 1) / 2
        self.pulse_r     = self.R * (0.55 + 0.15 * breath)
        self.pulse_alpha = 0.03 + 0.03 * breath

        # ── Disable old effects ──────────────────────────
        self.scan_alpha    = 0.0
        self.grid_alpha    = 0.0
        self.bracket_alpha = 0.0
        self.bracket_scale = 0.0
        self.mesh_alpha    = 0.0
        self.mesh_lines.clear()

        # ── Colors (iPhone blue) ─────────────────────────
        tc              = min(p / 0.5, 1)
        self.face_color = self._lerp([255, 255, 255], [40, 130, 240], tc)
        self.ring_color = [40, 130, 240]
        self.glow_alpha = 0.06 + 0.04 * math.sin(now * 2.8)
        self.glow_color = [60, 150, 255]

        # ══════════════════════════════════════════════════
        # SEQUENCE STEPS
        # ══════════════════════════════════════════════════
        self.scan_step_t += dt

        # ── Helper: force eyes open and cancel any wink ──
        def _no_wink():
            self.wink_t          = -1.0
            self.left_eye_open   = 1.0
            self.right_eye_open  = 1.0
            self._wink_triggered = False

        # ════════════════════════════════════════════════════
        # PROFESSIONAL ANIMATION STATE MACHINE
        #
        # SUCCESS path:  0→1→2→3→4→5→6→7 (done)
        # FAIL path:     0→1→2→3→20→21→22 (retry)
        #
        # Timing designed for premium, unhurried feel
        # Total success: ~3.8s   Total fail: ~3.2s
        # ════════════════════════════════════════════════════

        # ── SUCCESS STATES ───────────────────────────────

        # Step 0: Opening settle (0.40s)
        if self.scan_step == 0:
            self.target_dir   = 0.0
            self.bracket_show = 1.0
            self.target_morph = 0.0
            _no_wink()
            self.txt          = "Look straight ahead"
            if self.scan_step_t > 0.40:
                self.scan_step   = 1
                self.scan_step_t = 0.0

        # Step 1: Turn RIGHT (0.55s)
        elif self.scan_step == 1:
            self.target_dir   = 1.0
            self.bracket_show = 1.0
            self.target_morph = 0.0
            _no_wink()
            self.txt          = "Move your head slowly"
            if self.scan_step_t > 0.55:
                self.scan_step   = 2
                self.scan_step_t = 0.0

        # Step 2: Turn LEFT (0.55s)
        elif self.scan_step == 2:
            self.target_dir   = -1.0
            self.bracket_show = 1.0
            self.target_morph = 0.0
            _no_wink()
            self.txt          = "Keep moving slowly"
            if self.scan_step_t > 0.55:
                self.scan_step   = 3
                self.scan_step_t = 0.0

        # Step 3: Return to center (0.25s)
        elif self.scan_step == 3:
            self.target_dir   = 0.0
            self.bracket_show = 1.0
            self.target_morph = 0.0
            _no_wink()
            self.txt          = "Almost done"
            if self.scan_step_t > 0.25:
                # Route: success→4, fail→20
                nxt = getattr(self, "_next_after_scan", 4)
                self.scan_step   = nxt
                self.scan_step_t = 0.0

        # Step 4: Morph rectangle→circle (0.45s)
        elif self.scan_step == 4:
            self.target_dir   = 0.0
            self.bracket_show = 1.0
            self.target_morph = 1.0
            _no_wink()
            self.txt          = "Face Recognized"
            if self.scan_step_t > 0.45:
                self.scan_step   = 5
                self.scan_step_t = 0.0

        # Step 5: Wink (0.40s)
        elif self.scan_step == 5:
            self.target_dir   = 0.0
            self.bracket_show = 1.0
            self.target_morph = 1.0

            if (not self._wink_triggered
                and abs(self.face_dir) < 0.08
                and self.shape_morph > 0.95
                and self.scan_step_t > 0.10):
                self._wink_triggered = True
                self.wink_t          = 0.0

            self.txt = "Face Recognized"
            if self.scan_step_t > 0.40:
                self.scan_step   = 6
                self.scan_step_t = 0.0

        # Step 6: Fade out (0.30s)
        elif self.scan_step == 6:
            self.target_dir   = 0.0
            self.bracket_show *= math.exp(-dt * 6.5)
            if self.bracket_show < 0.002:
                self.bracket_show = 0.0
            self.target_morph = 1.0
            self.txt          = "Face Recognized"
            if self.scan_step_t > 0.30:
                self.scan_step   = 7
                self.scan_step_t = 0.0

        # ── FAIL STATES ──────────────────────────────────

        # Step 20: Bracket turns red + shake (0.50s)
        elif self.scan_step == 20:
            self.target_dir   = 0.0
            self.target_morph = 0.0
            _no_wink()
            self.txt          = "Face Not Recognized"
            # Animate bracket red via _fail_t
            if not hasattr(self, "_fail_t"):
                self._fail_t = 0.0
            self._fail_t += dt
            # ── Premium damped shake ──
            # Frequency 14Hz, decay 4.5 → smooth, not rattly
            shake_amp     = 14.0 * math.exp(-self._fail_t * 4.5)
            self._shake_x = shake_amp * math.sin(
                self._fail_t * 14.0 * 2 * math.pi)
            # Bracket blends to red smoothly (cubic ease-in)
            t_r = min(self._fail_t * 2.5, 1.0)
            self._fail_red = t_r * t_r * (3 - 2 * t_r)
            if self.scan_step_t > 0.50:
                self.scan_step   = 21
                self.scan_step_t = 0.0

        # Step 21: Hold red + show message (0.70s)
        elif self.scan_step == 21:
            self.target_dir = 0.0
            _no_wink()
            self._shake_x  = 0.0
            tries_left = getattr(self, "_tries_left", 2)
            if tries_left > 0:
                self.txt = f"Try again  ({tries_left} attempt{'s' if tries_left!=1 else ''} left)"
            else:
                self.txt = "Too many attempts"
            if self.scan_step_t > 0.70:
                self.scan_step   = 22
                self.scan_step_t = 0.0

        # Step 22: Fade red back to normal or lockout (0.45s)
        elif self.scan_step == 22:
            self.target_dir = 0.0
            _no_wink()
            # Smooth exponential red fade
            fr = getattr(self, "_fail_red", 0.0)
            self._fail_red = fr * math.exp(-dt * 3.2)
            if self._fail_red < 0.005:
                self._fail_red = 0.0
            tries_left = getattr(self, "_tries_left", 2)
            if tries_left > 0:
                self.txt = "Scanning again" + "." * (int(self.scan_step_t * 3) % 4)
            else:
                self.txt = "Locked — contact admin"
            if self.scan_step_t > 0.45:
                if tries_left > 0:
                    # Retry: decrement and restart scan
                    self._tries_left     = tries_left - 1
                    self._fail_t         = 0.0
                    self._shake_x        = 0.0
                    self._shake_y        = 0.0
                    self._shake_rot      = 0.0
                    self._fail_red       = 0.0
                    self._next_after_scan = 4   # success path
                    self.scan_step        = 0
                    self.scan_step_t      = 0.0
                    self._wink_triggered  = False
                    self.wink_t           = -1.0
                else:
                    # Lockout
                    self.scan_step   = 99
                    self.scan_step_t = 0.0

        # Step 99: Locked out
        elif self.scan_step == 99:
            self.target_dir   = 0.0
            self.bracket_show = max(0.2,
                self.bracket_show - dt * 1.5)
            self.txt = "Locked Out"
            self._fail_red = 1.0

        # Step 7: Trigger success animation
        elif self.scan_step == 7:
            self.txt = "Face Recognized"
            if self.demo_mode and self.scan_step_t > 0.1:
                self._on_ok("Demo_User")
                self.scan_step_t = 0.0

        # ════════════════════════════════════════════════
        # PREMIUM SMOOTH INTERPOLATION
        # Exponential decay — same as Core Animation
        # Never overshoots, always settles perfectly
        # ════════════════════════════════════════════════

        # Face direction: 3.8 = slow human head movement
        diff_d = self.target_dir - self.face_dir
        self.face_dir    += diff_d * (1.0 - math.exp(-dt * 5.5))

        # Shape morph
        diff_m = self.target_morph - self.shape_morph
        self.shape_morph += diff_m * (1.0 - math.exp(-dt * 4.5))

        # Bracket show/hide: 2.5 = very gentle fade
        diff_b = self.target_bracket - self.bracket_show                  if hasattr(self, "target_bracket") else 0
        if abs(diff_b) > 0.0005:
            self.bracket_show += diff_b * (1.0 - math.exp(-dt * 2.5))

        # ══════════════════════════════════════════════════
        # SYNCHRONIZED FADE SYSTEM
        # All alphas driven by same master timeline
        # Like CAAnimationGroup — everything in sync
        # ══════════════════════════════════════════════════

        # Master opacity: fades in over 0.3s at start
        master = min(p / 0.30, 1.0)
        master = master * master * (3 - 2 * master)  # smoothstep

        # Text: synced to master, slightly delayed
        t_txt  = max(0.0, min((p - 0.08) / 0.28, 1.0))
        t_txt  = t_txt * t_txt * (3 - 2 * t_txt)
        self.txt_alpha = 0.82 * t_txt * master
        self.txt_color = [210, 225, 255]

        # Ring alpha: synced to master
        self.ring_alpha  = min(p / 0.35, 0.12) * master
        self.ring3_alpha = (0.05 + 0.03 *
                           math.sin(p * 1.8)) * min(p / 0.6, 1.0) * master

        # Glow: breathes but tied to master
        self.glow_alpha = (0.06 + 0.04 * math.sin(
                           p * 2.8)) * master
        self.glow_color = [60, 150, 255]

        # Pulse: synced
        breath = (math.sin(p * 2.2) + 1) / 2
        self.pulse_alpha = (0.03 + 0.03 * breath) * master

        # ══════════════════════════════════════════════════
        # WINK animation
        # GUARD: Only allow wink when face is FRONT-facing
        # If face turns sideways mid-wink, abort and force eyes open
        # ══════════════════════════════════════════════════
        is_front = abs(self.face_dir) < 0.15

        if self.wink_t >= 0:
            # If face moved off-center mid-wink, cancel immediately
            if not is_front:
                self.wink_t          = -1.0
                self.left_eye_open   = 1.0
                self.right_eye_open  = 1.0
                self._wink_triggered = False
                self.flash_alpha     = 0.0
            else:
                self.wink_t += dt
                wt = self.wink_t

                # ════════════════════════════════════════════
                # PREMIUM NATURAL WINK
                # Phase 1 — quintic ease-in close:  150ms
                # Phase 2 — fully closed hold:       90ms
                # Phase 3 — elastic ease-out open:  220ms
                # Total: 460ms — alive, warm, organic
                # ════════════════════════════════════════════
                if wt < 0.15:
                    # Quintic ease-in: very slow start → fast snap
                    t = wt / 0.15
                    self.left_eye_open = 1.0 - (t * t * t * t * t)

                elif wt < 0.24:
                    # Fully closed — intentional pause
                    self.left_eye_open = 0.0

                elif wt < 0.46:
                    # Elastic ease-out: spring back with character
                    t = (wt - 0.24) / 0.22
                    # Smooth overshoot then settle
                    elastic = 1 - pow(1 - t, 4)
                    spring  = 0.08 * math.sin(t * math.pi * 1.6) * (1 - t)
                    self.left_eye_open = min(1.0, elastic + spring)
                else:
                    self.left_eye_open = 1.0
                    self.wink_t        = -1.0

                # Warm luminous flash at peak closure
                if 0.12 < wt < 0.38:
                    # Bell curve glow — peaks at eye closure
                    mid   = 0.22
                    sigma = 0.10
                    peak  = 0.25 * math.exp(
                        -0.5 * ((wt - mid) / sigma) ** 2)
                    self.flash_alpha = max(0.0, peak)
                else:
                    # Exponential decay after glow
                    self.flash_alpha = max(0.0,
                        self.flash_alpha * math.exp(-dt * 4.0))
        else:
            # Not winking — if face is sideways, force eyes open
            if not is_front:
                self.left_eye_open  = 1.0
                self.right_eye_open = 1.0
            self.flash_alpha = max(0, self.flash_alpha - dt * 2)

    # ── OK — Ring→Checkmark (fast professional) ────────────
    def _tick_ok(self, p, dt):
        import math

        # ════════════════════════════════════════════════════
        # FAST TIMELINE (total ~1.8s active + hold):
        #
        # 0.00–0.15s: Face fades out instantly
        # 0.10–0.40s: Ring spins + fills fast
        # 0.40–0.55s: Ring completes with speed burst
        # 0.55–0.75s: Ring→Checkmark morph
        # 0.65–0.80s: Text slides up
        # 1.60–2.00s: Widget fade out
        # ════════════════════════════════════════════════════

        # ── Colors: instant blue→green ──
        tc              = min(p / 0.15, 1.0)
        self.face_color = self._lerp([60, 140, 255], [0, 230, 118], tc)
        self.ring_color = self._lerp([60, 140, 255], [0, 230, 118], tc)
        self.glow_color = [0, 230, 118]

        # ══ Phase 0: Face vanishes (0→0.15s) ════════════════
        if p < 0.15:
            ft = min(p / 0.12, 1.0)
            ft = ft * ft * ft
            self.face_alpha   = max(0.0, 1.0 - ft)
            self.eye_alpha    = max(0.0, 0.6 * (1.0 - ft))
            bt = min(p / 0.14, 1.0)
            bt = bt * bt * (3 - 2 * bt)
            self.bracket_show = max(0.0, 1.0 - bt)
            self.ring_seg_alpha = 0.0
            self.ring_progress  = 0.0
        else:
            self.face_alpha   = 0.0
            self.eye_alpha    = 0.0
            self.bracket_show = 0.0

        # ══ Phase 1: Ring spins at CONSTANT speed (0.10→0.55s) ══
        # Pure linear rotation — no easing, no acceleration
        # Angular velocity: 4.5 rad/s = ~258°/s ≈ 1.4 revolutions
        if 0.10 <= p < 0.55:
            phase_t = (p - 0.10) / 0.45

            # Instant appear
            self.ring_seg_alpha = min(phase_t / 0.06, 1.0)

            # ── CONSTANT angular velocity — linear, no easing ──
            OMEGA = 4.5   # rad/s — constant
            self.ring_rot += OMEGA * dt

            # Wrap at 2*pi (360° = 0°)
            if self.ring_rot > 6.2831853:
                self.ring_rot -= 6.2831853

            # ring_progress not used for rotation but kept for morph
            self.ring_progress = phase_t

            # Subtle glow breathe
            self.glow_alpha    = 0.08 + 0.04 * math.sin(p * 4.0)
            self.ring_to_check = 0.0
            self.check_alpha   = 0.0
            self.check_stroke  = 0.0
            self.ripple_alpha  = 0.0

        # ══ Phase 2: Ring → Checkmark morph (0.55→0.82s) ══════
        elif 0.55 <= p < 0.82:
            phase_t = (p - 0.55) / 0.27

            # Ring fades — rotation continues but decelerates to stop
            self.ring_seg_alpha = max(0.0, 1.0 - phase_t * 2.8)
            self.ring_progress  = 1.0
            self.ring_to_check  = min(phase_t * 2.2, 1.0)

            # Rotation decelerates linearly to zero
            decel = max(0.0, 1.0 - phase_t)
            self.ring_rot += 4.5 * decel * dt
            if self.ring_rot > 6.2831853:
                self.ring_rot -= 6.2831853

            # Checkmark draws on with spring
            if phase_t > 0.08:
                raw  = min((phase_t - 0.08) / 0.55, 1.0)
                ease = 1 - pow(1 - raw, 4)
                sv   = self.check_spring.step(dt)
                xtra = max(0, sv * 0.10) if not self.check_spring.settled else 0
                self.check_stroke = min(1.0, ease + xtra)
                self.check_alpha  = min((phase_t - 0.08) / 0.08, 1.0)
            else:
                self.check_stroke = 0.0
                self.check_alpha  = 0.0

            # Spring scale bounce
            if phase_t > 0.12:
                bt   = (phase_t - 0.12) / 0.50
                sv_s = self._ring_spring.step(dt)
                self.face_scale = 1.0 + 0.06 * math.sin(
                    bt * math.pi) + max(0, sv_s * 0.04)
            else:
                self.face_scale = 1.0

            # Glow bell curve at morph midpoint
            mid = 0.40
            sig = 0.18
            self.glow_alpha = 0.06 + 0.25 * math.exp(
                -0.5 * ((phase_t - mid) / sig) ** 2)

            # Ripple expands
            rt = min(phase_t / 0.7, 1.0)
            self.ripple_r     = (self.R + 14) * (1 + 2.5 * rt)
            self.ripple_alpha = max(0, 0.24 * pow(1 - rt, 2.0))

        # ══ Phase 3: Hold checkmark (0.82→1.60s) ═══════════
        elif 0.82 <= p < 1.60:
            self.ring_seg_alpha = 0.0
            self.ring_progress  = 1.0
            self.ring_to_check  = 1.0
            self.check_stroke   = 1.0
            self.check_alpha    = 1.0
            self.face_scale     = 1.0
            self.glow_alpha     = max(0.01,
                0.05 * math.exp(-(p - 0.80) * 3.0))
            self.ripple_alpha   = 0.0

        # ── Text: synced to checkmark midpoint ──────────────
        if p > 0.65:
            t_ok = min((p - 0.65) / 0.20, 1.0)
            t_ok = t_ok * t_ok * (3 - 2 * t_ok)
            self.txt_alpha = 0.92 * t_ok
        else:
            self.txt_alpha = 0.0
        self.txt       = "Unlocked"
        self.txt_color = [0, 230, 118]

        # ── Dots fade ──
        for i in range(self.N):
            self.dot_a[i]  += (0.0 - self.dot_a[i]) * 0.12
            self.dot_sz[i] += (self.DS - self.dot_sz[i]) * 0.10

        # ── Widget fade out ──
        if p > 1.60:
            t2 = min((p - 1.60) / 0.35, 1.0)
            self.widget_fade = max(0.0, 1.0 - t2 * t2 * (3 - 2 * t2))
            if p > 2.10:
                if self.demo_mode:
                    self._full_reset()

    # ── FAIL — Red sphere + shake + X mark ─────────────────
    def _tick_fail(self, p, dt):
        import math
        self.ring_speed = 0

        # ── Color transition: cyan/green → RED ──
        tc              = min(p / 0.15, 1.0)
        # Cubic ease for color shift
        tc_eased        = tc * tc * (3 - 2 * tc)
        self.face_color = self._lerp([0, 200, 255], [255, 60, 60], tc_eased)
        self.ring_color = self._lerp([0, 200, 255], [255, 60, 60], tc_eased)
        self.glow_color = [255, 60, 60]

        # ── Impact flash: bright white burst (0→0.08s) ──
        if p < 0.08:
            flash_t = p / 0.08
            # Bright flash that fades quickly
            self.flash_alpha = 0.55 * (1 - flash_t * flash_t)
        else:
            # Decay flash
            self.flash_alpha = max(0.0,
                self.flash_alpha * math.exp(-dt * 8))

        # ── Red glow pulse on impact ──
        if p < 0.4:
            glow_t = p / 0.4
            self.glow_alpha = 0.25 * (1 - glow_t) + 0.05
        else:
            self.glow_alpha = max(0.02,
                0.06 * math.exp(-(p - 0.4) * 2.5))

        # ── Sphere stays visible but turns red + shakes ──
        # Keep ring alpha at full during fail
        self.ring_seg_alpha = max(0.5,
            1.0 - max(0, (p - 1.2)) / 0.4)
        self.ring_to_check = 0.0   # don't morph to checkmark

        # Sphere rotates SLOWER on fail (feels heavy/sad)
        OMEGA_FAIL = 2.0   # rad/s — half normal speed
        self.ring_rot += OMEGA_FAIL * dt
        if self.ring_rot > 6.2831853:
            self.ring_rot -= 6.2831853

        # ════════════════════════════════════════════════
        # SHOCK SHAKE — frame-rate INDEPENDENT
        # Uses absolute time (p = seconds since fail start)
        # Frequencies in Hz × 2π = rad/s
        # Same feel at 30fps, 60fps, 120fps
        # ════════════════════════════════════════════════

        TWO_PI = 6.28318530718

        # Phase A: SHOCK impact (0→0.15s)
        if p < 0.15:
            shock_amp     = 35.0 * (1.0 - p / 0.15)
            # 14.3 Hz × 2π — actual physical frequency
            self._shake_x = shock_amp * math.sin(p * 14.3 * TWO_PI)
            self._shake_y = (shock_amp * 0.4) * math.cos(p * 17.5 * TWO_PI)
            self._shake_rot = (shock_amp * 0.015) * math.sin(p * 12.7 * TWO_PI)

        # Phase B: Aftershock (0.15→0.55s)
        elif p < 0.55:
            local_t   = p - 0.15
            shake_amp = 25.0 * math.exp(-local_t * 6.0)
            # 6 Hz + 10.3 Hz mixed (organic damped feel)
            self._shake_x = shake_amp * (
                0.7 * math.sin(local_t * 6.0  * TWO_PI) +
                0.3 * math.sin(local_t * 10.3 * TWO_PI)
            )
            self._shake_y   = (shake_amp * 0.3) * math.sin(local_t * 8.0 * TWO_PI)
            self._shake_rot = (shake_amp * 0.008) * math.sin(local_t * 7.2 * TWO_PI)

        # Phase C: Settled
        else:
            self._shake_x   = 0.0
            self._shake_y   = 0.0
            self._shake_rot = 0.0

        # ── Brackets fade fast ──
        self.bracket_show = max(0.0, self.bracket_show - dt * 5.0)

        # ── Face dots dim ──
        for i in range(self.N):
            target_a = 0.30
            self.dot_a[i]  += (target_a - self.dot_a[i]) * 0.15
            self.dot_sz[i] += (self.DS * 0.8 - self.dot_sz[i]) * 0.12

        # ── Face fades ──
        if p > 0.15:
            ft = min((p - 0.15) / 0.20, 1.0)
            ft = ft * ft
            self.face_alpha = max(0.0, 1.0 - ft)
            self.eye_alpha  = max(0.0, 0.6 * (1.0 - ft))

        # ── X mark draws on top of sphere ──
        if p > 0.25:
            raw            = min((p - 0.25) / 0.20, 1.0)
            # Quintic ease — snappy
            self.x_stroke  = 1.0 - pow(1.0 - raw, 5)
            self.x_alpha   = min((p - 0.25) / 0.08, 1.0)

        # ── "Try Again" text: smoothstep fade in ──
        t_fa = min((p - 0.30) / 0.20, 1.0) if p > 0.30 else 0.0
        t_fa = max(0.0, t_fa * t_fa * (3 - 2 * t_fa))
        self.txt         = "Try Again"
        self.txt_alpha   = 0.92 * t_fa
        self.txt_color   = [255, 80, 80]

        # ── X mark fades after holding ──
        if p > 1.4:
            self.x_alpha = max(0.0, self.x_alpha - dt * 1.8)

        # ── Sphere fades out at end ──
        if p > 1.2:
            self.ring_seg_alpha = max(0.0,
                self.ring_seg_alpha - dt * 1.5)

        # ── Reset to scan for retry ──
        if p > 1.8:
            self._reset_to_scan()

    def _reset_to_scan(self):
        self.ph          = self.SCAN
        self.t0          = time.time()
        self.face_alpha  = 1.0
        self.face_scale  = 1.0
        self.face_color  = [255, 255, 255]
        self.eye_alpha   = 0.6
        self.mesh_lines.clear()
        self._wink_triggered = False
        self.wink_t      = -1.0
        self.left_eye_open  = 1.0
        self.right_eye_open = 1.0
        self.flash_alpha = 0.0
        self.scan_step      = 0
        self.scan_step_t    = 0.0
        self.face_dir       = 0.0
        self.target_dir     = 0.0
        self.bracket_show   = 0.0
        self.shape_morph    = 0.0
        self.target_morph   = 0.0
        self.check_stroke   = 0.0
        # Ring reset
        self.ring_progress  = 0.0
        self.ring_rot       = 0.0
        self.ring_seg_alpha = 0.0
        self.ring_to_check  = 0.0
        self.ring_speed_ok  = 4.5
        self._check_draw_t  = 0.0
        self._success_phase = 0
        self._ring_spring.reset(x=0.0, v=0.0)
        self.check_alpha = 0.0
        self.x_stroke    = 0.0
        self.x_alpha     = 0.0
        self.ripple_alpha= 0.0
        self.shake_t     = -1.0
        self.widget_fade = 1.0
        self.txt_color   = [255, 255, 255]
        self.ring_color  = [255, 255, 255]
        play(SND_SCAN)

    def _full_reset(self):
        self.ph          = self.IDLE
        self.t0          = time.time()
        self.demo_cy    += 1
        # Visual state
        self.check_stroke= 0.0
        self.check_alpha = 0.0
        self.x_stroke    = 0.0
        self.x_alpha     = 0.0
        self.ring_arc    = 0.0
        self.ring_speed  = 0.0
        self.dot_rot     = 0.0
        self.widget_fade = 1.0
        self.particles.particles.clear()

        # ── Scan sequence reset ──────────────────────────
        self.scan_step      = 0
        self.scan_step_t    = 0.0
        self.face_dir       = 0.0
        self.target_dir     = 0.0
        self.bracket_show   = 0.0
        self.shape_morph    = 0.0
        self.target_morph   = 0.0

        # ── Wink reset ───────────────────────────────────
        self._wink_triggered  = False
        self.wink_t           = -1.0
        self._buf             = None   # double buffer pixmap
        self._buf             = None   # double buffer pixmap
        # Fail state
        self._fail_red        = 0.0   # 0=normal 1=full red
        self._fail_t          = 0.0
        self._shake_x         = 0.0
        self._shake_y         = 0.0
        self._shake_rot       = 0.0
        self._tries_left      = 2     # allow 2 retries (3 total)
        self._next_after_scan = 4     # default: success path
        self.left_eye_open   = 1.0
        self.right_eye_open  = 1.0
        self.flash_alpha     = 0.0

        # ── Face appearance reset ────────────────────────
        self.face_alpha     = 0.0
        self.face_scale     = 0.55
        self.eye_alpha      = 0.0
        self.ripple_alpha   = 0.0
        self.shake_t        = -1.0
        self.txt            = ""
        self.txt_alpha      = 0.0
        self._fail_count    = 0

        # ── Reset check spring ───────────────────────────
        self.check_spring.reset(x=0.0, v=0.0)
        # Ring reset
        self.ring_progress  = 0.0
        self.ring_rot       = 0.0
        self.ring_seg_alpha = 0.0
        self.ring_to_check  = 0.0
        self.ring_speed_ok  = 4.5
        self._check_draw_t  = 0.0
        self._success_phase = 0
        if hasattr(self, "_ring_spring"):
            self._ring_spring.reset(x=0.0, v=0.0)

    # ── Paint ──────────────────────────────────────────────
    def paintEvent(self, e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing,       True)
        P.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # UIViewPropertyAnimator spring fade
        if self.widget_fade < 1.0:
            P.setOpacity(max(0.0, self.widget_fade))

        # CAKeyframeAnimation shake offset
        sx = int(shake_at(self.shake_t)) if self.shake_t >= 0 else 0
        cx = self.CX + sx
        cy = self.CY

        # ══════════════════════════════════════════════════
        # DYNAMIC ISLAND — Laptop version (clean morph)
        # ══════════════════════════════════════════════════
        prog = max(0.0, min(1.06, self.island_progress))

        # ── Dimensions with squish/stretch feel ──
        # Horizontal expands slightly faster (iOS DI behavior)
        p_w  = min(1.0, prog * 1.08)
        p_h  = min(1.0, prog)
        cur_w = self.PILL_W + (self.W - 40 - self.PILL_W) * p_w
        cur_h = self.PILL_H + (self.H - 40 - self.PILL_H) * p_h

        rect_x = (self.W - cur_w) / 2
        rect_y = self.PILL_Y

        # ── INDIVIDUAL CORNER RADII (real bezier blob) ──
        # Each corner animates independently like iOS
        pill_r = self.PILL_H / 2

        # Corners reach their targets at different speeds:
        # Top corners: faster (they define the pill shape)
        # Bottom corners: slightly slower (creates blob morph)
        p_top = min(1.0, prog * 1.15)   # top corners lead
        p_bot = min(1.0, prog * 0.90)   # bottom corners trail

        r_tl = pill_r + (28 - pill_r) * p_top   # top-left
        r_tr = pill_r + (28 - pill_r) * p_top   # top-right
        r_bl = pill_r + (36 - pill_r) * p_bot   # bottom-left (rounder)
        r_br = pill_r + (36 - pill_r) * p_bot   # bottom-right (rounder)

        # Clamp radii to half dimensions
        max_rx = cur_w / 2
        max_ry = cur_h / 2
        r_tl = min(r_tl, max_rx, max_ry)
        r_tr = min(r_tr, max_rx, max_ry)
        r_bl = min(r_bl, max_rx, max_ry)
        r_br = min(r_br, max_rx, max_ry)

        def _rounded_blob(x, y, w, h, tl, tr, br, bl):
            """
            QPainterPath with 4 individual corner radii.
            Mimics iOS CALayer cornerRadius per-corner API.
            """
            path = QPainterPath()
            path.moveTo(x + tl, y)
            path.lineTo(x + w - tr, y)
            path.quadTo(x + w, y,         x + w, y + tr)
            path.lineTo(x + w, y + h - br)
            path.quadTo(x + w, y + h,     x + w - br, y + h)
            path.lineTo(x + bl, y + h)
            path.quadTo(x,      y + h,     x, y + h - bl)
            path.lineTo(x, y + tl)
            path.quadTo(x, y,              x + tl, y)
            path.closeSubpath()
            return path

        blob = _rounded_blob(rect_x, rect_y, cur_w, cur_h,
                             r_tl, r_tr, r_br, r_bl)

        # ── Clean drop shadow (2 passes) ──
        shadow_offset = 4 + 8 * prog
        shadow_a      = int(80 * (0.3 + 0.7 * prog))
        for i in range(2):
            alpha = max(0, shadow_a // (i + 2))
            P.save()
            P.translate(0, shadow_offset + i * 3)
            P.setBrush(QBrush(QColor(0, 0, 0, alpha)))
            P.setPen(Qt.NoPen)
            P.drawPath(blob)
            P.restore()

        # ── Main blob background ──
        P.setBrush(QBrush(QColor(6, 6, 8, 248)))
        P.setPen(Qt.NoPen)
        P.drawPath(blob)

        # ── Glossy top highlight ──
        gloss = QLinearGradient(rect_x, rect_y,
                                rect_x, rect_y + cur_h * 0.45)
        gloss.setColorAt(0,   QColor(255, 255, 255, int(28 * (0.3 + 0.7 * prog))))
        gloss.setColorAt(0.6, QColor(255, 255, 255, int(8  * prog)))
        gloss.setColorAt(1,   QColor(255, 255, 255, 0))
        P.setBrush(QBrush(gloss))
        P.drawPath(blob)

        # ── Inner rim light (subtle edge definition) ──
        P.setPen(QPen(QColor(255, 255, 255, int(22 * prog)), 0.8))
        P.setBrush(Qt.NoBrush)
        # Slightly inset blob for border
        blob_in = _rounded_blob(rect_x+0.5, rect_y+0.5,
                                cur_w-1, cur_h-1,
                                r_tl, r_tr, r_br, r_bl)
        P.drawPath(blob_in)

        # ══════════════════════════════════════════════════
        # PILL STATE CONTENT (lock icon + camera indicator)
        # ══════════════════════════════════════════════════
        if prog < 0.25:
            pill_opacity = 1.0 - (prog / 0.25)
            P.setOpacity(pill_opacity)

            cy_pill = rect_y + cur_h / 2

            # Left: white lock icon
            lx = rect_x + 28
            ly = cy_pill
            P.setPen(QPen(QColor(255, 255, 255, 230), 1.8,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.setBrush(Qt.NoBrush)
            # Lock body
            P.drawRoundedRect(QRectF(lx - 6, ly - 1, 12, 10), 2, 2)
            # Lock shackle
            P.drawArc(QRectF(lx - 5, ly - 9, 10, 12),
                      0 * 16, 180 * 16)

            # Center: "Face ID" text (only visible mid pill state)
            if prog > 0.05:
                txt_a = int(255 * pill_opacity * 0.85)
                font  = QFont("Noto Sans, SF Pro Display, Helvetica Neue, Arial")
                font.setPixelSize(13)
                font.setWeight(QFont.DemiBold)
                P.setFont(font)
                P.setPen(QPen(QColor(255, 255, 255, txt_a)))
                fm = P.fontMetrics()
                txt = "Face ID"
                tw = fm.horizontalAdvance(txt)
                P.drawText(int(rect_x + cur_w / 2 - tw / 2),
                           int(cy_pill + 4), txt)

            # Right: glowing camera dot (pulsing)
            pulse  = (math.sin(time.time() * 4) + 1) / 2
            dot_x  = rect_x + cur_w - 28
            dot_y  = cy_pill
            # Glow
            P.setBrush(QBrush(QColor(0, 200, 255,
                              int(60 + 60 * pulse))))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(dot_x, dot_y), 9, 9)
            # Inner dot
            P.setBrush(QBrush(QColor(0, 220, 255, 255)))
            P.drawEllipse(QPointF(dot_x, dot_y), 4, 4)
            # Highlight
            P.setBrush(QBrush(QColor(255, 255, 255, 200)))
            P.drawEllipse(QPointF(dot_x - 1, dot_y - 1), 1.5, 1.5)

            P.setOpacity(1.0)
            P.end()
            return

        # ══════════════════════════════════════════════════
        # EXPANDED STATE
        # ══════════════════════════════════════════════════
        # Fade in content as expansion progresses
        content_opacity = max(0.0, min(1.0, (prog - 0.25) / 0.5))
        P.setOpacity(content_opacity * self.widget_fade)

        # ── Metal blur equivalent: radial glow ──
        if self.glow_alpha > 0.003:
            gc = self.glow_color
            gr = QRadialGradient(cx, cy, self.R * 3.2)
            gr.setColorAt(0,   QColor(gc[0], gc[1], gc[2], int(255 * self.glow_alpha)))
            gr.setColorAt(0.4, QColor(gc[0], gc[1], gc[2], int(255 * self.glow_alpha * 0.4)))
            gr.setColorAt(1,   QColor(gc[0], gc[1], gc[2], 0))
            P.setBrush(QBrush(gr))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), self.R * 3.2, self.R * 3.2)

        # ══════════════════════════════════════════════════
        # iOS FaceID + HyperOS SCANNING VISUALS
        # ══════════════════════════════════════════════════

        if self.ph == self.SCAN:

            # ── Grid mesh — iOS depth sensor pattern ──────
            if self.grid_alpha > 0.01:
                self._draw_grid(P, cx, cy)

            # ── Corner brackets: REMOVED ──

            # ── Breathing pulse — HyperOS inner glow ──────
            if self.pulse_alpha > 0.005:
                pg = QRadialGradient(cx, cy, self.pulse_r)
                pg.setColorAt(0,   QColor(0, 200, 255,
                              int(255 * self.pulse_alpha * 0.9)))
                pg.setColorAt(0.5, QColor(0, 150, 255,
                              int(255 * self.pulse_alpha * 0.4)))
                pg.setColorAt(1,   QColor(0, 100, 255, 0))
                P.setBrush(QBrush(pg))
                P.setPen(Qt.NoPen)
                P.drawEllipse(QPointF(cx, cy),
                              self.pulse_r, self.pulse_r)

            # ── Scan line sweep — HyperOS IR sweep ────────
            if self.scan_alpha > 0.01:
                self._draw_scan_line(P, cx, cy)

            # ── Ring 3: Slow outer orbit ───────────────────
            if self.ring3_alpha > 0.005:
                R3   = self.R + 26
                rect3= QRectF(cx - R3, cy - R3, R3*2, R3*2)
                pen3 = QPen(QColor(0, 180, 255,
                            int(255 * self.ring3_alpha)), 0.8,
                            Qt.DotLine)
                P.setPen(pen3)
                P.setBrush(Qt.NoBrush)
                P.drawEllipse(rect3)

            # ── Ring 2: REMOVED (was rotating inside face) ─

        # ── Ring 1: REMOVED (was rotating inside face icon) ──
        # Only draw static outer ring during non-scan phases
        if self.ring_alpha > 0.005 and self.ph != self.SCAN:
            rc       = self.ring_color
            arc_span = int(self.ring_arc * 360 * 16)
            pen      = QPen(QColor(rc[0], rc[1], rc[2],
                            int(255 * self.ring_alpha)), 1.8)
            P.setPen(pen)
            P.setBrush(Qt.NoBrush)
            rect = QRectF(cx - self.R - 16, cy - self.R - 16,
                          (self.R + 16) * 2, (self.R + 16) * 2)
            if arc_span >= 5760:
                P.drawEllipse(rect)
            else:
                P.drawArc(rect, 90 * 16, -arc_span)

        # ── Ripple — CASpringAnimation pop ──
        if self.ripple_alpha > 0.005:
            P.setPen(QPen(QColor(0, 230, 118, int(255 * self.ripple_alpha)), 1.2))
            P.setBrush(Qt.NoBrush)
            P.drawEllipse(QPointF(cx, cy), self.ripple_r, self.ripple_r)

        # ── iPhone Face ID brackets (rectangle frame) ──
        if self.ph == self.SCAN and self.bracket_show > 0.01:
            self._draw_faceid_brackets(P, cx, cy)

        # ── 3D sphere ring (SCAN, OK, FAIL phases) ──
        if self.ring_seg_alpha > 0.005:
            # ── Multi-axis shock shake during FAIL ──
            shx = getattr(self, "_shake_x",   0.0)
            shy = getattr(self, "_shake_y",   0.0)
            srt = getattr(self, "_shake_rot", 0.0)

            if abs(srt) > 0.001:
                # Rotation shake — pivot around sphere center
                P.save()
                P.translate(cx + sx + shx, cy + shy)
                P.rotate(srt * 57.2958)   # rad → deg
                self._draw_scan_ring(P, 0, 0)
                P.restore()
            else:
                self._draw_scan_ring(P, cx + sx + shx, cy + shy)

        # ── Face dots ──
        if self.face_alpha > 0.01:
            shake_x = getattr(self, "_shake_x", 0.0)

            # ── Motion blur: ghost trail on fast head turn ──
            # Speed estimated from face_dir change
            blur_strength = abs(getattr(self, "_face_dir_prev", 0)
                                - self.face_dir) * 60
            blur_strength = min(blur_strength, 1.0)

            if blur_strength > 0.08:
                # Single ghost trail (efficient)
                P.save()
                P.translate(cx + shake_x - self.face_dir * 7, cy)
                P.scale(self.face_scale, self.face_scale)
                P.setOpacity(0.10 * blur_strength)
                self._draw_dots(P)
                P.setOpacity(1.0)
                P.restore()

            # Store previous dir for next frame blur calc
            self._face_dir_prev = self.face_dir

            # ── Main face ──
            P.save()
            P.translate(cx + shake_x, cy)
            P.scale(self.face_scale, self.face_scale)
            self._draw_dots(P)
            P.restore()

        # ── Checkmark — CAShapeLayer strokeEnd draw-on ──
        if self.check_alpha > 0.01:
            P.save()
            P.translate(cx, cy)
            P.scale(self.face_scale, self.face_scale)
            self._draw_checkmark(P)
            P.restore()

        # ── X mark — CAShapeLayer strokeEnd draw-on ──
        if self.x_alpha > 0.01:
            self._draw_x(P, cx, cy)

        # ── Particles — Metal CAEmitterLayer equivalent ──
        self.particles.draw(P)

        # ── Text ──
        if self.txt_alpha > 0.01:
            self._draw_text(P, self.CX + sx)

        P.end()

        # ── Blit offscreen buffer → screen (atomic, no flicker) ──
        if not hasattr(self, "_buf") or self._buf is None:
            return
        screen = QPainter(self)
        if not screen.isActive():
            return
        screen.setRenderHint(QPainter.SmoothPixmapTransform, True)
        screen.drawPixmap(0, 0, self._buf)
        screen.end()

    # ── Draw helpers ───────────────────────────────────────
    def _draw_grid(self, P, cx, cy):
        """iOS depth sensor dot grid pattern"""
        import math
        spacing = 8.5
        R       = self.R * 0.88
        P.setPen(Qt.NoPen)

        # Animated wave distortion
        wave_t  = self.grid_phase

        rows = int(R * 2 / spacing) + 2
        cols = int(R * 2 / spacing) + 2

        for row in range(rows):
            for col in range(cols):
                gx = cx - R + col * spacing
                gy = cy - R + row * spacing

                # Circular clip
                dx = gx - cx
                dy = gy - cy
                if dx*dx + dy*dy > R*R:
                    continue

                # Wave distortion (HyperOS breathing grid)
                dist   = math.sqrt(dx*dx + dy*dy) / R
                wave   = math.sin(dist * 5 - wave_t * 3) * 0.5 + 0.5
                edge   = 1.0 - dist

                alpha  = int(255 * self.grid_alpha * wave * edge * 0.7)
                if alpha < 4:
                    continue

                sz = 0.9 + 0.6 * wave
                P.setBrush(QBrush(QColor(0, 200, 255, alpha)))
                P.drawEllipse(QPointF(gx, gy), sz, sz)

    def _draw_scan_line(self, P, cx, cy):
        """HyperOS IR scan line sweep"""
        import math
        sy    = cy + self.scan_y
        R     = self.R * 0.9
        half_w= math.sqrt(max(0, R*R - self.scan_y**2))

        if half_w < 2:
            return

        # Horizontal scan line with gradient fade
        lg = QLinearGradient(cx - half_w, sy, cx + half_w, sy)
        a  = int(255 * self.scan_alpha)
        lg.setColorAt(0,    QColor(0, 200, 255, 0))
        lg.setColorAt(0.2,  QColor(0, 220, 255, int(a * 0.6)))
        lg.setColorAt(0.5,  QColor(100, 230, 255, a))
        lg.setColorAt(0.8,  QColor(0, 220, 255, int(a * 0.6)))
        lg.setColorAt(1,    QColor(0, 200, 255, 0))

        P.setBrush(QBrush(lg))
        P.setPen(Qt.NoPen)
        P.drawRect(QRectF(cx - half_w, sy - 1.0,
                          half_w * 2,   2.0))

        # Glow above line
        lg2 = QLinearGradient(cx - half_w, sy - 8, cx + half_w, sy - 8)
        lg2.setColorAt(0,   QColor(0, 200, 255, 0))
        lg2.setColorAt(0.5, QColor(0, 200, 255, int(a * 0.15)))
        lg2.setColorAt(1,   QColor(0, 200, 255, 0))
        P.setBrush(QBrush(lg2))
        P.drawRect(QRectF(cx - half_w, sy - 8, half_w * 2, 8))

    def _draw_brackets(self, P, cx, cy):
        """HyperOS corner face brackets"""
        import math
        BW  = int((self.R + 22) * self.bracket_scale)
        BH  = int((self.R + 28) * self.bracket_scale)
        LEN = 14   # bracket arm length
        THK = 2.2  # line thickness

        a   = int(255 * self.bracket_alpha)
        col = QColor(0, 210, 255, a)
        P.setPen(QPen(col, THK, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)

        corners = [
            (cx - BW, cy - BH, +1, +1),  # top-left
            (cx + BW, cy - BH, -1, +1),  # top-right
            (cx - BW, cy + BH, +1, -1),  # bottom-left
            (cx + BW, cy + BH, -1, -1),  # bottom-right
        ]
        for (bx, by, dx, dy) in corners:
            P.drawLine(QPointF(bx, by),
                       QPointF(bx + dx * LEN, by))
            P.drawLine(QPointF(bx, by),
                       QPointF(bx, by + dy * LEN))

    def _draw_mesh_lines(self, P, cx, cy):
        """
        iPhone Face ID flowing wave mesh lines.
        Lines travel from bottom to top with wave distortion,
        clipped to face area (circle).
        """
        import math

        FACE_R = self.R * 0.95

        for line in self.mesh_lines:
            y_pos = line["y"]
            # Clip: only draw if within face circle bounds
            if abs(y_pos) > FACE_R * 1.1:
                continue

            # Calculate horizontal width at this y (circular clip)
            dy = y_pos
            if abs(dy) >= FACE_R:
                continue
            half_w = math.sqrt(FACE_R * FACE_R - dy * dy)

            # Line fade: stronger in middle of face, fade at edges
            edge_fade = 1.0 - (abs(dy) / FACE_R) ** 2
            life_fade = max(0, 1.0 - abs(y_pos / (FACE_R * 1.1)))
            alpha     = self.mesh_alpha * edge_fade * life_fade * 0.85

            if alpha < 0.02:
                continue

            # Draw wave line: multiple segments for smooth curve
            segments = 40
            points   = []
            for i in range(segments + 1):
                t      = i / segments
                # X position: from -half_w to +half_w
                lx     = -half_w + t * (half_w * 2)
                # Y wave distortion (silk flowing effect)
                wave_y = math.sin(t * line["freq"] * math.pi * 2 +
                                  line["phase"]) * line["amp"] * edge_fade * 0.4
                ly     = y_pos + wave_y
                points.append((cx + lx, cy + ly))

            # Draw line with gradient pen
            a = int(255 * alpha)

            # Outer glow
            P.setPen(QPen(QColor(100, 200, 255, int(a * 0.3)), 3.5,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.setBrush(Qt.NoBrush)
            path = QPainterPath()
            path.moveTo(points[0][0], points[0][1])
            for px, py in points[1:]:
                path.lineTo(px, py)
            P.drawPath(path)

            # Main line (bright)
            P.setPen(QPen(QColor(255, 255, 255, a), 1.5,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.drawPath(path)

            # Subtle cyan tint
            P.setPen(QPen(QColor(180, 230, 255, int(a * 0.6)), 0.8,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.drawPath(path)

    def _draw_scan_ring(self, P, cx, cy):
        """
        iOS Face ID 3D wireframe sphere — production grade.

        Features:
          • PERSPECTIVE PROJECTION (true 3D depth)
          • DEPTH-SORTED rendering (back-to-front)
          • ANTI-ALIASED lines (HighQualityAA)
          • SCANLINE SHIMMER (subtle wave)
          • CHROMATIC ABERRATION on bright edges
          • Frame-rate independent (dt-based rotation)
        """
        import math
        from PyQt5.QtCore import QRectF, QPointF
        from PyQt5.QtGui import QRadialGradient

        seg_a = self.ring_seg_alpha
        if seg_a < 0.005:
            return

        R       = 55.0
        morph   = self.ring_to_check
        rc      = self.ring_color
        base_a  = int(255 * seg_a)
        t       = self.ring_rot

        # ── Force max-quality anti-aliasing for sphere ──
        P.setRenderHint(QPainter.Antialiasing,           True)
        P.setRenderHint(QPainter.TextAntialiasing,       True)
        try:
            P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except AttributeError:
            pass   # Qt6 removed this, AA hint is enough

        if morph >= 0.95:
            fa = int(base_a * seg_a)
            if fa > 4:
                P.setPen(QPen(QColor(rc[0], rc[1], rc[2],
                                     fa // 3), 7))
                P.setBrush(Qt.NoBrush)
                P.drawEllipse(QPointF(cx, cy), R, R)
                P.setPen(QPen(QColor(rc[0], rc[1], rc[2], fa), 3.8))
                P.drawEllipse(QPointF(cx, cy), R, R)
            return

        # ════════════════════════════════════════════════
        # PERSPECTIVE PROJECTION setup
        # focal_length controls "lens" — smaller = more dramatic
        # ════════════════════════════════════════════════
        FOCAL = 160.0   # virtual camera focal length
        CAM_Z = 180.0   # camera distance from sphere center

        def project(x, y, z):
            """
            Perspective projection: world (x,y,z) → screen (sx,sy,scale,depth)
            Returns scale_factor so caller can size strokes/glow by depth.
            """
            # Z-distance from camera (sphere centered at world origin)
            dist = CAM_Z - z
            if dist < 1.0:
                dist = 1.0
            scale = FOCAL / dist
            sx_ = x * scale
            sy_ = y * scale
            # depth_t: 0 = farthest back, 1 = closest front
            depth_t = (z + R) / (2 * R)
            return sx_, sy_, scale, depth_t

        # ════════════════════════════════════════════════
        # Generate all segments from all rings, with depth
        # Then DEPTH SORT (back-to-front) before drawing
        # ════════════════════════════════════════════════
        N_POINTS = 44

        rings_config = [
            ('Y',  0.0,        1.00, 0.95),
            ('X',  math.pi/3,  0.85, 0.90),
            ('Z',  math.pi/2,  0.70, 0.80),
            ('XY', math.pi/4,  1.15, 0.75),
        ]

        def gen_ring(axis, angle, n_pts):
            """Generate 3D points for a ring rotated in 3D space."""
            pts = []
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            for i in range(n_pts + 1):
                theta = (i / n_pts) * 2 * math.pi
                x = R * math.cos(theta)
                y = R * math.sin(theta)
                z = 0.0
                if axis == 'Y':
                    nx = x * cos_a + z * sin_a
                    nz = -x * sin_a + z * cos_a
                    x, z = nx, nz
                elif axis == 'X':
                    ny = y * cos_a - z * sin_a
                    nz = y * sin_a + z * cos_a
                    y, z = ny, nz
                elif axis == 'Z':
                    nx = x * cos_a - y * sin_a
                    ny = x * sin_a + y * cos_a
                    x, y = nx, ny
                elif axis == 'XY':
                    nx = x * cos_a + z * sin_a
                    nz = -x * sin_a + z * cos_a
                    x, z = nx, nz
                    ny = y * cos_a - z * sin_a
                    nz = y * sin_a + z * cos_a
                    y, z = ny, nz
                pts.append((x, y, z))
            return pts

        # ── Collect ALL segments with their average depth ──
        # Each item: (avg_z, x1, y1, z1, x2, y2, z2, ring_alpha)
        all_segments = []
        for axis, phase, speed, b_alpha in rings_config:
            ring_angle = t * speed + phase
            pts = gen_ring(axis, ring_angle, N_POINTS)
            for i in range(len(pts) - 1):
                x1, y1, z1 = pts[i]
                x2, y2, z2 = pts[i + 1]
                avg_z = (z1 + z2) * 0.5
                all_segments.append(
                    (avg_z, x1, y1, z1, x2, y2, z2, b_alpha)
                )

        # ── DEPTH SORT: back (lowest z) first, front (highest z) last ──
        all_segments.sort(key=lambda seg: seg[0])

        # ── Scanline shimmer: subtle wave that travels through sphere ──
        # Frame-rate independent (uses ring_rot which is dt-based)
        shimmer_phase = t * 1.5

        # ════════════════════════════════════════════════
        # Draw sorted segments back-to-front
        # ════════════════════════════════════════════════
        for (avg_z, x1, y1, z1, x2, y2, z2, b_alpha) in all_segments:
            # Project both endpoints with perspective
            sx1, sy1, scale1, d1 = project(x1, y1, z1)
            sx2, sy2, scale2, d2 = project(x2, y2, z2)

            avg_scale = (scale1 + scale2) * 0.5
            avg_depth = (d1 + d2) * 0.5

            # Brightness: front bright, back dim (perceptual)
            depth_bright = 0.18 + 0.82 * avg_depth

            # Scanline shimmer: subtle wave modulates brightness
            # +/- 12% based on y position
            avg_y_world = (y1 + y2) * 0.5
            shimmer = 1.0 + 0.10 * math.sin(
                shimmer_phase + avg_y_world * 0.08
            )

            seg_alpha = int(base_a * b_alpha * depth_bright * shimmer
                            * (1.0 - morph * 0.85))
            if seg_alpha < 3:
                continue

            # Stroke width scaled by perspective (closer = thicker)
            stroke_w = (1.0 + 1.5 * avg_depth) * (avg_scale / 1.4)
            stroke_w = max(0.6, min(stroke_w, 4.5))

            # Screen coords (Y flipped — Qt Y is down)
            p1 = QPointF(cx + sx1, cy - sy1)
            p2 = QPointF(cx + sx2, cy - sy2)

            # ── Outer glow (front segments only — saves draws) ──
            if avg_depth > 0.55:
                ga = max(0, seg_alpha // 4)
                if ga > 2:
                    P.setPen(QPen(QColor(rc[0], rc[1], rc[2], ga),
                                  stroke_w + 3.5,
                                  Qt.SolidLine, Qt.RoundCap))
                    P.drawLine(p1, p2)

            # ── Chromatic aberration on BRIGHT front segments ──
            # Red shift on one side, blue shift on other
            # Real lens effect — adds "alive" feel
            if avg_depth > 0.75 and seg_alpha > 100:
                # Red ghost (1px offset)
                red_a = int(seg_alpha * 0.25)
                P.setPen(QPen(QColor(255, 80, 80, red_a),
                              stroke_w * 0.7,
                              Qt.SolidLine, Qt.RoundCap))
                P.drawLine(
                    QPointF(p1.x() + 0.7, p1.y()),
                    QPointF(p2.x() + 0.7, p2.y())
                )
                # Blue ghost (-1px offset)
                blue_a = int(seg_alpha * 0.20)
                P.setPen(QPen(QColor(80, 150, 255, blue_a),
                              stroke_w * 0.7,
                              Qt.SolidLine, Qt.RoundCap))
                P.drawLine(
                    QPointF(p1.x() - 0.7, p1.y()),
                    QPointF(p2.x() - 0.7, p2.y())
                )

            # ── Main line ──
            P.setPen(QPen(QColor(rc[0], rc[1], rc[2], seg_alpha),
                          stroke_w,
                          Qt.SolidLine, Qt.RoundCap))
            P.drawLine(p1, p2)

            # ── Inner highlight on brightest front segments ──
            if avg_depth > 0.80 and seg_alpha > 120:
                hi_a = int(seg_alpha * 0.45)
                P.setPen(QPen(QColor(255, 255, 255, hi_a),
                              stroke_w * 0.35,
                              Qt.SolidLine, Qt.RoundCap))
                P.drawLine(p1, p2)

        # ════════════════════════════════════════════════
        # Center radial glow — adds depth/volume
        # ════════════════════════════════════════════════
        core_a = int(base_a * 0.4 * (1.0 - morph))
        if core_a > 4:
            rg = QRadialGradient(cx, cy, R * 0.45)
            rg.setColorAt(0,   QColor(rc[0], rc[1], rc[2], core_a))
            rg.setColorAt(0.5, QColor(rc[0], rc[1], rc[2],
                                      core_a // 3))
            rg.setColorAt(1,   QColor(rc[0], rc[1], rc[2], 0))
            P.setPen(Qt.NoPen)
            P.setBrush(QBrush(rg))
            P.drawEllipse(QPointF(cx, cy), R * 0.45, R * 0.45)


    def _draw_faceid_brackets(self, P, cx, cy):
        """
        Professional Face ID frame morph:
          shape_morph 0.0 → rounded-corner rectangle with bracket gaps
          shape_morph 1.0 → perfect circle (continuous ring)
          bracket_show controls overall opacity (fade in/out)

        Both rectangle and circle share same bounding box for smooth morph.
        Final circle radius matches face icon for visual harmony.
        """
        import math
        from PyQt5.QtCore import QRectF

        if self.bracket_show < 0.01:
            return

        a   = int(255 * self.bracket_show)
        col = QColor(30, 120, 245, a)
        P.setPen(QPen(col, 5.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)

        # ── PROFESSIONAL SIZING ────────────────────────────
        # Single unified size — frame ALWAYS this big
        # Both rectangle and circle fit this exact bounding box
        FRAME_R = 56                # half-size (same for both shapes)

        # Morph parameter
        m  = max(0.0, min(1.0, self.shape_morph))
        em = m * m * (3 - 2 * m)    # smoothstep easing

        # Corner radius interpolation
        # m=0: small bracket curve (16px)
        # m=1: equals FRAME_R → perfect circle
        SMALL_R  = 18
        cr       = SMALL_R + (FRAME_R - SMALL_R) * em

        # Edge arm length
        # m=0: short bracket arms (24px) — leaves gap in middle
        # m=1: arms grow until they merge (full edge filled)
        straight_len = max(0.0, 2 * FRAME_R - 2 * cr)
        ARM_MIN      = 22
        full_arm     = straight_len / 2
        arm_len      = ARM_MIN + (full_arm - ARM_MIN) * em
        arm_len      = max(0.0, min(arm_len, full_arm))

        # ── Edge coordinates (fixed bounding box) ──────────
        top_y   = cy - FRAME_R
        bot_y   = cy + FRAME_R
        left_x  = cx - FRAME_R
        right_x = cx + FRAME_R

        # ── Draw 4 corner arcs (quarter circles) ──────────
        corners = [
            (cx - FRAME_R + cr, cy - FRAME_R + cr,  90),  # top-left
            (cx + FRAME_R - cr, cy - FRAME_R + cr,   0),  # top-right
            (cx + FRAME_R - cr, cy + FRAME_R - cr, 270),  # bottom-right
            (cx - FRAME_R + cr, cy + FRAME_R - cr, 180),  # bottom-left
        ]
        for (ax, ay, start_deg) in corners:
            rect = QRectF(ax - cr, ay - cr, cr * 2, cr * 2)
            P.drawArc(rect, start_deg * 16, 90 * 16)

        # ── Skip arms when fully circular (corners already touch) ──
        if cr >= FRAME_R - 0.5:
            return

        # ── Edge points where straight lines start/end ──
        e_left  = left_x  + cr
        e_right = right_x - cr
        e_top   = top_y   + cr
        e_bot   = bot_y   - cr

        # ── Draw 8 straight arms (2 per edge) ──
        # Top edge
        P.drawLine(QPointF(e_left,  top_y),
                   QPointF(e_left + arm_len, top_y))
        P.drawLine(QPointF(e_right - arm_len, top_y),
                   QPointF(e_right, top_y))
        # Bottom edge
        P.drawLine(QPointF(e_left,  bot_y),
                   QPointF(e_left + arm_len, bot_y))
        P.drawLine(QPointF(e_right - arm_len, bot_y),
                   QPointF(e_right, bot_y))
        # Left edge
        P.drawLine(QPointF(left_x, e_top),
                   QPointF(left_x, e_top + arm_len))
        P.drawLine(QPointF(left_x, e_bot - arm_len),
                   QPointF(left_x, e_bot))
        # Right edge
        P.drawLine(QPointF(right_x, e_top),
                   QPointF(right_x, e_top + arm_len))
        P.drawLine(QPointF(right_x, e_bot - arm_len),
                   QPointF(right_x, e_bot))

    def _draw_dots(self, P):
        """
        iPhone Face ID style face icon with head-turn animation.
        Shows circle outline + eyes + nose + smile.
        Face direction shifts based on self.face_dir:
            -1.0 = full left, 0.0 = front, +1.0 = full right
        """
        import math

        fc = self.face_color
        a  = int(255 * self.face_alpha)
        if a < 4:
            return

        # Face direction offset (parallax for side view)
        d = self.face_dir   # -1 to +1

        # ── Face outline: drawn by brackets function (morphed) ──
        # No separate circle here — brackets→circle morph handled
        # in _draw_faceid_brackets

        # ── Facial features (eyes, nose, smile) ──────────
        if self.eye_alpha > 0.01:
            ea = int(255 * self.eye_alpha * self.face_alpha)

            # ── Eyes (vertical thick lines, iPhone Face ID style) ──
            # Sized to fit FRAME_R=56 bounding box
            eye_y     = -14
            eye_sep   = 18
            eye_len   = 14    # vertical eye line length
            eye_thick = 4.5

            # Parallax shift for side view (NO fading — both eyes stay full)
            shift = d * 8

            # ── Left eye (always full opacity, only blinks during wink) ──
            le_open = self.left_eye_open
            if le_open > 0.05:
                P.setPen(QPen(QColor(fc[0], fc[1], fc[2], ea),
                              eye_thick, Qt.SolidLine, Qt.RoundCap))
                lx = -eye_sep + shift
                half_len = (eye_len / 2) * le_open
                P.drawLine(QPointF(lx, eye_y - half_len),
                           QPointF(lx, eye_y + half_len))

            # ── Right eye (always full opacity, only blinks during wink) ──
            re_open = self.right_eye_open
            if re_open > 0.05:
                P.setPen(QPen(QColor(fc[0], fc[1], fc[2], ea),
                              eye_thick, Qt.SolidLine, Qt.RoundCap))
                rx = eye_sep + shift
                half_len = (eye_len / 2) * re_open
                P.drawLine(QPointF(rx, eye_y - half_len),
                           QPointF(rx, eye_y + half_len))

            # ── Nose (J/curve shape) ──────────────────────
            P.setPen(QPen(QColor(fc[0], fc[1], fc[2], ea),
                          4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            P.setBrush(Qt.NoBrush)
            nose_x = shift * 0.5
            nose_path = QPainterPath()
            nose_path.moveTo(nose_x, -3)
            nose_path.lineTo(nose_x, 11)
            nose_path.quadTo(nose_x, 16, nose_x - 6, 16)
            P.drawPath(nose_path)

            # ── Smile (curved arc) ────────────────────────
            sm_w = 30
            sm_h = 20
            sm_x = shift * 0.3
            P.setPen(QPen(QColor(fc[0], fc[1], fc[2], ea),
                          4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            smile_rect = QRectF(sm_x - sm_w / 2, 24 - sm_h / 2,
                                sm_w, sm_h)
            P.drawArc(smile_rect, 200 * 16, 140 * 16)

    def _draw_checkmark(self, P):
        """
        CAShapeLayer strokeEnd animation equivalent.
        Draws checkmark progressively from stroke=0 to stroke=1.
        Circle ring draws first, then tick strokes on.
        """
        a = int(255 * self.check_alpha)
        if a < 4: return

        # Circle — draws as arc first (strokeEnd on circle)
        circle_done  = min(self.check_stroke / 0.4, 1.0)
        arc_span     = int(circle_done * 360 * 16)
        P.setPen(QPen(QColor(0, 230, 118, a), 2.4,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        if arc_span >= 5760:
            P.drawEllipse(QPointF(0, 0), 30, 30)
        else:
            P.drawArc(QRectF(-30, -30, 60, 60), 90 * 16, -arc_span)

        # Tick — draws after circle completes (strokeEnd on path)
        if self.check_stroke > 0.4:
            tick_prog = (self.check_stroke - 0.4) / 0.6

            p1 = QPointF(-13,  2)
            p2 = QPointF( -4, 12)
            p3 = QPointF( 15,-10)

            P.setPen(QPen(QColor(0, 230, 118, a), 3.0,
                          Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

            if tick_prog < 0.45:
                # First stroke segment draws on
                t   = tick_prog / 0.45
                mid = QPointF(p1.x() + (p2.x() - p1.x()) * t,
                              p1.y() + (p2.y() - p1.y()) * t)
                P.drawLine(p1, mid)
            else:
                P.drawLine(p1, p2)
                # Second stroke segment draws on
                t   = (tick_prog - 0.45) / 0.55
                end = QPointF(p2.x() + (p3.x() - p2.x()) * t,
                              p2.y() + (p3.y() - p2.y()) * t)
                P.drawLine(p2, end)

    def _draw_x(self, P, cx, cy):
        """CAShapeLayer strokeEnd — X draws itself diagonally"""
        a  = int(255 * self.x_alpha)
        if a < 4: return

        # Circle ring
        circle_done = min(self.x_stroke / 0.35, 1.0)
        arc_span    = int(circle_done * 360 * 16)
        P.setPen(QPen(QColor(255, 74, 74, a), 2.2))
        P.setBrush(Qt.NoBrush)
        if arc_span >= 5760:
            P.drawEllipse(QPointF(cx, cy), 30, 30)
        else:
            P.drawArc(QRectF(cx-30, cy-30, 60, 60), 90*16, -arc_span)

        # X strokes draw on sequentially
        if self.x_stroke > 0.35:
            xp  = (self.x_stroke - 0.35) / 0.65
            d   = 11
            P.setPen(QPen(QColor(255, 74, 74, a), 2.8,
                          Qt.SolidLine, Qt.RoundCap))
            if xp < 0.5:
                # First diagonal
                t   = xp / 0.5
                end = QPointF(cx - d + (2 * d) * t,
                              cy - d + (2 * d) * t)
                P.drawLine(QPointF(cx - d, cy - d), end)
            else:
                P.drawLine(QPointF(cx - d, cy - d),
                           QPointF(cx + d, cy + d))
                # Second diagonal
                t   = (xp - 0.5) / 0.5
                end = QPointF(cx + d - (2 * d) * t,
                              cy - d + (2 * d) * t)
                P.drawLine(QPointF(cx + d, cy - d), end)

    def _draw_text(self, P, cx):
        # ── iOS-style text: slide-up + fade in ──
        f = QFont("SF Pro Display, Helvetica Neue, Noto Sans, Arial")
        f.setPixelSize(13)
        f.setWeight(QFont.Light)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        P.setFont(f)

        tc  = self.txt_color
        alpha = self.txt_alpha

        # Slide-up offset: text rises 8px as it fades in
        # When alpha=0 → offset=8, when alpha=1 → offset=0
        # Cubic ease makes it feel natural
        ease_a  = alpha * alpha * (3 - 2 * alpha)   # smoothstep
        slide_y = int(8 * (1.0 - ease_a))

        fm  = P.fontMetrics()
        tw  = fm.horizontalAdvance(self.txt)
        ty  = self.CY + self.R + 60 + slide_y

        # Soft text shadow for depth
        P.setPen(QPen(QColor(0, 0, 0, int(120 * alpha)), 1))
        P.drawText(cx - tw // 2 + 1, ty + 1, self.txt)

        # Main text
        P.setPen(QPen(QColor(tc[0], tc[1], tc[2],
                             int(255 * alpha))))
        P.drawText(cx - tw // 2, ty, self.txt)

    # ── Helpers ────────────────────────────────────────────
    def _lerp(self, a, b, t):
        t = max(0.0, min(1.0, t))
        return [int(a[i] + (b[i] - a[i]) * t) for i in range(3)]

    def _ease_out(self, t):
        """kCAMediaTimingFunctionEaseOut equivalent"""
        t = max(0.0, min(1.0, t))
        return 1 - pow(1 - t, 3)

    def _ease_out_spring(self, t):
        """Spring overshoot easing for Dynamic Island"""
        import math
        t = max(0.0, min(1.0, t))
        if t < 0.001:
            return 0.0
        if t > 0.999:
            return 1.0
        # Spring with overshoot then settle
        return 1 + pow(2, -8 * t) * math.sin((t - 0.1) * math.pi * 3.5) * -1

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()


# ══════════════════════════════════════════════════════════════
# FACE WORKER THREAD
# ══════════════════════════════════════════════════════════════
class FaceWorker(QThread):
    def __init__(self, sig):
        super().__init__()
        self.sig    = sig
        self.on     = True
        self.result = None

    def stop(self):
        self.on = False

    def run(self):
        try:
            import cv2, numpy as np, face_recognition
            from nova_unlock.vision.face_recognizer import (
                get_enrolled_users, load_face, THRESHOLD
            )

            pf = {}
            for u in get_enrolled_users():
                e = load_face(u)
                if e is not None:
                    pf[u] = e

            if not pf:
                # Route to fail animation instead of instant close
                if hasattr(self.sig, "_widget_ref"):
                    w = self.sig._widget_ref
                    if w is not None:
                        w._next_after_scan = 20   # fail path
                self.sig.fail.emit()
                return

            cap = None
            for i in range(3):
                c = cv2.VideoCapture(i)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_BUFFERSIZE,    1)
                    c.set(cv2.CAP_PROP_FRAME_WIDTH,  320)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    c.set(cv2.CAP_PROP_FPS,           30)
                    r, _ = c.read()
                    if r:
                        cap = c; break
                c.release()

            if not cap:
                self.sig.fail.emit(); return

            for _ in range(4): cap.read()

            for attempt in range(3):
                if not self.on: break
                embs = []
                for _ in range(6):
                    if not self.on: break
                    r, f = cap.read()
                    if not r: continue
                    try:
                        rgb  = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(rgb, model="hog")
                        if locs:
                            enc = face_recognition.face_encodings(rgb, locs)
                            if enc: embs.append(enc[0])
                    except: pass
                    time.sleep(0.04)

                if not embs:
                    self.sig.fail.emit()
                    time.sleep(2.0)
                    continue

                live = np.mean(embs, axis=0)
                bu, bd = None, 999.0
                for u, s in pf.items():
                    d = float(face_recognition.face_distance([s], live)[0])
                    if d < bd: bd, bu = d, u

                if bd <= THRESHOLD:
                    self.result = bu
                    self.sig.ok.emit(bu)
                    cap.release(); return
                else:
                    self.sig.fail.emit()
                    time.sleep(2.0)

            cap.release()
            self.sig.fail.emit()

        except:
            import traceback; traceback.print_exc()
            self.sig.fail.emit()


# ══════════════════════════════════════════════════════════════
# APP RUNNER
# ══════════════════════════════════════════════════════════════
class FaceIDLoginApp:
    def __init__(self):
        self.result = None

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()
        w   = FaceUnlockWidget(sig, demo_mode=False)

        scr = app.primaryScreen().geometry()
        # Top-center, touching top edge (camera position)
        w.move((scr.width() - w.W) // 2, 0)
        w.show(); w.raise_(); w.activateWindow()

        def force_top():
            try:
                wid = int(w.winId())
                subprocess.run(["xdotool","windowraise", str(wid)],
                               capture_output=True, timeout=2)
            except: pass
            w.raise_(); w.activateWindow()

        top = QTimer()
        top.timeout.connect(force_top)
        top.start(300)
        QTimer.singleShot(100,  force_top)
        QTimer.singleShot(500,  force_top)
        QTimer.singleShot(1000, force_top)

        wk = FaceWorker(sig)

        def done(n):
            self.result = n
            top.stop()
            QTimer.singleShot(2800, app.quit)

        sig.ok.connect(done)
        wk.start()
        app.exec_()
        wk.stop(); wk.wait(2000)
        return self.result


# ══════════════════════════════════════════════════════════════
# DEMO / TEST
# ══════════════════════════════════════════════════════════════
def demo():
    app = QApplication(sys.argv)
    sig = Sig()
    w   = FaceUnlockWidget(sig, demo_mode=True)
    scr = app.primaryScreen().geometry()
    # Top-center, touching top edge (camera position)
    w.move((scr.width() - w.W) // 2, 0)
    w.show()
    app.exec_()

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        print(f"User: {FaceIDLoginApp().run()}")
    else:
        demo()
