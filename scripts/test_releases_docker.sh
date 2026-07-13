#!/bin/bash
# test_releases_docker.sh — Drive nova_docker_check.sh across all release targets.
# Usage: test_releases_docker.sh [ARTIFACT_DIR] [REPORT_FILE]
#
# Installs the real release artifact inside a live container per target and runs
# the check battery. Windows is handled separately (structural only).
set -u
ARTDIR="${1:-/tmp/nova-reltest/v5.4}"
REPORT="${2:-/tmp/nova-reltest/report-v5.4.txt}"
CHECK="$(cd "$(dirname "$0")" && pwd)/nova_docker_check.sh"
TIMEOUT="${TIMEOUT:-600}"

mkdir -p "$(dirname "$REPORT")"
: > "$REPORT"

run_target(){
  local name="$1" image="$2" mode="$3" pkgtype="$4" glob="$5"
  local art; art=$(ls "$ARTDIR"/$glob 2>/dev/null | head -1)
  if [ -z "$art" ]; then echo "SKIP $name: no artifact matching '$glob' in $ARTDIR" | tee -a "$REPORT"; return; fi
  local base; base=$(basename "$art")
  echo "####################################################################" | tee -a "$REPORT"
  echo "# TARGET: $name  ($image, mode=$mode, $base)" | tee -a "$REPORT"
  echo "####################################################################" | tee -a "$REPORT"
  # Mount read-WRITE (so the binary can be chmod +x and executed) and give the
  # container host network access (some distros need to fetch deps at install).
  timeout "$TIMEOUT" docker run --rm --network=host \
    -v "$ARTDIR:/artifacts" \
    -v "$CHECK:/nova_docker_check.sh:ro" \
    "$image" bash -c "chmod +x '/artifacts/$base' 2>/dev/null; bash /nova_docker_check.sh $mode $pkgtype '/artifacts/$base'" \
    2>&1 | tee -a "$REPORT"
  echo "" | tee -a "$REPORT"
}

echo "NovaUnlock release Docker test — $(date)" | tee -a "$REPORT"
echo "Artifact dir: $ARTDIR" | tee -a "$REPORT"
echo "" | tee -a "$REPORT"

run_target "debian12"  debian:12        native deb  "NovaUnlock-v5.4-Debian.deb"
run_target "ubuntu2404" ubuntu:24.04     native deb  "NovaUnlock-v5.4-Debian.deb"
run_target "fedora"    fedora:latest    native rpm  "NovaUnlock-v5.4-Fedora.rpm"
run_target "arch"      archlinux:latest native arch "NovaUnlock-v5.4-Arch.pkg.tar.zst"
run_target "bin"       ubuntu:24.04     bin    bin   "nova_unlock_installer_v5.4*"

echo "####################################################################" | tee -a "$REPORT"
echo "# DONE. Report: $REPORT" | tee -a "$REPORT"
echo "####################################################################" | tee -a "$REPORT"
