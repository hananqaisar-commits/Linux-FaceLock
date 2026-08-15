#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="3.2"

RELEASE_DIR="$ROOT_DIR/build/release/linux-v$VERSION"
BUNDLE_DIR="$RELEASE_DIR/nova_bundle"
DIST_DIR="$ROOT_DIR/dist"
OUTPUT="$DIST_DIR/nova_unlock_installer_v$VERSION"
PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-$ROOT_DIR/build/pyinstaller-cache}"

echo "Building protected NovaUnlock release..."

command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    echo "$PYTHON_BIN is required" >&2
    exit 1
}

"$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1 || {
    echo "PyInstaller is required. Install it in your build environment first." >&2
    exit 1
}

rm -rf "$RELEASE_DIR"
mkdir -p "$BUNDLE_DIR" "$DIST_DIR" "$PYINSTALLER_CONFIG_DIR"

mkdir -p \
    "$BUNDLE_DIR/config" \
    "$BUNDLE_DIR/data/faces" \
    "$BUNDLE_DIR/nova_unlock" \
    "$BUNDLE_DIR/scripts"

cp -a "$ROOT_DIR/nova_unlock/." "$BUNDLE_DIR/nova_unlock/"
cp -a "$ROOT_DIR/scripts/." "$BUNDLE_DIR/scripts/"
# Include nova_facelock_service.sh in bundle
cp "$ROOT_DIR/scripts/nova_facelock_service.sh" "$BUNDLE_DIR/scripts/nova_facelock_service.sh"
chmod +x "$BUNDLE_DIR/scripts/nova_facelock_service.sh"

cp -a "$ROOT_DIR/data/config.yaml" "$BUNDLE_DIR/data/config.yaml"
cp -a "$ROOT_DIR/config/nova.conf" "$BUNDLE_DIR/config/nova.conf"
rm -f "$BUNDLE_DIR/scripts/build_pro_release.sh"
find "$BUNDLE_DIR/scripts" -maxdepth 1 \( -name 'windows_*.py' -o -name 'windows_*.pyc' -o -name 'build_pro_release.sh.bak*' -o -name '*.bak*' -o -name '*.orig' \) -delete
# Remove build/CI/Windows/Docker scripts — not needed by end users
rm -f \
    "$BUNDLE_DIR/scripts/build_deb.sh" \
    "$BUNDLE_DIR/scripts/build_rpm.sh" \
    "$BUNDLE_DIR/scripts/build_arch.sh" \
    "$BUNDLE_DIR/scripts/build_pkg_tree.sh" \
    "$BUNDLE_DIR/scripts/build_windows_release.sh" \
    "$BUNDLE_DIR/scripts/upload_github_release.sh" \
    "$BUNDLE_DIR/scripts/audit_release_artifacts.sh" \
    "$BUNDLE_DIR/scripts/vendor_wheels.sh" \
    "$BUNDLE_DIR/scripts/nova_docker_check.sh" \
    "$BUNDLE_DIR/scripts/test_releases_docker.sh" \
    "$BUNDLE_DIR/scripts/capture_demo.sh" \
    "$BUNDLE_DIR/scripts/windows_daemon.pyc" \
    "$BUNDLE_DIR/scripts/windows_enroll_face.pyc" \
    "$BUNDLE_DIR/scripts/windows_enroll_password.pyc"
# The product entrypoint is nova_unlock/ui/enrollment_wizard.py.  Do not ship
# legacy CLI/GUI enrollment launchers that could bypass its flow.
rm -f "$BUNDLE_DIR/scripts/enroll.py" \
      "$BUNDLE_DIR/scripts/enroll_gui.py" \
      "$BUNDLE_DIR/scripts/enroll_entry.py"
# License issuance is operator-only. The release contains the offline
# validator, never the private generator or developer activation.
rm -f \
    "$BUNDLE_DIR/nova_unlock/licensing/license_generator.py" \
    "$BUNDLE_DIR/nova_unlock/licensing/license_generator.pyc" \
    "$BUNDLE_DIR/nova_unlock/licensing/license_signer.py" \
    "$BUNDLE_DIR/nova_unlock/licensing/license_signer.pyc" \
    "$BUNDLE_DIR/nova_unlock/licensing/license_hanan_qaisar_lifetime.json"

# Bundle ALL Linux offline wheels (cp311/cp312/cp313) so installs work
# offline across different distro Python versions. Never bundle win_amd64 here.
if [ -d "$ROOT_DIR/wheels" ]; then
    echo "==> Bundling offline Linux wheels -> $BUNDLE_DIR/wheels"
    mkdir -p "$BUNDLE_DIR/wheels"
    copied=0
    for d in "$ROOT_DIR"/wheels/cp3*; do
        [ -d "$d" ] || continue
        cp -a "$d" "$BUNDLE_DIR/wheels/"
        echo "==> Copied wheels/$(basename "$d")"
        copied=1
    done
    [ "$copied" -eq 1 ] || echo "!! WARNING: no Linux cp3xx wheel dirs found" >&2
else
    echo "!! WARNING: $ROOT_DIR/wheels MISSING — installer cannot build venv offline" >&2
fi

"$PYTHON_BIN" -m compileall -q -b "$BUNDLE_DIR/nova_unlock" "$BUNDLE_DIR/scripts"
find "$BUNDLE_DIR/nova_unlock" "$BUNDLE_DIR/scripts" -name '*.py' -delete
find "$BUNDLE_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +

if find "$BUNDLE_DIR" -name '*.py' -print -quit | grep -q .; then
    echo "Release bundle still contains Python source files" >&2
    exit 1
fi

if find "$BUNDLE_DIR" \( -iname '*hanan*qaisar*' -o -name 'license_generator.py' -o -name 'license_generator.pyc' -o -name 'license_signer.py' -o -name 'license_signer.pyc' \) -print -quit | grep -q .; then
    echo "Release bundle contains private license-issuance material" >&2
    exit 1
fi

"$PYTHON_BIN" -m PyInstaller \
    --clean \
    -y \
    --onefile \
    --name "nova_unlock_installer_v$VERSION" \
    --distpath "$DIST_DIR" \
    --workpath "$ROOT_DIR/build/pyinstaller/linux-v$VERSION" \
    --specpath "$RELEASE_DIR" \
    --add-data "$BUNDLE_DIR:nova_bundle" \
    --add-data "$ROOT_DIR/install.sh:." \
    --hidden-import subprocess \
    --hidden-import shutil \
    --hidden-import pathlib \
    "$ROOT_DIR/installer_main.py"

if [ ! -x "$OUTPUT" ]; then
    echo "Expected installer was not created: $OUTPUT" >&2
    exit 1
fi

sha256sum "$OUTPUT" > "$OUTPUT.sha256"

if strings "$OUTPUT" | grep -E '\.py$|\.cpp$|\.hpp$|\.h$' >/dev/null 2>&1; then
    echo "Warning: binary string audit found source-looking paths. Inspect before release." >&2
fi

echo
echo "Protected installer ready:"
echo "  $OUTPUT"
echo "  $OUTPUT.sha256"
echo
echo "Share only this file with users. Do not share the repository, build/, or nova_bundle/."
