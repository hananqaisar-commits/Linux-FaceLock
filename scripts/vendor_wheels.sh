#!/bin/bash
# vendor_wheels.sh — Build + collect prebuilt wheels so NovaUnlock installs OFFLINE.
#
# dlib ships SOURCE-ONLY on PyPI (no wheels), so we BUILD portable manylinux
# wheels for cp311/cp312/cp313 inside the official manylinux container. Every
# other dependency is downloaded as a manylinux wheel. The result tree:
#   wheels/<pyver>/   (dlib + face_recognition + face_recognition_models + the
#                      venv deps opencv-python-headless/PyQt5/numpy/python-xlib/
#                      PyYAML/setuptools)
# is copied into both the native package (opt/novaunlock/wheels) and the bundled
# installer (nova_bundle/wheels). Native post-install installs only the ML trio
# by name; the installer installs the full set into its venv.
set -uo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHEELS="$ROOT_DIR/wheels"
MLIST="cp311 cp312 cp313"

PURE_PKGS="python-xlib PyYAML setuptools"
PLAT_PKGS="opencv-python-headless PyQt5 numpy"
# face_recognition depends on dlib, which has NO PyPI wheel -> a normal resolve
# hits ResolutionImpossible. We build dlib ourselves (step 1), so this must be
# fetched WITHOUT dependency resolution.
NODEPS_PKGS="face_recognition"

mkdir -p "$WHEELS"

# robust_download PKG DEST PYVER [extra pip args...]
# Escalating fetch: try progressively looser strategies until a wheel lands,
# so any single failure mode is handled and retried rather than aborting.
robust_download() {
  local pkg="$1" dest="$2" pyver="$3"; shift 3
  local before after
  before=$(ls "$dest"/*.whl 2>/dev/null | wc -l)
  # 1) strict: binary-only for the exact target interpreter
  pip3 download --only-binary=:all: --python-version "$pyver" -d "$dest" "$@" "$pkg" 2>&1 | tail -1
  after=$(ls "$dest"/*.whl 2>/dev/null | wc -l); [ "$after" -gt "$before" ] && return 0
  # 2) drop the interpreter pin (let pip pick the best compatible wheel)
  echo "    ~ $pkg: retry without --python-version"
  pip3 download --only-binary=:all: -d "$dest" "$@" "$pkg" 2>&1 | tail -1
  after=$(ls "$dest"/*.whl 2>/dev/null | wc -l); [ "$after" -gt "$before" ] && return 0
  # 3) allow source dists, then build a wheel from them
  echo "    ~ $pkg: retry allowing sdist + local build"
  pip3 wheel --no-deps -w "$dest" "$@" "$pkg" 2>&1 | tail -2
  after=$(ls "$dest"/*.whl 2>/dev/null | wc -l); [ "$after" -gt "$before" ] && return 0
  echo "    ! $pkg: all download strategies exhausted"
  return 1
}

# ── 1) dlib: build manylinux wheels (no PyPI wheel exists) ───────────────
echo ">>> Pulling manylinux_2_28 image ..."
docker pull quay.io/pypa/manylinux_2_28_x86_64 2>&1 | tail -2
for v in $MLIST; do
  d="$WHEELS/$v"; mkdir -p "$d"
  echo ">>> Building dlib wheel for $v ..."
  if docker run --rm -v "$WHEELS:/io" quay.io/pypa/manylinux_2_28_x86_64 bash -c "
        set -u
        PIP=/opt/python/$v-$v/bin/pip
        OUT=/io/$v
        have_wheel() { ls \$OUT/dlib-*.whl >/dev/null 2>&1; }
        # Provision the PEP517 build toolchain FIRST so no attempt runs without it
        # (root cause of the BackendUnavailable failure).
        \$PIP install -q --upgrade pip setuptools wheel cmake >/dev/null 2>&1 || true
        # Attempt 1: no build isolation — reuse the setuptools we just installed.
        echo '  [dlib $v] attempt 1: --no-build-isolation'
        \$PIP wheel --no-build-isolation dlib -w \$OUT 2>&1 | tail -4
        # Attempt 2: normal isolated build (pip provisions its own backend).
        if ! have_wheel; then
          echo '  [dlib $v] attempt 2: isolated build'
          \$PIP wheel dlib -w \$OUT 2>&1 | tail -4
        fi
        # Attempt 3: refreshed toolchain + pinned known-good source, no isolation.
        if ! have_wheel; then
          echo '  [dlib $v] attempt 3: pinned dlib==19.24.6 + refreshed toolchain'
          \$PIP install -q --upgrade 'setuptools>=68' wheel cmake >/dev/null 2>&1 || true
          \$PIP wheel --no-build-isolation 'dlib==19.24.6' -w \$OUT 2>&1 | tail -4
        fi
        have_wheel
      "; then
    echo ">>> dlib $v: $(ls "$d"/dlib-*.whl 2>/dev/null | wc -l) wheel(s)"
  else
    echo "!!! dlib $v BUILD FAILED (all attempts exhausted)"
  fi
done

# ── 2) face_recognition_models: source-only -> build ONE universal wheel ──
echo ">>> Building universal face_recognition_models wheel ..."
mkdir -p /tmp/nova-wheels-common
pip3 wheel --no-deps face_recognition_models -w /tmp/nova-wheels-common 2>&1 | tail -2
FRM_WHL=$(ls /tmp/nova-wheels-common/face_recognition_models-*.whl 2>/dev/null | head -1)
if [ -n "$FRM_WHL" ]; then
  for v in $MLIST; do cp "$FRM_WHL" "$WHEELS/$v/"; done
  echo ">>> face_recognition_models -> $(basename "$FRM_WHL") copied to all versions"
fi

# ── 3) download pure + platform wheels per version ───────────────────────
for v in $MLIST; do
  d="$WHEELS/$v"; mkdir -p "$d"
  pyver="${v#cp}"
  for p in $PURE_PKGS; do
    echo ">>> download $p ($v)"
    robust_download "$p" "$d" "$pyver" \
      || echo "    ! $p $v download issue"
  done
  for p in $PLAT_PKGS; do
    echo ">>> download $p ($v)"
    robust_download "$p" "$d" "$pyver" \
      || echo "    ! $p $v download issue"
  done
  # face_recognition: --no-deps so pip does NOT try to resolve dlib (no wheel).
  # It depends only on dlib (built above) + face_recognition_models (built above),
  # both present in this tree, so the installer can satisfy the runtime import.
  for p in $NODEPS_PKGS; do
    echo ">>> download $p ($v) [--no-deps]"
    pip3 download --no-deps --only-binary=:all: --python-version "$pyver" -d "$d" "$p" 2>&1 | tail -1 \
      || pip3 download --no-deps -d "$d" "$p" 2>&1 | tail -1 \
      || echo "    ! $p $v download issue"
  done
done

echo "=== FINAL INVENTORY ==="
for v in $MLIST; do
  echo "$v ($(ls "$WHEELS/$v" 2>/dev/null | wc -l) files):"
  ls -1 "$WHEELS/$v" 2>/dev/null
done
