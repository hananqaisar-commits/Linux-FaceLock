# 🔒 Linux-FaceLock (NovaUnlock)

> **Modern, Ultra-Fast Dynamic Island Face ID & PAM Face Authentication for Linux & Windows**

![Release](https://img.shields.io/github/v/release/hananqaisar-commits/NovaUnlock?style=for-the-badge&color=007ACC)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg?style=for-the-badge)
![Distros](https://img.shields.io/badge/Distros-Ubuntu%20%7C%20Fedora%20%7C%20Arch%20%7C%20Debian-orange.svg?style=for-the-badge)

---

## 🌟 Overview

**Linux-FaceLock** is an open-source, high-performance facial recognition lock utility designed for Linux desktop environments (GNOME, KDE Plasma, XFCE, LightDM, SDDM) and Windows. It brings an authentic **Dynamic Island Face ID UI** with zero lag, instant spring-physics animation, camera & lock state icons, and interactive sound cues.

---

## ✨ Features

- ⚡ **Zero-Lag Dynamic Island UI**: Lightweight PyQt5 widget rendered smoothly on top of your lockscreen.
- 🔒 **Camera & Lock Icons**: Authentic scanning indicators (Camera ⚪ + Lock 🔒 morphing to Unlocked 🔓).
- 🟢 **3D Wireframe Sphere**: Cinematic green wireframe 3D sphere animation on facial match.
- 🔊 **Sound Cues**: Audio feedback for popup, unlock success, and failure shake.
- 🛡️ **PAM Authentication Integration**: Works with standard Linux PAM stack (`pam_script` / GDM / LightDM / sudo / lockscreens).
- 🐧 **Cross-Distro Native Support**: Prebuilt packages for Debian/Ubuntu, Fedora/RHEL, and Arch/Manjaro.
- 🪟 **Windows Credential Provider Support**: Native Windows lockscreen face authentication bridge.

---

## 🚀 Quick Start / Installation

### Option 1: Native Packages (Recommended)

Download the latest prebuilt package for your distribution from [GitHub Releases](https://github.com/hananqaisar-commits/NovaUnlock/releases):

#### 🌀 Debian / Ubuntu / Kali / Pop!_OS / Mint (`.deb`)
```bash
sudo dpkg -i NovaUnlock-v2.21-Debian.deb
sudo apt-get install -f
```

#### 🎩 Fedora / RHEL / openSUSE (`.rpm`)
```bash
sudo dnf install ./NovaUnlock-v2.21-Fedora.rpm
```

#### 🏹 Arch Linux / Manjaro (`.pkg.tar.zst`)
```bash
sudo pacman -U ./NovaUnlock-v2.21-Arch.pkg.tar.zst
```

---

### Option 2: Universal One-File Installer

```bash
chmod +x nova_unlock_installer_v2.21
sudo ./nova_unlock_installer_v2.21
```

---

### Option 3: Run / Build from Source

```bash
git clone https://github.com/hananqaisar-commits/Linux-FaceLock.git
cd Linux-FaceLock

# Create venv and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run UI Demo
python3 -m nova_unlock.ui.face_unlock_widget --demo
```

---

## 🎬 Testing the Dynamic Island UI

You can test the Dynamic Island Face ID animation cycle at any time by running:

```bash
python3 -m nova_unlock.ui.face_unlock_widget --demo
```

---

## 🤝 Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on code style, unit testing, and submitting pull requests.

---

## 📄 License

Distributed under the **MIT License**. See [LICENSE](LICENSE) for more information.
