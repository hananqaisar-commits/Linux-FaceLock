#!/usr/bin/env python3
"""
NovaUnlock — Authentic iOS Dynamic Island Face ID
- SCAN: Lock 🔒 + Camera ⚪ icons
- SUCCESS: Realistic green 3D wireframe sphere (like real iOS)
           Lock simultaneously animates to UNLOCKED 🔓
           Screen unlocks ONLY after full animation complete
- FAIL: Island shakes left-right smoothly
"""
import sys, math, time, struct, wave, tempfile, os, subprocess, random
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore    import (Qt, QTimer, QPointF, QRectF,
                              pyqtSignal, QObject, QThread)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QFont,
                              QRadialGradient, QLinearGradient,
                              QBrush, QPainterPath)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

# ══════════════════════════════════════════════════════════════
# SOUND
# ══════════════════════════════════════════════════════════════
SDIR = tempfile.mkdtemp(prefix="nova_snd_")

def _wav(name, samples, rate=44100):
    path = os.path.join(SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h', max(-32767, min(32767, int(s)))))
    return path

def _pluck(freq, dur, vol=0.4, rate=44100):
    n = int(rate * dur)
    delay = max(1, int(rate / freq))
    buf = [random.uniform(-1, 1) * vol for _ in range(delay)]
    out = []
    for i in range(n):
        idx = i % delay
        nxt = (buf[idx] + buf[(idx + 1) % delay]) * 0.498
        buf[idx] = nxt
        t = i / rate
        env = math.exp(-t * 3.5)
        out.append(32767 * nxt * env)
    return out

def _whoosh(start_f, end_f, dur, vol=0.3, rate=44100):
    n = int(rate * dur); out = []; prev = 0.0
    for i in range(n):
        t = i / rate
        freq = start_f + (end_f - start_f) * (t / dur)
        noise = random.uniform(-1, 1)
        prev = prev * 0.85 + noise * 0.15
        env = min(1, t * 30) * math.exp(-t * 3) * vol
        tone = math.sin(2 * math.pi * freq * t) * 0.5
        out.append(32767 * env * (tone + prev * 0.4))
    return out

def _bell(freq, dur, vol=0.4, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        env = math.exp(-t * 4.5) * vol
        s = math.sin(2 * math.pi * freq * t)
        s += math.sin(2 * math.pi * freq * 2.0 * t) * 0.3
        out.append(32767 * env * s * 0.5)
    return out

def mk_pop():
    return _wav("pop.wav", _whoosh(180, 800, 0.18, vol=0.15))

def mk_ok():
    lead = _pluck(1046.5, 0.50, vol=0.40)
    peak = max(abs(x) for x in lead) if lead else 1
    if peak > 30000:
        lead = [x * 30000 / peak for x in lead]
    return _wav("ok.wav", lead)

def mk_fail():
    s = _bell(330, 0.18, 0.30) + _bell(247, 0.22, 0.30)
    return _wav("fail.wav", s)

def mk_collapse():
    return _wav("collapse.wav", _whoosh(800, 180, 0.15, vol=0.12))

SND_POP      = mk_pop()
SND_OK       = mk_ok()
SND_FAIL     = mk_fail()
SND_COLLAPSE = mk_collapse()

def play(path):
    try:
        subprocess.Popen(
            ["paplay", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ,
                 "XDG_RUNTIME_DIR": os.environ.get(
                     "XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}
        )
    except Exception:
        try:
            subprocess.Popen(["aplay", "-q", "-D", "default", path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
class Sig(QObject):
    ok = pyqtSignal(str)
    fail = pyqtSignal()
    unlock_complete = pyqtSignal()  # emitted ONLY after sphere animation done

class Spring:
    def __init__(self, mass=1.0, stiffness=180.0, damping=18.0):
        self.m = mass; self.k = stiffness; self.d = damping
        self.x = 0.0; self.v = 0.0
    def reset(self, x=1.0, v=0.0):
        self.x = x; self.v = v
    def _derivatives(self, x, v):
        return v, (-self.k * x - self.d * v) / self.m
    def step(self, dt=0.016):
        x, v = self.x, self.v
        dx1, dv1 = self._derivatives(x, v)
        dx2, dv2 = self._derivatives(x + dx1*dt*0.5, v + dv1*dt*0.5)
        dx3, dv3 = self._derivatives(x + dx2*dt*0.5, v + dv2*dt*0.5)
        dx4, dv4 = self._derivatives(x + dx3*dt, v + dv3*dt)
        self.x += (dt / 6.0) * (dx1 + 2*dx2 + 2*dx3 + dx4)
        self.v += (dt / 6.0) * (dv1 + 2*dv2 + 2*dv3 + dv4)
        return self.x

# ══════════════════════════════════════════════════════════════
# MAIN WIDGET
# ══════════════════════════════════════════════════════════════
class FaceUnlockWidget(QWidget):
    IDLE = 0
    SCAN = 1
    OK   = 2
    FAIL = 3

    W  = 420
    H  = 160

    PILL_W = 280
    PILL_H = 38
    PILL_Y = 8

    def __init__(self, sig, demo_mode=False):
        super().__init__()
        self.sig = sig
        self.demo_mode = demo_mode
        self.sig.ok.connect(self._on_ok)
        self.sig.fail.connect(self._on_fail)

        self.ph = self.IDLE
        self.t0 = time.time()
        self.nm = ""
        self._last_tick = time.time()

        self.appear_t = 0.0
        self.appear_prog = 0.0
        self._pop_played = False

        self.shake_t = -1.0
        self.shake_amp = 0.0

        # Lock state
        self.lock_alpha = 0.0
        self.lock_open_prog = 0.0   # 0 = locked, 1 = unlocked (shackle up)

        # Camera state
        self.cam_alpha  = 0.0
        self.cam_pulse_t = 0.0
        self.cam_fade_out = 0.0

        # 3D Sphere
        self.sphere_alpha  = 0.0
        self.sphere_scale  = 0.0
        self.sphere_rot_x  = 0.0   # X axis (pitch)
        self.sphere_rot_y  = 0.0   # Y axis (yaw)
        self.sphere_rot_z  = 0.0   # Z axis (roll)
        self.sphere_color  = [48, 209, 88]  # iOS authentic green

        self.widget_fade = 1.0
        self._unlock_emitted = False  # only emit unlock once

        self._pending_ok = False
        self._pending_ok_user = None

        self._demo_cycle = 0

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )
        self.setFixedSize(self.W, self.H)

        self._tmr = QTimer()
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

    def _on_ok(self, n):
        if self.ph == self.OK: return
        self._pending_ok_user = n
        self._pending_ok = True
        if self.appear_prog >= 0.95:
            self._trigger_ok(n)

    def _trigger_ok(self, n):
        if self.ph == self.OK: return
        self.ph = self.OK
        self.t0 = time.time()
        self.nm = n
        self._pending_ok = False
        self._unlock_emitted = False
        play(SND_OK)

    def _on_fail(self):
        if self.ph == self.OK: return
        if self.ph == self.FAIL: return
        self.ph = self.FAIL
        self.t0 = time.time()
        self.shake_t = 0.0
        self.shake_amp = 14.0
        play(SND_FAIL)

    def _tick(self):
        now = time.time()
        raw_dt = min(now - self._last_tick, 0.040)
        self._last_tick = now

        if not hasattr(self, "_sdt"):
            self._sdt = 0.016
        self._sdt = self._sdt * 0.80 + raw_dt * 0.20
        dt = max(0.006, self._sdt)
        p = now - self.t0

        # Appear animation
        self.appear_t += dt
        if self.appear_prog < 1.0:
            T = 0.45
            if self.appear_t >= T:
                self.appear_prog = 1.0
            else:
                t = self.appear_t / T
                ease = 1 - pow(1 - t, 5)
                bump = math.sin(t * math.pi) * 0.04 * math.exp(-t * 3)
                self.appear_prog = min(1.04, ease + bump)

            if not self._pop_played and self.appear_t > 0.05:
                play(SND_POP)
                self._pop_played = True

        self.cam_pulse_t += dt

        # Shake decay
        if self.shake_t >= 0:
            self.shake_t += dt
            T_SHAKE = 0.65
            if self.shake_t >= T_SHAKE:
                self.shake_t = -1.0
                self.shake_amp = 0.0
            else:
                self.shake_amp = 14.0 * math.exp(-self.shake_t * 5.0)

        if self.ph == self.IDLE:
            self._tick_idle(p, dt)
        elif self.ph == self.SCAN:
            self._tick_scan(p, dt)
        elif self.ph == self.OK:
            self._tick_ok(p, dt)
        elif self.ph == self.FAIL:
            self._tick_fail(p, dt)

        self.update()

    def _tick_idle(self, p, dt):
        self.lock_alpha = min(1.0, self.appear_prog)
        self.cam_alpha  = min(1.0, self.appear_prog)
        self.lock_open_prog = 0.0
        self.widget_fade = 1.0
        if p > 0.6 and self.appear_prog >= 0.95:
            self.ph = self.SCAN
            self.t0 = time.time()

    def _tick_scan(self, p, dt):
        self.lock_alpha = 1.0
        self.cam_alpha = 1.0
        self.cam_fade_out = 0.0
        self.sphere_alpha = 0.0
        self.lock_open_prog = 0.0

        if self._pending_ok and self._pending_ok_user:
            self._trigger_ok(self._pending_ok_user)

        # Demo mode cycles
        if self.demo_mode:
            if self._demo_cycle == 0 and p > 2.0:
                self._on_ok("Demo_User")
            elif self._demo_cycle == 1 and p > 2.0:
                self._on_fail()
            elif self._demo_cycle == 2 and p > 2.0:
                self._on_ok("Demo_User")

    def _tick_ok(self, p, dt):
        """
        SUCCESS ANIMATION TIMELINE:
        0.00 - 0.20s : Camera fades out
        0.08 - 0.50s : Sphere grows in (left rotation 0 → 720°)
        0.10 - 0.85s : Lock animates: locked → unlocked (synchronized)
        0.85 - 1.30s : Hold: full sphere + open lock
        1.30 - 1.70s : Everything fades out smoothly
        1.70 - 1.85s : Widget closes / unlock screen
        """
        self.lock_alpha = 1.0

        # ── Camera fade out (0 → 0.20s) ──
        if p < 0.20:
            self.cam_fade_out = p / 0.20
        else:
            self.cam_fade_out = 1.0
        self.cam_alpha = max(0.0, 1.0 - self.cam_fade_out)

        # ── Sphere appears (0.05 → 0.25s) ──
        if p > 0.05:
            t = min((p - 0.05) / 0.20, 1.0)
            # Smooth quintic ease-out for scale
            self.sphere_scale = 1 - pow(1 - t, 5)
            # Alpha
            self.sphere_alpha = min(1.0, t * 2.2)
        else:
            self.sphere_scale = 0.0
            self.sphere_alpha = 0.0

        # ── iOS authentic 3D rotation (tumbling motion) ──
        # Real iOS sphere rotates on multiple axes simultaneously
        # Like a ball tumbling through space — never repeats same view
        self.sphere_rot_y += 13.0 * dt  # Main yaw (horizontal) — primary
        self.sphere_rot_x += 5.9 * dt   # Pitch (vertical) — secondary
        self.sphere_rot_z += 3.2 * dt   # Roll (twist) — subtle

        # ── Lock unlock animation (0.08 → 0.35s) ──
        # Synchronized with sphere appearance
        if p > 0.08:
            lock_t = min((p - 0.08) / 0.27, 1.0)
            # Spring-like ease for the shackle lifting
            self.lock_open_prog = 1 - pow(1 - lock_t, 3)
        else:
            self.lock_open_prog = 0.0

        # ── Brief hold (0.35 → 0.45s) ──

        # ── Fade out everything (0.45 → 0.70s) ──
        if p > 0.45:
            t2 = min((p - 0.45) / 0.25, 1.0)
            fade = 1.0 - t2 * t2 * (3 - 2 * t2)
            self.widget_fade = max(0.0, fade)
            self.sphere_alpha = fade
            self.lock_alpha = fade

        # ── COMPLETE: emit unlock signal AFTER animation done ──
        if p > 0.70 and not self._unlock_emitted:
            self._unlock_emitted = True
            # Now actually emit unlock — screen unlocks here
            try:
                self.sig.unlock_complete.emit()
            except Exception:
                pass

            if self.demo_mode:
                self._demo_cycle = (self._demo_cycle + 1) % 3
                # Reset after small delay
                QTimer.singleShot(150, self._full_reset)
            else:
                # Close window — unlock happens via signal
                QTimer.singleShot(150, self.close)

    def _tick_fail(self, p, dt):
        self.lock_alpha = 1.0
        self.cam_alpha = 1.0
        self.sphere_alpha = 0.0
        self.lock_open_prog = 0.0

        if p > 1.2:
            if self.demo_mode:
                self._demo_cycle = (self._demo_cycle + 1) % 3
                self._full_reset()
            else:
                self._reset_to_scan()

    def _reset_to_scan(self):
        self.ph = self.SCAN
        self.t0 = time.time()
        self.shake_t = -1.0
        self.shake_amp = 0.0
        self.widget_fade = 1.0

    def _full_reset(self):
        self.ph = self.IDLE
        self.t0 = time.time()
        self.appear_t = 0.0
        self.appear_prog = 0.0
        self._pop_played = False
        self.shake_t = -1.0
        self.shake_amp = 0.0
        self.lock_alpha = 0.0
        self.cam_alpha = 0.0
        self.cam_fade_out = 0.0
        self.lock_open_prog = 0.0
        self.sphere_alpha = 0.0
        self.sphere_scale = 0.0
        self.sphere_rot_x = 0.0
        self.sphere_rot_y = 0.0
        self.sphere_rot_z = 0.0
        self.widget_fade = 1.0
        self._unlock_emitted = False
        self._pending_ok = False
        self._pending_ok_user = None

    # ══════════════════════════════════════════════════
    # PAINT
    # ══════════════════════════════════════════════════
    def paintEvent(self, e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)
        P.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try:
            P.setRenderHint(QPainter.HighQualityAntialiasing, True)
        except AttributeError:
            pass

        if self.widget_fade < 1.0:
            P.setOpacity(max(0.0, self.widget_fade))

        # Shake (X only)
        sx = 0.0
        if self.shake_t >= 0 and self.shake_amp > 0.01:
            sx = self.shake_amp * math.sin(self.shake_t * 12.0 * 2 * math.pi)

        prog = max(0.0, min(1.04, self.appear_prog))
        cur_w = self.PILL_W * (0.4 + 0.6 * prog)
        cur_h = self.PILL_H * (0.5 + 0.5 * prog)
        cur_w = max(60, cur_w)
        cur_h = max(20, cur_h)

        rect_x = (self.W - cur_w) / 2 + sx
        rect_y = self.PILL_Y + (self.PILL_H - cur_h) / 2
        radius = cur_h / 2

        # Shadow
        for i in range(3):
            alpha = max(0, int(40 / (i + 1)))
            P.save()
            P.translate(0, 2 + i * 2)
            P.setBrush(QBrush(QColor(0, 0, 0, alpha)))
            P.setPen(Qt.NoPen)
            P.drawRoundedRect(QRectF(rect_x, rect_y, cur_w, cur_h),
                              radius, radius)
            P.restore()

        # Main pill (pure black)
        P.setBrush(QBrush(QColor(0, 0, 0, 255)))
        P.setPen(Qt.NoPen)
        P.drawRoundedRect(QRectF(rect_x, rect_y, cur_w, cur_h),
                          radius, radius)

        # Subtle gloss
        gloss = QLinearGradient(rect_x, rect_y, rect_x, rect_y + cur_h * 0.5)
        gloss.setColorAt(0, QColor(255, 255, 255, 14))
        gloss.setColorAt(1, QColor(255, 255, 255, 0))
        P.setBrush(QBrush(gloss))
        P.drawRoundedRect(QRectF(rect_x, rect_y, cur_w, cur_h),
                          radius, radius)

        if prog < 0.6:
            P.end()
            return

        content_opacity = min(1.0, (prog - 0.5) / 0.4)
        P.setOpacity(content_opacity * self.widget_fade)

        ic_y = rect_y + cur_h / 2

        # LOCK icon (left) — animates locked → unlocked
        if self.lock_alpha > 0.01:
            lock_x = rect_x + cur_h * 0.85
            self._draw_lock_icon(P, lock_x, ic_y,
                                 self.lock_alpha, self.lock_open_prog)

        # CAMERA position (right)
        cam_x = rect_x + cur_w - cur_h * 0.85
        cam_y = ic_y

        if self.cam_alpha > 0.01:
            pulse_active = 1.0
            if self.ph == self.SCAN:
                pulse_active = 1.0 + 0.08 * math.sin(self.cam_pulse_t * 3.5)
            self._draw_camera_indicator(P, cam_x, cam_y,
                                         self.cam_alpha, pulse_active)

        # 3D SPHERE over camera (only on success)
        if self.sphere_alpha > 0.01:
            sphere_r = (cur_h / 2 + 1) * self.sphere_scale
            if sphere_r > 2:
                self._draw_sphere_ios(P, cam_x, cam_y, sphere_r,
                                       self.sphere_alpha)

        P.end()

    # ══════════════════════════════════════════════════
    # LOCK ICON (animated: locked → unlocked)
    # open_prog: 0 = locked closed, 1 = unlocked (shackle up + rotated)
    # ══════════════════════════════════════════════════
    def _draw_lock_icon(self, P, cx, cy, alpha, open_prog):
        a = int(255 * alpha)
        if a < 4: return

        body_w = 11
        body_h = 9
        shackle_r = 4.5

        # ── Shackle: lifts up + tilts when unlocking ──
        # When open_prog = 0: shackle sits on body
        # When open_prog = 1: shackle lifts 4px up + tilts 25°
        shackle_lift = -4 * open_prog
        shackle_tilt = -25 * open_prog  # degrees

        # Color tint: changes to green when unlocked
        if open_prog > 0:
            # Lerp white → light green
            r_val = int(255 - 60 * open_prog)
            g_val = 255
            b_val = int(255 - 80 * open_prog)
            shackle_col = QColor(r_val, g_val, b_val, a)
            body_col    = QColor(r_val, g_val, b_val, a)
        else:
            shackle_col = QColor(255, 255, 255, a)
            body_col    = QColor(255, 255, 255, a)

        # Draw shackle (arc) — translated and rotated for unlock
        P.save()
        # Pivot point is the right side of the shackle base
        # (so it tilts open from the right hinge)
        pivot_x = cx + shackle_r * 0.6
        pivot_y = cy - 1
        P.translate(pivot_x, pivot_y + shackle_lift)
        P.rotate(shackle_tilt)
        P.translate(-pivot_x, -pivot_y)

        P.setPen(QPen(shackle_col, 1.6,
                      Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        P.setBrush(Qt.NoBrush)
        P.drawArc(QRectF(cx - shackle_r, cy - shackle_r - 2.5,
                         shackle_r * 2, shackle_r * 2),
                  0 * 16, 180 * 16)
        P.restore()

        # Lock body (stays in place)
        P.setBrush(QBrush(body_col))
        P.setPen(Qt.NoPen)
        P.drawRoundedRect(QRectF(cx - body_w/2, cy + 0.5,
                                 body_w, body_h), 2, 2)

        # Keyhole
        P.setBrush(QBrush(QColor(0, 0, 0, a)))
        P.drawEllipse(QPointF(cx, cy + body_h/2 + 0.5), 1.2, 1.2)

        # ── Unlock glow effect ──
        if open_prog > 0.3:
            glow_a = int(60 * (open_prog - 0.3) / 0.7 * alpha)
            if glow_a > 4:
                gg = QRadialGradient(cx, cy, 12)
                gg.setColorAt(0,   QColor(100, 255, 140, glow_a))
                gg.setColorAt(0.5, QColor(48, 209, 88, glow_a // 2))
                gg.setColorAt(1,   QColor(48, 209, 88, 0))
                P.setBrush(QBrush(gg))
                P.setPen(Qt.NoPen)
                P.drawEllipse(QPointF(cx, cy), 12, 12)

    # ══════════════════════════════════════════════════
    # CAMERA INDICATOR
    # ══════════════════════════════════════════════════
    def _draw_camera_indicator(self, P, cx, cy, alpha, pulse=1.0):
        a = int(255 * alpha)
        if a < 4: return

        r_outer = 8 * pulse
        r_inner = 6.5 * pulse

        P.setBrush(QBrush(QColor(40, 40, 45, a)))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), r_outer, r_outer)

        lens_grad = QRadialGradient(cx - 1.5, cy - 1.5, 7 * pulse)
        lens_grad.setColorAt(0,   QColor(50, 70, 100, a))
        lens_grad.setColorAt(0.5, QColor(20, 30, 50, a))
        lens_grad.setColorAt(1,   QColor(5, 10, 20, a))
        P.setBrush(QBrush(lens_grad))
        P.drawEllipse(QPointF(cx, cy), r_inner, r_inner)

        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(80, 100, 130, a // 2), 0.6))
        P.drawEllipse(QPointF(cx, cy), 5 * pulse, 5 * pulse)

        glint_a = int(180 * alpha)
        P.setPen(Qt.NoPen)
        P.setBrush(QBrush(QColor(180, 200, 230, glint_a)))
        P.drawEllipse(QPointF(cx - 2, cy - 2), 1.3, 1.3)

        P.setBrush(QBrush(QColor(0, 0, 0, a)))
        P.drawEllipse(QPointF(cx, cy), 1.5, 1.5)

    # ══════════════════════════════════════════════════
    # 🟢 AUTHENTIC iOS SPHERE — Pic 2/3 exact style
    # Pure wireframe (NO fill, NO specular highlight)
    # Only thin green rings rotating smoothly
    # ══════════════════════════════════════════════════
    def _draw_sphere_ios(self, P, cx, cy, r, alpha):
        base_a = int(255 * alpha)
        if base_a < 4 or r < 2: return

        # iOS sphere green (slightly brighter, more luminous)
        rc = [60, 220, 100]
        rx = self.sphere_rot_x
        ry = self.sphere_rot_y
        rz = self.sphere_rot_z

        # ════════════════════════════════════════════
        # Pure wireframe sphere — 3 perpendicular rings
        # Each ring rotates with same Y-axis spin
        # NO fill, NO specular — just clean wireframe
        # ════════════════════════════════════════════
        FOCAL = 100.0
        CAM_Z = 110.0

        def project(x, y, z):
            dist = CAM_Z - z
            if dist < 1.0: dist = 1.0
            scale = FOCAL / dist
            sx_ = x * scale
            sy_ = y * scale
            depth_t = (z + r) / (2 * r) if r > 0 else 0.5
            return sx_, sy_, scale, depth_t

        def rotate_3d(x, y, z, ax, ay, az):
            """Full 3D rotation: X, then Y, then Z axis (tumbling)"""
            # Rotate around X (pitch)
            cosA, sinA = math.cos(ax), math.sin(ax)
            y, z = y * cosA - z * sinA, y * sinA + z * cosA
            # Rotate around Y (yaw)
            cosA, sinA = math.cos(ay), math.sin(ay)
            x, z = x * cosA + z * sinA, -x * sinA + z * cosA
            # Rotate around Z (roll)
            cosA, sinA = math.cos(az), math.sin(az)
            x, y = x * cosA - y * sinA, x * sinA + y * cosA
            return x, y, z

        N_POINTS = 48  # smooth circles

        # ════════════════════════════════════════════
        # 3 rings — like the iOS sphere in Pic 2/3:
        # 1. Equator (horizontal ring)
        # 2. Meridian 1 (vertical, front-back)
        # 3. Meridian 2 (vertical, left-right)
        # All rotate together with Y-axis spin
        # ════════════════════════════════════════════

        def gen_ring(tilt_axis, n_pts):
            """
            Generate a ring tilted on specific axis.
            tilt_axis: 'XY' = equator, 'YZ' = meridian Y-Z, 'XZ' = meridian X-Z
            """
            pts = []
            for i in range(n_pts + 1):
                theta = (i / n_pts) * 2 * math.pi
                if tilt_axis == 'XY':
                    # Equator: XY plane
                    x = r * math.cos(theta)
                    y = 0
                    z = r * math.sin(theta)
                elif tilt_axis == 'YZ':
                    # Vertical ring 1: YZ plane (front-back)
                    x = 0
                    y = r * math.cos(theta)
                    z = r * math.sin(theta)
                elif tilt_axis == 'XY_TILT':
                    # Tilted meridian
                    x = r * math.cos(theta) * 0.7
                    y = r * math.sin(theta)
                    z = r * math.cos(theta) * 0.7

                # Apply FULL 3D rotation (tumbling — iOS authentic)
                x, y, z = rotate_3d(x, y, z, rx, ry, rz)
                pts.append((x, y, z))
            return pts

        # Generate all rings
        rings = [
            gen_ring('XY', N_POINTS),
            gen_ring('YZ', N_POINTS),
            gen_ring('XY_TILT', N_POINTS),
        ]

        # ════════════════════════════════════════════
        # Collect segments with depth for sorting
        # ════════════════════════════════════════════
        all_segments = []
        for pts in rings:
            for i in range(len(pts) - 1):
                x1, y1, z1 = pts[i]
                x2, y2, z2 = pts[i + 1]
                avg_z = (z1 + z2) * 0.5
                all_segments.append((avg_z, x1, y1, z1, x2, y2, z2))

        # Depth sort: back first
        all_segments.sort(key=lambda seg: seg[0])

        # ════════════════════════════════════════════
        # Subtle outer glow (NOT a fill — just halo)
        # ════════════════════════════════════════════
        glow_r = r + 3
        gg = QRadialGradient(cx, cy, glow_r)
        gg.setColorAt(0,   QColor(rc[0], rc[1], rc[2], int(50 * alpha)))
        gg.setColorAt(0.7, QColor(rc[0], rc[1], rc[2], int(15 * alpha)))
        gg.setColorAt(1,   QColor(rc[0], rc[1], rc[2], 0))
        P.setBrush(QBrush(gg))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # ════════════════════════════════════════════
        # Draw wireframe segments back-to-front
        # ════════════════════════════════════════════
        for (avg_z, x1, y1, z1, x2, y2, z2) in all_segments:
            sx1, sy1, scale1, d1 = project(x1, y1, z1)
            sx2, sy2, scale2, d2 = project(x2, y2, z2)

            avg_scale = (scale1 + scale2) * 0.5
            avg_depth = (d1 + d2) * 0.5

            # ── Depth-based opacity ──
            # Back segments (depth < 0.5): much dimmer
            # Front segments (depth > 0.5): full brightness
            if avg_depth < 0.5:
                # Back hemisphere: 25% to 60% brightness
                depth_bright = 0.25 + (avg_depth / 0.5) * 0.35
            else:
                # Front hemisphere: 60% to 100% brightness
                depth_bright = 0.60 + ((avg_depth - 0.5) / 0.5) * 0.40

            seg_alpha = int(base_a * depth_bright)
            if seg_alpha < 3: continue

            # ── Stroke width: perspective-scaled ──
            # Same width feel as iOS — about 1.5px on front
            stroke_w = 1.3 * (avg_scale / 1.0)
            stroke_w = max(0.6, min(stroke_w, 2.2))

            p1 = QPointF(cx + sx1, cy - sy1)
            p2 = QPointF(cx + sx2, cy - sy2)

            # ── Glow halo on front segments only ──
            if avg_depth > 0.6:
                ga = max(0, int(seg_alpha * 0.25))
                if ga > 2:
                    P.setPen(QPen(QColor(rc[0], rc[1], rc[2], ga),
                                  stroke_w + 2.0,
                                  Qt.SolidLine, Qt.RoundCap))
                    P.drawLine(p1, p2)

            # ── Main wireframe line ──
            P.setPen(QPen(QColor(rc[0], rc[1], rc[2], seg_alpha),
                          stroke_w, Qt.SolidLine, Qt.RoundCap))
            P.drawLine(p1, p2)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()


# ══════════════════════════════════════════════════════════════
# FACE WORKER
# ══════════════════════════════════════════════════════════════
class FaceWorker(QThread):
    def __init__(self, sig):
        super().__init__()
        self.sig = sig
        self.on = True
        self.result = None
        self.setPriority(QThread.LowPriority)

    def stop(self):
        self.on = False

    def run(self):
        import cv2, numpy as np, face_recognition, time

        def _cleanup(cap):
            try:
                if cap: cap.release()
            except: pass

        try:
            from nova_unlock.vision.face_recognizer import (
                get_enrolled_users, load_face, get_threshold
            )
            THRESHOLD = get_threshold()
            pf = {}
            for u in get_enrolled_users():
                e = load_face(u)
                if e is not None: pf[u] = e

            if not pf:
                self.sig.fail.emit()
                return

            cap = None
            for i in range(3):
                c = cv2.VideoCapture(i, cv2.CAP_V4L2)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    c.set(cv2.CAP_PROP_FPS, 30)
                    for _ in range(5): c.grab()
                    r, _ = c.read()
                    if r:
                        cap = c
                        break
                c.release()

            if not cap:
                self.sig.fail.emit()
                return

            waited = 0
            while waited < 1.0 and self.on:
                time.sleep(0.05)
                waited += 0.05
            if not self.on:
                _cleanup(cap); return

            for attempt in range(3):
                if not self.on: break
                embs = []
                frames_tried = 0

                while len(embs) < 4 and frames_tried < 12:
                    if not self.on: break
                    cap.grab()
                    r, frame = cap.retrieve()
                    frames_tried += 1
                    if not r or frame is None:
                        time.sleep(0.03); continue

                    try:
                        small = cv2.resize(frame, (160, 120))
                        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(rgb, model="hog")
                        if locs:
                            sx_ = frame.shape[1] / 160
                            sy_ = frame.shape[0] / 120
                            sl = [(int(t*sy_), int(rt*sx_),
                                   int(b*sy_), int(l*sx_))
                                  for (t, rt, b, l) in locs]
                            rgb_full = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            encs = face_recognition.face_encodings(rgb_full, sl)
                            if encs: embs.append(encs[0])
                    except Exception: pass
                    time.sleep(0.08)

                if not embs:
                    if attempt < 2:
                        self.sig.fail.emit()
                        for _ in range(20):
                            if not self.on: break
                            time.sleep(0.08)
                    continue

                live = np.mean(embs, axis=0)
                best_u = None
                best_d = 999.0
                for user, stored in pf.items():
                    d = float(face_recognition.face_distance([stored], live)[0])
                    if d < best_d:
                        best_d = d
                        best_u = user

                if best_u is not None and best_d <= THRESHOLD:
                    self.result = best_u
                    _cleanup(cap)
                    self.sig.ok.emit(best_u)
                    return

                self.sig.fail.emit()
                for _ in range(20):
                    if not self.on: break
                    time.sleep(0.08)

            _cleanup(cap)
            self.sig.fail.emit()
        except Exception:
            import traceback
            traceback.print_exc()
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
        w = FaceUnlockWidget(sig, demo_mode=False)
        scr = app.primaryScreen().geometry()
        w.move((scr.width() - w.W) // 2, 0)
        w.show(); w.raise_(); w.activateWindow()

        def force_top():
            try:
                wid = int(w.winId())
                subprocess.run(["xdotool", "windowraise", str(wid)],
                               capture_output=True, timeout=2)
            except: pass
            w.raise_(); w.activateWindow()

        top = QTimer()
        top.timeout.connect(force_top)
        top.start(300)
        QTimer.singleShot(100, force_top)
        QTimer.singleShot(500, force_top)
        QTimer.singleShot(1000, force_top)

        wk = FaceWorker(sig)

        # ── CRITICAL: Wait for unlock_complete signal ──
        # Screen unlocks ONLY when sphere animation done
        def store_user(n):
            self.result = n
            # Write PAM cache so screen unlocks
            try:
                import json, time
                CACHE = "/tmp/nova_unlock_pam_cache.json"
                with open(CACHE, "w") as f:
                    json.dump({"user": n, "profile": n, "ts": time.time()}, f)
                os.chmod(CACHE, 0o600)
            except Exception as e:
                print(f"PAM cache write failed: {e}")

        def do_unlock():
            top.stop()
            def press_enter():
                try:
                    subprocess.run(["xdotool", "key", "Return"],
                                   timeout=2, capture_output=True)
                except Exception:
                    pass
            press_enter()
            QTimer.singleShot(300, press_enter)
            QTimer.singleShot(700, press_enter)
            QTimer.singleShot(1000, app.quit)

        sig.ok.connect(store_user)
        sig.unlock_complete.connect(do_unlock)

        wk.start()
        app.exec_()
        wk.stop(); wk.wait(2000)
        return self.result


def demo():
    """Demo: SUCCESS → FAIL → SUCCESS cycle"""
    app = QApplication(sys.argv)
    sig = Sig()
    w = FaceUnlockWidget(sig, demo_mode=True)
    scr = app.primaryScreen().geometry()
    w.move((scr.width() - w.W) // 2, 0)
    w.show()
    print("🎬 Demo Mode: SUCCESS → FAIL → SUCCESS (auto-cycling)")
    print("   • Watch lock unlock alongside sphere animation")
    print("   • Press ESC to exit")
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
