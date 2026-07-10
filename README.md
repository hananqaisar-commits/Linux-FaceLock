<div align="center">

# 🔐 NovaUnlock

### Next-Generation Face Authentication System for Linux & Windows

Biometric Face Unlock • Dynamic Island UI • PAM Integration • Privacy-First • Zero Cloud Dependency

---

![Version](https://img.shields.io/badge/version-1.32-4a90d9?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-supported-27ae60?style=for-the-badge&logo=linux&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Desktop](https://img.shields.io/badge/desktop-GNOME%20%7C%20XFCE%20%7C%20KDE%20%7C%20Cinnamon-e67e22?style=for-the-badge)
![Auth](https://img.shields.io/badge/auth-PAM%20%7C%20Credential%20Provider-orange?style=for-the-badge)
![Privacy](https://img.shields.io/badge/privacy-100%25%20local-8e44ad?style=for-the-badge)
![License](https://img.shields.io/badge/license-commercial-lightgrey?style=for-the-badge)

</div>

---

## 📸 Interface Preview

<div align="center">

### 🔒 Face Scanning — Dynamic Island UI

<img src="assets/facelock_scanning.png" width="60%" alt="NovaUnlock — FaceLock Scanning State" />

> *iOS-inspired Dynamic Island with lock icon and Face ID scanner. The pill expands with a spring animation and begins biometric scanning.*

---

### 🟢 Authentication Success — 3D Wireframe Sphere

<img src="assets/facelock_success.png" width="60%" alt="NovaUnlock — Face Match Success" />

> *On successful face match: lock icon animates to unlocked (green glow), and an authentic iOS-style 3D wireframe sphere rotates with depth-sorted perspective rendering.*

---

### 👋 Welcome Greeting — Instant Hello Overlay

<img src="assets/hello_welcome.png" width="60%" alt="NovaUnlock — Hello Welcome Screen" />

> *After successful unlock, an elegant full-screen greeting overlay appears instantly — "hello, {Username}" — with a subtle gradient accent line.*

</div>

---

## 📌 Project Overview

**NovaUnlock** is a commercial, closed-source biometric face authentication system that replaces traditional password login with real-time facial recognition. It integrates directly with **Linux PAM** and **Windows Credential Provider** for system-level biometric authentication.

Every aspect of the system is designed for **local processing** — no cloud APIs, no telemetry, no external dependencies. Your biometric data never leaves your device.

> 💡 **Trial:** NovaUnlock ships with a **30-day free trial** — full functionality, no prompts. After the trial, face unlock still works, but a one-time paid license is required to remove the upgrade reminder. See [Trial & License](#-trial--license).

### Why NovaUnlock?

| Feature | NovaUnlock | Traditional Login |
|---|---|---|
| Authentication Speed | < 1 second | Manual typing |
| Security Layer | Biometric + Password fallback | Password only |
| Privacy | 100% local processing | Varies |
| User Experience | iOS-quality animations | Standard OS dialogs |
| Multi-Platform | Linux + Windows | OS-specific |

---

## 🎯 Core Features

### 🔓 Biometric Face Authentication
Real-time face recognition via webcam with configurable matching thresholds. Supports multiple face encodings per user for improved accuracy across lighting conditions.

### 🎨 Dynamic Island UI
An iOS-inspired animated interface built with PyQt5 featuring:
- **Spring-physics pill animation** with smooth expand/collapse
- **3D wireframe sphere** with perspective projection and depth-sorted rendering
- **Animated lock icon** that transitions from locked → unlocked with green glow
- **Face ID scanner icon** with natural eye-blink animation
- **Shake rejection effect** with spring-damped horizontal oscillation
- **Sound design** — procedurally generated pluck, bell, and whoosh audio cues

### 👋 Instant Welcome Overlay
After successful authentication, a full-screen greeting overlay displays instantly via Unix socket IPC — pre-warmed during the scan phase for zero-latency display.

### 🧩 PAM Integration (Linux)
Seamless integration with Linux **Pluggable Authentication Modules** for:
- Login screen authentication
- Lock screen unlock
- `sudo` elevation (optional)

### 🪟 Windows Credential Provider
Native Windows 10/11 support via a compiled C++ Credential Provider DLL that interfaces with LSA Secrets for secure password handling.

### 🔴 Anti-Spoof Liveness Detection
- **Adaptive EAR calibration** — learns your eye ratio in 30 frames
- dlib 68-point landmarks with 5-strategy face detection fallback
- MediaPipe Tasks / Legacy / OpenCV Haar cascade chain
- Rejects: printed photos, phone screens, static masks

### 💾 100% Local Processing
- No cloud APIs or external network calls
- No telemetry or tracking
- All face encoding data stored on local filesystem
- User-owned biometric data

### 👥 Multi-User Support
Separate face profiles per Linux/Windows user with independent encoding databases.

### 🔑 Secure Password Fallback
Automatic fallback to password authentication when:
- Face recognition fails after 3 attempts
- Camera is unavailable
- Liveness check fails

---

## 🖥️ Platform Support

### Linux
| Distribution | Package | Status |
|---|---|---|
| Ubuntu 22.04+ | `.deb` | ✅ Supported |
| Debian 12+ | `.deb` | ✅ Supported |
| Kali Linux | `.deb` | ✅ Supported |
| Linux Mint / Pop!_OS | `.deb` | ✅ Supported |
| Fedora / RHEL / openSUSE | `.rpm` | ✅ Supported |
| Arch / Manjaro | `.pkg.tar.zst` | ✅ Supported |
| KDE Plasma | `.deb` / `.rpm` | ⚠️ Experimental |

### Windows
| Version | Status |
|---|---|
| Windows 10 (21H2+) | ✅ Supported |
| Windows 11 | ✅ Supported |

---

## 🚀 Installation

Pick the package that matches your platform. Every asset is on the
[GitHub Releases · v1.32](https://github.com/hananqaisar-commits/NovaUnlock/releases/tag/v1.32) page.

| Platform | File | Install with |
|---|---|---|
| Ubuntu / Debian / Kali / Mint / Pop!_OS | `NovaUnlock-v1.32-Debian.deb` | `apt` |
| Fedora / RHEL / openSUSE | `NovaUnlock-v1.32-Fedora.rpm` | `dnf` |
| Arch / Manjaro | `NovaUnlock-v1.32-Arch.pkg.tar.zst` | `pacman` |
| Any Linux (universal) | `NovaUnlock-v1.32-linux.bin` | self-extracting installer |
| Windows 10 / 11 | `NovaUnlock-v1.32-Windows.zip` | `install.bat` |

### 🐧 Debian / Ubuntu / Kali / Mint / Pop!_OS — `.deb`
```bash
sudo apt update
sudo apt install ./NovaUnlock-v1.32-Debian.deb
```

### 🔴 Fedora / RHEL / openSUSE — `.rpm`
```bash
sudo dnf install ./NovaUnlock-v1.32-Fedora.rpm
```

### 🟠 Arch / Manjaro — `.pkg.tar.zst`
```bash
sudo pacman -U NovaUnlock-v1.32-Arch.pkg.tar.zst
```

### ⚙️ Any Linux — `.bin` (universal)
A self-contained installer — run it with `sudo` and it extracts to `~/NovaUnlock`,
then performs the full system integration automatically.
```bash
chmod +x NovaUnlock-v1.32-linux.bin
sudo ./NovaUnlock-v1.32-linux.bin
```

> 📦 **What gets installed:** the native packages (`.deb` / `.rpm` / `.pkg.tar.zst`) install to
> `/opt/novaunlock`, compile the shipped bytecode for your Python (3.11–3.13), wire **PAM** for
> your desktop (login + lock screen, optional `sudo`), start the 30-day trial, and enable the guard
> service. The universal `.bin` installs to `~/NovaUnlock` with the same integration.

### 🪟 Windows 10 / 11 — `.zip`
1. Download `NovaUnlock-v1.32-Windows.zip` and extract it.
2. Right-click **`install.bat`** → **Run as Administrator**.
3. Follow the on-screen steps (Python, VC++ runtime, dlib, face_recognition, Credential Provider, service).
4. Reboot and enroll your face from the lock screen.

---

### 👤 Enroll your face
Run this once after installing, so NovaUnlock can recognise you:
```bash
# Native packages
python3 /opt/novaunlock/scripts/enroll_gui.py

# Universal .bin install
~/NovaUnlock/.venv/bin/python3 ~/NovaUnlock/nova_unlock/ui/setup_flow.py --mode enroll
```
A GUI wizard opens and captures your face from the webcam at multiple angles.

### 🔓 Try it
Lock your screen, then authenticate with your face:
```bash
xflock4                # XFCE
loginctl lock-session  # GNOME / systemd
```
If face recognition fails 3× (or the camera is unavailable), NovaUnlock falls back to your password.

### 🗑️ Uninstall
```bash
sudo apt remove novaunlock          # Debian / Ubuntu / Kali
sudo dnf remove novaunlock          # Fedora / RHEL
sudo pacman -R novaunlock           # Arch
sudo bash ~/NovaUnlock/uninstall.sh # universal .bin
```

---

## ⚡ Quick Start (Linux)

After installing the native package:

```bash
# 1. Enroll your face (GUI wizard with multi-angle capture)
python3 /opt/novaunlock/scripts/enroll_gui.py

# 2. Test the Face ID animation (demo mode)
python3 /opt/novaunlock/nova_unlock/ui/face_id_screen.py --demo

# 3. Lock your screen and authenticate with your face!
xflock4                    # XFCE
loginctl lock-session      # GNOME / systemd
```

---

## 🧠 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NovaUnlock Architecture                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │  Camera   │──▶│ Face Detect  │──▶│ Face Recognition   │  │
│  │  Input    │   │  (OpenCV)    │   │  (face_recognition)│  │
│  └──────────┘   └──────────────┘   └────────┬───────────┘  │
│                                              │              │
│                                    ┌─────────▼──────────┐   │
│                                    │  Liveness Check    │   │
│                                    │  (EAR + Blink)     │   │
│                                    └─────────┬──────────┘   │
│                                              │              │
│  ┌──────────────────────────────────────────▼───────────┐  │
│  │              Authentication Controller               │  │
│  │   Match face encoding → Stored profiles → Decision   │  │
│  └───────────┬──────────────────────────┬───────────────┘  │
│              │                          │                   │
│  ┌───────────▼──────────┐  ┌───────────▼───────────────┐  │
│  │  Linux PAM Module    │  │ Windows Credential Provider│  │
│  │  (pam_exec.so)       │  │  (NovaUnlockProvider.dll) │  │
│  └──────────────────────┘  └───────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Dynamic Island UI (PyQt5)               │  │
│  │  Spring animations • 3D sphere • Sound design       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Hello Overlay (Unix Socket IPC)            │  │
│  │  Pre-warmed subprocess • Instant greeting display    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Authentication Flow

1. **Trigger** — User locks screen or initiates login
2. **PAM Request** — System calls NovaUnlock authentication module
3. **UI Launch** — Dynamic Island pill animates into view with spring physics
4. **Capture** — Webcam captures frames with face detection
5. **Encode** — Face encodings extracted and matched against stored profiles
6. **Match** — Encoded vector compared against stored user profiles
7. **Liveness** — EAR blink detection validates live presence
8. **Result** — Success: 3D sphere + unlock animation → screen unlocks
9. **Welcome** — Instant "hello, {user}" greeting overlay via pre-warmed socket

---

## 🔐 Security & Privacy

| Component | Implementation |
|---|---|
| **Face Data** | Stored as numpy arrays on local filesystem only |
| **Network** | Zero network calls — fully offline after install |
| **External APIs** | None used — all processing is local |
| **Telemetry** | None — no analytics, no tracking |
| **Biometric Control** | User-owned, user-deletable data |
| **Password Storage** | Linux: PAM / Windows: LSA Secrets (encrypted) |
| **Anti-Spoof** | EAR blink liveness + multi-frame validation |
| **Code Protection** | Closed-source bytecode + obfuscation + anti-tamper |

---

## 📋 System Requirements

| Requirement | Minimum |
|---|---|
| **Operating System** | Linux (Debian/Ubuntu/Fedora/Arch/Kali) or Windows 10/11 |
| **Python** | 3.11 / 3.12 / 3.13 (bundled deps installed automatically) |
| **Camera** | USB or built-in webcam |
| **RAM** | 2 GB+ |
| **Desktop (Linux)** | GNOME, XFCE, KDE, Cinnamon |

---

## 🎟️ Trial & License

NovaUnlock is **commercial software** distributed with a **30-day free trial**:

1. **First install** → the 30-day trial starts automatically (no sign-up).
2. **During trial** → full functionality, no interruptions.
3. **After trial** → face unlock still works, but an upgrade reminder appears each session with a countdown.
4. **Purchase** → email **hananqaisar316@gmail.com** to buy a license. You'll receive a `.lic` file bound to your device's Hardware ID.
5. **Activate** → drop the `.lic` file into the license folder; the reminder disappears.

Your Hardware ID is shown inside the upgrade dialog and can be copied with one click.

---

## 🆕 Changelog

### v1.32 — Current Release
- 🪟 Windows 10/11 Credential Provider support (refined installer)
- 🐧 Native packages for Debian (`.deb`), Fedora (`.rpm`) and Arch (`.pkg.tar.zst`)
- 🔴 Anti-spoof blink liveness detection (adaptive EAR)
- 🟠 GTK theme auto-switch (dark/light)
- 🟢 Auto-lock on face leave (10s timeout)
- 🔐 30-day trial + paid license system with hardware-bound activation

---

## 💬 Support

NovaUnlock is a commercial product. For licensing, enterprise enquiries, or support:

- 📧 **Email:** [hananqaisar316@gmail.com](mailto:hananqaisar316@gmail.com)
- 🐙 **Source & Releases:** [github.com/hananqaisar-commits/NovaUnlock](https://github.com/hananqaisar-commits/NovaUnlock)

*Secure your system with your face — not your password.*

---

<div align="center">

**Built by [Hanan Qaisar](https://github.com/hananqaisar-commits)**

</div>
