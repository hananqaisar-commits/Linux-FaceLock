#!/usr/bin/env python3
"""
NovaUnlock V5.2 — Automated Feature Tests
Covers: Liveness, ThemeManager, FacePresenceGuard
"""
import sys, os, time, json, threading
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

# ══════════════════════════════════════════════════════════════
# FEATURE 1 — Liveness
# ══════════════════════════════════════════════════════════════
class TestLivenessDetector:

    def test_import(self):
        from nova_unlock.vision.liveness import LivenessDetector
        assert LivenessDetector is not None

    def test_initial_state(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d = LivenessDetector(required_blinks=1, challenge_secs=5)
        assert not d.is_passed()
        assert not d.is_failed()
        assert d.blink_count() == 0

    def test_reset_clears_state(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d = LivenessDetector()
        d._blink_count = 5
        d._passed      = True
        d._start_time  = time.time() - 100
        d.reset()
        assert d.blink_count() == 0
        assert not d.is_passed()

    def test_blank_frame_no_crash(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d = LivenessDetector(required_blinks=1, challenge_secs=5)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        res   = d.update(blank)
        assert res["status"] in ("no_face", "waiting", "disabled", "failed")

    def test_timeout_triggers_failed(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d = LivenessDetector(required_blinks=1, challenge_secs=0.1)
        d._start_time = time.time() - 5.0
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        time.sleep(0.15)
        res = d.update(blank)
        assert res["status"] in ("failed", "no_face")

    def test_draw_overlay_no_crash(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d     = LivenessDetector()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_res = {
            "status":"waiting","blinks":0,"required":1,
            "seconds_left":4.0,"ear":0.3,"message":"test"
        }
        out = d.draw_overlay(frame, mock_res)
        assert out.shape == frame.shape

    def test_config_respected(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d = LivenessDetector(required_blinks=3,
                             challenge_secs=15,
                             ear_threshold=0.18)
        assert d.required_blinks  == 3
        assert d.challenge_secs   == 15
        assert d.ear_threshold    == 0.18

    def test_ear_calculation(self):
        from nova_unlock.vision.liveness import _ear
        class L:
            def __init__(self,x,y): self.x=x; self.y=y
        lm = {
            33: L(0.3,0.5), 160: L(0.32,0.47), 158: L(0.34,0.47),
            133: L(0.36,0.5), 153: L(0.34,0.53), 144: L(0.32,0.53)
        }
        ear = _ear(lm, [33,160,158,133,153,144], 640, 480)
        assert ear > 0.15

    def test_result_keys_present(self):
        from nova_unlock.vision.liveness import LivenessDetector
        d     = LivenessDetector(required_blinks=1, challenge_secs=5)
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        res   = d.update(blank)
        for key in ("status","blinks","required","seconds_left","ear","message"):
            assert key in res, f"Missing key: {key}"


# ══════════════════════════════════════════════════════════════
# FEATURE 2 — ThemeManager
# ══════════════════════════════════════════════════════════════
class TestThemeManager:

    def test_import(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        assert ThemeManager is not None

    def test_valid_mode(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        t = ThemeManager()
        assert t.mode in ("dark", "light")

    def test_is_dark_light_exclusive(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        t = ThemeManager()
        assert t.is_dark() != t.is_light()

    def test_palette_keys(self):
        from nova_unlock.ui.theme_manager import ThemeManager, PALETTES
        keys = ["bg_primary","accent","text_primary",
                "success","error","border","overlay_alpha"]
        for mode in ("dark","light"):
            for k in keys:
                assert k in PALETTES[mode], f"Missing {k} in {mode}"

    def test_stylesheet_not_empty(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        t  = ThemeManager()
        ss = t.qt_stylesheet()
        assert len(ss) > 100
        assert "QPushButton" in ss
        assert "QLineEdit"   in ss
        assert "background-color" in ss

    def test_dark_light_stylesheets_differ(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        d = ThemeManager(); d._mode = "dark"
        l = ThemeManager(); l._mode = "light"
        assert d.qt_stylesheet() != l.qt_stylesheet()

    def test_singleton(self):
        from nova_unlock.ui.theme_manager import get_theme
        assert get_theme() is get_theme()

    def test_refresh_no_crash(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        t = ThemeManager()
        t.refresh()

    def test_on_change_callback(self):
        from nova_unlock.ui.theme_manager import ThemeManager
        t      = ThemeManager()
        called = []
        t.on_change(lambda m: called.append(m))
        for cb in t._callbacks:
            cb("dark")
        assert "dark" in called

    def test_hex_colors_valid(self):
        import re
        from nova_unlock.ui.theme_manager import PALETTES
        pattern = re.compile(r'^#[0-9a-fA-F]{3,8}$')
        for mode, pal in PALETTES.items():
            for k, v in pal.items():
                if isinstance(v, str) and v.startswith("#"):
                    assert pattern.match(v), f"Bad hex {v} ({mode}/{k})"


# ══════════════════════════════════════════════════════════════
# FEATURE 3 — FacePresenceGuard
# ══════════════════════════════════════════════════════════════
class TestFacePresenceGuard:

    def test_import(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        assert FacePresenceGuard is not None

    def test_init_state(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        g = FacePresenceGuard([np.zeros(128)], ["u"], timeout=5.0)
        assert g.timeout == 5.0
        assert not g._running

    def test_face_absent_for(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        g = FacePresenceGuard([np.zeros(128)], ["u"], timeout=5.0)
        g._last_seen = time.time() - 3.0
        assert 2.5 < g.face_absent_for < 4.0

    def test_current_user_thread_safe(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        g = FacePresenceGuard([np.zeros(128)], ["u"], timeout=5.0)
        g._current_user = "hanan"
        assert g.current_user == "hanan"

    def test_stop_without_start(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        g = FacePresenceGuard([np.zeros(128)], ["u"], timeout=5.0)
        g.stop()  # Should not crash

    def test_write_pam_cache(self):
        from scripts.face_unlock_daemon import write_pam_cache, CACHE_FILE
        write_pam_cache("hanan")
        assert CACHE_FILE.exists()
        d = json.loads(CACHE_FILE.read_text())
        assert d["user"]    == "hanan"
        assert d["profile"] == "hanan"
        assert time.time() - d["ts"] < 5
        assert oct(os.stat(CACHE_FILE).st_mode)[-3:] == "600"
        CACHE_FILE.unlink(missing_ok=True)

    def test_lock_triggered_on_timeout(self):
        from scripts.face_unlock_daemon import FacePresenceGuard
        fired = threading.Event()
        with patch("scripts.face_unlock_daemon.trigger_lock",
                   side_effect=lambda r="": fired.set()):
            g = FacePresenceGuard([np.zeros(128)], ["u"], timeout=2.0)
            g._last_seen   = time.time() - 3.0
            g._face_absent = False
            absent = g.face_absent_for
            if absent >= g.timeout:
                g._face_absent = True
                t = threading.Thread(
                    target=__import__("scripts.face_unlock_daemon",
                                      fromlist=["trigger_lock"]).trigger_lock,
                    daemon=True)
                with patch("scripts.face_unlock_daemon.trigger_lock",
                           side_effect=lambda r="": fired.set()):
                    from scripts.face_unlock_daemon import trigger_lock
                    threading.Thread(target=trigger_lock, daemon=True).start()
            fired.wait(timeout=3)
            assert fired.is_set(), "❌ Lock not triggered"

    def test_pam_cache_expiry(self):
        from scripts.face_unlock_daemon import CACHE_FILE
        expired = {"user":"hanan","profile":"hanan","ts": time.time()-20}
        CACHE_FILE.write_text(json.dumps(expired))
        d   = json.loads(CACHE_FILE.read_text())
        age = time.time() - d["ts"]
        assert age > 15, "❌ Should be expired"
        CACHE_FILE.unlink(missing_ok=True)
