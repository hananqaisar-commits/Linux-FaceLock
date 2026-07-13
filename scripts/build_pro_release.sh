#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-5.4}"
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
cp -a "$ROOT_DIR/data/config.yaml" "$BUNDLE_DIR/data/config.yaml"
cp -a "$ROOT_DIR/config/nova.conf" "$BUNDLE_DIR/config/nova.conf"
rm -f "$BUNDLE_DIR/scripts/build_pro_release.sh"

# Bundle the prebuilt offline wheels so the installer can create the venv WITHOUT
# network access. setup_flow.py installs from nova_bundle/wheels with --no-index.
if [ -d "$ROOT_DIR/wheels" ]; then
    echo "==> Bundling offline wheels -> $BUNDLE_DIR/wheels"
    mkdir -p "$BUNDLE_DIR/wheels"
    cp -a "$ROOT_DIR/wheels/." "$BUNDLE_DIR/wheels/"
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
