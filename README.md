# NovaUnlock

Face unlock for Linux. Lock your screen, walk away, come back — it recognizes you and unlocks. No password.

I built this for myself because I wanted what my phone has. Everything I found online was either broken, abandoned, or required sending your face to some cloud. So I spent several days fighting with PAM, X11 authorization errors, LightDM internals, and window stacking issues until it worked. Now it does. Putting it out here so nobody else has to go through the same pain.

Tested on Kali Linux + XFCE + LightDM. Should work on any Debian/Ubuntu system with the same setup.

---

## What it does

- Unlocks your lockscreen when it sees your face
- Logs you in at the LightDM login screen without touching anything
- Multiple users — each person's face only unlocks their own session
- 3 failed attempts closes the scanner and falls back to your password
- Animated panel appears at the top of your screen while scanning
- Everything stays on your machine, nothing goes anywhere

---

## How it looks

When your screen locks, a small floating panel appears at the top center with a dot animation. Camera turns on, scans silently. Recognized — plays a sound and unlocks. Not recognized — tries twice more, then disappears and your normal lockscreen takes over.

At boot or user switch, it runs in the background and logs you straight in if your face matches.

---

## Requirements

Any Debian/Ubuntu distro with LightDM. Python 3.9+. A webcam.

```bash
sudo apt install -y \
    python3 python3-pip python3-venv \
    libpam-script \
    xdotool \
    cmake \
    libboost-python-dev \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    python3-xlib \
    alsa-utils
```

```bash
pip install \
    PyQt5 \
    face_recognition \
    opencv-python \
    dlib \
    numpy \
    python-xlib \
    PyYAML
```

`dlib` takes a few minutes — it compiles from source. That's normal.

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

The installer sets up the PAM hook, LightDM greeter hook, systemd user service, and autostart entry.

---

## Enroll your face

```bash
python3 scripts/enroll.py
```

Enter your Linux username (same as `whoami`), look at the camera, done. Collects 30 samples and saves your face embedding locally at `data/faces/yourusername.npy`.

For multiple users, log in as each user and run enroll separately.

```bash
# To re-enroll and overwrite
python3 scripts/enroll.py --force
```

---

## Configuration

`data/config.yaml`:

```yaml
face:
  threshold: 0.42      # lower = stricter. try 0.38-0.45
  max_attempts: 3
  camera_index: 0
  camera_width: 320
  camera_height: 240
```

Getting false positives → lower threshold to 0.38 or 0.40.  
Your face not being recognized → raise it a bit to 0.45.

---

## How the lockscreen part works

`xfce4-screensaver` locks normally. A watcher process sits in the background monitoring DBus. When it sees the lock signal, it spawns the NovaUnlock UI — a transparent window embedded on top of the lockscreen via X11 window reparenting.

When your face matches, it writes a short-lived cache file and calls PAM. PAM reads the cache and unlocks without prompting for a password. The cache expires in 15 seconds so if PAM misses it, you just enter your password normally.

## How the login screen part works

LightDM has a `greeter-setup-script` hook that runs when the greeter starts. NovaUnlock registers here. At boot or user switch, a face scanner runs in the background. On match, it writes a temporary autologin config for your user and restarts LightDM. LightDM logs you in directly.

The autologin config is deleted the moment your session opens via `session-setup-script`. One-time use.

---

## Security

- Face data stored as numpy embedding files, local only
- No raw photos saved anywhere
- Embeddings can't be reversed back into your photo
- PAM cache file is mode 600, expires after 15 seconds
- Autologin config deleted on session start
- 3 failed attempts forces password
- Each user's profile only matches against their own session

Same threat model as Windows Hello or Android face unlock. Not military grade, but reasonable for a personal desktop.

---

## Troubleshooting

**UI not showing on lockscreen**
```bash
tail -f /tmp/nova_unlock_face_auth.log
systemctl --user status nova-unlock-watcher
```

**Face not being recognized**  
Lighting matters more than you'd think. Re-enroll in the same conditions you normally use the machine:
```bash
python3 scripts/enroll.py --force
```

**Login screen not working**
```bash
sudo journalctl -u lightdm -n 50 --no-pager
cat /tmp/nova_unlock_greeter.log
```

**Camera not found**
```bash
python3 -c "
import cv2
for i in range(5):
    c = cv2.VideoCapture(i)
    print(f'camera {i}: {c.isOpened()}')
    c.release()
"
```

**dlib won't install**
```bash
sudo apt install -y cmake libboost-all-dev
pip install dlib --verbose
```

---

## Project structure

```
NovaUnlock/
├── nova_unlock/
│   ├── ui/
│   │   └── face_unlock_widget.py     PyQt5 animated UI
│   ├── vision/
│   │   ├── face_recognizer.py        recognition engine
│   │   └── face_enroller.py          enrollment
│   ├── security/
│   │   └── face_auth_pam.py          PAM integration
│   └── pam/
│       └── pam_script_auth           PAM hook (bash)
├── scripts/
│   ├── enroll.py
│   ├── face_unlock_daemon.py         lockscreen daemon
│   └── face_login_greeter.py         LightDM daemon
├── data/
│   ├── faces/                        enrolled embeddings (.gitignored)
│   └── config.yaml
├── install.sh
├── requirements.txt
└── README.md
```

---

## What's next

- Wayland support (currently X11 only)
- GNOME and KDE lockscreen support  
- Anti-spoofing so a printed photo can't unlock
- Raspberry Pi
- PIN fallback option

---

## Contributing

Most needed right now: Wayland support and testing on different hardware setups. Open an issue before starting big work so we can align.

## License

MIT. Do whatever you want, keep the copyright notice.

Copyright (c) 2026 Hanan Qaisar

---

*Built by a Pakistani developer who just wanted face unlock on his machine. If it works for you, star the repo. 
