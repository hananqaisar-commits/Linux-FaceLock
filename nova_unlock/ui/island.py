#!/usr/bin/env python3
"""
Island for Linux — Dynamic Island with Liquid Glass.
Morphing pill: media · battery · notifications · timer · face lock.
Pure PyQt5 + stdlib. Zero new dependencies.
"""
from __future__ import annotations
import math, os, sys, time, wave, struct, tempfile, subprocess, random
from pathlib import Path
from enum import Enum, auto
from typing import Optional

from PyQt5.QtWidgets import QApplication, QWidget, QDesktopWidget
from PyQt5.QtCore    import Qt, QTimer, QPointF, QRectF, pyqtSignal, QThread, QObject
from PyQt5.QtGui     import (QPainter, QColor, QPen, QBrush, QFont,
                              QLinearGradient, QRadialGradient,
                              QConicalGradient, QPainterPath, QFontMetrics)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))
from nova_unlock.ui.glass import draw_glass_pill


# ═══════════════════════════════════════════════════════════════
#  AUDIO
# ═══════════════════════════════════════════════════════════════
_SDIR = tempfile.mkdtemp(prefix="island_snd_")

def _wav(name, samples, rate=44100):
    path = os.path.join(_SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h', max(-32767, min(32767, int(s)))))
    return path

def _expand_snd(dur=0.20, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        env = math.sin(math.pi * t / dur)
        s = math.sin(2*math.pi*(300 + 200*(t/dur))*t)*0.10
        out.append(32767 * s * env * 0.45)
    return out

def _collapse_snd(dur=0.14, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        env = 1.0 - (t / dur)
        s = math.sin(2*math.pi*(480 - 180*(t/dur))*t)*0.08
        out.append(32767 * s * env * 0.38)
    return out

def _media_tick(dur=0.09, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        env = math.exp(-t * 50)
        s = (math.sin(2*math.pi*1320*t)*0.22 +
             math.sin(2*math.pi*2200*t)*0.12)
        out.append(32767 * s * env * 0.48)
    return out

def _charge_snd(dur=0.38, rate=44100):
    n = int(rate * dur); out = []
    for i in range(n):
        t = i / rate
        f = 880 if t < 0.16 else 1108
        env = math.exp(-((t if t<0.16 else t-0.16))*16)
        s = math.sin(2*math.pi*f*t)*0.20 + math.sin(2*math.pi*f*2*t)*0.08
        out.append(32767 * s * env * 0.44)
    return out

def _notif_snd(dur=0.45, rate=44100):
    n = int(rate * dur); out = [0.0]*n
    for freq, st, vol in [(880,0.00,0.22),(698,0.12,0.20),(587,0.26,0.22)]:
        si = int(rate*st)
        for j in range(int(rate*0.20)):
            if si+j >= n: break
            t = j/rate
            out[si+j] += 32767*math.sin(2*math.pi*freq*t)*math.exp(-t*11)*vol
    pk = max(abs(x) for x in out) or 1
    return [x*28000/pk for x in out]

def _timer_snd(dur=1.2, rate=44100):
    n = int(rate * dur); out = [0.0]*n
    for freq,st,vol,dc in [(523,0.0,0.28,0.55),(659,0.2,0.26,0.65),(784,0.4,0.28,0.80)]:
        si = int(rate*st)
        for j in range(int(rate*dc)):
            if si+j >= n: break
            t = j/rate
            env = math.exp(-t*3.5)*vol
            s = math.sin(2*math.pi*freq*t)+math.sin(2*math.pi*freq*2*t)*0.3
            out[si+j] += 32767*s*env
    pk = max(abs(x) for x in out) or 1
    return [x*28000/pk for x in out]

SND = {
    "expand":   _wav("expand.wav",   _expand_snd()),
    "collapse": _wav("collapse.wav", _collapse_snd()),
    "media":    _wav("media.wav",    _media_tick()),
    "charge":   _wav("charge.wav",   _charge_snd()),
    "notif":    _wav("notif.wav",    _notif_snd()),
    "timer":    _wav("timer.wav",    _timer_snd()),
}

def play(key):
    path = SND.get(key)
    if not path: return
    try:
        subprocess.Popen(["paplay", path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        try:
            subprocess.Popen(["aplay", "-q", path],
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except Exception: pass


# ═══════════════════════════════════════════════════════════════
#  PHYSICS
# ═══════════════════════════════════════════════════════════════
class Spring:
    __slots__ = ('omega','x','v')
    def __init__(self, freq=9.0):
        self.omega = 2*math.pi*freq; self.x=0.0; self.v=0.0
    def update(self, dt, target):
        f=1+2*dt*self.omega; oo=self.omega**2
        hoo=dt*oo; hhoo=dt*hoo; di=1/(f+hhoo)
        self.x=(f*self.x+dt*self.v+hhoo*target)*di
        self.v=(self.v+hoo*(target-self.x))*di
        return self.x

def easeOutExpo(t):
    return 0.0 if t<=0 else (1.0 if t>=1 else 1-pow(2,-10*t))

def easeOutBack(t, s=1.70158):
    if t<=0: return 0.0
    if t>=1: return 1.0
    t-=1; return t*t*((s+1)*t+s)+1


# ═══════════════════════════════════════════════════════════════
#  DATA
# ═══════════════════════════════════════════════════════════════
class Mode(Enum):
    IDLE    = auto()
    MEDIA   = auto()
    BATTERY = auto()
    NOTIF   = auto()
    TIMER   = auto()
    FACE    = auto()

class MediaInfo:
    def __init__(self):
        self.title=""; self.artist=""; self.playing=False
        self.position=0.0; self.length=0

class BatteryInfo:
    def __init__(self):
        self.pct=100; self.charging=False
        self.time_left=""; self.full=False

class NotifInfo:
    def __init__(self):
        self.app=""; self.summary=""; self.body=""; self.urgency=1


# ═══════════════════════════════════════════════════════════════
#  POLLERS
# ═══════════════════════════════════════════════════════════════
class MediaPoller(QThread):
    updated = pyqtSignal(object)
    def __init__(self):
        super().__init__(); self.running=True; self._last=""
    def stop(self): self.running=False
    def run(self):
        while self.running:
            info = self._poll()
            key = f"{info.title}{info.playing}{info.position:.2f}"
            if key != self._last:
                self._last = key; self.updated.emit(info)
            time.sleep(1.5)
    def _poll(self):
        m = MediaInfo()
        try:
            def r(args):
                return subprocess.run(args, capture_output=True,
                                      text=True, timeout=1.5).stdout.strip()
            m.title   = r(["playerctl","metadata","title"])
            m.artist  = r(["playerctl","metadata","artist"])
            m.playing = r(["playerctl","status"]) == "Playing"
            try:
                pos = float(r(["playerctl","position"]))
                ln  = float(r(["playerctl","metadata","mpris:length"]))
                if ln > 0: m.position=pos/(ln/1e6); m.length=int(ln/1e6)
            except: pass
        except: pass
        return m

class BatteryPoller(QThread):
    updated  = pyqtSignal(object)
    plugged  = pyqtSignal()
    critical = pyqtSignal(int)
    def __init__(self):
        super().__init__(); self.running=True
        self._last_charge=None; self._last_pct=100
    def stop(self): self.running=False
    def run(self):
        while self.running:
            info = self._poll(); self.updated.emit(info)
            if self._last_charge is not None and \
               info.charging != self._last_charge and info.charging:
                self.plugged.emit()
            if info.pct<=15 and info.pct!=self._last_pct and not info.charging:
                self.critical.emit(info.pct)
            self._last_charge=info.charging; self._last_pct=info.pct
            time.sleep(30)
    def _poll(self):
        b = BatteryInfo()
        try:
            out = subprocess.run(
                ["upower","-i","/org/freedesktop/UPower/devices/battery_BAT0"],
                capture_output=True, text=True, timeout=2).stdout
            for line in out.splitlines():
                line=line.strip()
                if line.startswith("percentage:"):
                    b.pct=int(line.split()[-1].rstrip("%"))
                elif line.startswith("state:"):
                    b.charging="charging" in line; b.full="full" in line
                elif line.startswith("time to"):
                    b.time_left=" ".join(line.split(":")[1:]).strip()
        except:
            try:
                p=Path("/sys/class/power_supply/BAT0/capacity")
                s=Path("/sys/class/power_supply/BAT0/status")
                if p.exists(): b.pct=int(p.read_text().strip())
                if s.exists():
                    st=s.read_text().strip().lower()
                    b.charging="charging" in st; b.full="full" in st
            except: pass
        return b


# ═══════════════════════════════════════════════════════════════
#  LIQUID GLASS ISLAND
# ═══════════════════════════════════════════════════════════════
class Island(QWidget):

    PILL_W_IDLE = 126
    PILL_H      = 36
    TOP_MARGIN  = 10
    CORNER_R    = 18.0

    EXPAND = {
        Mode.MEDIA:   (400, 94),
        Mode.BATTERY: (270, 76),
        Mode.NOTIF:   (360, 84),
        Mode.TIMER:   (210, 76),
        Mode.FACE:    (220, 76),
    }

    def __init__(self, screen_w, screen_h, parent=None):
        super().__init__(parent,
                         Qt.WindowStaysOnTopHint |
                         Qt.FramelessWindowHint  |
                         Qt.Tool                 |
                         Qt.X11BypassWindowManagerHint)
        self.screen_w = screen_w
        self.screen_h = screen_h

        self.mode       = Mode.IDLE
        self._mode_t    = 0.0
        self._dismiss_t = 0.0

        self.media   = MediaInfo()
        self.battery = BatteryInfo()
        self.notif   = NotifInfo()
        self.timer_end   = 0.0
        self.timer_label = ""

        # Geometry springs
        self.w_spr = Spring(freq=10.0); self.w_spr.x = self.PILL_W_IDLE
        self.h_spr = Spring(freq=10.0); self.h_spr.x = self.PILL_H

        # Content alpha spring
        self.ca_spr = Spring(freq=7.0)

        # Per-mode springs
        self.prog_spr   = Spring(freq=3.0)   # media progress
        self.batt_spr   = Spring(freq=2.5)   # battery fill
        self.charge_spr = Spring(freq=5.0)   # charge pulse

        # Hover
        self.hovered   = False
        self.hover_spr = Spring(freq=8.0)

        # Glass shimmer phase
        self._shimmer_t = 0.0

        self.t_last = time.time()

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMouseTracking(True)

        self.resize(440, 110)
        self._repos()

        # Pollers
        self.mp = MediaPoller()
        self.mp.updated.connect(self._on_media)
        self.mp.start()

        self.bp = BatteryPoller()
        self.bp.updated.connect(self._on_battery)
        self.bp.plugged.connect(self._on_plug)
        self.bp.critical.connect(self._on_crit)
        self.bp.start()

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(13)   # ~75fps

    def _repos(self):
        self.move((self.screen_w - self.width())//2, self.TOP_MARGIN)

    # ── Public API ──────────────────────────────────
    def show_media(self, info):
        self.media = info; self._enter(Mode.MEDIA, 9.0); play("media")

    def show_battery(self, info):
        self.battery = info; self._enter(Mode.BATTERY, 5.0)

    def show_notif(self, info):
        self.notif = info; self._enter(Mode.NOTIF, 6.0); play("notif")

    def start_timer(self, seconds, label="Timer"):
        self.timer_end=time.time()+seconds; self.timer_label=label
        self._enter(Mode.TIMER, seconds+2.0)

    def show_face(self):
        self._enter(Mode.FACE, 0)

    def dismiss(self):
        self._enter(Mode.IDLE, 0); play("collapse")

    # ── Internal ─────────────────────────────────────
    def _enter(self, mode, dismiss=0.0):
        if mode == self.mode and mode != Mode.IDLE: return
        self.mode    = mode
        self._mode_t = time.time()
        self._dismiss_t = time.time()+dismiss if dismiss>0 else 0.0
        if mode != Mode.IDLE: play("expand")

    def _on_media(self, info):
        if info.title and info.title != self.media.title:
            self.media = info
            if self.mode != Mode.MEDIA: self.show_media(info)
        elif info.title: self.media = info

    def _on_battery(self, info):
        self.battery = info
        self.batt_spr.x = info.pct/100.0

    def _on_plug(self):
        play("charge"); self.show_battery(self.battery)

    def _on_crit(self, pct):
        n=NotifInfo(); n.app="Battery"
        n.summary=f"Low battery — {pct}%"
        n.body="Connect charger"; n.urgency=2
        self.show_notif(n)

    def _tick(self):
        now = time.time()
        dt  = min(now - self.t_last, 0.05)
        self.t_last = now
        self._shimmer_t += dt

        # Auto dismiss
        if self._dismiss_t>0 and now>self._dismiss_t and self.mode!=Mode.IDLE:
            self._enter(Mode.IDLE, 0); play("collapse")

        # Target size
        tw, th = (self.PILL_W_IDLE, self.PILL_H) \
                 if self.mode==Mode.IDLE \
                 else self.EXPAND.get(self.mode, (280,76))

        cw = self.w_spr.update(dt, tw)
        ch = self.h_spr.update(dt, th)
        self.ca_spr.update(dt, 0.0 if self.mode==Mode.IDLE else 1.0)
        self.hover_spr.update(dt, 1.0 if self.hovered else 0.0)

        # Media progress
        if self.media.length>0:
            self.prog_spr.update(dt, self.media.position)

        # Battery
        self.batt_spr.update(dt, self.battery.pct/100.0)

        # Charge pulse
        if self.battery.charging:
            self.charge_spr.update(dt, (math.sin(now*2.5)+1)/2)
        else:
            self.charge_spr.update(dt, 0.0)

        # Timer done
        if self.mode==Mode.TIMER and self.timer_end>0:
            if now >= self.timer_end:
                play("timer"); self._enter(Mode.IDLE, 0)

        # Resize
        cw_ = int(max(cw, self.PILL_W_IDLE) + 44)
        ch_ = int(max(ch, self.PILL_H) + 22)
        if abs(cw_-self.width())>1 or abs(ch_-self.height())>1:
            self.resize(cw_, ch_); self._repos()

        self.update()

    # ── Paint ────────────────────────────────────────
    def paintEvent(self, _e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing)
        P.setRenderHint(QPainter.SmoothPixmapTransform)
        # HighQualityAntialiasing intentionally omitted — deprecated in Qt5 and
        # a major source of frame drops on the raster backend.

        cw = self.w_spr.x
        ch = self.h_spr.x
        cx = self.width()/2
        cy = self.height()/2
        x  = cx - cw/2
        y  = cy - ch/2
        r  = min(ch/2, self.CORNER_R)

        # ── Liquid Glass Pill ──
        self._draw_liquid_glass(P, x, y, cw, ch, r)

        # ── Content ──
        ca = self.ca_spr.x
        if ca > 0.02:
            P.setClipRect(QRectF(x+1, y+1, cw-2, ch-2))
            P.setOpacity(ca)
            if self.mode == Mode.MEDIA:
                self._paint_media(P, x, y, cw, ch)
            elif self.mode == Mode.BATTERY:
                self._paint_battery(P, x, y, cw, ch)
            elif self.mode == Mode.NOTIF:
                self._paint_notif(P, x, y, cw, ch)
            elif self.mode == Mode.TIMER:
                self._paint_timer(P, x, y, cw, ch)
            elif self.mode == Mode.FACE:
                self._paint_face(P, x, y, cw, ch)
            P.setOpacity(1.0)
            P.setClipping(False)

        # ── Idle camera dot ──
        if self.mode == Mode.IDLE:
            self._paint_idle_dot(P, cx, cy, cw)

        P.end()

    def _draw_liquid_glass(self, P, x, y, w, h, r):
        """
        Full liquid glass morphing pill.
        7 layers: outer glow → shadow → base → refraction
                  → caustic → specular sheen → rim → border
        """
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), r, r)

        hover_a = self.hover_spr.x

        # ── Layer 0: Outer ambient glow (hover activated) ──
        if hover_a > 0.01:
            for spread, alpha in [(18, 12), (10, 22), (5, 35)]:
                gp = QPainterPath()
                gp.addRoundedRect(
                    QRectF(x-spread/2, y-spread/2+1, w+spread, h+spread),
                    r+spread/2, r+spread/2)
                P.setBrush(QBrush(QColor(255,255,255,int(alpha*hover_a))))
                P.setPen(Qt.NoPen)
                P.drawPath(gp)

        # ── Layer 1: Drop shadow ──
        for dy, blur, alpha in [(2,6,32),(6,14,20),(14,26,10)]:
            sp = QPainterPath()
            sp.addRoundedRect(
                QRectF(x-blur/2, y+dy-blur/2, w+blur, h+blur),
                r+blur/2, r+blur/2)
            P.setBrush(QBrush(QColor(0,0,0,alpha)))
            P.setPen(Qt.NoPen)
            P.drawPath(sp)

        # ── Layer 2: Base — deep black glass ──
        base = QLinearGradient(x, y, x, y+h)
        base.setColorAt(0.0, QColor(8,  8, 10, 245))
        base.setColorAt(0.5, QColor(4,  4,  6, 252))
        base.setColorAt(1.0, QColor(2,  2,  4, 255))
        P.setBrush(QBrush(base))
        P.setPen(Qt.NoPen)
        P.drawPath(path)

        # ── Layer 3: Refraction — prismatic edge glow ──
        refract = QRadialGradient(x+w*0.25, y+h*0.15, w*0.75)
        refract.setColorAt(0.0, QColor(100,140,255, 0))
        refract.setColorAt(0.7, QColor( 80,120,255, 7))
        refract.setColorAt(1.0, QColor( 60,100,255,16))
        P.setBrush(QBrush(refract))
        P.drawPath(path)

        # ── Layer 4: Caustic light — animated shimmer ──
        shimmer = (math.sin(self._shimmer_t*0.8)+1)/2
        shimmer2= (math.sin(self._shimmer_t*1.3+1.2)+1)/2
        ca_x = x + w*(0.15 + shimmer*0.20)
        ca_g = QRadialGradient(ca_x, y+h*0.3, h*0.9)
        ca_g.setColorAt(0.0, QColor(180,210,255,int(12+shimmer2*8)))
        ca_g.setColorAt(0.5, QColor(140,180,255,int(5+shimmer*5)))
        ca_g.setColorAt(1.0, QColor(100,150,255,0))
        P.setBrush(QBrush(ca_g))
        P.drawPath(path)

        # ── Layer 5: Top specular sheen ──
        sheen_h = h * 0.44
        sheen_path = QPainterPath()
        sheen_path.addRoundedRect(QRectF(x+1, y+1, w-2, sheen_h), r-1, r-1)
        sheen_path = sheen_path.intersected(path)
        sheen = QLinearGradient(x, y, x, y+sheen_h)
        sheen.setColorAt(0.0, QColor(255,255,255,62))
        sheen.setColorAt(0.4, QColor(255,255,255,20))
        sheen.setColorAt(1.0, QColor(255,255,255, 0))
        P.setBrush(QBrush(sheen))
        P.drawPath(sheen_path)

        # ── Layer 6: Inner rim highlight ──
        rim = QLinearGradient(x, y, x, y+h)
        rim.setColorAt(0.0,  QColor(255,255,255,55))
        rim.setColorAt(0.06, QColor(255,255,255,18))
        rim.setColorAt(0.94, QColor(255,255,255, 0))
        rim.setColorAt(1.0,  QColor(255,255,255,12))
        inner = QPainterPath()
        inner.addRoundedRect(QRectF(x+0.5,y+0.5,w-1,h-1), r-0.5, r-0.5)
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QBrush(rim), 0.8))
        P.drawPath(inner)

        # ── Layer 7: Outer border — crisp 0.5px ──
        P.setPen(QPen(QColor(255,255,255,38), 0.5))
        P.setBrush(Qt.NoBrush)
        P.drawPath(path)

    # ── Idle ─────────────────────────────────────────
    def _paint_idle_dot(self, P, cx, cy, cw):
        now = time.time()
        pulse = (math.sin(now*1.9)+1)/2
        dot_x = cx + self.PILL_W_IDLE/2 - 20
        blue  = QColor(10,132,255)

        # Glow ring
        P.setBrush(QBrush(QColor(10,132,255,int(20+28*pulse))))
        P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(dot_x, cy), 7, 7)
        # Core
        P.setBrush(QBrush(blue))
        P.drawEllipse(QPointF(dot_x, cy), 3.5, 3.5)
        # Specular
        P.setBrush(QBrush(QColor(255,255,255,90)))
        P.drawEllipse(QPointF(dot_x-0.8, cy-0.8), 1.2, 1.2)

    # ── Media ────────────────────────────────────────
    def _paint_media(self, P, x, y, cw, ch):
        pad = 14
        cr  = (ch - pad*2)/2
        ccx = x + pad + cr
        ccy = y + ch/2

        # Album circle — glass tinted
        grad = QRadialGradient(ccx-cr*0.3, ccy-cr*0.3, cr*1.5)
        grad.setColorAt(0.0, QColor(50, 70,110))
        grad.setColorAt(0.6, QColor(25, 35, 65))
        grad.setColorAt(1.0, QColor( 8, 12, 24))
        P.setBrush(QBrush(grad)); P.setPen(Qt.NoPen)
        P.drawEllipse(QPointF(ccx, ccy), cr, cr)

        # Sheen on circle
        c_sheen = QLinearGradient(ccx-cr, ccy-cr, ccx, ccy)
        c_sheen.setColorAt(0.0, QColor(255,255,255,30))
        c_sheen.setColorAt(1.0, QColor(255,255,255, 0))
        clip = QPainterPath()
        clip.addEllipse(QPointF(ccx,ccy), cr, cr)
        P.setClipPath(clip)
        P.setBrush(QBrush(c_sheen))
        P.drawEllipse(QPointF(ccx, ccy), cr, cr)
        P.setClipping(False)

        # Play/pause icon
        icon = QColor(255,255,255,210)
        P.setBrush(QBrush(icon)); P.setPen(Qt.NoPen)
        if self.media.playing:
            bw,bh = 2.8, cr*0.52
            P.drawRoundedRect(QRectF(ccx-bw-1.5, ccy-bh/2, bw, bh), 1, 1)
            P.drawRoundedRect(QRectF(ccx+1.5,    ccy-bh/2, bw, bh), 1, 1)
        else:
            tp = QPainterPath(); ts = cr*0.36
            tp.moveTo(ccx-ts*0.6, ccy-ts)
            tp.lineTo(ccx-ts*0.6, ccy+ts)
            tp.lineTo(ccx+ts*0.9, ccy)
            tp.closeSubpath(); P.drawPath(tp)

        # Text
        tx = ccx + cr + 14
        tw = cw - (tx-x) - 14

        P.setFont(self._font(13, QFont.DemiBold))
        P.setPen(QPen(QColor(255,255,255,245)))
        P.drawText(int(tx), int(ccy-7), self._elide(self.media.title, P.fontMetrics(), int(tw)))

        P.setFont(self._font(11, QFont.Normal, text=True))
        P.setPen(QPen(QColor(160,170,185,200)))
        P.drawText(int(tx), int(ccy+10), self._elide(self.media.artist, P.fontMetrics(), int(tw)))

        # Progress bar
        by  = y + ch - 11
        bw_ = tw
        bh_ = 2.5
        P.setBrush(QBrush(QColor(255,255,255,25))); P.setPen(Qt.NoPen)
        P.drawRoundedRect(QRectF(tx, by, bw_, bh_), 1.2, 1.2)
        prog = self.prog_spr.x
        if prog > 0.005:
            P.setBrush(QBrush(QColor(255,255,255,200)))
            P.drawRoundedRect(QRectF(tx, by, bw_*prog, bh_), 1.2, 1.2)
            P.setBrush(QBrush(QColor(255,255,255)))
            P.drawEllipse(QPointF(tx+bw_*prog, by+bh_/2), 4, 4)

    # ── Battery ──────────────────────────────────────
    def _paint_battery(self, P, x, y, cw, ch):
        cx_ = x + cw/2
        cy_ = y + ch/2
        pct = self.battery.pct

        # Color
        if self.battery.charging:
            col = QColor(10,132,255)
        elif pct > 20:
            col = QColor(48,209,88)
        else:
            col = QColor(255,69,58)

        # Battery icon
        bx = x + 18; by_ = cy_ - 11
        bw = 38;     bh  = 22; br = 4

        # Outer shell — glass
        shell = QPainterPath()
        shell.addRoundedRect(QRectF(bx, by_, bw, bh), br, br)
        P.setBrush(QBrush(QColor(255,255,255,18)))
        P.setPen(Qt.NoPen); P.drawPath(shell)
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(255,255,255,160), 1.5))
        P.drawPath(shell)
        # Nub
        P.drawRoundedRect(QRectF(bx+bw, by_+bh*0.28, 3.5, bh*0.44), 1,1)

        # Fill — animated for charging
        fill_w = (bw-4)*(pct/100.0)
        if self.battery.charging:
            pulse = self.charge_spr.x
            fill_w_anim = fill_w + (bw-4-fill_w)*pulse*0.15
        else:
            fill_w_anim = fill_w

        if fill_w_anim > 2:
            fill_grad = QLinearGradient(bx+2, by_+2, bx+2+fill_w_anim, by_+2)
            fill_grad.setColorAt(0.0, QColor(
                min(255,col.red()+20),
                min(255,col.green()+15),
                min(255,col.blue()+10)))
            fill_grad.setColorAt(1.0, col)
            P.setBrush(QBrush(fill_grad)); P.setPen(Qt.NoPen)
            P.drawRoundedRect(
                QRectF(bx+2, by_+2, fill_w_anim, bh-4), br-1, br-1)

            # Sheen on fill
            fill_sheen = QLinearGradient(bx+2, by_+2, bx+2, by_+2+bh*0.4)
            fill_sheen.setColorAt(0.0, QColor(255,255,255,40))
            fill_sheen.setColorAt(1.0, QColor(255,255,255, 0))
            P.setBrush(QBrush(fill_sheen))
            P.drawRoundedRect(
                QRectF(bx+2, by_+2, fill_w_anim, (bh-4)*0.5), br-1, br-1)

        # Bolt icon for charging
        if self.battery.charging:
            bolt = QPainterPath()
            bcx = bx+bw/2
            bolt.moveTo(bcx+2,  by_+3)
            bolt.lineTo(bcx-4,  by_+bh/2)
            bolt.lineTo(bcx,    by_+bh/2)
            bolt.lineTo(bcx-2,  by_+bh-3)
            bolt.lineTo(bcx+4,  by_+bh/2)
            bolt.lineTo(bcx,    by_+bh/2)
            bolt.closeSubpath()
            P.setBrush(QBrush(QColor(255,255,255,230)))
            P.setPen(Qt.NoPen); P.drawPath(bolt)

        # Percentage text
        P.setFont(self._font(24, QFont.Bold))
        P.setPen(QPen(QColor(255,255,255)))
        pct_str = f"{pct}%"
        fm = P.fontMetrics()
        px_ = bx + bw + 18
        P.drawText(int(px_), int(cy_+9), pct_str)

        # Status
        P.setFont(self._font(10, QFont.Normal, text=True))
        P.setPen(QPen(QColor(160,170,185,200)))
        status = ("Charging" if self.battery.charging
                  else "Full" if self.battery.full
                  else self.battery.time_left or "On battery")
        sx = px_ + fm.horizontalAdvance(pct_str) + 10
        P.drawText(int(sx), int(cy_+1), status)

    # ── Notification ─────────────────────────────────
    def _paint_notif(self, P, x, y, cw, ch):
        pad = 16; cy_ = y+ch/2

        # Urgency accent
        uc = [QColor(10,132,255), QColor(255,159,10),
              QColor(255,69,58)][min(self.notif.urgency, 2)]

        # Animated left strip
        strip_h = ch - 20
        strip_path = QPainterPath()
        strip_path.addRoundedRect(QRectF(x+5, y+10, 3, strip_h), 1.5,1.5)
        P.setBrush(QBrush(uc)); P.setPen(Qt.NoPen)
        P.drawPath(strip_path)

        # Glow from strip
        sg = QLinearGradient(x+5, cy_, x+5+cw*0.3, cy_)
        sg.setColorAt(0.0, QColor(uc.red(), uc.green(), uc.blue(), 18))
        sg.setColorAt(1.0, QColor(uc.red(), uc.green(), uc.blue(),  0))
        P.setBrush(QBrush(sg)); P.drawRect(QRectF(x, y, cw*0.4, ch))

        # App name
        P.setFont(self._font(10, QFont.DemiBold, tracking=0.06, text=True))
        P.setPen(QPen(QColor(140,150,165,220)))
        P.drawText(int(x+pad+8), int(cy_-13), self.notif.app.upper())

        # Summary
        P.setFont(self._font(13, QFont.DemiBold))
        P.setPen(QPen(QColor(255,255,255,245)))
        P.drawText(int(x+pad+8), int(cy_+3),
                   self._elide(self.notif.summary, P.fontMetrics(), int(cw-pad*2-8)))

        # Body
        P.setFont(self._font(11, QFont.Normal, text=True))
        P.setPen(QPen(QColor(160,170,185,200)))
        P.drawText(int(x+pad+8), int(cy_+17),
                   self._elide(self.notif.body, P.fontMetrics(), int(cw-pad*2-8)))

    # ── Timer ────────────────────────────────────────
    def _paint_timer(self, P, x, y, cw, ch):
        cx_ = x+cw/2; cy_ = y+ch/2
        remaining = max(0, self.timer_end - time.time())
        mins = int(remaining//60); secs = int(remaining%60)
        ts   = f"{mins:02d}:{secs:02d}"

        # Circular arc progress
        total = max(1, self.timer_end - self._mode_t)
        prog  = 1.0 - (remaining/total)
        arc_r = min(cw,ch)*0.34
        rect  = QRectF(cx_-arc_r, cy_-arc_r, arc_r*2, arc_r*2)

        # Track
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(255,255,255,22), 2.0, Qt.SolidLine, Qt.FlatCap))
        P.drawEllipse(QPointF(cx_,cy_), arc_r, arc_r)

        # Progress arc — blue with glow
        if prog > 0.005:
            P.setPen(QPen(QColor(10,132,255), 2.8, Qt.SolidLine, Qt.RoundCap))
            P.drawArc(rect, int(90*16), int(-prog*360*16))
            # Glow
            P.setPen(QPen(QColor(10,132,255,60), 5.5, Qt.SolidLine, Qt.RoundCap))
            P.drawArc(rect, int(90*16), int(-prog*360*16))

        # Label
        P.setFont(self._font(10, QFont.Normal, tracking=0.04, text=True))
        P.setPen(QPen(QColor(130,140,155,200)))
        lw = P.fontMetrics().horizontalAdvance(self.timer_label)
        P.drawText(int(cx_-lw/2), int(y+14), self.timer_label)

        # Countdown
        P.setFont(self._font(26, QFont.Bold))
        P.setPen(QPen(QColor(255,255,255)))
        fm = P.fontMetrics(); tw = fm.horizontalAdvance(ts)
        P.drawText(int(cx_-tw/2), int(cy_+5), ts)

    # ── Face ─────────────────────────────────────────
    def _paint_face(self, P, x, y, cw, ch):
        cx_ = x+cw/2; cy_ = y+ch/2
        now = time.time()
        rot = (now*28)%360
        r_  = min(cw,ch)*0.27

        # Rotating arc — conical gradient
        conic = QConicalGradient(cx_, cy_, -rot)
        conic.setColorAt(0.0, QColor(10,132,255,230))
        conic.setColorAt(0.4, QColor(10,132,255, 50))
        conic.setColorAt(0.8, QColor(10,132,255,180))
        conic.setColorAt(1.0, QColor(10,132,255,230))

        # Glow arc
        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QBrush(conic), 5.5, Qt.SolidLine, Qt.RoundCap))
        P.setOpacity(0.35)
        P.drawEllipse(QPointF(cx_,cy_), r_, r_)
        P.setOpacity(self.ca_spr.x)

        # Sharp arc
        P.setPen(QPen(QBrush(conic), 2.2, Qt.SolidLine, Qt.RoundCap))
        P.drawEllipse(QPointF(cx_,cy_), r_, r_)

        # Label
        P.setFont(self._font(11, QFont.Normal, text=True))
        P.setPen(QPen(QColor(200,205,215,220)))
        label = "Scanning"
        lx = cx_ + r_ + 12
        lw = P.fontMetrics().horizontalAdvance(label)
        P.drawText(int(lx), int(cy_+4), label)

    # ── Helpers ──────────────────────────────────────
    @staticmethod
    def _font(size, weight=QFont.Normal, tracking=0.0, text=False):
        fam = ("SF Pro Text, Inter, Helvetica Neue, Arial" if (text or size<14)
               else "SF Pro Display, Inter, Helvetica Neue, Arial")
        f = QFont(fam); f.setPixelSize(size); f.setWeight(weight)
        if tracking: f.setLetterSpacing(QFont.AbsoluteSpacing, tracking*size)
        f.setHintingPreference(QFont.PreferFullHinting)
        f.setStyleStrategy(QFont.PreferAntialias|QFont.PreferQuality)
        return f

    @staticmethod
    def _elide(text, fm, max_w):
        if not text: return ""
        return fm.elidedText(text, Qt.ElideRight, max_w)

    def enterEvent(self, e): self.hovered = True
    def leaveEvent(self, e): self.hovered = False

    def mousePressEvent(self, e):
        if e.button()==Qt.LeftButton and self.mode!=Mode.IDLE:
            self.dismiss()

    def closeEvent(self, e):
        self.mp.stop(); self.bp.stop()
        self.mp.wait(1000); self.bp.wait(1000)
        e.accept()


# ═══════════════════════════════════════════════════════════════
#  DEMO
# ═══════════════════════════════════════════════════════════════
def _mk_notif(app, summary, body, urgency=1):
    n=NotifInfo(); n.app=app; n.summary=summary; n.body=body; n.urgency=urgency; return n

def _mk_media(title, artist, playing, pos):
    m=MediaInfo(); m.title=title; m.artist=artist; m.playing=playing; m.position=pos; return m

def _mk_battery(pct, charging, time_left=""):
    b=BatteryInfo(); b.pct=pct; b.charging=charging; b.time_left=time_left; return b

def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    except: pass

    app = QApplication(sys.argv)
    scr = app.primaryScreen().geometry()
    isl = Island(scr.width(), scr.height())
    isl.show()

    # Demo cycle
    QTimer.singleShot(1000,  lambda: isl.show_notif(
        _mk_notif("Messages", "Hanan", "See you at 6?", 1)))
    QTimer.singleShot(7500,  lambda: isl.show_media(
        _mk_media("Midnight Rain", "Taylor Swift", True, 0.38)))
    QTimer.singleShot(16000, lambda: isl.show_battery(
        _mk_battery(42, True, "1h 20m")))
    QTimer.singleShot(22000, lambda: isl.start_timer(20, "Focus Timer"))
    QTimer.singleShot(44000, lambda: isl.show_face())
    QTimer.singleShot(52000, app.quit)

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
