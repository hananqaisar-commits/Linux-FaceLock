<div align="center">

<img src="https://img.shields.io/badge/NovaUnlock-v4.2-1a1a2e?style=for-the-badge&logo=linux&logoColor=white" alt="NovaUnlock"/>

# NovaUnlock

**Premium Face Authentication for Linux**

*iOS Face ID-style biometric unlock — local, private, and instant*

[![Version](https://img.shields.io/badge/version-4.2-4a90d9?style=flat-square&logo=github)]()
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20X11-27ae60?style=flat-square&logo=linux&logoColor=white)]()
[![License](https://img.shields.io/badge/license-Proprietary-e74c3c?style=flat-square)]()
[![Status](https://img.shields.io/badge/status-Production%20Ready-2ecc71?style=flat-square)]()
[![Privacy](https://img.shields.io/badge/privacy-100%25%20Local-8e44ad?style=flat-square&logo=shield&logoColor=white)]()

[Download](#-quick-install) · [Features](#-features) · [Install](#-quick-install) · [Usage](#-usage) · [Troubleshoot](#-troubleshooting)

</div>

---

## Overview

**NovaUnlock** brings iOS Face ID-style biometric authentication to Linux. Look at your camera — you're in. No passwords, no delays, no cloud.

> **100% local processing.** Your face data never leaves your machine. No telemetry, no network calls, no exceptions.

---

## Features

### Core Authentication
| Feature | Description |
|---|---|
| **Instant Face Unlock** | Look at the camera to unlock your lock screen |
| **Auto Login at Boot** | Face recognition triggers at the greeter screen |
| **Multi-User Support** | One face profile per Linux user account |
| **Password Fallback** | Automatic switch to password after timeout or failed attempts |
| **Anti-Spoofing** | Blink detection + texture analysis blocks photo attacks |

### Enrollment Experience
- **iOS Face ID Wizard** — Familiar circular scanning UI with dark blue theme
- **16-Position Auto-Capture** — Move your head; dashes fill green as each angle is captured
- **Cinematic Animations** — Particle burst on startup, smooth screen transitions
- **Professional Audio Cues** — Synthesized sound feedback throughout enrollment
- **Built-in Settings Panel** — Manage faces and adjust sensitivity from the wizard

### Privacy & Security
- **Local-Only Storage** — Face data lives in `~/NovaUnlock/data/faces/`
- **No Raw Images** — Only mathematical encodings (`.npy` files) are stored
- **PAM Integration** — Secure 15-second expiring cache, single-use per unlock
- **Liveness Detection** — Blink-based real-person verification
- **Texture Analysis** — Detects and blocks screens, prints, and photo spoofs

---

## Quick Install

### 1 — Download

```bash
wget https://github.com/hananqaisar-commits/NovaUnlock/raw/main/releases/nova_unlock_installer_v4.2
```

Or get the latest binary from the **[Releases](https://github.com/hananqaisar-commits/NovaUnlock/releases)** page.

### 2 — Install

```bash
chmod +x nova_unlock_installer_v4.2
sudo ./nova_unlock_installer_v4.2
```

> Installation takes **5–10 minutes** (includes dlib compilation from source).

The installer automatically:
- Detects your Linux distribution and package manager
- Installs all system dependencies
- Sets up a Python virtual environment with face recognition models
- Configures PAM authentication
- Integrates with your lock screen and display manager (LightDM)
- Creates an uninstaller for clean removal

### 3 — Enroll Your Face

```bash
~/NovaUnlock/.venv/bin/python3 ~/NovaUnlock/scripts/enroll_gui.py
```

**Enrollment flow:**

```
1. Welcome Screen    →  Select your user account
2. Position Face     →  Camera detects your face
3. Move Head         →  16 positions captured automatically
4. Setup Complete    →  Green checkmark confirms success
```

---

## Usage

| Action | How to Trigger |
|---|---|
| Lock screen | `xflock4` or `Super + L` |
| Face unlock | Look at the camera when locked |
| Boot login | Automatic face recognition at the greeter |
| Open settings | Enrollment wizard → Settings button (top-right) |
| Re-enroll face | Run enrollment wizard again |
| Uninstall | `sudo bash ~/NovaUnlock/uninstall.sh` |

---

## Supported Systems

### Linux Distributions

| Distribution | Package Manager | Status |
|---|---|---|
| Kali Linux | `apt` | ✅ Fully Supported *(Primary)* |
| Ubuntu 22.04+ | `apt` | ✅ Fully Supported |
| Debian 12+ | `apt` | ✅ Fully Supported |
| Fedora 38+ | `dnf` | ⚠️ Experimental |
| Arch / Manjaro | `pacman` | ⚠️ Experimental |
| openSUSE | `zypper` | ⚠️ Experimental |

### Desktop Environments

| Desktop | Lock Screen | Greeter Login | Notes |
|---|---|---|---|
| XFCE | ✅ Full | ✅ Full | Primary target — fully tested |
| GNOME | ⚠️ Partial | ❌ | Manual shortcut binding required |
| KDE Plasma | ⚠️ Partial | ❌ | Manual shortcut binding required |
| MATE | ⚠️ Partial | ❌ | PAM auto-configured |
| Cinnamon | ⚠️ Partial | ❌ | PAM auto-configured |

### Display Managers

| Display Manager | Status |
|---|---|
| LightDM | ✅ Full support (lock screen + greeter) |
| GDM | ⚠️ Lock screen only |
| SDDM | ⚠️ Lock screen only |

### System Requirements

| Component | Minimum |
|---|---|
| OS | Linux (X11 session) |
| Python | 3.10+ *(auto-installed)* |
| RAM | 2 GB |
| Disk Space | ~500 MB |
| Camera | Any USB or built-in webcam |
| Privileges | `sudo` access for installation |

---

## Configuration

Edit `~/NovaUnlock/config/nova.conf` to customize behavior:

```ini
[recognition]
threshold    = 0.50    # Lower = stricter (range: 0.35–0.65)
timeout      = 10      # Seconds before falling back to password
max_attempts = 3       # Failed attempts before password fallback
angles       = 16      # Number of enrollment positions

[ui]
theme               = dark
show_camera_preview = true
animation           = true

[audio]
success_sound = true
fail_sound    = true

[security]
liveness_check  = true   # Blink detection
anti_spoof      = true   # Texture analysis
min_blinks      = 1
liveness_window = 3.0
```

> Changes take effect on the next lock/unlock cycle.

---

## Troubleshooting

### Camera Not Detected

```bash
# List available cameras
ls /dev/video*

# Test camera devices
v4l2-ctl --list-devices

# Verify camera works with OpenCV
~/NovaUnlock/.venv/bin/python3 - <<'EOF'
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    print(f"Camera {i}: {'OK' if cap.isOpened() else 'Not available'}")
    cap.release()
EOF
```

### Face Not Recognized

- Ensure good lighting — avoid strong backlighting from windows
- Re-enroll if you started or stopped wearing glasses
- Lower the recognition threshold in **Settings → Recognition Sensitivity**
- Try re-enrollment with your face at a different starting angle

### Lock Screen Hangs

```bash
# Check authentication logs
tail -50 ~/NovaUnlock/logs/face_auth.log

# Check watcher status
tail -50 ~/NovaUnlock/logs/watcher.log

# Check system journal
sudo journalctl -u lightdm -n 50 --no-pager
```

### Installation Fails

```bash
# View the installation log
cat ~/NovaUnlock/logs/install.log

# Install missing build tools, then retry
sudo apt update && sudo apt install -y cmake build-essential
sudo ./nova_unlock_installer_v4.2
```

---

## Privacy & Security

NovaUnlock is designed from the ground up for offline, private biometric authentication:

- **No network activity** — Verify yourself with `sudo tcpdump -i any host 0.0.0.0`
- **No raw face images** — Only 128-dimensional mathematical encodings are written to disk
- **No cloud dependency** — Works fully air-gapped
- **Tamper-visible storage** — Inspect `~/NovaUnlock/data/faces/` yourself; only `.npy` files
- **Auto-expiring PAM cache** — Authentication tokens expire after 15 seconds and are single-use

---

## Uninstall

```bash
sudo bash ~/NovaUnlock/uninstall.sh
```

This cleanly removes:
- All NovaUnlock files and directories
- PAM configuration entries
- Display manager hooks (LightDM)
- Sudoers entries
- Autostart watcher service
- Lock screen wrapper scripts

---

## Roadmap

### v4.2 *(Coming Soon)*
- [ ] Screenshots and demo video
- [ ] Wayland support (GNOME 40+, Fedora)
- [ ] GDM and SDDM greeter integration
- [ ] Multiple camera selection in UI
- [ ] Desktop notifications on unlock

### v5.0 *(Future)*
- [ ] Optional encrypted cloud sync
- [ ] Gesture-based commands
- [ ] Web-based settings panel
- [ ] Authentication analytics dashboard

---

## Support

| Resource | Link |
|---|---|
| Report a Bug | [GitHub Issues](https://github.com/hananqaisar-commits/NovaUnlock/issues) |
| Latest Release | [Releases Page](https://github.com/hananqaisar-commits/NovaUnlock/releases) |
| Community | [GitHub Discussions](https://github.com/hananqaisar-commits/NovaUnlock/discussions) |

---

## License

NovaUnlock is **proprietary software** provided for personal, non-commercial use.

Reverse engineering, decompilation, modification, and commercial redistribution are strictly prohibited. Source code is not publicly available. See [LICENSE](./LICENSE) for full terms.

*Copyright © 2026 NovaUnlock. All rights reserved.*

---

<div align="center">

If you find NovaUnlock useful, consider starring the repo ⭐

**NovaUnlock v4.2** · Premium Linux Biometric Authentication · Built for the Linux community

</div>
