#!/bin/bash
# nova_docker_check.sh — run inside a test container.
# Usage: nova_docker_check.sh <mode> <pkgtype> <artifact>
#   mode    : native | bin
#   pkgtype : deb | rpm | arch   (native only)
#   artifact: path to the release file inside the container
#
# Performs the real OS install of the artifact, then a check battery:
#   - install exit code
#   - /opt/novaunlock (native) or ~/NovaUnlock/.venv (bin) tree present
#   - no .py source left in installed tree (native)
#   - import dlib/face_recognition/face_recognition_models  (THE key test)
#   - import cv2, PyQt5
#   - deps_status.json written
#   - systemd user unit present
#   - pam_script_auth bash syntax
set -u
MODE="$1"; PKGTYPE="${2:-}"; ART="$3"
NOVA_OPT=/opt/novaunlock
PASS=0; FAIL=0
report(){ # $1=name $2=0/1 $3=detail
  if [ "$2" = "0" ]; then echo "PASS: $1"; PASS=$((PASS+1));
  else echo "FAIL: $1 :: $3"; FAIL=$((FAIL+1)); fi
}
py_imp(){ # $1=expr  -> prints "OK <ver>" or "ERR <msg>"
  python3 -c "$1" 2>&1 | tail -2
}

echo "===== NovaUnlock Docker check: mode=$MODE pkgtype=$PKGTYPE artifact=$ART ====="
. /etc/os-release 2>/dev/null && echo "OS: $PRETTY_NAME"
python3 --version 2>&1

# ---------- INSTALL ----------
echo "----- install -----"
IRC=0
if [ "$MODE" = "native" ]; then
  case "$PKGTYPE" in
    deb)
      apt-get update -qq 2>&1 | tail -2
      apt-get install -y "$ART" 2>&1 | tail -8; IRC=${PIPESTATUS[0]} ;;
    rpm)
      dnf install -y --nogpgcheck "$ART" 2>&1 | tail -10; IRC=${PIPESTATUS[0]} ;;
    arch)
      pacman -Sy --noconfirm >/dev/null 2>&1
      pacman -U --noconfirm "$ART" 2>&1 | tail -10; IRC=${PIPESTATUS[0]} ;;
  esac
  report "native package install rc=0" "$([ "$IRC" = "0" ] && echo 0 || echo 1)" "irc=$IRC"
  NOVA_DIR="$NOVA_OPT"
elif [ "$MODE" = "bin" ]; then
  id testuser >/dev/null 2>&1 || useradd -m testuser
  SUDO_USER=testuser HOME=/home/testuser timeout 400 "$ART" < /dev/null 2>&1 | tail -20; IRC=${PIPESTATUS[0]}
  report "installer binary ran rc=0" "$([ "$IRC" = "0" ] && echo 0 || echo 1)" "irc=$IRC"
  NOVA_DIR=/home/testuser/NovaUnlock
fi

# ---------- TREE ----------
echo "----- tree -----"
[ -d "$NOVA_DIR" ] && report "nova tree present ($NOVA_DIR)" 0 || report "nova tree present ($NOVA_DIR)" 1 "missing"
if [ "$MODE" = "native" ]; then
  LEFT=$(find "$NOVA_DIR" -name '*.py' 2>/dev/null | wc -l)
  report "no .py source left in tree" "$([ "$LEFT" = "0" ] && echo 0 || echo 1)" "$LEFT .py files remain"
  for f in scripts/face_unlock_daemon.pyc scripts/enroll_gui.pyc nova_unlock/pam/pam_script_auth; do
    [ -e "$NOVA_DIR/$f" ] && report "entrypoint $f" 0 || report "entrypoint $f" 1 "missing"
  done
fi

# ---------- IMPORTS (key) ----------
echo "----- python imports -----"
OUT=$(python3 -c "import dlib, face_recognition, face_recognition_models; print('ML OK', dlib.__version__)" 2>&1); RC=$?
report "import dlib/face_recognition/face_recognition_models" "$([ $RC = 0 ] && echo 0 || echo 1)" "$OUT"
OUT=$(python3 -c "import cv2; print('cv2', cv2.__version__)" 2>&1); RC=$?
report "import cv2" "$([ $RC = 0 ] && echo 0 || echo 1)" "$OUT"
OUT=$(python3 -c "import PyQt5; from PyQt5 import QtCore; print('PyQt5', QtCore.QT_VERSION_STR)" 2>&1); RC=$?
report "import PyQt5" "$([ $RC = 0 ] && echo 0 || echo 1)" "$OUT"

if [ "$MODE" = "bin" ]; then
  VPY=/home/testuser/NovaUnlock/.venv/bin/python3
  if [ -x "$VPY" ]; then
    OUT=$("$VPY" -c "import dlib, face_recognition; print('VENV ML OK', dlib.__version__)" 2>&1); RC=$?
    report "venv import dlib/face_recognition" "$([ $RC = 0 ] && echo 0 || echo 1)" "$OUT"
  else
    report "venv python present" 1 "no $VPY"
  fi
fi

# ---------- deps status ----------
echo "----- dependency status -----"
if [ -f /var/lib/novaunlock/deps_status.json ]; then
  report "deps_status.json written" 0
  echo "    $(cat /var/lib/novaunlock/deps_status.json 2>/dev/null)"
else
  report "deps_status.json written" 1 "missing"
fi

# ---------- systemd unit ----------
echo "----- systemd -----"
if command -v systemctl >/dev/null 2>&1; then
  U=$(systemctl --user cat nova-unlock-watcher.service 2>&1 | head -1)
  report "systemd user unit present" "$([ -n "$U" ] && echo 0 || echo 1)" "$U"
else
  report "systemd user unit present" 1 "no systemctl in image"
fi

# ---------- pam script syntax ----------
echo "----- pam -----"
PAM="$NOVA_DIR/nova_unlock/pam/pam_script_auth"
[ -e "$PAM" ] && { bash -n "$PAM" 2>&1 && report "pam_script_auth bash syntax" 0 || report "pam_script_auth bash syntax" 1 "bash -n failed"; } \
              || report "pam_script_auth present" 1 "missing"

# ---------- post-install logs (diagnostics) ----------
echo "----- post-install logs -----"
for lf in "$NOVA_DIR"/logs/*.log /var/log/novaunlock/* /opt/novaunlock/logs/*.log; do
  [ -f "$lf" ] && { echo "### $lf ###"; tail -25 "$lf"; }
done
echo "(end of logs)"

echo "===== SUMMARY: PASS=$PASS FAIL=$FAIL ====="
exit $FAIL
