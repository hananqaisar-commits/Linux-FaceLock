#!/usr/bin/env bash
#
# build_rpm.sh — Build NovaUnlock-v${VERSION:-5.4}-Fedora.rpm
# Pyc compiled with CPython 3.12 (matches Fedora 39). Falls back to shipping
# .py + %post compile if a 3.12 interpreter is unavailable.
#
set -euo pipefail

VERSION="${VERSION:-2.014}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE="$REPO/build/release"
OUT="$RELEASE/NovaUnlock-v$VERSION-Fedora.rpm"

PY312="/home/hanan/py312/bin/python3.12"
FALLBACK=0
if [ ! -x "$PY312" ]; then
    echo "!! python3.12 not found at $PY312 — using fallback (ship .py, %post compiles)"
    FALLBACK=1
    PY312="python3.12"
fi

WORK="$(mktemp -d)"
STAGE="$WORK/root"
TOPDIR="$WORK/rpmbuild"
mkdir -p "$TOPDIR/"{BUILD,RPMS,SRPMS,SOURCES,SPECS}

echo "==> Staging pyc tree (python $PY312)"
if [ "$FALLBACK" -eq 0 ]; then
    bash "$REPO/scripts/build_pkg_tree.sh" "$PY312" "$STAGE"
else
    # Fallback: copy source .py (postinstall/%post will compile on target)
    mkdir -p "$STAGE/opt/novaunlock"
    rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude 'tests' \
        "$REPO/nova_unlock/" "$STAGE/opt/novaunlock/nova_unlock/"
    rm -f "$STAGE/opt/novaunlock/nova_unlock/licensing/license_hanan_qaisar_lifetime.json"
    mkdir -p "$STAGE/opt/novaunlock/scripts"
    for s in face_unlock_daemon.py face_login_greeter.py nova_pam_auth.py enroll_gui.py enroll.py enroll_entry.py; do
        [ -f "$REPO/scripts/$s" ] && cp "$REPO/scripts/$s" "$STAGE/opt/novaunlock/scripts/$s"
    done
    cp "$REPO/scripts/nova_pkg_postinstall.sh" "$STAGE/opt/novaunlock/nova_pkg_postinstall.sh"
    chmod 755 "$STAGE/opt/novaunlock/nova_pkg_postinstall.sh"
fi

# Static integration files
mkdir -p "$STAGE/usr/lib/systemd/user" "$STAGE/etc/xdg/autostart"
cat > "$STAGE/usr/lib/systemd/user/nova-unlock-watcher.service" << 'UNIT'
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

cat > "$STAGE/etc/xdg/autostart/nova-unlock-watcher.desktop" << 'DESK'
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

# Tarball the staged tree as SOURCE0
tar -C "$STAGE" -czf "$TOPDIR/SOURCES/novaunlock-tree.tar.gz" .

# Spec
cat > "$TOPDIR/SPECS/novaunlock.spec" << SPEC
Name:           novaunlock
Version:        ${VERSION}
Release:        1%{?dist}
Summary:        Next-generation face authentication for Linux
License:        Proprietary
URL:            https://github.com/hananqaisar-commits/NovaUnlock
BuildArch:      x86_64
Source0:        novaunlock-tree.tar.gz
Requires:       python3, python3-pip, python3-qt5, python3-opencv, python3-numpy, python3-pyyaml, python3-xlib, pam_script

%description
NovaUnlock is a commercial biometric face-unlock system with a Dynamic
Island UI, PAM integration and privacy-first local processing. It ships
as closed-source bytecode with a 30-day trial; a paid license is required
for continued use. dlib / face_recognition are installed automatically on
first run if missing.

%prep
%build
%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
tar -C %{buildroot} -xzf %{SOURCE0}

%post
# The shared postinstall (ensure_runtime_deps) pip-installs dlib / face_recognition
# into the SYSTEM site-packages with --break-system-packages. Do NOT use
# `pip install --user` here: the daemon runs as root / system python, which does
# not consult user-site (PEP 370 disables it for uid 0), so --user installs would
# never be importable at runtime.
[ -x /opt/novaunlock/nova_pkg_postinstall.sh ] && /opt/novaunlock/nova_pkg_postinstall.sh configure || true

%preun
[ -x /opt/novaunlock/nova_pkg_postinstall.sh ] && /opt/novaunlock/nova_pkg_postinstall.sh remove || true

%postun
rm -rf /opt/novaunlock
rm -f /var/lib/novaunlock/pam_cache.json
rm -rf /var/log/novaunlock

%files
/opt/novaunlock
/usr/lib/systemd/user/nova-unlock-watcher.service
/etc/xdg/autostart/nova-unlock-watcher.desktop

%changelog
* Fri Jul 10 2026 Hanan Qaisar <hananqaisar316@gmail.com> - ${VERSION}-1
- Native Fedora package with closed-source pyc tree, PAM, trial, guard service.
SPEC

echo "==> rpmbuild"
rpmbuild --define "_topdir $TOPDIR" --define "_rpmdbpath /tmp/nova_rpmdb" -bb "$TOPDIR/SPECS/novaunlock.spec" 2>&1 | tail -15
RPM=$(find "$TOPDIR/RPMS" -name "novaunlock-${VERSION}-1.*.rpm" | head -1)
if [ -n "$RPM" ]; then
    mkdir -p "$RELEASE"
    cp "$RPM" "$OUT"
    echo "==> Built: $OUT ($(stat -c %s "$OUT") bytes)"
else
    echo "!! rpm build failed"; exit 1
fi

rm -rf "$WORK"
echo "==> Done."
