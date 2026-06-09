
<div align="center">

<img src="https://img.shields.io/badge/NovaUnlock-v4.6-1a1a2e?style=for-the-badge&logo=linux&logoColor=white" alt="NovaUnlock"/>

# 🔐 NovaUnlock

**Premium Face Authentication for Linux**

*Smart face unlock for Linux — local, private, and instant*

[![Version](https://img.shields.io/badge/version-4.6-4a90d9?style=flat-square&logo=github)]()
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=flat-square&logo=python&logoColor=white)]()
[![Platform](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Kali%20%7C%20Fedora%20%7C%20Debian-27ae60?style=flat-square&logo=linux&logoColor=white)]()
[![Desktop](https://img.shields.io/badge/desktop-XFCE%20%7C%20GNOME%20%7C%20KDE%20%7C%20Cinnamon-e67e22?style=flat-square&logo=windowsterminal&logoColor=white)]()
[![License](https://img.shields.io/badge/license-Proprietary-e74c3c?style=flat-square&logo=creativecommons&logoColor=white)]()
[![Status](https://img.shields.io/badge/status-Production%20Ready-2ecc71?style=flat-square&logo=statuspage&logoColor=white)]()
[![Privacy](https://img.shields.io/badge/privacy-100%25%20Local-8e44ad?style=flat-square&logo=shield&logoColor=white)]()
[![Build](https://img.shields.io/badge/build-passing%2016%2F16-brightgreen?style=flat-square&logo=githubactions&logoColor=white)]()

[Download](#-quick-install-binary) · [Features](#-features) · [Install](#-installation) · [Usage](#-usage) · [Troubleshoot](#-troubleshooting)

</div>

---

## 🧬 Overview

**NovaUnlock** brings smart face unlock to Linux. Look at your camera — you're in. No passwords, no delays, no cloud.

> 🛡️ **100% local processing.** Your face data never leaves your machine. No telemetry, no network calls, no exceptions.

---

## 🎯 Features

| Feature | Description |
|:---:|:---|
| 🔓 **Instant Face Unlock** | Look at camera to unlock lock screen |
| 🖥️ **Auto Login at Boot** | Face recognition at LightDM/GDM greeter |
| 👥 **Multi-User Support** | One face profile per Linux user |
| 🔑 **Password Fallback** | Auto switch to password if face fails |
| 🐍 **Python 3.13 Ready** | Latest Python — maximum performance |
| 🎨 **Animated Face ID UI** | Beautiful Face ID style scanning animation |
| 📷 **Auto Camera Detect** | USB & built-in webcam auto-detection |
| 🔄 **DBus Watcher** | Auto-trigger on screen lock event |
| 🛡️ **Liveness Detection** | Anti-spoofing protection |
| 🧩 **PAM Integration** | Native PAM module for screen lock auth |

---

## 💻 Supported Systems

| Distro | Desktop | Display Manager | Status |
|:---:|:---:|:---:|:---:|
| ![Ubuntu](https://img.shields.io/badge/Ubuntu-20.04+-E95420?style=flat-square&logo=ubuntu&logoColor=white) | GNOME | GDM | 🟢 Full |
| ![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04+-E95420?style=flat-square&logo=ubuntu&logoColor=white) | GNOME | GDM | 🟢 Full |
| ![Ubuntu](https://img.shields.io/badge/Ubuntu-24.04+-E95420?style=flat-square&logo=ubuntu&logoColor=white) | GNOME | GDM | 🟢 Full |
| ![Kali](https://img.shields.io/badge/Kali-Latest-557C94?style=flat-square&logo=kalilinux&logoColor=white) | XFCE / GNOME | LightDM | 🟢 Full |
| ![Fedora](https://img.shields.io/badge/Fedora-38+-51A2DA?style=flat-square&logo=fedora&logoColor=white) | GNOME | GDM | 🟢 Full |
| ![Debian](https://img.shields.io/badge/Debian-11+-A81D33?style=flat-square&logo=debian&logoColor=white) | GNOME / XFCE | LightDM / GDM | 🟢 Full |

---

## 📦 Installation

### Method 1 — wget (Recommended)

```bash
wget -O nova_install.sh https://raw.githubusercontent.com/hananqaisar-commits/NovaUnlock/main/install.sh
sudo bash nova_install.sh

Method 2 — curl

Bash

curl -fsSL https://raw.githubusercontent.com/hananqaisar-commits/NovaUnlock/main/install.sh | sudo bash

Method 3 — Git Clone

Bash

git clone https://github.com/hananqaisar-commits/NovaUnlock.git
cd NovaUnlock
sudo bash install.sh

    💡 Note: All 3 methods work the same way. Installer auto-detects path.

⚡ Quick Install (Binary)

Bash

wget -O nova_unlock_installer https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v4.6/nova_unlock_installer_v4.6
chmod +x nova_unlock_installer
sudo ./nova_unlock_installer

🚀 Usage
Step 1 — Install

Bash

sudo bash install.sh

Expected output:

text

✅ Passed : 16/16

Step 2 — Enroll Face

Bash

cd ~/NovaUnlock && source .venv/bin/activate
python3 scripts/enroll_gui.py

Follow on-screen instructions:

    Look straight at camera
    10 samples will be captured automatically
    Face data saved to ~/NovaUnlock/data/faces/

Step 3 — Test UI

Bash

source ~/NovaUnlock/.venv/bin/activate
export DISPLAY=:0
python3 ~/NovaUnlock/nova_unlock/ui/face_id_screen.py

Step 4 — Lock Screen

XFCE:

Bash

xflock4

GNOME:

Bash

dbus-send --type=method_call \
  --dest=org.gnome.ScreenSaver \
  /org/gnome/ScreenSaver \
  org.gnome.ScreenSaver.Lock

Step 5 — Face Unlock

Look at camera — NovaUnlock unlocks automatically! 🎉
🔧 Troubleshooting
🐍 face_recognition_models Error

Bash

cd ~/NovaUnlock
source .venv/bin/activate
python3 scripts/patch_face_models_py313.py

🔄 Watcher Service Not Running

Bash

sudo systemctl daemon-reload
sudo systemctl enable --now nova-unlock-watcher.service
sudo systemctl status nova-unlock-watcher.service

📷 Camera Not Found

Bash

ls /dev/video*

🖥️ Display/Qt Error

XFCE:

Bash

export DISPLAY=:0
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=/home/$USER/.Xauthority

GNOME/GDM:

Bash

export DISPLAY=:1
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=/run/user/1000/gdm/Xauthority

👤 Re-Enroll Face

Bash

python3 ~/NovaUnlock/scripts/enroll_entry.py --force

📋 Check Logs

Bash

cat ~/NovaUnlock/logs/install.log
journalctl -u nova-unlock-watcher.service -n 50

🗑️ Uninstall

Bash

sudo bash ~/NovaUnlock/uninstall.sh

📋 Changelog
🔥 v4.6 (Latest)

    🎨 face_id_screen.py UI included in installer bundle
    🐍 Fixed Python 3.13 compatibility (setuptools, pkg_resources)
    📦 Fixed face_recognition_models install order
    🖥️ Fixed OpenCV GUI support (headless → full)
    🔍 Auto PYTHONPATH detection
    🛠️ Installer 16/16 checks passing

⚡ v4.5 → v4.6

    🎨 New animated Face ID UI
    🖥️ Multi-desktop support
    🔄 DBus watcher integration

🔧 v4.4

    🔒 PAM authentication support
    🖥️ LightDM greeter hooks

🚀 v4.2

    🎉 Initial release
    🔓 Basic face recognition unlock

🔒 Privacy
Aspect	Detail
💾 Data Storage	Face data stored locally only: ~/NovaUnlock/data/faces/
🌐 Network	No internet required after install
📊 Telemetry	Zero telemetry or tracking
🔐 Control	Open enrollment — you control your data
🛡️ Processing	100% on-device face recognition
🛠️ System Requirements
Requirement	Minimum
💻 OS	Linux (Debian / Ubuntu / Kali / Fedora)
🐍 Python	3.11 or higher
📷 Camera	USB or built-in webcam
🖥️ Desktop	XFCE / GNOME / KDE / Cinnamon
🧠 RAM	2GB+
💾 Disk	500MB free space
📄 License

text

Proprietary — NovaUnlock v4.6
© 2026 NovaUnlock Team
All rights reserved.

<div align="center">
👨‍💻 Author

Hanan Qaisar

GitHub

⭐ Star this repo if NovaUnlock made your Linux life easier!