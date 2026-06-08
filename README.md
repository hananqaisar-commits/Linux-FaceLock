# NovaUnlock

NovaUnlock is a local Linux face unlock system for desktop login and lock-screen authentication. It uses a PyQt5 camera UI, local face embeddings, PAM integration, and LightDM/XFCE hooks so a recognized enrolled user can unlock their own session without sending face data to a cloud service.

Tested primary target: Kali Linux, XFCE, LightDM, X11, Python 3.13.

## Features

- PyQt5 face unlock panel for lock-screen scanning
- PyQt5 enrollment wizard with live camera preview
- Automatic five-angle enrollment: front, left, right, up, down
- Face encodings stored locally in `data/faces/`
- Multi-user support with one face profile per Linux user
- Configurable recognition threshold, timeout, attempts, angle count, UI, audio, and security flags in `config/nova.conf`
- Password fallback after timeout or repeated recognition failure
- Password fallback authenticates through Linux PAM using `libpam`
- GUI error dialogs for missing camera, missing enrollment, low light, and spoof warnings
- Basic liveness and anti-spoof checks using blink tracking and texture analysis when dependencies/models are available
- LightDM greeter hook for login flow
- XFCE lock-screen watcher and PAM cache flow for unlock
- Local-only storage: no cloud calls and no raw face images saved

## Installation

### Install from a private binary release

If you are installing NovaUnlock for another Linux user and do not want to share the source code, build a protected installer on your machine:

```bash
cd NovaUnlock
chmod +x scripts/build_pro_release.sh
./scripts/build_pro_release.sh
```

Give the other user only this file:

```text
dist/nova_unlock_installer
```

They install it with:

```bash
chmod +x nova_unlock_installer
sudo ./nova_unlock_installer
```

The installer extracts a sourceless runtime under `~/NovaUnlock`, configures dependencies and PAM integration, and prints the enrollment command when it finishes. Do not distribute the repository, `build/`, or `nova_bundle/` if you want to keep the source private.

### Install from source

```bash
git clone https://github.com/yourusername/NovaUnlock.git
cd NovaUnlock
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo bash install.sh
```

The installer configures system packages, Python dependencies, PAM integration, the lock-screen wrapper, the watcher, LightDM hooks when available, sudoers entries for display-manager restart, and `uninstall.sh`.

## Enrollment Guide

Launch the GUI enrollment wizard:

```bash
cd ~/Desktop/NovaUnlock
source .venv/bin/activate
python3 scripts/enroll_gui.py
```

In the wizard:

1. Select the Linux user account to enroll.
2. Confirm the live camera preview detects your face.
3. Let NovaUnlock automatically capture front, left, right, up, and down angles.
4. Wait for the "Enrollment Complete" screen.

Enrollment saves the averaged face encoding to `data/faces/<username>.npy` and metadata to `data/faces/users_meta.json`.

## Configuration

Edit `config/nova.conf`:

```ini
[recognition]
threshold = 0.5
timeout = 10
max_attempts = 3
angles = 5

[ui]
theme = dark
show_camera_preview = true
animation = true

[audio]
success_sound = true
fail_sound = true

[security]
liveness_check = true
anti_spoof = true
```

Lower `threshold` values are stricter. Increase it only if recognition is reliable but too strict in your lighting conditions.

## Supported Distros and Desktop Environments

| Distro family | Package manager | Lock screen | Greeter login | Status |
| --- | --- | --- | --- | --- |
| Kali / Debian / Ubuntu | `apt` | XFCE supported | LightDM supported | Primary target |
| Fedora / RHEL | `dnf` / `yum` | Partial | GDM greeter not supported | Experimental |
| Arch | `pacman` | Partial | SDDM greeter not supported | Experimental |
| openSUSE | `zypper` | Partial | Depends on DM | Experimental |

| Desktop environment | Lock integration | Notes |
| --- | --- | --- |
| XFCE | Supported | Primary target with `xfce4-screensaver` or LightDM lock flow |
| GNOME | Partial | Manual shortcut binding may be required |
| KDE Plasma | Partial | Manual shortcut binding may be required |
| MATE | Partial | PAM file configured when detected |
| Cinnamon | Partial | PAM file configured when detected |

## Screenshots

Screenshots will be added here:

- Enrollment wizard
- Face unlock panel
- Password fallback screen
- Error dialogs

## Testing

```bash
# Demo the animated face unlock UI
.venv/bin/python3 nova_unlock/ui/face_unlock_widget.py --demo

# Run GUI enrollment
python3 scripts/enroll_gui.py

# Test lock screen flow
xflock4
```

## Troubleshooting

Check logs:

```bash
tail -50 logs/face_auth.log
tail -50 logs/watcher.log
tail -50 /tmp/nova_xflock4.log
tail -50 /tmp/nova_lock_ui.err
sudo journalctl -u lightdm -n 50 --no-pager
```

If no camera is detected, verify OpenCV can see it:

```bash
python3 - <<'PY'
import cv2
for i in range(5):
    cap = cv2.VideoCapture(i)
    print(f"camera {i}: {cap.isOpened()}")
    cap.release()
PY
```

If recognition fails repeatedly, improve lighting and re-run:

```bash
python3 scripts/enroll_gui.py
```

## Project Structure

```text
NovaUnlock/
├── config/nova.conf
├── data/
│   ├── config.yaml
│   └── faces/
├── install.sh
├── installer_main.py
├── scripts/build_pro_release.sh
├── nova_unlock/
│   ├── core/
│   ├── pam/
│   ├── security/
│   ├── ui/
│   └── vision/
├── requirements.txt
└── scripts/
```

## Uninstall

```bash
sudo bash uninstall.sh
```

## License

NovaUnlock is released under the license included in `LICENSE`.
