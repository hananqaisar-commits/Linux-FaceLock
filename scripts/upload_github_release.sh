#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-2.014}"
TAG="v$VERSION"
TITLE="NovaUnlock v$VERSION"

ASSETS=(
    "$ROOT_DIR/dist/nova_unlock_installer_v$VERSION"
    "$ROOT_DIR/dist/nova_unlock_installer_v$VERSION.sha256"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Debian.deb"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Debian.deb.sha256"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Fedora.rpm"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Fedora.rpm.sha256"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Arch.pkg.tar.zst"
    "$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Arch.pkg.tar.zst.sha256"
    "$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.zip"
    "$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.zip.sha256"
    "$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.exe"
    "$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.exe.sha256"
    "$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.manifest.txt"
)

"$ROOT_DIR/scripts/audit_release_artifacts.sh"

# Windows binaries are built on a separate Windows host and may be absent here.
# Skip (warn) missing assets instead of hard-failing so a Linux-only publish works.
UPLOAD=()
for asset in "${ASSETS[@]}"; do
    if [ -f "$asset" ]; then
        UPLOAD+=("$asset")
    else
        echo "!! Skipping missing asset (not built on this host): $asset"
    fi
done

if [ "${#UPLOAD[@]}" -eq 0 ]; then
    echo "No release assets present to upload." >&2
    exit 1
fi

# Remove any pre-existing release for this tag (including a half-made DRAFT from a
# previous interrupted run) so we always create a clean, fully-populated release.
# `gh release delete` (a draft) does not always remove the tag ref, so clean it up.
if gh release view "$TAG" >/dev/null 2>&1; then
    echo "!! Removing pre-existing release for $TAG (will recreate cleanly)"
    gh release delete "$TAG" --yes --cleanup-tag >/dev/null 2>&1 || true
fi

notes_file="$(mktemp)"
cat > "$notes_file" << NOTES
NovaUnlock v$VERSION binary release. Offline ML stack bundled: dlib + face_recognition prebuilt (Linux native packages and the universal installer ship prebuilt dlib; the Windows package bundles a prebuilt dlib wheel so setup is a fully offline 1-2 minutes, no compilation needed).

Assets:
- NovaUnlock-v$VERSION-Debian.deb: native package for Ubuntu/Debian/Kali/Mint/Pop!_OS (apt).
- NovaUnlock-v$VERSION-Fedora.rpm: native package for Fedora/RHEL/openSUSE (dnf).
- NovaUnlock-v$VERSION-Arch.pkg.tar.zst: native package for Arch/Manjaro (pacman).
- nova_unlock_installer_v$VERSION: universal Linux one-file installer for any distro.
- nova_unlock_windows_v$VERSION.zip: Windows runtime package with prebuilt dlib wheel (source files stripped).
- *.sha256: integrity checksums for each asset.
- nova_unlock_windows_v$VERSION.manifest.txt: Windows package audit details.

No source archive is uploaded by this script.
NOTES
gh release create "$TAG" "${UPLOAD[@]}" --title "$TITLE" --latest --notes-file "$notes_file"
rm -f "$notes_file"

echo "Uploaded binary assets to GitHub release $TAG"
