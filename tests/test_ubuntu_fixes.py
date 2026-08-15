#!/usr/bin/env python3
"""Automated tests for NovaUnlock install + UI visibility logic."""

import ast
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestPamCacheContract(unittest.TestCase):
    def test_cache_constants_match_install_sh(self):
        install = (ROOT / "install.sh").read_text()
        embed = (ROOT / "nova_unlock/ui/face_id_embed.py").read_text()
        self.assertIn("/tmp/nova_unlock_pam_cache.json", install)
        self.assertIn('CACHE_FILE = "/tmp/nova_unlock_pam_cache.json"', embed)

    def test_write_pam_cache_produces_valid_json(self):
        from nova_unlock.ui import face_id_embed as mod
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "pam_cache.json"
            with patch.object(mod, "CACHE_FILE", str(cache)):
                with patch.object(mod, "log", lambda _m: None):
                    mod.write_pam_cache("testuser")
            data = json.loads(cache.read_text())
            self.assertEqual(data["user"], "testuser")
            self.assertIsInstance(data["ts"], float)


class TestGreeterResultContract(unittest.TestCase):
    def test_greeter_and_install_use_same_result_path(self):
        greeter = (ROOT / "scripts/face_login_greeter.py").read_text()
        install = (ROOT / "install.sh").read_text()
        expected = "/tmp/nova_unlock_greeter_result"
        self.assertIn(f'RESULT_FILE = "{expected}"', greeter)
        self.assertIn(expected, install)


class TestInstallShWiring(unittest.TestCase):
    def test_lock_launches_ui_after_screen_lock(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("launch_face_ui", install)
        self.assertIn("sleep 1.2", install)
        self.assertNotIn("exec xfce4-screensaver-command -l", install)

    def test_watcher_runtime_dbus_and_nova_root(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("detect_dbus_iface", install)
        self.assertIn('NOVA_ROOT="$NOVA_DIR"', install)
        self.assertIn("wmctrl", install)

    def test_post_install_verification(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("Verifying installation", install)
        self.assertIn("Python deps verified", install)


class TestUiVisibility(unittest.TestCase):
    def test_ensure_on_top_exists(self):
        source = (ROOT / "nova_unlock/ui/universal_embed.py").read_text()
        self.assertIn("def ensure_on_top", source)
        self.assertIn("wmctrl", source)
        self.assertIn("windowraise", source)

    def test_face_id_embed_uses_ensure_on_top(self):
        source = (ROOT / "nova_unlock/ui/face_id_embed.py").read_text()
        self.assertIn("ensure_on_top", source)
        self.assertIn("lambda _w=w:", source)

    def test_raise_embedded_falls_back_to_ensure_on_top(self):
        source = (ROOT / "nova_unlock/ui/universal_embed.py").read_text()
        idx = source.index("def raise_embedded")
        body = source[idx:idx + 800]
        self.assertIn("ensure_on_top", body)

    def test_unlock_tries_xdotool_return_first(self):
        source = (ROOT / "nova_unlock/ui/face_id_embed.py").read_text()
        xdotool_idx = source.index('["xdotool", "key", "Return"]')
        loginctl_idx = source.index('["loginctl", "unlock-session"]')
        self.assertLess(xdotool_idx, loginctl_idx)


class TestNovaRootResolution(unittest.TestCase):
    def test_find_nova_root_checks_home_novaunlock(self):
        source = (ROOT / "nova_unlock/core/system_detect.py").read_text()
        self.assertIn('Path(f"/home/{user}/NovaUnlock")', source)

    def test_daemon_uses_find_nova_root(self):
        source = (ROOT / "scripts/face_unlock_daemon.py").read_text()
        self.assertIn("find_nova_root", source)
        self.assertNotIn('HOME / "NovaUnlock"', source)

    def test_daemon_resolves_pyc_entrypoint(self):
        source = (ROOT / "scripts/face_unlock_daemon.py").read_text()
        self.assertIn("_resolve_entry", source)
        self.assertIn('.pyc', source)


class TestBinaryInstaller(unittest.TestCase):
    def test_installer_uses_real_group(self):
        source = (ROOT / "installer_main.py").read_text()
        self.assertIn('id", "-gn"', source)
        self.assertIn("NOVA_ROOT", source)


class TestPamAndWaylandSafety(unittest.TestCase):
    def test_wayland_fix_does_not_mention_pam_changes(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("does NOT touch PAM", install)
        self.assertIn("GDM_WAYLAND_ON", install)

    def test_gdm_pam_uses_ignore_on_failure(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("[success=ok default=ignore]", install)
        self.assertIn("configure_pam_gdm_safe", install)

    def test_gdm_pam_preserves_common_auth(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("@include common-auth", install)
        self.assertIn("password login preserved", install)

    def test_dangerous_pam_targets_removed(self):
        install = (ROOT / "install.sh").read_text()
        self.assertNotIn('configure_pam "/etc/pam.d/lightdm"', install)
        self.assertNotIn("/etc/pam.d/lightdm \\", install)
        self.assertNotIn("/etc/pam.d/sddm \\", install.split("configure_pam_lockscreen")[0])

    def test_gdm_greeter_does_not_auto_submit_password(self):
        install = (ROOT / "install.sh").read_text()
        hook = install.split("GDMHOOK")[1].split("GDMHOOK")[0]
        self.assertNotIn("xdotool key Return", hook)
        self.assertIn("Do NOT auto-submit password", install)

    def test_pam_script_fast_exit_without_cache(self):
        install = (ROOT / "install.sh").read_text()
        self.assertIn("[ ! -f \"\\$CACHE\" ] && exit 1", install)


class TestFaceLockSystemService(unittest.TestCase):
    def test_pam_helper_supports_native_package_root_and_service_switch(self):
        source = (ROOT / "nova_unlock/pam/pam_script_auth").read_text()
        self.assertIn('NOVA_DIR="/opt/novaunlock"', source)
        self.assertIn('/etc/novaunlock/facelock.enabled', source)
        self.assertIn('timeout 25s', source)

    def test_system_service_controls_greeter_before_display_manager(self):
        unit = (ROOT / "systemd/novaunlock.service").read_text()
        self.assertIn("Before=display-manager.service", unit)
        self.assertIn("RemainAfterExit=yes", unit)
        self.assertIn("nova_facelock_service.sh start", unit)
        self.assertIn("nova_facelock_service.sh stop", unit)
        self.assertIn("Alias=nova-facelock.service", unit)

    def test_native_builds_ship_the_system_service(self):
        for name in ("build_deb.sh", "build_rpm.sh", "build_arch.sh"):
            source = (ROOT / "scripts" / name).read_text()
            self.assertTrue("novaunlock.service" in source or "nova-facelock.service" in source, name)

    def test_hello_overlay_has_signal_protection_and_topmost_loop(self):
        overlay = (ROOT / "nova_unlock/ui/hello_overlay.py").read_text()
        welcome = (ROOT / "nova_unlock/ui/welcome_screen.py").read_text()
        self.assertIn("SIG_IGN", overlay)
        self.assertIn("SIG_IGN", welcome)
        self.assertIn("_force_topmost", overlay)
        self.assertIn("_wait_for_desktop_ready", welcome)


if __name__ == "__main__":
    unittest.main(verbosity=2)

