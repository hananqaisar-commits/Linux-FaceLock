#!/usr/bin/env python3
"""
nova_unlock/ui/jarvis_overlay.py
Jarvis-style real-time face tracking HUD overlay.
Drawn directly on OpenCV frames — pure numpy/cv2, no Qt needed here.
"""
import cv2
import math
import time
import numpy as np
from typing import Optional, Tuple, List

# ── Color palette (BGR) ─────────────────────────────────────
C_CYAN    = (255, 220,  50)   # gold/amber — Jarvis primary
C_BLUE    = (255, 160,  20)   # deep amber
C_GREEN   = ( 50, 255, 120)   # success green
C_RED     = ( 50,  50, 255)   # fail red
C_WHITE   = (255, 255, 255)
C_DIM     = (120, 120, 140)
C_RING1   = (255, 200,  40)   # outer ring
C_RING2   = (200, 255, 240)   # inner ring cyan
C_SCAN    = (255, 240,  80)   # scan line


def _alpha_blend(frame, overlay, alpha=0.85):
    """Blend overlay onto frame with given alpha."""
    mask = overlay[:, :, 3:4] / 255.0 * alpha
    bgr  = overlay[:, :, :3]
    frame[:] = (frame * (1 - mask) + bgr * mask).astype(np.uint8)


def draw_dashed_circle(img, center, radius, color, thickness=1,
                        dash_len=12, gap_len=8, angle_offset=0.0):
    """Draw a dashed circle arc by arc."""
    cx, cy = center
    total = dash_len + gap_len
    n_segments = max(1, int(2 * math.pi * radius / total))
    for i in range(n_segments):
        a0 = angle_offset + (i * total / radius)
        a1 = a0 + dash_len / radius
        pts = []
        steps = max(4, int((a1 - a0) * radius / 2))
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            x = int(cx + radius * math.cos(a))
            y = int(cy + radius * math.sin(a))
            pts.append((x, y))
        for j in range(len(pts) - 1):
            cv2.line(img, pts[j], pts[j+1], color, thickness, cv2.LINE_AA)


class JarvisHUD:
    """
    Real-time Jarvis HUD drawn on camera frames.
    Call update(frame, face_loc) every frame.
    """

    # States
    IDLE      = "IDLE"
    LOCKING   = "LOCKING"
    SCANNING  = "SCANNING"
    ANALYZING = "ANALYZING"
    SUCCESS   = "SUCCESS"
    FAIL      = "FAIL"

    def __init__(self, w: int = 640, h: int = 480):
        self.w = w
        self.h = h
        self.state      = self.IDLE
        self._t         = time.time()
        self._state_t   = time.time()
        self._rot1      = 0.0    # outer ring rotation
        self._rot2      = 0.0    # inner ring rotation (counter)
        self._rot3      = 0.0    # data ring rotation
        self._scan_y    = 0.0    # scan line y offset
        self._scan_dir  = 1
        self._lock_x    = w // 2
        self._lock_y    = h // 2
        self._lock_r    = 80
        self._target_x  = w // 2
        self._target_y  = h // 2
        self._target_r  = 80
        self._flash     = 0.0
        self._progress  = 0.0   # 0→1 scan progress
        self._corner_a  = 0.0   # corner bracket alpha
        self._check_t   = 0.0   # checkmark draw progress
        self._fail_shake= 0.0
        self._data_lines= self._gen_data_lines()
        self._data_t    = 0.0
        self._landmarks : List[Tuple[int,int]] = []
        self._angle_idx = 0
        self._angle_prog= 0.0   # 0→1 for current angle
        self._face_conf = 0.0   # fake confidence readout

        # Smooth tracking
        self._smooth_x  = float(w // 2)
        self._smooth_y  = float(h // 2)
        self._smooth_r  = 80.0

    def _gen_data_lines(self):
        import random
        lines = []
        tags  = [
            "INFRARED SCAN", "DEPTH MAP", "BIOMETRIC HASH",
            "NEURAL MATCH", "LIVENESS CHECK", "ENTROPY SCAN",
            "PATTERN LOCK", "FEATURE EXTRACT", "ENCODE 128D",
            "ANTI-SPOOF", "THERMAL MAP", "TEXTURE ANALYSIS",
        ]
        for tag in tags:
            lines.append({
                "tag": tag,
                "val": f"{random.uniform(0,100):.1f}%",
                "spd": random.uniform(0.8, 2.5),
                "phase": random.uniform(0, 10),
            })
        return lines

    def set_face(self, face_loc: Optional[Tuple],
                 landmarks: Optional[List] = None):
        """
        Update face position.
        face_loc: (top, right, bottom, left) in original frame coords
        landmarks: list of (x,y) tuples — 68 points if available
        """
        if face_loc is not None:
            top, right, bottom, left = face_loc
            fx = (left + right) // 2
            fy = (top + bottom) // 2
            fr = max(right - left, bottom - top) // 2 + 20
            self._target_x = fx
            self._target_y = fy
            self._target_r = fr
            self._corner_a = min(1.0, self._corner_a + 0.15)
        else:
            self._corner_a = max(0.0, self._corner_a - 0.08)

        if landmarks:
            self._landmarks = landmarks
        else:
            self._landmarks = []

    def set_state(self, state: str):
        if state != self.state:
            self.state    = state
            self._state_t = time.time()
            if state == self.SUCCESS:
                self._check_t  = 0.0
                self._flash    = 1.0
            elif state == self.FAIL:
                self._fail_shake = 1.0
                self._flash      = 0.8

    def set_angle(self, idx: int, progress: float = 0.0):
        self._angle_idx  = idx
        self._angle_prog = progress

    def set_progress(self, p: float):
        self._progress = p

    def _lerp(self, a, b, t):
        return a + (b - a) * min(1.0, max(0.0, t))

    def update(self, frame: np.ndarray) -> np.ndarray:
        """
        Draw full Jarvis HUD onto frame (in-place).
        Returns the modified frame.
        """
        now = time.time()
        dt  = min(now - self._t, 0.05)
        self._t = now
        st  = now - self._state_t

        h, w = frame.shape[:2]

        # ── Smooth face tracking (exponential lerp) ───────
        spd = 1.0 - math.exp(-dt * 8.0)
        self._smooth_x = self._lerp(self._smooth_x, self._target_x, spd)
        self._smooth_y = self._lerp(self._smooth_y, self._target_y, spd)
        self._smooth_r = self._lerp(self._smooth_r, self._target_r, spd)

        cx = int(self._smooth_x)
        cy = int(self._smooth_y)
        R  = int(self._smooth_r)

        # ── Rotation ──────────────────────────────────────
        self._rot1 += dt * 45.0    # outer ring: 45°/s
        self._rot2 -= dt * 90.0    # inner ring: 90°/s counter
        self._rot3 += dt * 20.0    # data ring: slow

        # ── Scan line sweep ───────────────────────────────
        if self.state in (self.SCANNING, self.ANALYZING):
            self._scan_y += dt * 120 * self._scan_dir
            if self._scan_y >  R: self._scan_dir = -1
            if self._scan_y < -R: self._scan_dir =  1
        self._data_t += dt

        # ── Flash decay ───────────────────────────────────
        self._flash      = max(0.0, self._flash - dt * 4)
        self._fail_shake = max(0.0, self._fail_shake - dt * 3)
        if self.state == self.SUCCESS:
            self._check_t = min(1.0, self._check_t + dt * 2.5)

        # ── Shake offset ──────────────────────────────────
        shake = 0
        if self._fail_shake > 0.01:
            shake = int(18 * self._fail_shake *
                        math.sin(now * 18 * math.pi))

        # ── Dark vignette overlay ─────────────────────────
        self._draw_vignette(frame, w, h)

        # ── Corner HUD brackets (fixed corners of frame) ──
        self._draw_frame_corners(frame, w, h)

        # ── Top / bottom data bars ─────────────────────────
        self._draw_top_bar(frame, w, h, now)
        self._draw_bottom_bar(frame, w, h, now)

        # ── Data readout panels ───────────────────────────
        self._draw_data_panel(frame, w, h, now)

        ca = self._corner_a
        if ca < 0.02:
            # No face — draw searching animation
            self._draw_searching(frame, cx, cy, now)
            return frame

        # ── Color based on state ──────────────────────────
        if self.state == self.SUCCESS:
            rc, gc, bc = C_GREEN
        elif self.state == self.FAIL:
            rc, gc, bc = (50, 50, 255)
        elif self.state == self.ANALYZING:
            rc, gc, bc = (255, 200, 50)
        else:
            rc, gc, bc = C_RING1

        col_main  = (bc, gc, rc)   # BGR
        col_inner = (int(bc*0.6), int(gc*0.9), int(rc*0.9))
        alpha_a   = int(255 * ca)

        cx_s = cx + shake

        # ── 1. Outer glow (soft circle) ───────────────────
        self._draw_glow(frame, cx_s, cy, R + 30, col_main, ca * 0.4)

        # ── 2. Outer dashed ring (slow rotate) ────────────
        draw_dashed_circle(frame, (cx_s, cy), R + 28,
                           col_main, thickness=1,
                           angle_offset=math.radians(self._rot1))

        # ── 3. Main solid ring ────────────────────────────
        ring_alpha = int(220 * ca)
        cv2.circle(frame, (cx_s, cy), R,
                   col_main, 2, cv2.LINE_AA)

        # ── 4. Inner ring (counter-rotate) ────────────────
        draw_dashed_circle(frame, (cx_s, cy), R - 14,
                           col_inner, thickness=1,
                           dash_len=20, gap_len=10,
                           angle_offset=math.radians(self._rot2))

        # ── 5. Corner targeting brackets ──────────────────
        self._draw_brackets(frame, cx_s, cy, R, col_main, ca)

        # ── 6. Crosshair lines ────────────────────────────
        self._draw_crosshair(frame, cx_s, cy, R, col_main, ca)

        # ── 7. Landmark dots on face ──────────────────────
        self._draw_landmarks(frame, col_main, ca)

        # ── 8. Scan line ──────────────────────────────────
        if self.state in (self.SCANNING, self.ANALYZING):
            self._draw_scan_line(frame, cx_s, cy, R,
                                 col_main, ca)

        # ── 9. Rotating data ring (outer) ─────────────────
        self._draw_data_ring(frame, cx_s, cy, R + 45, now)

        # ── 10. Progress arc ──────────────────────────────
        if self._progress > 0.01:
            self._draw_progress_arc(frame, cx_s, cy, R + 6,
                                    self._progress, col_main)

        # ── 11. Angle progress arcs (per angle) ───────────
        self._draw_angle_arcs(frame, cx_s, cy, R + 18, ca)

        # ── 12. State label ───────────────────────────────
        self._draw_state_label(frame, cx_s, cy, R, now)

        # ── 13. Face confidence readout ───────────────────
        self._draw_confidence(frame, cx_s, cy, R, now)

        # ── 14. SUCCESS checkmark ─────────────────────────
        if self.state == self.SUCCESS and self._check_t > 0.01:
            self._draw_checkmark(frame, cx_s, cy, R)

        # ── 15. FAIL X mark ───────────────────────────────
        if self.state == self.FAIL and st > 0.1:
            self._draw_fail_x(frame, cx_s, cy, R)

        # ── 16. Flash overlay ─────────────────────────────
        if self._flash > 0.01:
            overlay = frame.copy()
            r, g, b = col_main
            cv2.rectangle(overlay, (0, 0), (w, h), (b, g, r), -1)
            cv2.addWeighted(overlay, self._flash * 0.25,
                            frame, 1 - self._flash * 0.25,
                            0, frame)

        return frame

    # ── Draw helpers ──────────────────────────────────────────

    def _draw_vignette(self, frame, w, h):
        """Subtle dark vignette edges — cinematic feel."""
        overlay = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        # Clear center
        cx, cy = w // 2, h // 2
        mask = np.zeros((h, w), dtype=np.float32)
        cv2.ellipse(mask, (cx, cy), (w//2, h//2),
                    0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (w|1, h|1), w//3)
        vign = (1.0 - mask[:,:,None]) * 0.55
        frame[:] = np.clip(
            frame.astype(np.float32) * (1 - vign),
            0, 255
        ).astype(np.uint8)

    def _draw_frame_corners(self, frame, w, h):
        """Fixed HUD corner brackets in frame corners."""
        col = (80, 160, 255)   # dim blue
        arm = 28
        thick = 1
        pad = 18
        corners = [
            (pad, pad, +1, +1),
            (w-pad, pad, -1, +1),
            (pad, h-pad, +1, -1),
            (w-pad, h-pad, -1, -1),
        ]
        for bx, by, dx, dy in corners:
            cv2.line(frame, (bx, by), (bx+dx*arm, by),
                     col, thick, cv2.LINE_AA)
            cv2.line(frame, (bx, by), (bx, by+dy*arm),
                     col, thick, cv2.LINE_AA)
            # Inner dot
            cv2.circle(frame, (bx, by), 3, col, -1, cv2.LINE_AA)

    def _draw_top_bar(self, frame, w, h, now):
        """Top HUD status bar."""
        # Line across top
        cv2.line(frame, (40, 14), (w-40, 14),
                 (60, 120, 200), 1, cv2.LINE_AA)

        # Left: NOVA UNLOCK
        cv2.putText(frame, "NOVA UNLOCK  //  BIOMETRIC AUTH",
                    (48, 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                    (120, 200, 255), 1, cv2.LINE_AA)

        # Right: timestamp
        ts = time.strftime("%H:%M:%S")
        cv2.putText(frame, ts,
                    (w - 100, 11),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38,
                    (120, 200, 255), 1, cv2.LINE_AA)

    def _draw_bottom_bar(self, frame, w, h, now):
        """Bottom HUD status bar."""
        cv2.line(frame, (40, h-14), (w-40, h-14),
                 (60, 120, 200), 1, cv2.LINE_AA)

        angle_names = ["FRONT","LEFT","RIGHT","UP","DOWN"]
        aname = angle_names[self._angle_idx % len(angle_names)]

        left_txt = f"ANGLE: {aname}  |  FRAME: {int(now*30)%9999:04d}"
        cv2.putText(frame, left_txt,
                    (48, h-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (100, 180, 255), 1, cv2.LINE_AA)

        right_txt = f"STATUS: {self.state}"
        tw, _ = cv2.getTextSize(right_txt,
                                 cv2.FONT_HERSHEY_SIMPLEX, 0.35, 1)
        cv2.putText(frame, right_txt,
                    (w - tw[0] - 48, h-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                    (100, 180, 255), 1, cv2.LINE_AA)

    def _draw_data_panel(self, frame, w, h, now):
        """Scrolling data readout on right side."""
        x0 = w - 145
        y0 = 35
        cv2.line(frame, (x0, y0), (x0, y0+200),
                 (40, 80, 140), 1, cv2.LINE_AA)

        for i, dl in enumerate(self._data_lines[:8]):
            t   = now * dl["spd"] + dl["phase"]
            blink = (math.sin(t * 3) + 1) / 2
            a   = int(60 + 80 * blink)
            # Update fake value
            dl["val"] = f"{(math.sin(t)*50+50):.1f}%"
            txt = f"{dl['tag'][:12]:<12}  {dl['val']}"
            cv2.putText(frame, txt,
                        (x0 + 5, y0 + 10 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.28,
                        (a, int(a*1.5), 255), 1, cv2.LINE_AA)

    def _draw_glow(self, frame, cx, cy, r, col, strength=0.3):
        """Soft radial glow around face ring."""
        if strength < 0.01:
            return
        overlay = frame.copy()
        b, g, rc = col[2], col[1], col[0]
        for rr, aa in [(r, int(40*strength)),
                       (r//2, int(20*strength))]:
            cv2.circle(overlay, (cx, cy), rr, (b, g, rc), -1)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

    def _draw_brackets(self, frame, cx, cy, R, col, alpha):
        """Targeting corner brackets around face."""
        pad   = 8
        arm   = max(16, R // 3)
        thick = 2
        x0, y0 = cx - R - pad, cy - R - pad
        x1, y1 = cx + R + pad, cy + R + pad
        a = int(255 * alpha)
        c = tuple(int(v * alpha) for v in col)

        corners = [
            (x0, y0, +1, +1),
            (x1, y0, -1, +1),
            (x0, y1, +1, -1),
            (x1, y1, -1, -1),
        ]
        for bx, by, dx, dy in corners:
            cv2.line(frame, (bx, by), (bx+dx*arm, by),
                     c, thick, cv2.LINE_AA)
            cv2.line(frame, (bx, by), (bx, by+dy*arm),
                     c, thick, cv2.LINE_AA)
            cv2.circle(frame, (bx, by), 3, c, -1, cv2.LINE_AA)

    def _draw_crosshair(self, frame, cx, cy, R, col, alpha):
        """Crosshair lines through center."""
        gap  = R // 3
        ext  = R + 24
        thick = 1
        a = alpha
        c = tuple(int(v * a * 0.5) for v in col)

        # Horizontal
        cv2.line(frame, (cx-ext, cy), (cx-gap, cy), c, thick, cv2.LINE_AA)
        cv2.line(frame, (cx+gap, cy), (cx+ext, cy), c, thick, cv2.LINE_AA)
        # Vertical
        cv2.line(frame, (cx, cy-ext), (cx, cy-gap), c, thick, cv2.LINE_AA)
        cv2.line(frame, (cx, cy+gap), (cx, cy+ext), c, thick, cv2.LINE_AA)
        # Center dot
        cv2.circle(frame, (cx, cy), 3,
                   tuple(int(v*a) for v in col), -1, cv2.LINE_AA)

    def _draw_scan_line(self, frame, cx, cy, R, col, alpha):
        """Horizontal scan beam sweeping through face."""
        sy = cy + int(self._scan_y)
        sy = max(cy - R, min(sy, cy + R))

        # Half-width at this y
        dy = sy - cy
        hw = int(math.sqrt(max(1, R*R - dy*dy)))

        # Gradient line
        for x in range(cx - hw, cx + hw, 2):
            t = abs(x - cx) / max(1, hw)
            a = int(alpha * 200 * (1 - t*t))
            if a < 4:
                continue
            b, g, r = col[2], col[1], col[0]
            cv2.line(frame, (x, sy), (x+2, sy),
                     (int(b*0.6), int(g*0.9), 255), 1, cv2.LINE_AA)

        # Bright center
        cv2.line(frame, (cx-hw, sy), (cx+hw, sy),
                 tuple(int(v*alpha*0.7) for v in col),
                 1, cv2.LINE_AA)

        # Glow above
        for dy2 in range(1, 6):
            a = int(alpha * 60 * (1 - dy2/6))
            cv2.line(frame, (cx-hw//2, sy-dy2), (cx+hw//2, sy-dy2),
                     (a, int(a*1.2), 255), 1, cv2.LINE_AA)

    def _draw_landmarks(self, frame, col, alpha):
        """68 facial landmark dots (or estimated grid if no dlib)."""
        if self._landmarks:
            for (lx, ly) in self._landmarks:
                a = int(alpha * 180)
                cv2.circle(frame, (lx, ly), 2,
                           (a, int(a*1.2), 255), -1, cv2.LINE_AA)
        else:
            # Estimated landmark grid based on face bounds
            cx = int(self._smooth_x)
            cy = int(self._smooth_y)
            R  = int(self._smooth_r)
            if R < 10:
                return
            # Simulate ~20 key points
            pts = [
                (-0.35, -0.30), (0.35, -0.30),   # eyes
                (-0.20, -0.30), (0.20, -0.30),
                (0.0,   -0.10),                   # nose bridge
                (0.0,    0.05),                   # nose tip
                (-0.25,  0.30), (0.25,  0.30),   # mouth
                (-0.10,  0.32), (0.10,  0.32),
                (0.0,    0.40),                   # chin
                (-0.50,  0.0),  (0.50,  0.0),    # cheeks
                (-0.45, -0.45), (0.45, -0.45),   # temples
                (-0.30,  0.55), (0.30,  0.55),   # jaw
                (0.0,   -0.55),                   # forehead
                (-0.55,  0.20), (0.55,  0.20),   # jaw sides
            ]
            t = time.time()
            for i, (px, py) in enumerate(pts):
                lx = int(cx + px * R)
                ly = int(cy + py * R)
                pulse = (math.sin(t * 3 + i * 0.4) + 1) / 2
                a = int(alpha * (120 + 80 * pulse))
                sz = 1 if i > 10 else 2
                cv2.circle(frame, (lx, ly), sz,
                           (a, int(a*1.3), 255), -1, cv2.LINE_AA)
                # Connection lines for some pairs
                if i > 0 and i % 2 == 1 and i < 10:
                    lx2 = int(cx + pts[i-1][0] * R)
                    ly2 = int(cy + pts[i-1][1] * R)
                    cv2.line(frame, (lx, ly), (lx2, ly2),
                             (a//3, a//2, 180), 1, cv2.LINE_AA)

    def _draw_data_ring(self, frame, cx, cy, R, now):
        """Rotating ring of tick marks and labels."""
        n_ticks = 36
        for i in range(n_ticks):
            angle = math.radians(i * 360/n_ticks + self._rot3)
            is_major = i % 6 == 0
            inner_r = R - (8 if is_major else 4)
            outer_r = R
            x1 = int(cx + inner_r * math.cos(angle))
            y1 = int(cy + inner_r * math.sin(angle))
            x2 = int(cx + outer_r * math.cos(angle))
            y2 = int(cy + outer_r * math.sin(angle))
            col = (80, 160, 255) if is_major else (40, 80, 140)
            cv2.line(frame, (x1,y1), (x2,y2), col, 1, cv2.LINE_AA)

        # Labels at major ticks
        labels = ["0°","60°","120°","180°","240°","300°"]
        for i, lbl in enumerate(labels):
            angle = math.radians(i * 60 + self._rot3)
            lx = int(cx + (R+12) * math.cos(angle))
            ly = int(cy + (R+12) * math.sin(angle))
            cv2.putText(frame, lbl, (lx-10, ly+4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.22,
                        (60, 120, 200), 1, cv2.LINE_AA)

    def _draw_progress_arc(self, frame, cx, cy, R, progress, col):
        """Filled arc showing capture progress."""
        span = int(progress * 360)
        axes = (R, R)
        cv2.ellipse(frame, (cx, cy), axes,
                    -90, 0, span, col, 3, cv2.LINE_AA)

    def _draw_angle_arcs(self, frame, cx, cy, R, alpha):
        """5 small arcs around ring showing per-angle progress."""
        n      = 5
        arc_sz = 60   # degrees per slot
        gap    = 12
        cols   = [
            (255, 220, 50), (200, 80, 255),
            (50, 180, 255), (50, 255, 120),
            (50, 220, 255),
        ]
        for i in range(n):
            start = -90 + i * (arc_sz + gap)
            if i < self._angle_idx:
                # Complete
                cv2.ellipse(frame, (cx, cy), (R, R),
                            0, start, start+arc_sz,
                            cols[i], 2, cv2.LINE_AA)
            elif i == self._angle_idx:
                # In progress
                span = int(self._angle_prog * arc_sz)
                if span > 0:
                    cv2.ellipse(frame, (cx, cy), (R, R),
                                0, start, start+span,
                                cols[i], 2, cv2.LINE_AA)
                # Dim remaining
                cv2.ellipse(frame, (cx, cy), (R, R),
                            0, start+span, start+arc_sz,
                            (40, 60, 100), 1, cv2.LINE_AA)
            else:
                cv2.ellipse(frame, (cx, cy), (R, R),
                            0, start, start+arc_sz,
                            (30, 50, 80), 1, cv2.LINE_AA)

    def _draw_state_label(self, frame, cx, cy, R, now):
        """State label below face ring."""
        labels = {
            self.IDLE:      ("INITIALIZING",   (100, 160, 255)),
            self.LOCKING:   ("ACQUIRING LOCK", (255, 200, 50)),
            self.SCANNING:  ("SCANNING",        (255, 220, 80)),
            self.ANALYZING: ("ANALYZING",       (200, 255, 100)),
            self.SUCCESS:   ("IDENTITY CONFIRMED", (50, 255, 120)),
            self.FAIL:      ("ACCESS DENIED",   (50, 50, 255)),
        }
        txt, col = labels.get(self.state, ("", C_WHITE))
        if not txt:
            return

        # Blink for scanning states
        if self.state in (self.SCANNING, self.LOCKING):
            blink = (math.sin(now * 4) + 1) / 2
            col = tuple(int(c * (0.5 + 0.5*blink)) for c in col)

        tw, th = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)[0]
        tx = cx - tw // 2
        ty = cy + R + 28
        cv2.putText(frame, txt, (tx, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    col, 1, cv2.LINE_AA)

        # Underline
        cv2.line(frame, (tx, ty+3), (tx+tw, ty+3),
                 tuple(c//2 for c in col), 1, cv2.LINE_AA)

    def _draw_confidence(self, frame, cx, cy, R, now):
        """Fake confidence % and biometric readout near face."""
        if self._corner_a < 0.3:
            return

        # Animated confidence
        t  = now * 1.2
        if self.state == self.SUCCESS:
            conf = 98.0 + math.sin(t) * 0.5
        elif self.state == self.FAIL:
            conf = 22.0 + math.sin(t) * 3
        else:
            conf = 60 + 25 * (math.sin(t) * 0.5 + 0.5)

        col = (50, 255, 120) if conf > 80 else \
              (50, 200, 255) if conf > 50 else \
              (50, 50, 255)

        txt = f"{conf:.1f}%"
        cv2.putText(frame, txt,
                    (cx - R - 60, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    col, 1, cv2.LINE_AA)
        cv2.putText(frame, "CONF",
                    (cx - R - 60, cy - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28,
                    (80, 140, 200), 1, cv2.LINE_AA)

        # Hash readout
        import random
        random.seed(int(now * 2))
        h1 = f"{random.randint(0,0xFFFF):04X}"
        h2 = f"{random.randint(0,0xFFFF):04X}"
        cv2.putText(frame, f"ID:{h1}-{h2}",
                    (cx + R + 8, cy - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28,
                    (80, 140, 200), 1, cv2.LINE_AA)

    def _draw_checkmark(self, frame, cx, cy, R):
        """Animated checkmark draw-on for success."""
        t = self._check_t
        col = (50, 255, 120)
        sz  = int(R * 0.55)

        p1 = (cx - sz, cy)
        p2 = (cx - sz//4, cy + sz//2)
        p3 = (cx + sz, cy - sz//2)

        if t < 0.45:
            frac = t / 0.45
            mid  = (int(p1[0] + (p2[0]-p1[0])*frac),
                    int(p1[1] + (p2[1]-p1[1])*frac))
            cv2.line(frame, p1, mid, col, 3, cv2.LINE_AA)
        else:
            cv2.line(frame, p1, p2, col, 3, cv2.LINE_AA)
            frac = (t - 0.45) / 0.55
            end  = (int(p2[0] + (p3[0]-p2[0])*frac),
                    int(p2[1] + (p3[1]-p2[1])*frac))
            cv2.line(frame, p2, end, col, 3, cv2.LINE_AA)

        # Glow circle
        cv2.circle(frame, (cx, cy), R+4, col, 2, cv2.LINE_AA)

    def _draw_fail_x(self, frame, cx, cy, R):
        """Red X mark for fail."""
        col = (50, 50, 255)
        sz  = int(R * 0.45)
        t   = min(1.0, (time.time() - self._state_t - 0.1) * 3)
        if t < 0.5:
            frac = t / 0.5
            cv2.line(frame,
                     (cx-sz, cy-sz),
                     (int(cx-sz+(2*sz)*frac), int(cy-sz+(2*sz)*frac)),
                     col, 3, cv2.LINE_AA)
        else:
            cv2.line(frame, (cx-sz,cy-sz), (cx+sz,cy+sz),
                     col, 3, cv2.LINE_AA)
            frac = (t - 0.5) / 0.5
            cv2.line(frame,
                     (cx+sz, cy-sz),
                     (int(cx+sz-(2*sz)*frac), int(cy-sz+(2*sz)*frac)),
                     col, 3, cv2.LINE_AA)
        cv2.circle(frame, (cx,cy), R+4, col, 2, cv2.LINE_AA)

    def _draw_searching(self, frame, cx, cy, now):
        """Animated searching ring when no face detected."""
        t = now
        R = 70 + int(10 * math.sin(t * 2))
        a = int(80 + 60 * (math.sin(t*3)+1)/2)
        col = (a, int(a*1.2), 255)

        draw_dashed_circle(frame, (cx, cy), R, col,
                           thickness=1, dash_len=15, gap_len=10,
                           angle_offset=math.radians(t*60))
        draw_dashed_circle(frame, (cx, cy), R+20,
                           (a//2, a//3, 180),
                           thickness=1, dash_len=8, gap_len=15,
                           angle_offset=math.radians(-t*40))

        cv2.putText(frame, "SEARCHING...",
                    (cx-55, cy+R+25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (80, 140, 255), 1, cv2.LINE_AA)
