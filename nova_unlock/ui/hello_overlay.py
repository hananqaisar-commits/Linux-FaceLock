OVERLAY_DEBUG = True
#!/usr/bin/env python3
"""
nova_unlock/ui/hello_overlay.py
─────────────────────────────
NovaUnlock Hello Overlay v1 - Apple Intelligence Style
Theme: Cyan spectrum (matches 4-dot animation)

Features:
  ✦ Rotating cyan-spectrum gradient border (chaaron taraf)
  ✦ Original 4-dot pulsing animation
  ✦ "hello" greeting with Sacramento font + neon glow
  ✦ Smooth transitions
"""
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gtk, Gdk, GLib
import cairo
import math
import time
import threading
import queue
import socket
import os
import sys
import json
import signal

# Protect against desktop session manager signals (SIGHUP/SIGTERM during KDE load)
for _sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT):
    try:
        signal.signal(_sig, signal.SIG_IGN)
    except Exception:
        pass

SOCKET_PATH = "/tmp/nova_hello.sock"

# ── Color Palette ─────────────────────────────────────────────────────────
PURE_WHITE  = (1.0, 1.0, 1.0)
SOFT_WHITE  = (0.88, 0.91, 0.96)
FADED       = (0.50, 0.54, 0.60)
ACCENT      = (0.0, 0.75, 1.0)

# Original 4 dots — cyan spectrum (PRESERVED)
DOT_COLORS = [
    (0.00, 0.85, 1.00),
    (0.00, 0.65, 0.95),
    (0.15, 0.80, 1.00),
    (0.00, 0.72, 0.88),
]

# Border gradient — cyan spectrum that COMPLEMENTS the 4 dots
# Deep blue → electric cyan → mint → bright cyan
BORDER_COLORS = [
    (0.00, 0.45, 0.95),   # deep blue
    (0.00, 0.70, 1.00),   # electric blue
    (0.10, 0.90, 1.00),   # bright cyan
    (0.20, 1.00, 0.95),   # cyan-mint
    (0.00, 0.85, 1.00),   # core cyan (matches dots)
    (0.30, 0.60, 1.00),   # blue-violet
]

# "hello" greeting — same cyan family
HELLO_COLORS = [
    (0.00, 0.80, 1.00),   # cyan
    (0.20, 0.65, 1.00),   # blue
    (0.10, 0.95, 1.00),   # bright cyan
]

# Border config
BORDER_THICKNESS = 90    # px - how thick the glow extends inward

MAX_LIVE_WORDS = 6
FADE_SPEED     = 12.0
SLIDE_SPEED    = 8.0
SLIDE_DISTANCE = 20.0

# Cursive font for "hello" (in priority order)
HELLO_FONT_CANDIDATES = [
    "Sacramento",
    "Great Vibes",
    "Allura",
    "Snell Roundhand",
    "Dancing Script",
    "Brush Script MT",
    "Comic Sans MS",
    "Sans",
]


class JarvisOverlay(Gtk.Window):

    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self._text         = ""
        self._display_text = ""
        self._state        = "idle"
        self._audio_rms    = 0.0        # current mic level (0..1)
        self._rms_smooth   = 0.0        # smoothed for animation
        self._bar_heights  = [0.0] * 7  # 7 bars trailing history
        self._visible      = False
        self._opacity      = 0.0
        self._target_op    = 0.0
        self._slide_y      = SLIDE_DISTANCE
        self._target_sy    = 0.0
        self._phase        = 0.0
        self._border_phase = 0.0
        self._hello_phase  = 0.0
        self._last_t       = time.time()
        self._queue        = queue.Queue()
        self._word_times   = {}
        self._hide_timer   = None
        self._hold_until   = 0.0
        self._border_intensity = 0.0
        self._hello_font   = self._pick_cursive_font()

        self._setup_window()
        self.connect('delete-event', self._on_delete_event)
        self.connect('unmap-event', self._on_unmap_event)
        self._topmost_tick_counter = 0

        da = Gtk.DrawingArea()
        da.connect('draw', self._draw)
        self.add(da)
        self._da = da

        GLib.timeout_add(16, self._tick)

    def _on_delete_event(self, widget, event):
        if self._state == "hello" and time.time() < self._hold_until:
            return True
        return False

    def _on_unmap_event(self, widget, event):
        if self._state == "hello" and time.time() < self._hold_until:
            GLib.idle_add(self._force_topmost)
            return True
        return False

    def _force_topmost(self):
        try:
            if not self.get_visible():
                self.show_all()
                self._visible = True
            self.set_keep_above(True)
            self.stick()
            self.present()
            win = self.get_window()
            if win:
                win.raise_()
                win.show()
        except Exception:
            pass


    def _pick_cursive_font(self):
        """Find best available cursive font"""
        try:
            import subprocess
            result = subprocess.run(
                ["fc-list", ":family"],
                capture_output=True, text=True, timeout=2
            )
            installed = result.stdout.lower()
            for font in HELLO_FONT_CANDIDATES:
                if font.lower() in installed:
                    print(f"Hello font: {font}", flush=True)
                    return font
        except Exception:
            pass
        return "Sans"

    def _setup_window(self):
        screen = Gdk.Screen.get_default()
        visual = screen.get_rgba_visual()
        if visual:
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)
        self.stick()

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() if display else None
        if not monitor and display and display.get_n_monitors() > 0:
            monitor = display.get_monitor(0)

        if monitor:
            geo = monitor.get_geometry()
            self._sw = geo.width
            self._sh = geo.height
            gx, gy = geo.x, geo.y
        else:
            self._sw = 1920
            self._sh = 1200
            gx, gy = 0, 0

        # Full screen for border effect
        self.set_size_request(self._sw, self._sh)
        self.move(gx, gy)

        self.realize()
        region = cairo.Region(cairo.RectangleInt(0, 0, 0, 0))
        self.get_window().input_shape_combine_region(region, 0, 0)


    # ══════════════════════════════════════════════════════════════════════
    #  MAIN DRAW
    # ══════════════════════════════════════════════════════════════════════

    def _draw(self, widget, cr):
        w = widget.get_allocated_width()
        h = widget.get_allocated_height()

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self._opacity < 0.005 and self._border_intensity < 0.005:
            return

        # ── Apple Intelligence style border ─────────────────────────────
        # Hide border during hello greeting — clean welcome screen
        if self._state == "hello":
            self._border_intensity = 0.0
        elif self._border_intensity > 0.005:
            self._draw_ai_border(cr, w, h)

        if self._opacity < 0.005:
            return

        # ── Hello greeting (full-screen centered) ───────────────────────
        if self._state == "hello":
            cr.save()
            cr.translate(0, self._slide_y)
            cr.push_group()
            self._draw_hello(cr, w, h)
            cr.pop_group_to_source()
            cr.paint_with_alpha(self._opacity)
            cr.restore()
            return

        # ── Bottom HUD (dots + text) ────────────────────────────────────
        hud_h = 200
        hud_y_offset = h - hud_h - 60

        cr.save()
        cr.translate(0, hud_y_offset + self._slide_y)
        cr.push_group()

        if self._state == "listening" and not self._display_text:
            self._draw_premium_dots(cr, w, hud_h)
        elif self._state == "processing":
            self._draw_premium_dots(cr, w, hud_h)
            if self._display_text:
                self._draw_words(cr, w, hud_h, below=True)
        else:
            if self._display_text:
                self._draw_words(cr, w, hud_h)

        cr.pop_group_to_source()
        cr.paint_with_alpha(self._opacity)
        cr.restore()

    # ══════════════════════════════════════════════════════════════════════
    #  Apple Intelligence Border — Cyan Spectrum (matches dots)
    # ══════════════════════════════════════════════════════════════════════

    def _draw_ai_border(self, cr, w, h):
        """
        Rotating cyan-spectrum gradient on screen edges.
        Apple Intelligence style but in CIPHER cyan theme.
        Flowing color band travels around the perimeter.
        """
        intensity = self._border_intensity
        thickness = BORDER_THICKNESS

        # ── Step 1: 4 edge gradients (inward fade) ──────────────────────
        # Each edge: solid color outside → transparent inside

        # TOP edge
        for x_offset in range(0, w, 80):
            # Position along perimeter (0 to 1)
            t = (x_offset / max(w, 1)) * 0.25  # 0 to 0.25 (top quarter)
            color = self._sample_border_color(t)
            self._paint_edge_segment(
                cr, x_offset, 0, 80, thickness,
                color, intensity, side="top"
            )

        # RIGHT edge
        for y_offset in range(0, h, 80):
            t = 0.25 + (y_offset / max(h, 1)) * 0.25
            color = self._sample_border_color(t)
            self._paint_edge_segment(
                cr, w - thickness, y_offset, thickness, 80,
                color, intensity, side="right"
            )

        # BOTTOM edge
        for x_offset in range(w, 0, -80):
            t = 0.5 + ((w - x_offset) / max(w, 1)) * 0.25
            color = self._sample_border_color(t)
            self._paint_edge_segment(
                cr, x_offset - 80, h - thickness, 80, thickness,
                color, intensity, side="bottom"
            )

        # LEFT edge
        for y_offset in range(h, 0, -80):
            t = 0.75 + ((h - y_offset) / max(h, 1)) * 0.25
            color = self._sample_border_color(t)
            self._paint_edge_segment(
                cr, 0, y_offset - 80, thickness, 80,
                color, intensity, side="left"
            )

        # ── Step 2: corner brightness boost ─────────────────────────────
        corner_size = thickness * 2.5
        corners = [
            (0,         0,         0.0),   # top-left
            (w,         0,         0.25),  # top-right
            (w,         h,         0.5),   # bottom-right
            (0,         h,         0.75),  # bottom-left
        ]
        for cx, cy, t_off in corners:
            color = self._sample_border_color(t_off + 0.125)
            pulse = 0.85 + 0.15 * math.sin(
                self._border_phase * 1.2 + t_off * 6.28)
            grad = cairo.RadialGradient(cx, cy, 0, cx, cy, corner_size)
            grad.add_color_stop_rgba(
                0.0, color[0], color[1], color[2], 0.55 * intensity * pulse)
            grad.add_color_stop_rgba(
                0.5, color[0], color[1], color[2], 0.25 * intensity * pulse)
            grad.add_color_stop_rgba(
                1.0, color[0], color[1], color[2], 0.0)
            cr.set_source(grad)
            cr.rectangle(0, 0, w, h)
            cr.fill()

    def _sample_border_color(self, t):
        """
        Sample a color from BORDER_COLORS at position t (0..1),
        offset by current rotation phase for animation.
        """
        # Rotate the gradient over time
        rotation = (self._border_phase * 0.15) % 1.0
        t_rot = (t + rotation) % 1.0

        # Map t_rot to color index (smooth interpolation)
        n = len(BORDER_COLORS)
        idx_f = t_rot * n
        i0 = int(idx_f) % n
        i1 = (i0 + 1) % n
        blend = idx_f - int(idx_f)

        c0 = BORDER_COLORS[i0]
        c1 = BORDER_COLORS[i1]
        return (
            c0[0] * (1-blend) + c1[0] * blend,
            c0[1] * (1-blend) + c1[1] * blend,
            c0[2] * (1-blend) + c1[2] * blend,
        )

    def _paint_edge_segment(self, cr, x, y, ew, eh, color, intensity, side):
        """Paint one segment of edge with inward fade"""
        r, g, b = color

        if side == "top":
            grad = cairo.LinearGradient(0, y, 0, y + eh)
            grad.add_color_stop_rgba(0.0, r, g, b, 0.65 * intensity)
            grad.add_color_stop_rgba(0.4, r, g, b, 0.30 * intensity)
            grad.add_color_stop_rgba(1.0, r, g, b, 0.0)
        elif side == "bottom":
            grad = cairo.LinearGradient(0, y, 0, y + eh)
            grad.add_color_stop_rgba(0.0, r, g, b, 0.0)
            grad.add_color_stop_rgba(0.6, r, g, b, 0.30 * intensity)
            grad.add_color_stop_rgba(1.0, r, g, b, 0.65 * intensity)
        elif side == "left":
            grad = cairo.LinearGradient(x, 0, x + ew, 0)
            grad.add_color_stop_rgba(0.0, r, g, b, 0.65 * intensity)
            grad.add_color_stop_rgba(0.4, r, g, b, 0.30 * intensity)
            grad.add_color_stop_rgba(1.0, r, g, b, 0.0)
        else:  # right
            grad = cairo.LinearGradient(x, 0, x + ew, 0)
            grad.add_color_stop_rgba(0.0, r, g, b, 0.0)
            grad.add_color_stop_rgba(0.6, r, g, b, 0.30 * intensity)
            grad.add_color_stop_rgba(1.0, r, g, b, 0.65 * intensity)

        cr.set_source(grad)
        cr.rectangle(x, y, ew, eh)
        cr.fill()

    # ══════════════════════════════════════════════════════════════════════
    #  "hello" Greeting — Cursive with Cyan Glow
    # ══════════════════════════════════════════════════════════════════════














    # ══════════════════════════════════════════════════════════════════════
    #  iOS HELLO SVG — Exact Apple path + dynamic username
    # ══════════════════════════════════════════════════════════════════════

    # Exact iOS "hello" cursive path (from mtynior/AppleHello)
    # Original viewBox: 900x300, hello ends at x≈727
    _HELLO_SVG_PATH = [
        ("M", 170.5, 194.7),
        ("C", 246.8, 155.0, 214.3, 178.2, 246.8, 155.0),
        ("C", 271.8, 137.2, 284.9, 113.2, 274.8, 102.8),
        ("C", 238.3, 65.3, 216.6, 202.2, 221.9, 202.2),
        ("C", 227.2, 202.3, 226.9, 162.4, 253.7, 153.3),
        ("C", 280.6, 144.3, 290.1, 156.3, 291.3, 162.0),
        ("C", 293.3, 171.0, 285.2, 185.4, 286.6, 190.6),
        ("C", 292.3, 212.6, 385.1, 191.0, 392.4, 166.2),
        ("C", 400.2, 139.5, 331.5, 140.8, 345.1, 183.4),
        ("C", 350.1, 199.1, 381.1, 203.2, 397.6, 200.8),
        ("C", 457.3, 192.3, 498.3, 149.0, 496.8, 115.7),
        ("C", 494.9, 72.6, 430.7, 116.2, 446.1, 182.6),
        ("C", 452.1, 208.2, 502.6, 199.9, 517.5, 193.1),
        ("C", 545.1, 180.5, 593.7, 144.2, 584.8, 108.9),
        ("C", 575.5, 72.2, 505.6, 132.7, 537.7, 187.8),
        ("C", 548.4, 206.2, 580.5, 200.0, 589.3, 197.2),
        ("C", 610.2, 190.4, 617.0, 166.1, 634.3, 155.5),
        ("C", 656.2, 142.0, 690.6, 152.1, 692.1, 168.0),
        ("C", 695.2, 203.2, 649.4, 203.2, 632.4, 195.3),
        ("C", 617.6, 188.5, 614.2, 168.1, 634.0, 155.5),
        ("C", 647.6, 146.8, 669.3, 146.6, 697.8, 156.3),
        ("C", 709.4, 160.3, 719.4, 159.5, 727.3, 153.2),
    ]

    # SVG path arclength approximation
    def _build_hello_segments(self, scale, ox, oy):
        """Convert SVG path to drawable segments with cumulative length"""
        cache_key = (scale, ox, oy)
        cached = getattr(self, '_hello_path_cache', None)
        if cached and cached.get('key') == cache_key:
            return cached

        segments = []  # list of (type, points...)
        cur_x, cur_y = 0, 0

        for cmd in self._HELLO_SVG_PATH:
            if cmd[0] == "M":
                cur_x = ox + cmd[1] * scale
                cur_y = oy + cmd[2] * scale
                segments.append(("M", cur_x, cur_y))
            elif cmd[0] == "C":
                x1 = ox + cmd[1] * scale
                y1 = oy + cmd[2] * scale
                x2 = ox + cmd[3] * scale
                y2 = oy + cmd[4] * scale
                x3 = ox + cmd[5] * scale
                y3 = oy + cmd[6] * scale
                segments.append(("C", cur_x, cur_y, x1, y1, x2, y2, x3, y3))
                cur_x, cur_y = x3, y3

        # Approximate total length by sampling each curve
        total_len = 0.0
        seg_lens = []
        for seg in segments:
            if seg[0] == "M":
                seg_lens.append(0.0)
            elif seg[0] == "C":
                # Sample 30 points along bezier
                _, x0, y0, x1, y1, x2, y2, x3, y3 = seg
                length = 0.0
                px, py = x0, y0
                for i in range(1, 31):
                    t = i / 30.0
                    mt = 1 - t
                    bx = mt**3*x0 + 3*mt**2*t*x1 + 3*mt*t**2*x2 + t**3*x3
                    by = mt**3*y0 + 3*mt**2*t*y1 + 3*mt*t**2*y2 + t**3*y3
                    length += math.sqrt((bx-px)**2 + (by-py)**2)
                    px, py = bx, by
                seg_lens.append(length)
                total_len += length

        result = {
            'key': cache_key,
            'segments': segments,
            'seg_lens': seg_lens,
            'total_len': total_len,
        }
        self._hello_path_cache = result
        return result

    def _draw_hello_path_partial(self, cr, scale, ox, oy, progress):
        """Draw the SVG path up to `progress` (0..1) of total arclength"""
        data = self._build_hello_segments(scale, ox, oy)
        segments = data['segments']
        seg_lens = data['seg_lens']
        total_len = data['total_len']
        target_len = total_len * progress

        cur_len = 0.0
        cr.new_path()
        last_pt = None

        for i, seg in enumerate(segments):
            seg_len = seg_lens[i]

            if seg[0] == "M":
                _, x, y = seg
                cr.move_to(x, y)
                last_pt = (x, y)
                continue

            if cur_len + seg_len <= target_len:
                # Draw entire bezier
                _, x0, y0, x1, y1, x2, y2, x3, y3 = seg
                cr.curve_to(x1, y1, x2, y2, x3, y3)
                cur_len += seg_len
                last_pt = (x3, y3)
            else:
                # Partial bezier — find t where we hit target_len
                _, x0, y0, x1, y1, x2, y2, x3, y3 = seg
                remaining = target_len - cur_len
                if seg_len > 0:
                    # Find t by sampling
                    sub_len = 0.0
                    px, py = x0, y0
                    t_found = 1.0
                    for j in range(1, 101):
                        t = j / 100.0
                        mt = 1 - t
                        bx = mt**3*x0 + 3*mt**2*t*x1 + 3*mt*t**2*x2 + t**3*x3
                        by = mt**3*y0 + 3*mt**2*t*y1 + 3*mt*t**2*y2 + t**3*y3
                        sub_len += math.sqrt((bx-px)**2 + (by-py)**2)
                        px, py = bx, by
                        if sub_len >= remaining:
                            t_found = t
                            break
                    # De Casteljau subdivide curve at t_found
                    t = t_found
                    mt = 1 - t
                    # Control points for subdivided curve [0, t]
                    p01x = mt*x0 + t*x1; p01y = mt*y0 + t*y1
                    p12x = mt*x1 + t*x2; p12y = mt*y1 + t*y2
                    p23x = mt*x2 + t*x3; p23y = mt*y2 + t*y3
                    p012x = mt*p01x + t*p12x; p012y = mt*p01y + t*p12y
                    p123x = mt*p12x + t*p23x; p123y = mt*p12y + t*p23y
                    p0123x = mt*p012x + t*p123x; p0123y = mt*p012y + t*p123y
                    cr.curve_to(p01x, p01y, p012x, p012y, p0123x, p0123y)
                return (p0123x, p0123y)

        return last_pt

    def _draw_hello(self, cr, w, h):
        """
        Real iOS hello — uses exact Apple SVG path coordinates.
        Then appends ", <username>" in matching script font.
        """
        # ── Glassy black background ──────────────────────────────
        cr.set_source_rgba(0, 0, 0, 0.85)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Radial vignette
        vign = cairo.RadialGradient(w/2, h/2, h*0.1, w/2, h/2, h*0.85)
        vign.add_color_stop_rgba(0.0, 0, 0, 0, 0.0)
        vign.add_color_stop_rgba(1.0, 0, 0, 0, 0.65)
        cr.set_source(vign)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        # Top glass reflection
        refl = cairo.LinearGradient(0, 0, 0, h * 0.15)
        refl.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 0.06)
        refl.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
        cr.set_source(refl)
        cr.rectangle(0, 0, w, h * 0.15)
        cr.fill()

        # Frost shimmer
        frost = cairo.LinearGradient(0, 0, 0, h)
        frost.add_color_stop_rgba(0.0, 1, 1, 1, 0.04)
        frost.add_color_stop_rgba(0.5, 1, 1, 1, 0.01)
        frost.add_color_stop_rgba(1.0, 1, 1, 1, 0.03)
        cr.set_source(frost)
        cr.rectangle(0, 0, w, h)
        cr.fill()

        # Username — prefer the name passed in the greeting payload
        # ("hello, <name>") over the environment user, so the overlay shows the
        # ACTUAL matched user, not the account running the overlay process.
        uname = "you"
        try:
            payload = (self._text or "").strip()
            if payload.lower().startswith("hello"):
                cand = payload[len("hello"):].strip().lstrip(",").strip()
                if cand:
                    uname = cand
        except Exception:
            pass
        if uname == "you":
            try:
                import os
                uname = os.environ.get("USER", "") or "you"
            except Exception:
                uname = "you"

        # Always show "hello"; if username available, add ", name"
        suffix_text = f", {uname}"
        phase = self._hello_phase

        # ── Timing ────────────────────────────────────────────────────
        HELLO_WRITE = 3.0     # SVG path draw time
        PAUSE       = 0.2     # tiny pause before name
        NAME_WRITE  = 1.2     # name appears
        HOLD        = 1.4
        FADE        = 0.8
        TOTAL = HELLO_WRITE + PAUSE + NAME_WRITE + HOLD + FADE  # 6.6s

        if phase >= TOTAL:
            return

        # Master alpha
        if phase < HELLO_WRITE + PAUSE + NAME_WRITE + HOLD:
            alpha = 1.0
        else:
            t = (phase - HELLO_WRITE - PAUSE - NAME_WRITE - HOLD) / FADE
            alpha = 1.0 - (0.5 - 0.5 * math.cos(math.pi * t))

        if alpha < 0.01:
            return

        # ── Layout & Screen Centering ──────────────────────────────────
        # SVG viewBox is 900x300, hello path uses x:170-727 = ~557 wide
        # Proportioned Apple welcome layout: hello ~34% of screen width
        target_hello_w = min(w * 0.34, 660)
        path_native_w = 727 - 170  # ~557
        scale = max(0.55, target_hello_w / float(path_native_w))

        scaled_path_w = path_native_w * scale

        cr.select_font_face(
            self._hello_font,
            cairo.FONT_SLANT_ITALIC,
            cairo.FONT_WEIGHT_NORMAL
        )
        font_size = int(125 * scale)
        cr.set_font_size(font_size)
        suffix_ext = cr.text_extents(suffix_text)
        suffix_w = suffix_ext.x_advance or suffix_ext.width

        # Exact total bounding width of combined phrase "hello, username"
        total_w = scaled_path_w + (14.0 * scale) + suffix_w
        left_margin = (w - total_w) / 2.0
        ox = left_margin - 170.0 * scale

        # Phrase vertical midpoint = 140.0 native units
        # Center the phrase dead-center on screen height (h / 2.0)
        oy = (h / 2.0) - (140.0 * scale)



        # ── Write progress for hello path ─────────────────────────────
        if phase < HELLO_WRITE:
            raw = phase / HELLO_WRITE
            # Ease in-out for natural pen rhythm
            hello_progress = 0.5 - 0.5 * math.cos(math.pi * raw)
        else:
            hello_progress = 1.0

        # ── Draw hello SVG path stroke ────────────────────────────────
        cr.save()
        cr.set_source_rgba(1, 1, 1, alpha)
        cr.set_line_width(8.5 * scale)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        end_point = self._draw_hello_path_partial(cr, scale, ox, oy, hello_progress)
        cr.stroke()
        cr.restore()

        # Soft glow under path (Apple's filter effect)
        cr.save()
        cr.set_source_rgba(1, 1, 1, alpha * 0.25)
        cr.set_line_width(16.0 * scale)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        self._draw_hello_path_partial(cr, scale, ox, oy, hello_progress)
        cr.stroke()
        cr.restore()

        # ── Draw ", username" suffix after hello completes ────────────
        if phase > HELLO_WRITE + PAUSE * 0.5:
            name_phase = phase - HELLO_WRITE - PAUSE
            if name_phase > 0:
                if name_phase < NAME_WRITE:
                    name_progress = name_phase / NAME_WRITE
                    name_progress = 0.5 - 0.5 * math.cos(math.pi * name_progress)
                else:
                    name_progress = 1.0

                # Position suffix right after hello path end
                # Hello path ends near x=727 (last point)
                suffix_x = ox + 727 * scale + 12 * scale
                suffix_y = oy + 192 * scale  # baseline align with hello

                # Reveal suffix via clip
                cr.save()
                clip_w = suffix_w * name_progress + 4
                cr.rectangle(suffix_x - 2, suffix_y - font_size,
                             clip_w, font_size * 1.6)
                cr.clip()


                cr.set_source_rgba(1, 1, 1, alpha)
                cr.move_to(suffix_x, suffix_y)
                cr.show_text(suffix_text)
                cr.restore()

                # Subtle glow under suffix
                cr.save()
                cr.rectangle(suffix_x - 2, suffix_y - font_size,
                             clip_w, font_size * 1.6)
                cr.clip()
                cr.set_source_rgba(1, 1, 1, alpha * 0.20)
                cr.set_line_width(3.5 * scale)
                cr.move_to(suffix_x, suffix_y)
                cr.text_path(suffix_text)
                cr.stroke()
                cr.restore()

    # ══════════════════════════════════════════════════════════════════════
    #  DOTS ENGINE — 4 cyan dots, single motion system
    # ══════════════════════════════════════════════════════════════════════

    def _draw_premium_dots(self, cr, w, h):
        """CIPHER Alpina HUD — BMW M-Sport futuristic precision instrument."""
        import math
        cx = w * 0.5
        cy = h * 0.5 + 10

        target = max(0.0, min(1.0, self._audio_rms))
        self._rms_smooth += (target - self._rms_smooth) * 0.22
        rms = self._rms_smooth
        phase = self._phase

        # ════════════════════════════════════════════════════
        # ALPINA COLOR PALETTE (BMW M / Alpina precision blue)
        # ════════════════════════════════════════════════════
        # Deep navy → Alpina blue → cyan → chrome white
        ALPINA_DEEP    = (0.02, 0.05, 0.12)    # carbon black-blue
        ALPINA_NAVY    = (0.05, 0.12, 0.28)    # deep navy
        ALPINA_BLUE    = (0.10, 0.35, 0.75)    # signature Alpina blue
        ALPINA_CYAN    = (0.30, 0.70, 1.0)     # M-sport cyan
        ALPINA_CHROME  = (0.85, 0.92, 1.0)     # chrome silver
        ALPINA_RED     = (0.95, 0.15, 0.20)    # BMW M red accent

        base_r = 70

        # ════════════════════════════════════════════════════
        # LAYER 1: Outer atmospheric haze
        # ════════════════════════════════════════════════════
        haze = cairo.RadialGradient(cx, cy, base_r * 1.2, cx, cy, base_r * 2.2)
        haze.add_color_stop_rgba(0.0, *ALPINA_BLUE, 0.0)
        haze.add_color_stop_rgba(0.3, *ALPINA_BLUE, 0.18 + rms * 0.15)
        haze.add_color_stop_rgba(0.7, *ALPINA_CYAN, 0.08)
        haze.add_color_stop_rgba(1.0, *ALPINA_NAVY, 0.0)
        cr.set_source(haze)
        cr.arc(cx, cy, base_r * 2.2, 0, 2 * math.pi)
        cr.fill()

        # ════════════════════════════════════════════════════
        # LAYER 2: Outer ring — chrome HUD frame (tick marks)
        # ════════════════════════════════════════════════════
        outer_ring_r = base_r * 1.45

        # Chrome ring base
        cr.set_source_rgba(*ALPINA_CHROME, 0.15)
        cr.set_line_width(0.8)
        cr.arc(cx, cy, outer_ring_r, 0, 2 * math.pi)
        cr.stroke()

        # Tick marks around ring (BMW gauge style)
        num_ticks = 60
        for i in range(num_ticks):
            angle = (i / num_ticks) * 2 * math.pi - math.pi / 2
            is_major = (i % 5 == 0)
            tick_len = 6 if is_major else 3
            tick_w = 1.2 if is_major else 0.6

            x1 = cx + math.cos(angle) * outer_ring_r
            y1 = cy + math.sin(angle) * outer_ring_r
            x2 = cx + math.cos(angle) * (outer_ring_r + tick_len)
            y2 = cy + math.sin(angle) * (outer_ring_r + tick_len)

            alpha = 0.6 if is_major else 0.25
            cr.set_source_rgba(*ALPINA_CHROME, alpha)
            cr.set_line_width(tick_w)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # ════════════════════════════════════════════════════
        # LAYER 3: Active progress arc (sweeps with voice)
        # ════════════════════════════════════════════════════
        sweep_start = -math.pi / 2 + phase * 0.6
        sweep_len = math.pi * 0.4 + rms * math.pi * 0.6

        # Arc with gradient
        for offset in [0, 0.5, 1.0]:
            cr.set_source_rgba(*ALPINA_CYAN, 0.7 - offset * 0.3)
            cr.set_line_width(2.5 + (1 - offset) * 1.5)
            cr.arc(cx, cy, outer_ring_r - 2, sweep_start, sweep_start + sweep_len)
            cr.stroke()

        # Bright sweep tip
        tip_x = cx + math.cos(sweep_start + sweep_len) * (outer_ring_r - 2)
        tip_y = cy + math.sin(sweep_start + sweep_len) * (outer_ring_r - 2)
        tip_glow = cairo.RadialGradient(tip_x, tip_y, 0, tip_x, tip_y, 12)
        tip_glow.add_color_stop_rgba(0.0, 1, 1, 1, 1.0)
        tip_glow.add_color_stop_rgba(0.5, *ALPINA_CYAN, 0.6)
        tip_glow.add_color_stop_rgba(1.0, *ALPINA_CYAN, 0.0)
        cr.set_source(tip_glow)
        cr.arc(tip_x, tip_y, 12, 0, 2 * math.pi)
        cr.fill()

        # ════════════════════════════════════════════════════
        # LAYER 4: Inner ring — segmented (tech HUD)
        # ════════════════════════════════════════════════════
        inner_ring_r = base_r * 1.15
        num_segments = 36
        for i in range(num_segments):
            seg_angle = (i / num_segments) * 2 * math.pi
            seg_phase = (phase * 1.5 + i * 0.18) % (2 * math.pi)
            seg_active = (math.sin(seg_phase) + 1) / 2
            seg_active = max(0.15, seg_active * (0.5 + rms * 0.8))

            x1 = cx + math.cos(seg_angle) * (inner_ring_r - 1.5)
            y1 = cy + math.sin(seg_angle) * (inner_ring_r - 1.5)
            x2 = cx + math.cos(seg_angle) * (inner_ring_r + 1.5)
            y2 = cy + math.sin(seg_angle) * (inner_ring_r + 1.5)

            cr.set_source_rgba(*ALPINA_CYAN, seg_active * 0.85)
            cr.set_line_width(1.6)
            cr.move_to(x1, y1)
            cr.line_to(x2, y2)
            cr.stroke()

        # ════════════════════════════════════════════════════
        # LAYER 5: Central hexagon (carbon fiber feel)
        # ════════════════════════════════════════════════════
        hex_r = base_r * 0.75
        hex_rot = phase * 0.15

        # Hexagon shadow
        cr.save()
        cr.translate(cx, cy + 2)
        cr.rotate(hex_rot)
        cr.set_source_rgba(0, 0, 0, 0.4)
        cr.move_to(hex_r, 0)
        for i in range(1, 7):
            a = i * math.pi / 3
            cr.line_to(math.cos(a) * hex_r, math.sin(a) * hex_r)
        cr.close_path()
        cr.fill()
        cr.restore()

        # Hexagon body (carbon fiber gradient)
        cr.save()
        cr.translate(cx, cy)
        cr.rotate(hex_rot)

        hex_grad = cairo.LinearGradient(0, -hex_r, 0, hex_r)
        hex_grad.add_color_stop_rgba(0.0, *ALPINA_NAVY, 1.0)
        hex_grad.add_color_stop_rgba(0.5, *ALPINA_DEEP, 1.0)
        hex_grad.add_color_stop_rgba(1.0, 0.0, 0.02, 0.08, 1.0)
        cr.set_source(hex_grad)

        cr.move_to(hex_r, 0)
        for i in range(1, 7):
            a = i * math.pi / 3
            cr.line_to(math.cos(a) * hex_r, math.sin(a) * hex_r)
        cr.close_path()
        cr.fill_preserve()

        # Hexagon chrome edge
        cr.set_source_rgba(*ALPINA_CHROME, 0.6)
        cr.set_line_width(1.5)
        cr.stroke()
        cr.restore()

        # ════════════════════════════════════════════════════
        # LAYER 6: Inner energy core (M-Sport blue glow)
        # ════════════════════════════════════════════════════
        core_r = (28 + rms * 18)

        # Outer glow
        core_glow = cairo.RadialGradient(cx, cy, core_r * 0.5, cx, cy, core_r * 1.6)
        core_glow.add_color_stop_rgba(0.0, *ALPINA_CYAN, 0.0)
        core_glow.add_color_stop_rgba(0.4, *ALPINA_CYAN, 0.5 + rms * 0.3)
        core_glow.add_color_stop_rgba(1.0, *ALPINA_BLUE, 0.0)
        cr.set_source(core_glow)
        cr.arc(cx, cy, core_r * 1.6, 0, 2 * math.pi)
        cr.fill()

        # Core body
        core_grad = cairo.RadialGradient(cx - core_r * 0.2, cy - core_r * 0.25, 0,
                                           cx, cy, core_r)
        core_grad.add_color_stop_rgba(0.0, 1, 1, 1, 1.0)
        core_grad.add_color_stop_rgba(0.2, *ALPINA_CHROME, 1.0)
        core_grad.add_color_stop_rgba(0.5, *ALPINA_CYAN, 1.0)
        core_grad.add_color_stop_rgba(0.85, *ALPINA_BLUE, 1.0)
        core_grad.add_color_stop_rgba(1.0, *ALPINA_NAVY, 1.0)
        cr.set_source(core_grad)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.fill()

        # Core chrome rim
        cr.set_source_rgba(*ALPINA_CHROME, 0.85)
        cr.set_line_width(1.2)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.stroke()

        # ════════════════════════════════════════════════════
        # LAYER 7: M-Sport tricolor accent (top notch)
        # ════════════════════════════════════════════════════
        # BMW M stripes: blue / red on top
        notch_y = cy - outer_ring_r - 4
        notch_w = 18

        # Blue stripe (left)
        cr.set_source_rgba(*ALPINA_BLUE, 0.95)
        cr.rectangle(cx - notch_w, notch_y, notch_w / 3, 4)
        cr.fill()

        # Purple stripe (middle)
        cr.set_source_rgba(0.5, 0.2, 0.7, 0.95)
        cr.rectangle(cx - notch_w + notch_w / 3, notch_y, notch_w / 3, 4)
        cr.fill()

        # Red stripe (right)
        cr.set_source_rgba(*ALPINA_RED, 0.95)
        cr.rectangle(cx, notch_y, notch_w / 3 * 2, 4)
        cr.fill()

        # ════════════════════════════════════════════════════
        # LAYER 8: Top specular highlight (3D depth)
        # ════════════════════════════════════════════════════
        hl = cairo.RadialGradient(cx - core_r * 0.3, cy - core_r * 0.55, 0,
                                    cx - core_r * 0.3, cy - core_r * 0.55, core_r * 0.5)
        hl.add_color_stop_rgba(0.0, 1, 1, 1, 0.75)
        hl.add_color_stop_rgba(0.5, 1, 1, 1, 0.2)
        hl.add_color_stop_rgba(1.0, 1, 1, 1, 0.0)
        cr.set_source(hl)
        cr.arc(cx, cy, core_r, 0, 2 * math.pi)
        cr.fill()


    def _draw_words(self, cr, w, h, below=False):
        words = self._display_text.split()
        if not words:
            return

        now = time.time()
        fs  = self._font_size(self._display_text)
        if below:
            fs = max(18, int(fs * 0.60))

        sp = self._space_w(cr, fs)
        widths_n = [self._word_w(cr, wd, fs, False) for wd in words]
        widths_b = [self._word_w(cr, wd, fs, True)  for wd in words]
        last = len(words) - 1

        total_w = sum(
            widths_b[i] if (i == last and self._state == "listening") else widths_n[i]
            for i in range(len(words))
        ) + sp * max(0, len(words) - 1)

        x = (w - total_w) / 2
        y = (h / 2 + 38 + fs / 3) if below else (h / 2 + fs / 3)

        for i, word in enumerate(words):
            wk = f"{i}_{word}"
            if wk not in self._word_times:
                self._word_times[wk] = now
            age  = now - self._word_times[wk]
            fade = min(1.0, age / 0.15)

            if self._state == "processing":
                r, g, b = FADED
                a, bold = fade * 0.7, False
            elif self._state == "speaking":
                word_delay = i * 0.06
                speak_fade = min(1.0, max(0.0, (age - word_delay) / 0.2))
                r, g, b = PURE_WHITE
                a, bold = speak_fade * 0.92, False
            elif i == last and self._state == "listening":
                r, g, b = PURE_WHITE
                a, bold = fade, True
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                                    cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(fs)
                line_progress = min(1.0, age / 0.25)
                line_w = widths_b[i] * line_progress
                cr.set_source_rgba(*ACCENT, fade * 0.65)
                cr.set_line_width(2.2)
                cr.move_to(x, y + fs * 0.22)
                cr.line_to(x + line_w, y + fs * 0.22)
                cr.stroke()
            else:
                dist = last - i
                dim  = max(0.45, 1.0 - dist * 0.07)
                t    = min(1.0, dist * 0.12)
                r = SOFT_WHITE[0] * (1 - t) + FADED[0] * t
                g = SOFT_WHITE[1] * (1 - t) + FADED[1] * t
                b = SOFT_WHITE[2] * (1 - t) + FADED[2] * t
                a, bold = fade * dim, False

            wt = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, wt)
            cr.set_font_size(fs)

            cr.set_source_rgba(0, 0, 0, a * 0.35)
            cr.move_to(x + 1.0, y + 1.0)
            cr.show_text(word)
            cr.set_source_rgba(r, g, b, a)
            cr.move_to(x, y)
            cr.show_text(word)

            x += (widths_b[i] if bold else widths_n[i]) + sp

    def _font_size(self, t):
        n = len(t)
        if n > 80:  return 22
        if n > 55:  return 28
        if n > 35:  return 34
        return 40

    def _space_w(self, cr, fs):
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
                            cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(fs)
        return cr.text_extents(" ").x_advance * 1.15

    def _word_w(self, cr, word, fs, bold):
        wt = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, wt)
        cr.set_font_size(fs)
        return cr.text_extents(word).x_advance

    # ══════════════════════════════════════════════════════════════════════
    #  ANIMATION TICK
    # ══════════════════════════════════════════════════════════════════════

    def _tick(self):
        now = time.time()
        dt  = now - self._last_t
        self._last_t = now

        try:
            while True:
                self._handle(self._queue.get_nowait())
        except queue.Empty:
            pass

        diff = self._target_op - self._opacity
        if abs(diff) > 0.002:
            self._opacity += diff * min(1.0, dt * FADE_SPEED)
        else:
            self._opacity = self._target_op

        sy_diff = self._target_sy - self._slide_y
        if abs(sy_diff) > 0.3:
            self._slide_y += sy_diff * min(1.0, dt * SLIDE_SPEED)
        else:
            self._slide_y = self._target_sy

        # Border intensity = active when overlay is showing
        target_border = 1.0 if (self._visible and self._state != "idle") else 0.0
        bi_diff = target_border - self._border_intensity
        if abs(bi_diff) > 0.002:
            self._border_intensity += bi_diff * min(1.0, dt * 4.0)
        else:
            self._border_intensity = target_border

        if (self._opacity < 0.005 and self._border_intensity < 0.005
                and self._visible):
            self.hide()
            self._visible = False
            self._text = ""
            self._display_text = ""
            self._word_times.clear()
            self._slide_y = SLIDE_DISTANCE

        self._phase        += dt
        self._border_phase += dt
        self._hello_phase  += dt

        if self._state == "hello" and self._visible:
            self._topmost_tick_counter = (getattr(self, '_topmost_tick_counter', 0) + 1) % 6
            if self._topmost_tick_counter == 0:
                self._force_topmost()

        if self._visible or self._border_intensity > 0.005:
            self._da.queue_draw()

        return True


    # ══════════════════════════════════════════════════════════════════════
    #  COMMAND HANDLER
    # ══════════════════════════════════════════════════════════════════════

    def _handle(self, cmd):
        a = cmd.get("action")
        # Audio level update from mic
        if a == "audio":
            lvl = cmd.get("level", 0.0)
            try:
                self._audio_rms = max(0.0, min(1.0, float(lvl)))
            except Exception:
                pass
            return

        if a == "show":
            self._state        = cmd.get("state", "listening")
            self._hold_until   = time.time() + (2.0 if self._state == "listening" else 1.0)
            new_text           = cmd.get("text", "")
            self._text         = new_text
            self._display_text = new_text
            self._word_times.clear()
            self._target_op = 1.0
            self._opacity   = max(self._opacity, 0.6)
            self._slide_y   = SLIDE_DISTANCE * 0.3
            self._target_sy = 0.0
            if self._hide_timer:
                GLib.source_remove(self._hide_timer)
                self._hide_timer = None
            if not self._visible:
                self.show_all()
                self._visible = True

        elif a == "update":
            new_text = cmd.get("text", "")
            if new_text != self._text:
                self._text = new_text
                all_words = new_text.split()
                if len(all_words) > MAX_LIVE_WORDS:
                    display_words = all_words[-MAX_LIVE_WORDS:]
                    self._display_text = "… " + " ".join(display_words)
                else:
                    self._display_text = new_text
                new_word_times = {}
                for i, w in enumerate(self._display_text.split()):
                    key = f"{i}_{w}"
                    new_word_times[key] = self._word_times.get(key, time.time())
                self._word_times = new_word_times
                if not self._visible:
                    self._target_op = 1.0
                    self._opacity   = 0.6
                    self.show_all()
                    self._visible = True

        elif a == "final":
            final_text         = cmd.get("text", "")
            self._text         = final_text
            self._display_text = final_text
            self._state        = "processing"
            self._word_times.clear()
            self._target_op = 1.0
            if self._hide_timer:
                GLib.source_remove(self._hide_timer)
            dur = max(4.0, len(final_text) * 0.05)
            self._hold_until = time.time() + max(8.0, dur)
            self._hide_timer = GLib.timeout_add(max(8000, int(dur * 1000)), self._autohide)

        elif a == "speaking":
            text = cmd.get("text", "")
            if len(text) > 120:
                text = text[:120] + "…"
            self._text         = text
            self._display_text = text
            self._state        = "speaking"
            self._word_times.clear()
            self._target_op = 1.0
            if not self._visible:
                self._opacity = 0.6
                self._slide_y = SLIDE_DISTANCE * 0.3
                self._target_sy = 0.0
                self.show_all()
                self._visible = True
            dur = max(3.0, len(text) * 0.05)
            if self._hide_timer:
                GLib.source_remove(self._hide_timer)
            self._hide_timer = GLib.timeout_add(max(8000, int(dur * 1000)), self._autohide)

        elif a == "hello":
            text = cmd.get("text", "hello")
            duration = float(cmd.get("duration", 4.0))
            self._text         = text
            self._display_text = text
            self._state        = "hello"
            self._hello_phase  = 0.0
            self._target_op    = 1.0
            self._opacity      = 1.0
            self._slide_y      = 0.0
            self._target_sy    = 0.0

            if not self._visible:
                self.show_all()
                self._visible = True
            if self._hide_timer:
                GLib.source_remove(self._hide_timer)
            self._hold_until = time.time() + max(5.0, duration)
            self._hide_timer = GLib.timeout_add(max(5000, int(duration * 1000)), self._autohide)

        elif a == "hide":
            if time.time() < self._hold_until:
                return
            self._target_op = 0.0
            self._target_sy = SLIDE_DISTANCE * 0.5
            self._state     = "idle"

    def _autohide(self):
        self._target_op  = 0.0
        self._target_sy  = SLIDE_DISTANCE * 0.5
        self._state      = "idle"
        self._hide_timer = None
        return False

    def push(self, cmd):
        self._queue.put(cmd)


def start_socket_server(overlay):
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o777)
    server.listen(5)
    server.settimeout(1.0)

    def _serve():
        while True:
            try:
                conn, _ = server.accept()
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                conn.close()
                if data:
                    for line in data.decode().splitlines():
                        line = line.strip()
                        if line:
                            cmd = json.loads(line)
                            GLib.idle_add(overlay.push, cmd)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Socket error: {e}", file=sys.stderr)

    t = threading.Thread(target=_serve, daemon=True)
    t.start()
    print(f"Overlay v3 (CIPHER theme border) ready: {SOCKET_PATH}", flush=True)


if __name__ == "__main__":
    overlay = JarvisOverlay()
    start_socket_server(overlay)
    Gtk.main()
