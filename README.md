# NovaUnlock

Face unlock for Linux. Lock your screen, walk away, come back — it recognizes you and unlocks. No password needed.

Built this because I wanted what my phone has. Everything I found was either broken, abandoned, or wanted to send your face to a cloud. Spent several days fighting PAM, X11 auth errors, LightDM internals, and window stacking until it worked. Putting it out here so nobody else has to.

Tested on Kali Linux + XFCE + LightDM.

---

## What it does

- Unlocks your lockscreen when it sees your face
- Logs you in at the LightDM login screen automatically
- Multiple users — each face only unlocks its own session
- 3 failed attempts closes the scanner, falls back to password
- Animated "Dynamic Island" style panel while scanning
- PulseAudio sound on unlock with ALSA fallback
- Everything local, nothing leaves your machine

---

## How it looks

Screen locks → small floating panel appears at top center with a scan animation. Camera on, scans silently. Match → sound plays, screen unlocks. No match → tries twice more, then disappears and normal lockscreen takes over.

At boot or user switch, face scanner runs in background. Match → you're logged in without touching anything.

---

## How it works

**Lock screen flow:**
```
xflock4
  → nova_xflock4_lock.sh
      → face_unlock_daemon.py
          → face_unlock_widget.py  (PyQt5 UI)
          → face_recognizer.py
          → PAM cache → xdotool unlock
```

**Login screen flow:**
```
LightDM greeter-setup-script
  → nova_unlock_greeter_hook.sh
      → nova_unlock_greeter_helper.sh
          → face_login_greeter.py
          → face match → temp autologin config → lightdm restart
```

The autologin config is deleted the moment your session opens. One use only.

---

## Requirements

Debian/Ubuntu with LightDM. Python 3.9+. Webcam.

```bash
sudo apt install -y \
    libpam-script xdotool python3-xlib \
    alsa-utils pulseaudio-utils xdpyinfo \
    cmake libboost-all-dev \
    python3 python3-pip python3-venv
```

```bash
pip install PyQt5 opencv-python face_recognition dlib numpy
```

`dlib` compiles from source, takes a few minutes. Normal.

---

## Install

```bash
git clone https://github.com/yourusername/NovaUnlock.git
cd NovaUnlock
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo bash install.sh
```

Installer sets up: PAM hook, xflock4 wrapper, LightDM greeter hooks, session cleanup, sudoers entry for lightdm restart, and autostart.

---

## Enroll your face

```bash
source .venv/bin/activate
python3 scripts/enroll.py
```

Enter your Linux username (same as `whoami`), look at the camera. Saves your embedding to `data/faces/yourusername.npy`. For multiple users, log in as each user and enroll separately.

```bash
python3 scripts/enroll.py --force   # re-enroll / overwrite
```

---

## Configuration

`data/config.yaml`:

```yaml
face:
  threshold: 0.42      # lower = stricter. range: 0.38–0.45
  max_attempts: 3
  camera_index: 0
  camera_width: 320
  camera_height: 240
```

False positives → lower to 0.38. Not recognizing you → raise to 0.45.

---

## Testing

```bash
# Demo the UI without locking anything
.venv/bin/python3 nova_unlock/ui/face_unlock_widget.py --demo

# Test lockscreen
xflock4

# Test login screen
xfce4-session-logout --logout --fast
```

---

## Troubleshooting

**UI not showing on lockscreen**
```bash
tail -50 /tmp/nova_xflock4.log
tail -50 /tmp/nova_lock_ui.err
tail -50 logs/face_auth.log
systemctl --user status nova-unlock-watcher
```

**Login screen not working**
```bash
sudo journalctl -u lightdm -n 50 --no-pager
tail -50 /tmp/nova_unlock_greeter.log
```

**Face not recognized**
Lighting matters a lot. Re-enroll in the same conditions you normally use the machine:
```bash
python3 scripts/enroll.py --force
```

**Camera not found**
```bash
python3 -c "
import cv2
for i in range(5):
    c = cv2.VideoCapture(i)
    print(f'camera {i}: {c.isOpened()}'
├── uninstall.sh
├── data/
│   ├── config.yaml
│   ├── face_user_map.json
│   └── faces/               ← enrolled)
    c.release()
"
```

---

## Project structure

```
NovaUnlock/
├── install.sh
├── uninstall.sh
├── data/
│   ├── config.yaml
│   ├── face_user_map.json
│   └── faces/               ← enrolled embeddings (.gitignored)
├── logs/
├── nova_unlock/
│   ├── core/
│   │   └── system_detect.py
│   ├── pam/
│   ├── security/
│   ├── ui/
│   │   ├── face_unlock_widget.py
│   │   └── face_id_embed.py
│   └── vision/
│       └── face_recognizer.py
└── scripts/
    ├── enroll.py
    ├── face_unlock_daemon.py
    ├── face_login_greeter.py
    └── nova_pam_auth.py
```

---

## Security

- Face embeddings stored locally as `.npy` files, no raw images
- Embeddings can't be reversed back to a photo
- PAM cache is mode 600, deleted after use
- Autologin config deleted on session start
- 3 failed attempts forces password fallback
- Each user profile only matches against their own session

Same threat model as Windows Hello or Android face unlock. Fine for a personal desktop.

---

## Uninstall

```bash
sudo bash uninstall.sh
```

---

## What's next

- Wayland support (currently X11 only)
- GNOME and KDE lockscreen support
- Anti-spoofing / liveness detection
- Raspberry Pi support
- PIN fallback option

---

## Contributing

Most useful right now: Wayland support and testing on different hardware. Open an issue before starting big work.

## License

MIT. Keep the copyright notice.

Copyright (c) 2026 Hanan Qaisar

---

*Built by a Pakistani Linux developer who just wanted face unlock on his machine. If it works for you, star the repo. If it doesn't, open an issue with your logs.*