#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${VERSION:-2.012}"
LINUX_BIN="$ROOT_DIR/dist/nova_unlock_installer_v$VERSION"
WINDOWS_ZIP="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.zip"
WINDOWS_EXE="$ROOT_DIR/dist/nova_unlock_windows_v$VERSION.exe"

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

if [ -f "$WINDOWS_ZIP" ]; then
    bad_files="$(zipinfo -1 "$WINDOWS_ZIP" | grep -E '(\.py|\.pyw|\.c|\.cc|\.cpp|\.cxx|\.h|\.hh|\.hpp|\.hxx|\.def|\.sln|\.vcxproj|\.filters|CMakeLists\.txt|README|\.md)$' || true)"
    if [ -n "$bad_files" ]; then
        echo "Windows ZIP contains source/project files:" >&2
        echo "$bad_files" >&2
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
