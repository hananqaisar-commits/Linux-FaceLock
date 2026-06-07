#!/bin/bash
set -e

NOVA_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$NOVA_DIR/.venv"
LOG_DIR="$NOVA_DIR/logs"
FACES_DIR="$NOVA_DIR/data/faces"

echo
echo "  NovaUnlock Installer"
echo

if [ "$EUID" -ne 0 ]; then
    echo "  Run with sudo: sudo bash install.sh"
    exit 1
fi

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(eval echo "~$REAL_USER")

echo "  Installing for user: $REAL_USER"
echo "  NovaUnlock directory: $NOVA_DIR"
echo

mkdir -p "$LOG_DIR" "$FACES_DIR"
chown -R "$REAL_USER:$REAL_USER" "$LOG_DIR" "$FACES_DIR"

echo "  [1/6] Installing system packages..."
apt-get install -y \
    libpam-script \
    xdotool \
    python3-xlib \
    alsa-utils \
    xdpyinfo \
    > /dev/null 2>&1
echo "        done"

echo "  [2/6] Setting up PAM hook..."
PSCRIPT_DIR="/usr/share/libpam-script"
mkdir -p "$PSCRIPT_DIR"

for f in pam_script_acct pam_script_ses_open pam_script_ses_close; do
    if [ ! -f "$PSCRIPT_DIR/$f" ]; then
        printf '#!/bin/bash\nexit 0\n' > "$PSCRIPT_DIR/$f"
        chmod +x "$PSCRIPT_DIR/$f"
    fi
done

CACHE_FILE="/tmp/nova_unlock_pam_cache.json"
LOGFILE="$NOVA_DIR/logs/pam_auth.log"

cat > "$PSCRIPT_DIR/pam_script_auth" << PAMEOF
#!/bin/bash
LOGFILE="$LOGFILE"
CACHE="$CACHE_FILE"

echo "\$(date) PAM called for: \$PAM_USER" >> "\$LOGFILE"

if [ -f "\$CACHE" ]; then
    CACHE_USER=\$(python3 - "\$CACHE" << 'PY'
import json, sys, time
try:
    d = json.load(open(sys.argv[1]))
    u = str(d.get("user","")).strip().lower()
    ts = float(d.get("ts",0))
    if u and (time.time()-ts) <= 15:
        print(u)
except Exception:
    pass
PY
)
    PAM_CLEAN=\$(echo "\$PAM_USER" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    if [ -n "\$CACHE_USER" ] && [ "\$CACHE_USER" = "\$PAM_CLEAN" ]; then
        echo "\$(date) CACHE HIT for \$PAM_CLEAN" >> "\$LOGFILE"
        rm -f "\$CACHE"
        exit 0
    fi
    echo "\$(date) CACHE MISS cache=\$CACHE_USER pam=\$PAM_CLEAN" >> "\$LOGFILE"
    rm -f "\$CACHE"
fi

echo "\$(date) NO CACHE - password required" >> "\$LOGFILE"
exit 1
PAMEOF
chmod +x "$PSCRIPT_DIR/pam_script_auth"
echo "        done"

echo "  [3/6] Setting up xfce4-screensaver PAM..."
cat > /etc/pam.d/xfce4-screensaver << PAMEOF
#%PAM-1.0
auth    sufficient    pam_script.so
auth    include       common-auth
account include       common-account
session include       common-session-noninteractive
PAMEOF
echo "        done"

echo "  [4/6] Setting up LightDM hooks..."
mkdir -p /etc/lightdm/lightdm.conf.d

cat > /usr/local/bin/nova_unlock_greeter_hook.sh << GREET
#!/bin/bash
nohup /usr/local/bin/nova_unlock_greeter_helper.sh >/tmp/nova_unlock_greeter_launcher.log 2>&1 &
exit 0
GREET
chmod +x /usr/local/bin/nova_unlock_greeter_hook.sh

cat > /usr/local/bin/nova_unlock_greeter_helper.sh << HELPER
#!/bin/bash
LOG=/tmp/nova_unlock_greeter.log
LOCK=/tmp/nova_unlock_greeter.lock
RESULT=/tmp/nova_unlock_greeter_result
CACHE=/tmp/nova_unlock_pam_cache.json
TMPCONF=/etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf

exec >>"\$LOG" 2>&1
echo "==== \$(date) ===="

exec 9>"\$LOCK"
flock -n 9 || exit 0

[ -f "\$TMPCONF" ] && exit 0

DISP="\${DISPLAY:-:1}"
DISP="\${DISP%%.*}"
XAUTH=""
for p in "/var/run/lightdm/root/\$DISP" "/var/run/lightdm/root/:1" "/var/run/lightdm/root/:0" "/var/lib/lightdm/.Xauthority"; do
    [ -e "\$p" ] && XAUTH="\$p" && break
done

export DISPLAY="\$DISP" XAUTHORITY="\$XAUTH" HOME=/root
export XDG_RUNTIME_DIR=/tmp/runtime-nova-unlock
mkdir -p /tmp/runtime-nova-unlock
chmod 700 /tmp/runtime-nova-unlock

[ -z "\$XAUTH" ] && exit 0

rm -f "\$RESULT"

nohup $VENV/bin/python3 $NOVA_DIR/scripts/face_login_greeter.py >/tmp/nova_unlock_greeter_ui.out 2>/tmp/nova_unlock_greeter_ui.err &
UI_PID=\$!
echo "UI_PID=\$UI_PID"

MATCHED=""
for i in \$(seq 1 12); do
    [ -f "\$RESULT" ] && MATCHED="\$(tr -d '[:space:]' < "\$RESULT")" && break
    sleep 1
done

kill "\$UI_PID" 2>/dev/null
rm -f "\$RESULT"

case "\$MATCHED" in
    ""|*[!a-zA-Z0-9._-]*) exit 0 ;;
esac

python3 - << PY
import json, time
open("$CACHE","w").write(json.dumps({"user":"\$MATCHED","profile":"\$MATCHED","ts":time.time()}))
PY
chmod 600 "\$CACHE"

cat > "\$TMPCONF" << CONF
[Seat:*]
autologin-user=\$MATCHED
autologin-user-timeout=0
CONF
chmod 644 "\$TMPCONF"
echo "autologin set for \$MATCHED"
nohup bash -lc 'sleep 2; systemctl restart lightdm' >/dev/null 2>&1 &
HELPER
chmod +x /usr/local/bin/nova_unlock_greeter_helper.sh

cat > /usr/local/bin/nova_unlock_session_cleanup.sh << CLEANUP
#!/bin/bash
rm -f /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
rm -f /run/nova_unlock_autologin.stamp
exit 0
CLEANUP
chmod +x /usr/local/bin/nova_unlock_session_cleanup.sh

cat > /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf << LDMEOF
[Seat:*]
greeter-setup-script=/usr/local/bin/nova_unlock_greeter_hook.sh
session-setup-script=/usr/local/bin/nova_unlock_session_cleanup.sh
greeter-show-manual-login=true
greeter-hide-users=true
LDMEOF
echo "        done"

echo "  [5/6] Setting up lockscreen watcher..."

WATCHER_SCRIPT="/usr/local/bin/nova_unlock_watcher.sh"
cat > "$WATCHER_SCRIPT" << WATCHER
#!/bin/bash
export DISPLAY=:0
export XAUTHORITY="$REAL_HOME/.Xauthority"
export XDG_RUNTIME_DIR="/run/user/\$(id -u $REAL_USER)"

echo "NovaUnlock watcher started"

dbus-monitor --session "type='signal',interface='org.xfce.ScreenSaver',member='ActiveChanged'" 2>/dev/null | while read LINE; do
    if echo "\$LINE" | grep -q "boolean true"; then
        echo "\$(date) LOCKED"
        pkill -f nova_unlock_daemon.py 2>/dev/null
        rm -f /tmp/nova_unlock_face.lock
        sleep 0.8
        cd $NOVA_DIR
        $VENV/bin/python3 $NOVA_DIR/scripts/face_unlock_daemon.py >> $NOVA_DIR/logs/face_auth.log 2>&1 &
    fi
    if echo "\$LINE" | grep -q "boolean false"; then
        echo "\$(date) UNLOCKED"
        pkill -f nova_unlock_daemon.py 2>/dev/null
        rm -f /tmp/nova_unlock_face.lock
    fi
done
WATCHER
chmod +x "$WATCHER_SCRIPT"

AUTOSTART_DIR="$REAL_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/nova-unlock-watcher.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=NovaUnlock Watcher
Exec=$WATCHER_SCRIPT
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
DESKTOP
chown "$REAL_USER:$REAL_USER" "$AUTOSTART_DIR/nova-unlock-watcher.desktop"
echo "        done"

echo "  [6/6] Starting watcher for current session..."
su -s /bin/bash "$REAL_USER" -c "
    export DISPLAY=:0
    export XAUTHORITY=$REAL_HOME/.Xauthority
    pkill -f nova_unlock_watcher.sh 2>/dev/null
    sleep 1
    nohup $WATCHER_SCRIPT > $NOVA_DIR/logs/watcher.log 2>&1 &
    disown
" 2>/dev/null || true
echo "        done"

echo
echo "  Installation complete."
echo
echo "  Next step: enroll your face"
echo "  source .venv/bin/activate"
echo "  python3 scripts/enroll.py"
echo
