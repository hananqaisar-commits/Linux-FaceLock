# NovaUnlock Windows (v6.35)

This branch contains the securely packaged, binary-only installer for **NovaUnlock v6.35** on Windows.
No proprietary `.py` source code is exposed in this distribution. All backend logic is natively compiled for Python 3.11 bytecode to ensure flawless `dlib` compatibility.

### Updates in v6.35
* **Fixed:** Bad Magic Number (.pyc) mismatches for Windows-native scripts (`windows_enroll_face`, `windows_enroll_password`, `windows_daemon`).
* **Fixed:** Completely isolated Python 3.11 dynamic compilation inside the packager to avoid Python 3.13 developer-side conflicts.
* **Fixed:** Simplified `cv2.VideoCapture(0)` camera initialization to prevent VirtualBox/VM crashes caused by problematic OpenCV backends (`CAP_DSHOW` / `CAP_MSMF`).

See the GitHub Release page to download the `.exe` installer.
