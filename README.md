<div align="center">

# NovaUnlock

### Next-Generation Face Authentication System for Linux & Windows

Biometric Face Unlock • Dynamic Island UI • PAM Integration • Privacy-First • Zero Cloud Dependency

---

![Version](https://img.shields.io/badge/version-2.012-4a90d9?style=for-the-badge)
![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-3776ab?style=for-the-badge&logo=python&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-supported-27ae60?style=for-the-badge&logo=linux&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Desktop](https://img.shields.io/badge/desktop-GNOME%20%7C%20XFCE%20%7C%20KDE%20%7C%20Cinnamon-e67e22?style=for-the-badge)
![Auth](https://img.shields.io/badge/auth-PAM%20%7C%20Credential%20Provider-orange?style=for-the-badge)
![Privacy](https://img.shields.io/badge/privacy-100%25%20local-8e44ad?style=for-the-badge)
![License](https://img.shields.io/badge/license-commercial-lightgrey?style=for-the-badge)

</div>

---

## Interface Preview

<div align="center">

### Face Scanning — Dynamic Island UI

<img src="assets/facelock_scanning.png" width="60%" alt="NovaUnlock — FaceLock Scanning State" />

> iOS-inspired Dynamic Island with lock icon and Face ID scanner. The pill expands with a spring animation and begins biometric scanning.

---

### Authentication Success — 3D Wireframe Sphere

<img src="assets/facelock_success.png" width="60%" alt="NovaUnlock — Face Match Success" />

> On successful face match: lock icon animates to unlocked (green glow), and an authentic iOS-style 3D wireframe sphere rotates with depth-sorted perspective rendering.

---

### Welcome Greeting — Instant Hello Overlay

<img src="assets/hello_welcome.png" width="60%" alt="NovaUnlock — Hello Welcome Screen" />

> After successful unlock, an elegant full-screen greeting overlay appears instantly — "hello, {Username}" — with a subtle gradient accent line.

</div>

---

## Project Overview

**NovaUnlock** is a commercial, closed-source biometric face authentication system that replaces traditional password login with real-time facial recognition. It integrates directly with **Linux PAM** and **Windows Credential Provider** for system-level biometric authentication.

Every aspect of the system is designed for **local processing** — no cloud APIs, no telemetry, no external dependencies. Your biometric data never leaves your device.

> **Trial:** NovaUnlock ships with a **30-day free trial** — full functionality, no prompts. After the trial, face unlock still works, but a one-time paid license is required to remove the upgrade reminder. See [Trial & License](#trial--license).

### Why NovaUnlock?

| Feature | NovaUnlock | Traditional Login |
|---|---|---|
| Authentication Speed | < 1 second | Manual typing |
| Security Layer | Biometric + Password fallback | Password only |
| Privacy | 100% local processing | Varies |
| User Experience | iOS-quality animations | Standard OS dialogs |
| Multi-Platform | Linux + Windows | OS-specific |

---

## Core Features

### Biometric Face Authentication
Real-time face recognition via webcam with configurable matching thresholds. Supports multiple face encodings per user for improved accuracy across lighting conditions.

### Dynamic Island UI
An iOS-inspired animated interface built with PyQt5 featuring:
- Spring-physics pill animation with smooth expand/collapse
- 3D wireframe sphere with perspective projection and depth-sorted rendering
- Animated lock icon that transitions from locked → unlocked with green glow
- Face ID scanner icon with natural eye-blink animation
- Shake rejection effect with spring-damped horizontal oscillation
- Sound design — procedurally generated pluck, bell, and whoosh audio cues

### Instant Welcome Overlay
After successful authentication, a full-screen greeting overlay displays instantly via Unix socket IPC — pre-warmed during the scan phase for zero-latency display.

### PAM Integration (Linux)
Seamless integration with Linux **Pluggable Authentication Modules** for:
- Login screen authentication
- Lock screen unlock
- `sudo` elevation (optional)

### Windows Credential Provider
Native Windows 10/11 support via a compiled C++ Credential Provider DLL that interfaces with LSA Secrets for secure password handling.

### Anti-Spoof Liveness Detection
- Adaptive EAR calibration — learns your eye ratio in 30 frames
- dlib 68-point landmarks with 5-strategy face detection fallback
- MediaPipe Tasks / Legacy / OpenCV Haar cascade chain
- Rejects: printed photos, phone screens, static masks

### 100% Local Processing
- No cloud APIs or external network calls
- No telemetry or tracking
- All face encoding data stored on local filesystem
- User-owned biometric data

### Multi-User Support
Separate face profiles per Linux/Windows user with independent encoding databases.

### Secure Password Fallback
Automatic fallback to password authentication when:
- Face recognition fails after 3 attempts
- Camera is unavailable
- Liveness check fails

---

## Platform Support

### Linux
| Distribution | Package | Status |
|---|---|---|
| Ubuntu 22.04+ | `.deb` | Supported |
| Debian 12+ | `.deb` | Supported |
| Kali Linux | `.deb` | Supported |
| Linux Mint / Pop!_OS | `.deb` | Supported |
| Fedora / RHEL / openSUSE | `.rpm` | Supported |
| Arch / Manjaro | `.pkg.tar.zst` | Supported |
| KDE Plasma | `.deb` / `.rpm` | Experimental |

### Windows
| Version | Status |
|---|---|
| Windows 10 (21H2+) | Supported |
| Windows 11 | Supported |

---

## Download (every release)

All releases live on the
[GitHub Releases page](https://github.com/hananqaisar-commits/NovaUnlock/releases).
The current release is **v2.012**. No source code is shipped — every package contains only compiled binaries.

### Option A — Download from the web
Open the release page, find the asset for your platform, and click to download:
- **v2.012 (Latest):** https://github.com/hananqaisar-commits/NovaUnlock/releases/tag/v2.012

### Option B — Download from the terminal
Pick the asset that matches your OS, then run one of the commands below (swap the filename for your platform).

```bash
# ── Debian / Ubuntu / Kali / Mint / Pop!_OS ──
gh release download v2.012 --repo hananqaisar-commits/NovaUnlock --pattern "NovaUnlock-v2.012-Debian.deb"
# or:
curl -L -O https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v2.012/NovaUnlock-v2.012-Debian.deb

# ── Fedora / RHEL / openSUSE ──
gh release download v2.012 --repo hananqaisar-commits/NovaUnlock --pattern "NovaUnlock-v2.012-Fedora.rpm"
# or:
curl -L -O https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v2.012/NovaUnlock-v2.012-Fedora.rpm

# ── Arch / Manjaro ──
gh release download v2.012 --repo hananqaisar-commits/NovaUnlock --pattern "NovaUnlock-v2.012-Arch.pkg.tar.zst"
# or:
curl -L -O https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v2.012/NovaUnlock-v2.012-Arch.pkg.tar.zst

# ── Any Linux (universal one-file installer) ──
gh release download v2.012 --repo hananqaisar-commits/NovaUnlock --pattern "nova_unlock_installer_v2.012"
# or:
curl -L -O https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v2.012/nova_unlock_installer_v2.012

# ── Windows 10 / 11 ──
gh release download v2.012 --repo hananqaisar-commits/NovaUnlock --pattern "nova_unlock_windows_v2.012.zip"
# or:
curl -L -O https://github.com/hananqaisar-commits/NovaUnlock/releases/download/v2.012/nova_unlock_windows_v2.012.zip
```

Each Linux asset is paired with a `*.sha256` file so you can verify integrity after download:

```bash
sha256sum -c NovaUnlock-v2.012-Debian.deb.sha256   # example for the .deb
```

---

## Installation (every release)

| Platform | File | Install with |
|---|---|---|
| Ubuntu / Debian / Kali / Mint / Pop!_OS | `NovaUnlock-v2.012-Debian.deb` | `apt` |
| Fedora / RHEL / openSUSE | `NovaUnlock-v2.012-Fedora.rpm` | `dnf` |
| Arch / Manjaro | `NovaUnlock-v2.012-Arch.pkg.tar.zst` | `pacman` |
| Any Linux (universal one-file) | `nova_unlock_installer_v2.012` | run as root |
| Windows 10 / 11 | `nova_unlock_windows_v2.012.zip` | `install.bat` |

> **Checksums:** every Linux asset ships with a matching `*.sha256`. Verify before installing:
> `sha256sum -c <file>.sha256`

### Debian / Ubuntu / Kali / Mint / Pop!_OS — `.deb`
```bash
# 1. Refresh your package lists (good habit before installing anything)
sudo apt update

# 2. Install the downloaded .deb. The "./" means "this local file", not a repo package.
sudo apt install ./NovaUnlock-v2.012-Debian.deb
```

### Fedora / RHEL / openSUSE — `.rpm`
```bash
# Install the .rpm. Use "dnf" on Fedora/RHEL; on openSUSE swap "dnf" for "zypper".
sudo dnf install ./NovaUnlock-v2.012-Fedora.rpm
```

### Arch / Manjaro — `.pkg.tar.zst`
```bash
# "-U" installs from a local package file (instead of downloading from the online repos)
sudo pacman -U NovaUnlock-v2.012-Arch.pkg.tar.zst
```

### Any Linux — `nova_unlock_installer_v2.012` (universal one-file)
One self-contained installer for every major distro (Ubuntu/Debian/Kali/Fedora/Arch/openSUSE).
You don't need Python or pip — it bundles everything it needs.
```bash
# 1. Make the downloaded file executable (Linux blocks running downloaded files by default)
chmod +x nova_unlock_installer_v2.012

# 2. Run it as root so it can install to /opt and wire up PAM
sudo ./nova_unlock_installer_v2.012
```

> **What gets installed (all Linux methods):** files land in `/opt/novaunlock`, the shipped
> bytecode is compiled for *your* Python (3.11–3.13), **PAM** is wired for your desktop
> (login + lock screen, optional `sudo`), the AI libraries (dlib / face_recognition) are
> pip-installed best-effort from bundled offline wheels, the 30-day trial starts, and the guard service is enabled.
> If a library can't auto-install, **your password still works** as a fallback.

### Windows 10 / 11 — `nova_unlock_windows_v2.012.zip`

In simple words: you download a zip, run **one file as Administrator**, and NovaUnlock adds a
**face-unlock button to your normal Windows login screen**. Your password always stays as a backup.

1. **Download** `nova_unlock_windows_v2.012.zip` from the releases page and unzip it anywhere
   (your Desktop is fine).
2. Open the unzipped folder. **Right-click `install.bat` → choose "Run as administrator".**
   This registers NovaUnlock's Credential Provider with Windows and starts its background service.
3. If Windows asks to install **Python** or the **Visual C++ runtime**, say yes — they're required.
4. **Restart** your PC so Windows loads the new login provider.
5. On the lock screen you'll now see a NovaUnlock face-unlock tile. Click it and sit in front of
   your camera to **enroll** (register) your face the first time.
6. After that, just look at the camera on the login screen and you're in — no typing needed.

---

### Enroll your face (Linux)
Run this once after installing so NovaUnlock knows what you look like. Run it **as your normal user**
(not `sudo`) and from a graphical session (so the camera + GUI can open):
```bash
# Opens the PyQt5 enrollment window (live preview + face box + progress ring).
# Falls back to a text wizard automatically if no display/camera is available.
python3 /opt/novaunlock/scripts/enroll_entry.pyc
```
> The installer compiles the shipped `.py` source into `.pyc` and deletes the `.py` files,
> so always run the **`.pyc`** binary. `enroll_entry.pyc` is the robust launcher (GUI first, CLI
> fallback). `enroll_gui.pyc` opens the GUI directly.
>
> Your profile is saved as `/var/lib/novaunlock/faces/<username>.npy`. Enroll **each** user you
> want to unlock separately, while logged in as that user.

### Try it (Linux)
Lock your screen, then authenticate with your face:
```bash
xflock4                 # XFCE
loginctl lock-session   # GNOME / systemd
```
If face recognition fails 3× (or the camera is unavailable), NovaUnlock falls back to your password.

### Uninstall
```bash
sudo apt remove novaunlock            # Debian / Ubuntu / Kali
sudo dnf remove novaunlock            # Fedora / RHEL
sudo pacman -R novaunlock             # Arch
```
On Windows, remove it from **Settings → Apps → NovaUnlock** (or the uninstall entry shipped in the zip).

---

## Quick Start (Linux)

After installing the native package:

```bash
# 1. Enroll your face (GUI wizard with multi-angle capture)
python3 /opt/novaunlock/scripts/enroll_entry.pyc

# 2. Test the Face ID animation (demo mode — SUCCESS → FAIL → SUCCESS)
python3 /opt/novaunlock/nova_unlock/ui/face_id_screen.pyc --demo

# 3. Lock your screen and authenticate with your face!
xflock4                    # XFCE
loginctl lock-session      # GNOME / systemd
```

---

## Debugging & Troubleshooting

Everything NovaUnlock does is observable through logs and config files. This section tells you
**where to look** and **what to check** for the most common problems.

### Where the logs are

| Log | What it shows |
|---|---|
| `/var/log/novaunlock/face_auth.log` | The lock-screen/guard daemon: camera open, face match result, unlock decision. **Start here.** |
| `/var/log/novaunlock/pam_auth.log` | PAM auth events (pam_script hook firing on login/sudo). |
| `/var/log/novaunlock/watcher.log` | The presence watcher (auto-lock when you walk away). |
| `/tmp/nova_greeter_ui.log` | The greeter UI process (camera preview at the login screen). |
| `/tmp/nova_unlock_greeter.log` | Greeter launcher stdout/stderr. |
| `/tmp/nova_unlock_greeter_launcher.log` | Greeter launcher bootstrap. |

Watch the live daemon log while you try to unlock:
```bash
sudo tail -f /var/log/novaunlock/face_auth.log
```

### Is the package actually installed?
```bash
# Native package
dpkg -l novaunlock            # Debian/Ubuntu
rpm -qi novaunlock            # Fedora
pacman -Qi novaunlock         # Arch

# Files present?
ls -1 /opt/novaunlock
ls -1 /opt/novaunlock/scripts | grep -E "enroll|face_unlock_daemon|face_login_greeter"
```

### Is my face enrolled?
```bash
ls -la /var/lib/novaunlock/faces
cat /var/lib/novaunlock/faces/users_meta.json
```
You should see `<your-username>.npy`. If the folder is empty, run the enrollment step again
(as your user, not root). To re-enroll from scratch:
```bash
rm -f /var/lib/novaunlock/faces/<username>.npy
python3 /opt/novaunlock/scripts/enroll_entry.pyc
```

### Is PAM wired up?
NovaUnlock hooks these PAM files (depending on desktop):
- `/etc/pam.d/xfce4-screensaver`
- `/etc/pam.d/gnome-screensaver`
- `/etc/pam.d/gdm-password`
- `/etc/pam.d/kde`

Check that a `pam_script` / `pam_exec` line pointing at `/opt/novaunlock/...` is present:
```bash
grep -RniE "novaunlock|pam_script|pam_exec" /etc/pam.d/ | head
```
The actual script that runs is `pam_script_auth` under `/usr/share/libpam-script/`
(or the bundled equivalent in `/opt/novaunlock`).

### Is the greeter configured? (login-screen camera)
For LightDM the config lives in:
- `/etc/lightdm/lightdm.conf.d/50-nova-unlock.conf`
- `/etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf`

Verify they exist and reference the greeter:
```bash
cat /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf
```
Changes here take effect after you **reboot** or restart the display manager.

### Is the guard service running?
```bash
systemctl --user status nova-unlock-watcher.service
systemctl --user enable --now nova-unlock-watcher.service
```
(The watcher is a **user** service, so check it as your user, not with `sudo`.)

### Camera problems
```bash
# Is a camera visible to the system at all?
ls -l /dev/video*
# Is something else holding the camera? (only one app can use it)
# Close Zoom/Cheese/OBS, then retry enrollment/unlock.
```
If enrollment prints `❌ No camera found` or the GUI never appears, the camera is missing or busy.
The enrollment will automatically fall back to a text wizard if there is no display.

### Enrollment opened as text/CLI instead of a GUI
This happens when:
- you ran it over SSH (no `DISPLAY`), or
- the PyQt5 GUI could not start.
Run it from a **local terminal inside your desktop session** (not SSH). Check `DISPLAY` is set:
```bash
echo "$DISPLAY"        # should be e.g. :0 or :1
python3 /opt/novaunlock/scripts/enroll_gui.pyc   # GUI directly
```

### Face is not recognized / unlock fails
1. Check `face_auth.log` — it records the match distance vs threshold.
2. Re-enroll in **good, even lighting** (10 samples, look straight at the camera).
3. Make sure you enrolled the **same user** you are logging in as.
4. After 3 failures it falls back to your password by design — that is expected.

### Unlock animation looks cut off / logs in too early
Fixed in v1.38: the success animation (camera fade → sphere grow → lock open → hold → fade) now
plays in full (~1.6s) **before** the desktop unlocks. If you still see an early cut-off, you are
running an older build — upgrade to v1.38 and re-test with:
```bash
python3 /opt/novaunlock/nova_unlock/ui/face_id_screen.pyc --demo
```

### Still stuck?
Collect these and include them in a support request:
```bash
echo "=== face_auth.log ==="; sudo tail -n 50 /var/log/novaunlock/face_auth.log
echo "=== pam_auth.log ==="; sudo tail -n 20 /var/log/novaunlock/pam_auth.log
echo "=== faces ==="; ls -la /var/lib/novaunlock/faces
echo "=== version ==="; cat /opt/novaunlock/nova_unlock/__init__.py | grep __version__
```

---

## System Architecture

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

## Security & Privacy

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

## System Requirements

| Requirement | Minimum |
|---|---|
| **Operating System** | Linux (Debian/Ubuntu/Fedora/Arch/Kali) or Windows 10/11 |
| **Python** | 3.11 / 3.12 / 3.13 (bundled deps installed automatically) |
| **Camera** | USB or built-in webcam |
| **RAM** | 2 GB+ |
| **Desktop (Linux)** | GNOME, XFCE, KDE, Cinnamon |

---

## Trial & License

NovaUnlock is **commercial software** distributed with a **30-day free trial**:

1. **First install** → the 30-day trial starts automatically (no sign-up).
2. **During trial** → full functionality, no interruptions.
3. **After trial** → face unlock still works, but an upgrade reminder appears each session with a countdown.
4. **Purchase** → email **hananqaisar316@gmail.com** to buy a license. You'll receive a `.lic` file bound to your device's Hardware ID.
5. **Activate** → drop the `.lic` file into the license folder; the reminder disappears.

Your Hardware ID is shown inside the upgrade dialog and can be copied with one click.

---

## Changelog

### v2.012 — Current Release
- Smoother unlock animation: the success sequence (camera fade → sphere grow → lock open → hold → smooth fade) now plays in full (~1.6s) **before** the desktop unlocks. Previously login fired at ~0.45s and cut the animation off mid-play. Affects both Linux and Windows unlock UI.
- Real PyQt5 enrollment GUI on Linux: enrollment now opens a genuine Qt window (live preview + green face box + progress ring). The old code used `cv2.imshow`, which silently fell back to a text-only CLI under the headless OpenCV build. CLI enrollment remains as a clean fallback when no camera/display is present.
- Native packages for Debian (`.deb`), Fedora (`.rpm`) and Arch (`.pkg.tar.zst`), plus a universal one-file installer and the Windows zip. All Linux installers bundle offline ML wheels (~1 minute setup, no network).
- **Dynamic Island "Retry" after failed attempts:** when all 5 face attempts fail, the iOS-style pill now shows a circular retry icon instead of the face. Hovering gives a smooth professional glow; clicking plays a press animation and restarts the scan.
- **Smoother animation:** removed the deprecated `HighQualityAntialiasing` render hint (a major frame-drop source on Qt5/X11/XWayland/Windows) and stopped needless idle repaints, so the Face ID / Dynamic Island UI no longer stutters.
- **Attempts capped at 5** across the shipped bundle (`nova_bundle` config + data config) so installed systems enforce exactly 5 attempts before retry.
- **Windows release made easy:** the packaged zip now bundles offline Windows wheels for every dependency except `dlib` (no official Windows wheel exists upstream, so it compiles from source with CMake + VS Build Tools auto-installed). `install.bat` installs the bundled wheels with no network, then builds `dlib` — mirroring the Linux offline flow.
- **Wayland support (Ubuntu & friends):** the installer no longer force-disables Wayland. NovaUnlock runs on Wayland via XWayland (Qt uses the `xcb` platform plugin), so your Wayland session stays enabled and face unlock works on the lock screen.

### v1.32
- Windows 10/11 Credential Provider support (refined installer)
- Native packages for Debian (`.deb`), Fedora (`.rpm`) and Arch (`.pkg.tar.zst`)
- Anti-spoof blink liveness detection (adaptive EAR)
- GTK theme auto-switch (dark/light)
- Auto-lock on face leave (10s timeout)
- 30-day trial + paid license system with hardware-bound activation

---

## Support

NovaUnlock is a commercial product. For licensing, enterprise enquiries, or support:

- **Email:** [hananqaisar316@gmail.com](mailto:hananqaisar316@gmail.com)
- **Source & Releases:** [github.com/hananqaisar-commits/NovaUnlock](https://github.com/hananqaisar-commits/NovaUnlock)

*Secure your system with your face — not your password.*

---

<div align="center">

**Built by [Hanan Qaisar](https://github.com/hananqaisar-commits)**

</div>
