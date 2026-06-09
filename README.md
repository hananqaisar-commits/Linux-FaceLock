<div align="center">

<img src="https://img.shields.io/badge/NovaUnlock-v4.6-1a1a2e?style=for-the-badge&logo=linux&logoColor=white" alt="NovaUnlock"/>

# NovaUnlock

**Premium Face Authentication for Linux**

*Smart face unlock for Linux — local, private, and instant*

[![Version](https://img.shields.io/badge/version-4.6-4a90d9?style=flat-square&logo=github)]()
[![Platform](https://img.shields.io/badge/platform-Ubuntu%20%7C%20Kali%20%7C%20Fedora-27ae60?style=flat-square&logo=linux&logoColor=white)]()
[![License](https://img.shields.io/badge/license-Proprietary-e74c3c?style=flat-square)]()
[![Status](https://img.shields.io/badge/status-Production%20Ready-2ecc71?style=flat-square)]()
[![Privacy](https://img.shields.io/badge/privacy-100%25%20Local-8e44ad?style=flat-square&logo=shield&logoColor=white)]()

[Download](#-quick-install) · [Features](#-features) · [Install](#-installation) · [Usage](#-usage) · [Troubleshoot](#-troubleshooting)

</div>

---

## Overview

**NovaUnlock** brings smart face unlock to Linux. Look at your camera — you're in. No passwords, no delays, no cloud.

> **100% local processing.** Your face data never leaves your machine. No telemetry, no network calls, no exceptions.

---

## Features

| Feature | Description |
|---|---|
| **Instant Face Unlock** | Look at camera to unlock lock screen |
| **Auto Login at Boot** | Face recognition at GDM greeter screen |
| **Multi-User Support** | One face profile per Linux user |
| **Password Fallback** | Auto switch to password if face fails |
| **Python 3.13** | Latest Python — maximum performance |
| **GUI + CLI Enrollment** | GUI first, CLI fallback automatically |

---

## Supported Systems

| Distro | Desktop | Status |
|--------|---------|--------|
| Ubuntu 20.04+ | GNOME/GDM | ✅ Full Support |
| Ubuntu 22.04+ | GNOME/GDM | ✅ Full Support |
| Ubuntu 24.04+ | GNOME/GDM | ✅ Full Support |
| Kali Linux | GNOME/XFCE | ✅ Full Support |
| Fedora 38+ | GNOME/GDM | ✅ Full Support |
| Debian 11+ | GNOME | ✅ Full Support |

---

## Installation

### Method 1 — wget (Recommended, No Clone Needed)

```bash
wget -O nova_install.sh https://raw.githubusercontent.com/YOUR_USERNAME/NovaUnlock/main/install.sh
sudo bash nova_install.sh

Method 2 — curl

Bash

curl -fsSL https://raw.githubusercontent.com/YOUR_USERNAME/NovaUnlock/main/install.sh | sudo bash

Method 3 — Git Clone

Bash

git clone https://github.com/YOUR_USERNAME/NovaUnlock.git
cd NovaUnlock
sudo bash install.sh

    ⚠️ Note: All 3 methods work the same way.
    Installer auto-detects path — no manual path changes needed.

Quick Install (Binary)

Download pre-built installer:

Bash

wget -O nova_unlock_installer https://github.com/YOUR_USERNAME/NovaUnlock/releases/download/v4.6/nova_unlock_installer_v4.6
chmod +x nova_unlock_installer
sudo ./nova_unlock_installer

Usage
Step 1 — Install

Bash

sudo bash install.sh

Step 2 — Enroll Face

After install, run:

Bash

cd ~/NovaUnlock
bash -c 'source .venv/bin/activate 2>/dev/null; python3 scripts/enroll_entry.pyc'

Or directly:

Bash

python3 ~/NovaUnlock/scripts/enroll_entry.pyc

Step 3 — Lock Screen

Press Super + L or:

Bash

dbus-send --type=method_call \
  --dest=org.gnome.ScreenSaver \
  /org/gnome/ScreenSaver \
  org.gnome.ScreenSaver.Lock

Step 4 — Face Unlock

Look at camera — NovaUnlock unlocks automatically!
Troubleshooting
face_recognition_models Error

Bash

cd ~/NovaUnlock
source .venv/bin/activate
python3 scripts/patch_face_models_py313.pyc

Watcher Service Not Running

Bash

systemctl --user daemon-reload
systemctl --user enable --now nova-unlock-watcher.service
systemctl --user status nova-unlock-watcher.service

Camera Not Found

Bash

ls /dev/video*

Display/Qt Error

Bash

export DISPLAY=:1
export QT_QPA_PLATFORM=xcb
export XAUTHORITY=/run/user/1000/gdm/Xauthority

Re-Enroll Face

Bash

python3 ~/NovaUnlock/scripts/enroll_entry.pyc --force

Check Logs

Bash

cat ~/NovaUnlock/logs/install.log
journalctl --user -u nova-unlock-watcher.service -n 50

Uninstall

Bash

sudo bash ~/NovaUnlock/uninstall.sh

Privacy

    ✅ Face data stored locally only: ~/NovaUnlock/data/faces/
    ✅ No internet connection after install
    ✅ No telemetry or tracking
    ✅ Open enrollment — you control your data

License

Proprietary — NovaUnlock v4.6
© 2026 NovaUnlock Team

