# NovaUnlock Windows (v6.34)

This branch contains the securely packaged, binary-only installer for **NovaUnlock v6.34** on Windows.
No proprietary `.py` source code is exposed in this distribution. All backend logic is natively compiled for Python 3.11 bytecode to ensure flawless `dlib` compatibility.

### Updates in v6.34
* **Fixed:** Bad Magic Number (.pyc) mismatches for Windows-native scripts (`windows_enroll_face`, `windows_enroll_password`, `windows_daemon`).
* **Fixed:** Completely isolated Python 3.11 dynamic compilation inside the packager to avoid Python 3.13 developer-side conflicts.

See the GitHub Release page to download the `.exe` installer.
