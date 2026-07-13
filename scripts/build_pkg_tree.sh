#!/usr/bin/env bash
#
# build_pkg_tree.sh — Stage a closed-source pyc tree for NovaUnlock native packages.
#
# Compiles the nova_unlock source + launcher scripts to .pyc at BUILD TIME using a
# Python interpreter matching the target distro, strips all .py source, and excludes
# the developer license + dev/test files. Output is a ready-to-package root layout.
#
# Usage:  scripts/build_pkg_tree.sh <python_bin> <out_root>
#
set -euo pipefail

PY_BIN="${1:?usage: build_pkg_tree.sh <python_bin> <out_root>}"
OUT_ROOT="${2:?usage: build_pkg_tree.sh <python_bin> <out_root>}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_NOVA="$REPO_ROOT/nova_unlock"
SRC_SCRIPTS="$REPO_ROOT/scripts"
STAGE_NOVA="$OUT_ROOT/opt/novaunlock"

echo "==> Staging NovaUnlock pyc tree"
echo "    python : $($PY_BIN --version 2>&1)"
echo "    out    : $STAGE_NOVA"

mkdir -p "$STAGE_NOVA/nova_unlock" "$STAGE_NOVA/scripts"

# 1) Copy nova_unlock source tree (exclude caches, tests, dev artifacts)
rsync -a --exclude '__pycache__' --exclude '*.pyc' --exclude '*.pyo' \
         --exclude 'tests' --exclude '.git' --exclude '*.egg-info' \
         "$SRC_NOVA/" "$STAGE_NOVA/nova_unlock/"

# 2) NEVER ship the developer's own lifetime license
rm -f "$STAGE_NOVA/nova_unlock/licensing/license_hanan_qaisar_lifetime.json"

# 3) Copy the launcher scripts we actually need at runtime
for s in face_unlock_daemon.py face_login_greeter.py nova_pam_auth.py \
         enroll_gui.py enroll.py enroll_entry.py; do
    if [ -f "$SRC_SCRIPTS/$s" ]; then
        cp "$SRC_SCRIPTS/$s" "$STAGE_NOVA/scripts/$s"
    fi
done

# 4) Cross-distro note: we SHIP .py source and compile to .pyc at INSTALL
#    time (postinst / %post / post_install) using the TARGET's python3.
#    Required because Debian-family Pythons differ (3.10–3.13), so a
#    build-time-compiled .pyc would not import on every target. After
#    install only .pyc remains (no .py in the installed tree).
#    Optional build-time precompile for single-version targets:
if [ "${NOVA_PRECOMPILE:-0}" = "1" ]; then
    "$PY_BIN" -m compileall -b -q "$STAGE_NOVA/nova_unlock" "$STAGE_NOVA/scripts"
    find "$STAGE_NOVA" -type f -name '*.py' -delete
    find "$STAGE_NOVA" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    echo "    precompiled with $($PY_BIN --version 2>&1)"
fi

# 5) Ship the post-install integration script (generates helpers + PAM + trial + service)
cp "$REPO_ROOT/scripts/nova_pkg_postinstall.sh" "$STAGE_NOVA/nova_pkg_postinstall.sh"

# 5a) Bundle the prebuilt offline wheels (dlib + face_recognition + face_recognition_models
#     + opencv/PyQt5/numpy/python-xlib/PyYAML/setuptools) so post-install can install the ML
#     stack with `pip --no-index` and NO network access. Without this the package ships no
#     wheels, post-install finds WHEELS_DIR missing, and dlib/face_recognition never install
#     (the offline import failure seen in the v1.32 Docker test).
if [ -d "$REPO_ROOT/wheels" ]; then
    echo "==> Staging offline wheels -> $STAGE_NOVA/wheels"
    mkdir -p "$STAGE_NOVA/wheels"
    cp -a "$REPO_ROOT/wheels/." "$STAGE_NOVA/wheels/"
    echo "    wheel dirs: $(ls -1 "$STAGE_NOVA/wheels" 2>/dev/null | tr '\n' ' ')"
else
    echo "!! WARNING: $REPO_ROOT/wheels MISSING — native post-install cannot install ML deps offline" >&2
fi

# 5b) Normalise permissions (Debian policy: files 0644, dirs 0755)
find "$STAGE_NOVA" -type d -exec chmod 0755 {} +
find "$STAGE_NOVA" -type f -exec chmod 0644 {} +
chmod 0755 "$STAGE_NOVA/nova_pkg_postinstall.sh"
[ -f "$STAGE_NOVA/nova_unlock/pam/pam_script_auth" ] && chmod 0755 "$STAGE_NOVA/nova_unlock/pam/pam_script_auth"

# 6) Sanity: no dev license leak; source present (compiled at install)
LEAK=$(find "$STAGE_NOVA" \( -name '*hanan*qaisar*' -o -name '*lifetime*' \) | wc -l)
PY_COUNT=$(find "$STAGE_NOVA" -name '*.py' | wc -l)
echo "    .py files : $PY_COUNT"
echo "    dev leak  : $LEAK  (must be 0)"
[ "$LEAK" -eq 0 ] && [ "$PY_COUNT" -gt 0 ] \
    || { echo "!! staging failed (leak=$LEAK py=$PY_COUNT) — aborting"; exit 1; }

echo "==> Staged OK: $STAGE_NOVA"
