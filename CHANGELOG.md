# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
