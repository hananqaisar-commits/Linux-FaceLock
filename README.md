<div align="center">

# 🔒 Linux-FaceLock

### *Authentic Dynamic Island Face ID & PAM Face Authentication for Linux & Windows*

[![CI](https://github.com/hananqaisar-commits/Linux-FaceLock/actions/workflows/ci.yml/badge.svg)](https://github.com/hananqaisar-commits/Linux-FaceLock/actions)
[![GitHub release](https://img.shields.io/github/v/release/hananqaisar-commits/Linux-FaceLock?style=for-the-badge&color=007ACC&logo=github)](https://github.com/hananqaisar-commits/Linux-FaceLock/releases)
[![GitHub Stars](https://img.shields.io/github/stars/hananqaisar-commits/Linux-FaceLock?style=for-the-badge&color=gold&logo=github)](https://github.com/hananqaisar-commits/Linux-FaceLock/stargazers)
[![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)](LICENSE)
[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?style=for-the-badge&logo=python)](https://python.org)
[![Linux Support](https://img.shields.io/badge/Distros-Ubuntu%20%7C%20Fedora%20%7C%20Arch%20%7C%20Debian-orange.svg?style=for-the-badge&logo=linux)](README.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg?style=for-the-badge)](CONTRIBUTING.md)

<br/>

**[Features](#-features)** • **[Installation](#-installation)** • **[Quick Demo](#-quick-demo)** • **[Architecture](#-architecture)** • **[Contributing](#-contributing)**

</div>


---

## ⚡ Overview

**Linux-FaceLock** is a next-generation, high-performance facial recognition lock screen integration for Linux desktop environments (GNOME, KDE Plasma, XFCE, LightDM, SDDM, GDM) and Windows.

Inspired by Apple's Dynamic Island aesthetics, it delivers **sub-second facial verification**, zero UI latency, smooth 60 FPS spring physics, interactive audio cues, and native Linux PAM stack security.

---

## ✨ Key Features

| Feature | Description |
| :--- | :--- |
| **🏝️ Dynamic Island UI** | Minimalist 280×38 pill widget floating seamlessly on your lock screen |
| **📷 Live Camera & Lock Morph** | Real-time camera icon `⚪` morphing dynamically into an animated unlocked `🔓` state |
| **🟢 3D Wireframe Mesh** | Futuristic green 3D sphere animation rendered on successful facial vector match |
| **🔊 Spatial Audio Feedback** | Interactive chime sound effects on popup, verification success, and invalid face shake |
| **🛡️ PAM Stack Security** | Native `pam_script` & PAM module integration (`gdm-password`, `lightdm`, `sudo`, `kscreenlocker`) |
| **📦 Multi-Distro Packages** | Pre-compiled packages for Ubuntu/Debian (`.deb`), Fedora/RPM (`.rpm`), and Arch (`.pkg.tar.zst`) |
| **🪟 Windows Bridge** | Windows Credential Provider unlock helper for dual-boot setups |

---

## 🚀 Installation

### Option 1: Native Package Manager (Recommended)

Download the latest binary release for your distribution from [GitHub Releases](https://github.com/hananqaisar-commits/Linux-FaceLock/releases):

#### 🌀 Debian / Ubuntu / Kali / Mint / Pop!_OS (`.deb`)
```bash
sudo dpkg -i NovaUnlock-v3.2-Debian.deb
sudo apt-get install -f
```

#### 🎩 Fedora / RHEL / openSUSE (`.rpm`)
```bash
sudo dnf install ./NovaUnlock-v3.2-Fedora.rpm
```

#### 🏹 Arch Linux / Manjaro (`.pkg.tar.zst`)
```bash
sudo pacman -U ./NovaUnlock-v3.2-Arch.pkg.tar.zst
```

---

### Option 2: Universal One-File Installer

Works on any Linux distribution without external package manager requirements:

```bash
chmod +x nova_unlock_installer_v3.2
sudo ./nova_unlock_installer_v3.2
```

---

### Option 3: Build & Run from Source

```bash
# Clone repository
git clone https://github.com/hananqaisar-commits/Linux-FaceLock.git
cd Linux-FaceLock

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run interactive Dynamic Island demo
python3 -m nova_unlock.ui.face_unlock_widget --demo
```

---

## 🎬 Quick Demo & Enrollment

Try out the biometric lock screens and enrollment screens locally:

### 1. Face ID Animation & Scanner Demo
To launch the authentic iOS-style Dynamic Island scanner and cycle through scanning states (Success ➔ Fail ➔ Success) with audio effects:
```bash
python3 -m nova_unlock.ui.face_id_embed
```

### 2. Face Enrollment Wizard
To enroll your face biometric template and register it locally:
```bash
python3 -m nova_unlock.ui.enrollment_wizard
```
### 3. Welcome Screen Demo
To launch the interactive macOS-style hello welcome screen (with hello greeting, dynamic island animation, and chime sound):

```bash
python3 -m nova_unlock.ui.welcome_screen

```

### 4. Service enable on System boot

```bash

sudo systemctl enable nova-facelock.service

```

### 5. Service disable on System boot

```bash
sudo systemctl disable nova-facelock.service
```

---

## 🧠 Architecture Overview

```mermaid
graph TD
    A[Linux Lock Screen / PAM Trigger] -->|Invoke PAM Module| B[nova_pam_auth.py]
    B -->|DBus IPC Connection| C[NovaUnlock Service Daemon]
    C -->|Camera Probe & OpenCV| D[Face Detection & 128D Embeddings]
    D -->|Match Verified| E[Dynamic Island UI Widget]
    E -->|Green Sphere + Unlock Sound| F[PAM Auth SUCCESS]
    D -->|Match Failed| E2[Red Shake + Retries]
```

---

## 🔒 Security & Privacy

- **Local Vector Storage**: Face embeddings are stored locally on your encrypted drive; no biometric data ever leaves your machine.
- **Liveness Detection**: Multi-frame blink & motion verification prevents static photo spoofs.
- **PAM Fallback**: Automatic seamless fallback to password prompt if face identification times out or is unrecognized.
- Please review our [SECURITY.md](SECURITY.md) for vulnerability disclosure guidelines.

---

## 🤝 Contributing

We welcome community contributions! Check out our [CONTRIBUTING.md](CONTRIBUTING.md) to get started with developer setup, testing, and PR guidelines.

---

## 🆚 How does it compare?

| | **Linux-FaceLock** | Howdy | fprintd |
|---|:---:|:---:|:---:|
| Dynamic Island UI | ✅ | ❌ | ❌ |
| PAM Integration | ✅ | ✅ | ✅ |
| Lock Screen Unlock | ✅ | ✅ | ❌ |
| Login Screen (LightDM/GDM) | ✅ | ❌ | ❌ |
| Suspend/Resume Auto-Relock | ✅ | ❌ | ❌ |
| Multi-distro Packages | ✅ `.deb` `.rpm` `.pkg` | `.deb` only | varies |
| Windows Support | ✅ | ❌ | ❌ |
| Audio Feedback | ✅ | ❌ | ❌ |
| Active Development (2026) | ✅ | ⚠️ | ⚠️ |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## ⭐ Star History

If Linux-FaceLock helped you, please consider giving it a ⭐ — it helps others discover the project!

<a href="https://star-history.com/#hananqaisar-commits/Linux-FaceLock&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=hananqaisar-commits/Linux-FaceLock&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=hananqaisar-commits/Linux-FaceLock&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=hananqaisar-commits/Linux-FaceLock&type=Date" width="600" />
 </picture>
</a>
