# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v3.2] - 2026-08-15

### Added
- **Fully Working Release v3.2** with unified systemd service (`novaunlock.service`) and `systemctl enable/disable novaunlock` support.
- **KDE Desktop Loading Immunity**: Greeting overlay ("hello + username") features signal protection (`SIG_IGN`), KDE splash screen detection (`_wait_for_desktop_ready`), unmap immunity, and continuous topmost re-raising loop (`_force_topmost`).
- **Voice Speech & Watchdog**: Integrated non-blocking speech synthesis ("Hello <user>, welcome back") with watchdog playback protection.
- **Legacy Files Directory (`old_versions/`)**: Separated legacy single-file scripts into `old_versions/` to streamline developer workspace and eliminate setup confusion.
- **Cross-Distro & Multi-Platform Support**: Preserved build pipelines for 4 major targets: Debian/Ubuntu (`.deb`), Fedora/RPM (`.rpm`), Arch (`.pkg.tar.zst`), and Windows 10/11 (`.exe` / `.zip`).

## [2.21] - 2026-08-11

### Added
- Open-sourced under the **MIT License**
- Dynamic Island UI with 60 FPS spring-physics animation engine
- Authentic iOS-style 3D wireframe sphere verification animation
- PAM stack integration for `sudo`, `su`, `polkit`, `gdm-password`, `lightdm`, `xfce4-screensaver`
- Native `.deb`, `.rpm`, and `.pkg.tar.zst` packaging scripts
- Face enrollment wizard with real-time camera preview and 32-segment arc progress
- Spatial audio feedback (pluck synthesis, whoosh, bell tones)
- LightDM greeter-level face unlock (auto-login on match)
- GDM PostLogin hook (experimental)
- Laptop lid-close / suspend-resume watcher (D-Bus `PrepareForSleep`)
- Offline wheel bundling for `dlib`, `face_recognition` (no network needed at install)
- Windows Credential Provider bridge for dual-boot setups

### Security
- All biometric embeddings stored locally — zero cloud transmission
- Multi-frame liveness detection (blink + motion)
- PAM cache TTL of 15 seconds with auto-purge
- Automatic password fallback on timeout

## [Unreleased]

### Planned
- Wayland-native compositor integration
- IR depth camera support for enhanced liveness
- Multi-user concurrent enrollment
- Fingerprint sensor fusion
