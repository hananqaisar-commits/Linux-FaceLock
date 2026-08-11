#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="2.21"
LINUX_BIN="$ROOT_DIR/dist/nova_unlock_installer_v$VERSION"
WINDOWS_ZIP="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.zip"
WINDOWS_EXE="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.exe"
DEB="$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Debian.deb"
RPM="$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Fedora.rpm"
ARCH="$ROOT_DIR/build/release/NovaUnlock-v$VERSION-Arch.pkg.tar.zst"

fail=0

check_file() {
    local path="$1"
    if [ ! -f "$path" ]; then
        echo "Missing artifact: $path" >&2
        fail=1
    fi
}

# Optional artifact: warn if absent but do NOT fail the audit. Used for Windows
# assets, which are produced on a separate Windows host and may not exist here.
check_optional() {
    local path="$1"
    [ -f "$path" ] || echo "  (optional artifact absent — skipped): $path"
}

check_file "$LINUX_BIN"
check_file "$LINUX_BIN.sha256"
check_optional "$WINDOWS_ZIP"
check_optional "$WINDOWS_ZIP.sha256"
check_optional "$WINDOWS_EXE"
check_optional "$WINDOWS_EXE.sha256"

check_native() {
    local artifact="$1" checksum="$2" format="$3" contents
    [ -f "$artifact" ] || return 0
    check_file "$checksum"
    if ! sha256sum -c "$checksum" >/dev/null 2>&1; then
        echo "Checksum failed: $artifact" >&2
        fail=1
        return
    fi
    case "$format" in
        deb) contents="$(dpkg-deb -c "$artifact" 2>/dev/null || true)" ;;
        rpm) contents="$(rpm -qlp "$artifact" 2>/dev/null || true)" ;;
        arch) contents="$(tar -tf "$artifact" 2>/dev/null || true)" ;;
    esac
    if [ -z "$contents" ]; then
        echo "Invalid or unreadable $format artifact: $artifact" >&2
        fail=1
    elif printf '%s\n' "$contents" | grep -E 'license_(generator|signer)|license_hanan_qaisar' >/dev/null; then
        echo "$format artifact contains private license-issuance material: $artifact" >&2
        fail=1
    fi
}

check_native "$DEB" "$DEB.sha256" deb
check_native "$RPM" "$RPM.sha256" rpm
check_native "$ARCH" "$ARCH.sha256" arch

check_enrollment() {
    local artifact="$1" format="$2" contents
    [ -f "$artifact" ] || return 0
    case "$format" in
        deb) contents="$(dpkg-deb -c "$artifact" 2>/dev/null || true)" ;;
        rpm) contents="$(rpm -qlp "$artifact" 2>/dev/null || true)" ;;
        arch) contents="$(tar -tf "$artifact" 2>/dev/null || true)" ;;
    esac
    # Native packages ship source first and compile it to bytecode in their
    # maintainer script so the installed bytecode matches the target Python.
    if ! printf '%s\n' "$contents" | grep -Eq 'nova_unlock/ui/enrollment_wizard\.pyc?'; then
        echo "$format artifact is missing enrollment_wizard.py: $artifact" >&2
        fail=1
    fi
}

check_enrollment "$DEB" deb
check_enrollment "$RPM" rpm
check_enrollment "$ARCH" arch

if [ -f "$WINDOWS_ZIP" ]; then
    bad_files="$(zipinfo -1 "$WINDOWS_ZIP" | grep -E '(\.py|\.pyw|\.c|\.cc|\.cpp|\.cxx|\.h|\.hh|\.hpp|\.hxx|\.def|\.sln|\.vcxproj|\.filters|CMakeLists\.txt|README|\.md)$' || true)"
    if [ -n "$bad_files" ]; then
        echo "Windows ZIP contains source/project files:" >&2
        echo "$bad_files" >&2
        fail=1
    fi
    if zipinfo -1 "$WINDOWS_ZIP" | grep -E 'license_(generator|signer)|license_hanan_qaisar' >/dev/null; then
        echo "Windows ZIP contains private license-issuance material:" >&2
        zipinfo -1 "$WINDOWS_ZIP" | grep -E 'license_(generator|signer)|license_hanan_qaisar' >&2
        fail=1
    fi
fi

if [ -f "$WINDOWS_EXE" ]; then
    bad_files="$(7z l "$WINDOWS_EXE" | awk 'NF {print $NF}' | grep -E '(\.py|\.pyw|\.c|\.cc|\.cpp|\.cxx|\.h|\.hh|\.hpp|\.hxx|\.def|\.sln|\.vcxproj|\.filters|CMakeLists\.txt|README|\.md)$' || true)"
    if [ -n "$bad_files" ]; then
        echo "Windows EXE contains source/project files:" >&2
        echo "$bad_files" >&2
        fail=1
    fi
fi

if [ "$fail" -ne 0 ]; then
    exit 1
fi

echo "Release artifact audit passed for v$VERSION"
