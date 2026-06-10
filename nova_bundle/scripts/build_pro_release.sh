#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RELEASE_DIR="$ROOT_DIR/build/release"
BUNDLE_DIR="$RELEASE_DIR/nova_bundle"
OUTPUT="$ROOT_DIR/dist/nova_unlock_installer"

echo "Building protected NovaUnlock release..."

command -v python3 >/dev/null 2>&1 || {
    echo "python3 is required" >&2
    exit 1
}

python3 -m PyInstaller --version >/dev/null 2>&1 || {
    echo "PyInstaller is required. Install it in your build environment first." >&2
    exit 1
}

rm -rf "$RELEASE_DIR"
mkdir -p "$BUNDLE_DIR"

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

python3 -m compileall -q -b "$BUNDLE_DIR/nova_unlock" "$BUNDLE_DIR/scripts"
find "$BUNDLE_DIR/nova_unlock" "$BUNDLE_DIR/scripts" -name '*.py' -delete
find "$BUNDLE_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +

if find "$BUNDLE_DIR" -name '*.py' -print -quit | grep -q .; then
    echo "Release bundle still contains Python source files" >&2
    exit 1
fi

python3 -m PyInstaller \
    --clean \
    -y \
    --onefile \
    --name nova_unlock_installer \
    --distpath "$ROOT_DIR/dist" \
    --workpath "$ROOT_DIR/build/pyinstaller" \
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

echo
echo "Protected installer ready:"
echo "  $OUTPUT"
echo
echo "Share only this file with users. Do not share the repository, build/, or nova_bundle/."
