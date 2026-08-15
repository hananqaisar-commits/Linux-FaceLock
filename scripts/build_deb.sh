#!/usr/bin/env bash
#
# build_deb.sh — Build NovaUnlock-v${VERSION:-2.21}-Debian.deb
# Pyc compiled with host python3.11 (matches Debian 12 / Kali 3.11).
#
set -euo pipefail

VERSION="3.2"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="$REPO/build/release"
WORK="$(mktemp -d)"
ROOT="$WORK/root"
OUT="$RELEASE/NovaUnlock-v$VERSION-Debian.deb"

PY_BIN="${PY_BIN:-python3}"
PKG_ARCH="amd64"

echo "==> Building Debian package in $WORK"

# 1) Stage closed-source pyc tree
bash "$REPO/scripts/build_pkg_tree.sh" "$PY_BIN" "$ROOT"

# 2) Static system integration files (package-owned → clean removal)
mkdir -p "$ROOT/usr/lib/systemd/user" "$ROOT/usr/lib/systemd/system" "$ROOT/etc/xdg/autostart"

install -m 0644 "$REPO/systemd/nova-facelock.service" \
    "$ROOT/usr/lib/systemd/system/nova-facelock.service"

cat > "$ROOT/usr/lib/systemd/user/nova-unlock-watcher.service" << 'UNIT'
[Unit]
Description=NovaUnlock Face Presence Guard
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=/bin/bash -c '/usr/bin/python3 /opt/novaunlock/scripts/face_unlock_daemon.pyc --guard'
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=NOVA_FACES_DIR=/var/lib/novaunlock/faces

[Install]
WantedBy=graphical-session.target
UNIT

cat > "$ROOT/etc/xdg/autostart/nova-unlock-watcher.desktop" << 'DESK'
[Desktop Entry]
Type=Application
Name=NovaUnlock Watcher
Exec=/usr/local/bin/nova_unlock_watcher.sh
Comment=NovaUnlock face authentication watcher
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
DESK

# 3) DEBIAN control + maintainer scripts
mkdir -p "$ROOT/DEBIAN"
cat > "$ROOT/DEBIAN/control" <<CTRL
Package: novaunlock
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${PKG_ARCH}
Depends: python3 (>= 3.11), python3-pip, python3-pyqt5, python3-opencv, python3-numpy, python3-yaml, python3-xlib, libpam-runtime, libpam-script
Recommends: libqt5svg5, pulseaudio-utils, dbus
Maintainer: Hanan Qaisar <hananqaisar316@gmail.com>
Description: Next-generation face authentication for Linux
 NovaUnlock is a commercial biometric face-unlock system with a Dynamic
 Island UI, PAM integration and privacy-first local processing. It ships
 as closed-source bytecode with a 30-day trial; a paid license is required
 for continued use.
CTRL

# 2b) Documentation (copyright + changelog) to satisfy lintian
mkdir -p "$ROOT/usr/share/doc/novaunlock"
cat > "$ROOT/usr/share/doc/novaunlock/copyright" << 'COPY'
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: NovaUnlock
Source: proprietary (commercial, no public source)

Copyright: 2024-2026 Hanan Qaisar <hananqaisar316@gmail.com>
License: Proprietary
 This software is distributed under a commercial license. Source code is
 not included. A 30-day trial is included; continued use requires a paid
 license obtained from hananqaisar316@gmail.com.
COPY

cat > "$ROOT/usr/share/doc/novaunlock/changelog" <<CHG
novaunlock (${VERSION}) stable; urgency=medium

  * Native Debian package bundling the closed-source pyc tree.
  * PAM integration, 30-day trial initialisation, guard service.

 -- Hanan Qaisar <hananqaisar316@gmail.com>  Thu, 10 Jul 2026 00:00:00 +0000
CHG
gzip -9n "$ROOT/usr/share/doc/novaunlock/changelog"

cat > "$ROOT/DEBIAN/postinst" << 'PI'
#!/bin/bash
set -e
if [ "$1" = "configure" ]; then
    [ -x /opt/novaunlock/nova_pkg_postinstall.sh ] && \
        /opt/novaunlock/nova_pkg_postinstall.sh configure || true
fi
PI
chmod 755 "$ROOT/DEBIAN/postinst"

cat > "$ROOT/DEBIAN/prerm" << 'PR'
#!/bin/bash
set -e
if [ "$1" = "remove" ] || [ "$1" = "upgrade" ]; then
    [ -x /opt/novaunlock/nova_pkg_postinstall.sh ] && \
        /opt/novaunlock/nova_pkg_postinstall.sh remove || true
fi
PR
chmod 755 "$ROOT/DEBIAN/prerm"

cat > "$ROOT/DEBIAN/postrm" << 'POR'
#!/bin/bash
set -e
if [ "$1" = "purge" ] || [ "$1" = "remove" ]; then
    rm -rf /opt/novaunlock
    rm -f /var/lib/novaunlock/pam_cache.json
    rm -rf /var/log/novaunlock
fi
POR
chmod 755 "$ROOT/DEBIAN/postrm"

# 3b) lintian overrides — /opt + shipped .pyc are intentional for this
#     closed-source third-party commercial package.
cat > "$ROOT/DEBIAN/lintian-overrides" << 'LO'
dir-or-file-in-opt
package-installs-python-bytecode
file-in-etc-not-marked-as-conffile
LO

# 4) Build + lint
# --root-owner-group makes a reproducible package without fakeroot. Use zstd
# instead of the host xz path, which has produced corrupt control archives on
# some Kali builds with very large offline wheel bundles.
dpkg-deb --root-owner-group -Zzstd --build "$ROOT" "$OUT"
# A successful exit is not sufficient: validate both the control and data
# archives before a checksum can be generated or the package released.
dpkg-deb --info "$OUT" >/dev/null
dpkg-deb --contents "$OUT" >/dev/null
sha256sum "$OUT" > "$OUT.sha256"
echo "==> Built: $OUT ($(stat -c %s "$OUT") bytes)"
echo "==> lintian (dir-or-file-in-opt + package-installs-python-bytecode are"
echo "    expected/benign for a closed-source third-party /opt package):"
lintian "$OUT" 2>&1 | head -40 || true

rm -rf "$WORK"
echo "==> Done."
