#!/usr/bin/env python3
"""
NovaUnlock Face Unlock UI — PyQt5
Transparent overlay ON TOP of original lockscreen
"""
import sys, math, time, struct, wave, tempfile, os, subprocess
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import (Qt, QTimer, QPointF,
                           pyqtSignal, QObject, QThread)
from PyQt5.QtGui import (QPainter, QColor, QPen,
                          QFont, QRadialGradient, QBrush)

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

SDIR = tempfile.mkdtemp(prefix="nova_snd_")

def _wav(name, samples, rate=44100):
    path = os.path.join(SDIR, name)
    with wave.open(path, 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for s in samples:
            w.writeframes(struct.pack('<h',
                max(-32767, min(32767, int(s)))))
    return path

def _sin(freq, dur, vol=0.5, rate=44100):
    n = int(rate * dur)
    out = []
    for i in range(n):
        t = i / rate
        env = min(1, min(t * 30, (dur - t) * 20))
        out.append(32767 * vol * env *
                   math.sin(2 * math.pi * freq * t))
    return out

def _silence(dur, rate=44100):
    return [0] * int(rate * dur)

def mk_scan():
    s = []
    rate = 44100
    dur = 0.15
    for i in range(int(rate * dur)):
        t = i / rate
        freq = 600 + 800 * (t / dur)
        env = min(1, t * 40) * max(0, 1 - t / dur) * 0.04
        s.append(32767 * env * math.sin(2 * math.pi * freq * t))
    return _wav("scan.wav", s)

def mk_ok():
    s = _sin(880, 0.12, 0.05)
    s += _silence(0.03)
    s += _sin(1109, 0.12, 0.045)
    s += _silence(0.03)
    s += _sin(1319, 0.16, 0.04)
    s2 = _sin(1760, 0.12, 0.015)
    s2 += _silence(0.03)
    s2 += _sin(2218, 0.12, 0.012)
    s2 += _silence(0.03)
    s2 += _sin(2638, 0.16, 0.01)
    for i in range(min(len(s), len(s2))):
        s[i] = s[i] + s2[i]
    return _wav("ok.wav", s)

def mk_fail():
    rate = 44100
    s = []
    for i in range(int(rate * 0.18)):
        t = i / rate
        freq = 280 - 150 * (t / 0.18)
        env = max(0, 1 - t / 0.18) * 0.06
        s.append(32767 * env * (2 * (t * freq % 1) - 1))
    s += _silence(0.04)
    for i in range(int(rate * 0.1)):
        t = i / rate
        env = max(0, 1 - t / 0.1) * 0.05
        s.append(32767 * env *
                 math.sin(2 * math.pi * 65 * t))
    return _wav("fail.wav", s)

SND_SCAN = mk_scan()
SND_OK   = mk_ok()
SND_FAIL = mk_fail()

def play(path):
    try:
        subprocess.Popen(["aplay", "-q", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
    except:
        pass


class Sig(QObject):
    ok   = pyqtSignal(str)
    fail = pyqtSignal()


class FaceUnlockWidget(QWidget):
    IDLE = 0
    SCAN = 1
    OK   = 2
    FAIL = 3

    def __init__(self, sig, demo_mode=False):
        super().__init__()
        self.sig = sig
        self.sig.ok.connect(self._on_ok)
        self.sig.fail.connect(self._on_fail)
        self.demo_mode = demo_mode

        self.W  = 220
        self.H  = 290
        self.CX = self.W // 2
        self.CY = 108
        self.R  = 36
        self.N  = 32
        self.DS = 2.0

        self.ph      = self.IDLE
        self.t0      = time.time()
        self.nm      = ""
        self.demo_cy = 0

        self._init_anim()

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowFlags(
            Qt.FramelessWindowHint        |
            Qt.WindowStaysOnTopHint       |
            Qt.X11BypassWindowManagerHint |
            Qt.Tool
        )
        self.setFixedSize(self.W, self.H)

        self._tmr = QTimer()
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(16)

        self._etmr = QTimer()
        self._etmr.timeout.connect(self._et)
        self._etmr.start(380)

    def _init_anim(self):
        self.fa     = 0.0
        self.fs     = 0.55
        self.rot    = 0.0
        self.rspd   = 0.0
        self.dot_a  = [0.7] * self.N
        self.dot_sz = [self.DS] * self.N
        self.fc     = [255, 255, 255]
        self.eye_a  = 0.0
        self.ring_a = 0.0
        self.ring_c = [255, 255, 255]
        self.ga     = 0.0
        self.gc     = [100, 100, 100]
        self.tk_a   = 0.0
        self.tk_p   = 0.0
        self.xa     = 0.0
        self.rip_r  = 0.0
        self.rip_a  = 0.0
        self.shake  = 0
        self.fade   = 1.0
        self.txt    = ""
        self.txt_a  = 0.0
        self.txt_c  = [255, 255, 255]
        self.ell    = 0

    def _on_ok(self, n):
        if self.ph == self.OK:
            return
        self.ph = self.OK
        self.t0 = time.time()
        self.nm = n
        play(SND_OK)

    def _on_fail(self):
        if self.ph == self.OK:
            return
        self.ph = self.FAIL
        self.t0 = time.time()
        play(SND_FAIL)
        
        # Count fails and close after 3
        if not hasattr(self, '_fail_count'):
            self._fail_count = 0
        self._fail_count += 1
        if self._fail_count >= 3:
            QTimer.singleShot(1500, self.close)

    def _et(self):
        if self.ph == self.SCAN:
            self.ell = (self.ell % 3) + 1

    def _reset_to_scan(self):
        self.ph    = self.SCAN
        self.t0    = time.time()
        self.fa    = 1.0
        self.fs    = 1.0
        self.rot   = 0.0
        self.rspd  = 0.0
        self.fc    = [255, 255, 255]
        self.eye_a = 0.6
        self.tk_a  = 0.0
        self.tk_p  = 0.0
        self.xa    = 0.0
        self.rip_r = 0.0
        self.rip_a = 0.0
        self.shake = 0
        self.fade  = 1.0
        self.txt_c = [255, 255, 255]
        self.ring_c = [255, 255, 255]
        play(SND_SCAN)

    def _full_reset(self):
        self.ph = self.IDLE
        self.t0 = time.time()
        self.demo_cy += 1
        self._init_anim()

    def _lr(self, a, b, t):
        t = max(0, min(1, t))
        return [int(a[i] + (b[i] - a[i]) * t) for i in range(3)]

    def _eo(self, t):
        return 1 - pow(1 - t, 3)

    def _spr(self, t):
        return 1 + pow(2, -10*t) * math.sin(
            (t - 0.075) * 20.94) * -1

    def _tick(self):
        now = time.time()
        p   = now - self.t0

        if self.ph == self.IDLE:
            if p < 0.5:
                t = min(p / 0.5, 1)
                s = self._spr(t)
                self.fs = 0.55 + 0.45 * min(s, 1.04)
                self.fa = min(t * 3, 1)
            else:
                self.fs = 1.0
                self.fa = 1.0

            for i in range(self.N):
                delay = i * 0.015
                dt = max(0, p - delay)
                self.dot_a[i]  = 0.65 * min(dt / 0.2, 1)
                self.dot_sz[i] = self.DS

            self.eye_a  = min(max(0, (p - 0.25) * 4), 0.6)
            self.fc     = [255, 255, 255]
            self.rot    = 0
            self.rspd   = 0
            self.ga     = 0.015
            self.gc     = [100, 100, 100]
            self.ring_a = min(max(0, (p - 0.3) * 2), 0.06)
            self.ring_c = [255, 255, 255]
            self.txt    = "Face Unlock"
            self.txt_a  = min(max(0, (p - 0.2) * 2.5), 0.35)
            self.txt_c  = [255, 255, 255]

            if p > 0.75:
                self.ph = self.SCAN
                self.t0 = now
                play(SND_SCAN)

        elif self.ph == self.SCAN:
            self.fa    = 1.0
            self.fs    = 1.0
            self.eye_a = 0.6

            if p < 0.4:
                self.rspd = (p / 0.4) * 3.2
            else:
                self.rspd = 3.2
            self.rot += self.rspd

            head = self.rot % 360
            for i in range(self.N):
                base  = (i / self.N) * 360
                diff  = (head - base) % 360
                trail = diff / 360
                self.dot_a[i]  = 0.25 + 0.75 * math.exp(-trail * 3.5)
                self.dot_sz[i] = self.DS * (0.7 + 0.6 * math.exp(-trail * 4))

            tc      = min(p / 0.6, 1)
            self.fc = self._lr([255, 255, 255], [0, 200, 255], tc)
            self.ring_a = min(p / 0.4, 0.3)
            self.ring_c = [0, 200, 255]
            self.ga     = 0.04 + 0.03 * math.sin(now * 3)
            self.gc     = [0, 200, 255]
            self.txt    = "Verifying" + "." * self.ell
            self.txt_a  = 0.55
            self.txt_c  = [180, 180, 180]

            if self.demo_mode and p > 3.0:
                import random
                if random.random() < 0.3:
                    self._on_fail()
                else:
                    self._on_ok("Demo_User")

        elif self.ph == self.OK:
            if p < 0.6:
                decel     = self._eo(p / 0.6)
                self.rspd = max(0, 3.2 * (1 - decel))
                self.rot += self.rspd
            else:
                self.rspd = 0

            for i in range(self.N):
                self.dot_a[i]  += (0.8 - self.dot_a[i])  * 0.12
                self.dot_sz[i] += (self.DS - self.dot_sz[i]) * 0.12

            tc          = min(p / 0.3, 1)
            self.fc     = self._lr([0, 200, 255], [0, 230, 118], tc)
            self.ring_c = self._lr([0, 200, 255], [0, 230, 118], tc)

            self.gc = [0, 230, 118]
            if p < 0.5:
                self.ga = 0.04 + 0.16 * math.sin(p / 0.5 * math.pi)
            else:
                self.ga = max(0.01, 0.04 * (1-(p-0.5)/0.4))

            if p > 0.45:
                ft       = min((p - 0.45) / 0.18, 1)
                self.fa  = max(0, 1 - ft)
                self.eye_a = max(0, 0.6 * (1 - ft))

            if p > 0.55:
                self.tk_a = min((p - 0.55) / 0.1, 1)
                raw       = min((p - 0.55) / 0.3, 1)
                self.tk_p = self._eo(raw)

            if 0.55 < p < 0.85:
                pt       = (p - 0.55) / 0.3
                self.fs  = 1.0 + 0.055 * math.sin(pt * math.pi)
            else:
                self.fs  = 1.0

            if 0.45 < p < 1.1:
                rt          = (p - 0.45) / 0.65
                self.rip_r  = (self.R + 14) * (1 + 1.5 * rt)
                self.rip_a  = max(0, 0.25 * (1 - rt))
            else:
                self.rip_a  = 0

            self.txt   = "Unlocked"
            self.txt_a = min(p / 0.2, 0.9)
            self.txt_c = [0, 230, 118]

            if p > 2.3:
                self.fade = max(0, 1 - (p - 2.3) / 0.35)
                if p > 2.7:
                    if self.demo_mode:
                        self._full_reset()

        elif self.ph == self.FAIL:
            self.rspd = 0

            for i in range(self.N):
                self.dot_a[i]  = 0.75
                self.dot_sz[i] = self.DS

            tc          = min(p / 0.1, 1)
            self.fc     = self._lr([0, 200, 255], [255, 74, 74], tc)
            self.ring_c = self._lr([0, 200, 255], [255, 74, 74], tc)

            self.gc = [255, 74, 74]
            self.ga = max(0, 0.1 * (1 - p / 0.4))

            if p < 0.42:
                decay      = 1 - p / 0.42
                self.shake = int(math.sin(p * 48) * 10 * decay)
            else:
                self.shake = 0

            if p > 0.2:
                self.fa    = max(0, 1 - (p - 0.2) / 0.12)
                self.eye_a = 0
            if p > 0.25:
                self.xa = min((p - 0.25) / 0.1, 1)

            self.txt   = "Try Again"
            self.txt_a = min(p / 0.1, 0.75)
            self.txt_c = [255, 74, 74]

            if p > 1.5:
                self.xa = max(0, self.xa - 0.03)
            if p > 1.8:
                self._reset_to_scan()

        self.update()

    def paintEvent(self, e):
        P = QPainter(self)
        P.setRenderHint(QPainter.Antialiasing, True)

        if self.fade < 1:
            P.setOpacity(self.fade)

        cx = self.CX + self.shake
        cy = self.CY

        bg_color = QColor(0, 0, 0, 200)
        P.setBrush(QBrush(bg_color))
        P.setPen(Qt.NoPen)
        P.drawRoundedRect(0, 0, self.W, self.H, 20, 20)

        P.setBrush(Qt.NoBrush)
        P.setPen(QPen(QColor(255, 255, 255, 40), 1))
        P.drawRoundedRect(0, 0, self.W, self.H, 20, 20)

        if self.ga > 0.003:
            gc = self.gc
            gr = QRadialGradient(cx, cy, self.R * 3)
            gr.setColorAt(0, QColor(gc[0], gc[1], gc[2],
                                     int(255 * self.ga)))
            gr.setColorAt(0.5, QColor(gc[0], gc[1], gc[2],
                                       int(255 * self.ga * 0.3)))
            gr.setColorAt(1, QColor(gc[0], gc[1], gc[2], 0))
            P.setBrush(QBrush(gr))
            P.setPen(Qt.NoPen)
            P.drawEllipse(QPointF(cx, cy), self.R*3, self.R*3)

        if self.ring_a > 0.005:
            rc = self.ring_c
            P.setPen(QPen(QColor(rc[0], rc[1], rc[2],
                                  int(255 * self.ring_a)), 1.2))
            P.setBrush(Qt.NoBrush)
            P.drawEllipse(QPointF(cx, cy), self.R+14, self.R+14)

        if self.rip_a > 0.005:
            P.setPen(QPen(QColor(0, 230, 118,
                                  int(255 * self.rip_a)), 1))
            P.setBrush(Qt.NoBrush)
            P.drawEllipse(QPointF(cx, cy), self.rip_r, self.rip_r)

        if self.fa > 0.01:
            P.save()
            P.translate(cx, cy)
            P.scale(self.fs, self.fs)
            self._draw_dots(P)
            P.restore()

        if self.tk_a > 0.01:
            P.save()
            P.translate(cx, cy)
            P.scale(self.fs, self.fs)
            self._draw_tick(P)
            P.restore()

        if self.xa > 0.01:
            self._draw_x(P, cx, cy)

        if self.txt_a > 0.01:
            self._draw_text(P, self.CX + self.shake)

        P.end()

    def _draw_dots(self, P):
        fc = self.fc
        P.setPen(Qt.NoPen)
        for i in range(self.N):
            angle = (i / self.N) * 360 + self.rot
            rad   = math.radians(angle)
            x     = self.R * math.cos(rad)
            y     = self.R * math.sin(rad)
            a     = int(255 * self.fa * self.dot_a[i])
            sz    = self.dot_sz[i]
            if self.dot_a[i] > 0.6 and self.ph == self.SCAN:
                P.setBrush(QBrush(QColor(fc[0], fc[1], fc[2],
                                          int(a * 0.3))))
                P.drawEllipse(QPointF(x, y), sz*2, sz*2)
            P.setBrush(QBrush(QColor(fc[0], fc[1], fc[2], a)))
            P.drawEllipse(QPointF(x, y), sz, sz)

        if self.eye_a > 0.01:
            ea = int(255 * self.eye_a * self.fa)
            P.setBrush(QBrush(QColor(fc[0], fc[1], fc[2], ea)))
            P.drawEllipse(QPointF(-10, -5), 2.8, 2.8)
            P.drawEllipse(QPointF( 10, -5), 2.8, 2.8)

    def _draw_tick(self, P):
        a = int(255 * self.tk_a)
        P.setPen(QPen(QColor(0, 230, 118, a), 2.2))
        P.setBrush(Qt.NoBrush)
        P.drawEllipse(QPointF(0, 0), 28, 28)
        if self.tk_p < 0.01:
            return
        P.setPen(QPen(QColor(0, 230, 118, a), 3,
                       Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p1 = QPointF(-13,  2)
        p2 = QPointF( -4, 12)
        p3 = QPointF( 15,-10)
        if self.tk_p < 0.4:
            t   = self.tk_p / 0.4
            mid = QPointF(p1.x()+(p2.x()-p1.x())*t,
                          p1.y()+(p2.y()-p1.y())*t)
            P.drawLine(p1, mid)
        else:
            P.drawLine(p1, p2)
            t   = (self.tk_p - 0.4) / 0.6
            end = QPointF(p2.x()+(p3.x()-p2.x())*t,
                          p2.y()+(p3.y()-p2.y())*t)
            P.drawLine(p2, end)

    def _draw_x(self, P, cx, cy):
        a = int(255 * self.xa)
        P.setPen(QPen(QColor(255, 74, 74, a), 2.2))
        P.setBrush(Qt.NoBrush)
        P.drawEllipse(QPointF(cx, cy), 28, 28)
        P.setPen(QPen(QColor(255, 74, 74, a), 2.8,
                       Qt.SolidLine, Qt.RoundCap))
        d = 10
        P.drawLine(QPointF(cx-d, cy-d), QPointF(cx+d, cy+d))
        P.drawLine(QPointF(cx+d, cy-d), QPointF(cx-d, cy+d))

    def _draw_text(self, P, cx):
        f = QFont("Noto Sans, Helvetica Neue, Arial")
        f.setPixelSize(13)
        f.setWeight(QFont.Light)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.4)
        P.setFont(f)
        tc = self.txt_c
        P.setPen(QPen(QColor(tc[0], tc[1], tc[2],
                              int(255 * self.txt_a))))
        fm = P.fontMetrics()
        tw = fm.horizontalAdvance(self.txt)
        ty = self.CY + self.R + 55
        P.drawText(cx - tw // 2, ty, self.txt)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


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
                self.sig.fail.emit()
                return

            cap = None
            for i in range(3):
                c = cv2.VideoCapture(i)
                if c.isOpened():
                    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    c.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
                    c.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
                    c.set(cv2.CAP_PROP_FPS, 30)
                    r, _ = c.read()
                    if r:
                        cap = c
                        break
                c.release()

            if not cap:
                self.sig.fail.emit()
                return

            for _ in range(4):
                cap.read()

            for attempt in range(3):
                if not self.on:
                    break

                embs = []
                for _ in range(6):
                    if not self.on:
                        break
                    r, f = cap.read()
                    if not r:
                        continue
                    try:
                        rgb  = cv2.cvtColor(f, cv2.COLOR_BGR2RGB)
                        locs = face_recognition.face_locations(
                            rgb, model="hog"
                        )
                        if locs:
                            enc = face_recognition.face_encodings(
                                rgb, locs
                            )
                            if enc:
                                embs.append(enc[0])
                    except:
                        pass
                    time.sleep(0.04)

                if not embs:
                    self.sig.fail.emit()
                    time.sleep(2.0)
                    continue

                live = np.mean(embs, axis=0)
                bu, bd = None, 999.0
                for u, s in pf.items():
                    d = float(
                        face_recognition.face_distance([s], live)[0]
                    )
                    if d < bd:
                        bd, bu = d, u

                if bd <= THRESHOLD:
                    self.result = bu
                    self.sig.ok.emit(bu)
                    cap.release()
                    return
                else:
                    self.sig.fail.emit()
                    time.sleep(2.0)

            cap.release()
            self.sig.fail.emit()

        except:
            import traceback
            traceback.print_exc()
            self.sig.fail.emit()


class FaceIDLoginApp:
    def __init__(self):
        self.result = None

    def run(self):
        app = QApplication.instance() or QApplication(sys.argv)
        sig = Sig()

        w = FaceUnlockWidget(sig, demo_mode=False)

        scr = app.primaryScreen().geometry()
        sw  = scr.width()
        sh  = scr.height()

        # TOP CENTER position
        x = (sw - w.W) // 2
        y = 50  # 50px from top

        w.move(x, y)
        w.show()
        w.raise_()
        w.activateWindow()

        # Force window to top repeatedly using xdotool
        def force_top():
            try:
                wid = int(w.winId())
                subprocess.run(
                    ["xdotool", "windowactivate", "--sync", str(wid)],
                    capture_output=True, timeout=2
                )
                subprocess.run(
                    ["xdotool", "windowraise", str(wid)],
                    capture_output=True, timeout=2
                )
            except:
                pass
            w.raise_()
            w.activateWindow()

        top_timer = QTimer()
        top_timer.timeout.connect(force_top)
        top_timer.start(300)

        # Also force immediately
        QTimer.singleShot(100, force_top)
        QTimer.singleShot(500, force_top)
        QTimer.singleShot(1000, force_top)

        wk = FaceWorker(sig)

        def done(n):
            self.result = n
            top_timer.stop()
            QTimer.singleShot(2800, app.quit)

        sig.ok.connect(done)
        wk.start()
        app.exec_()
        wk.stop()
        wk.wait(2000)
        return self.result


def demo():
    app = QApplication(sys.argv)
    sig = Sig()
    w   = FaceUnlockWidget(sig, demo_mode=True)
    scr = app.primaryScreen().geometry()
    w.move((scr.width() - w.W) // 2, 50)
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
