#!/usr/bin/env bash
#
# nova_pkg_postinstall.sh — Native-package system integration for NovaUnlock.
#
# Replaces the old `install.sh` for Debian/Fedora/Arch native packages.
# Generates the PAM auth script + helper scripts, wires PAM for the detected
# desktop environment, initialises the 30-day trial, and enables the guard service.
#
# Invoked by each package's maintainer script:
#     nova_pkg_postinstall.sh configure     # install / upgrade
#     nova_pkg_postinstall.sh remove        # uninstall
#
set -o pipefail

ACTION="${1:-configure}"

NOVA_DIR=/opt/novaunlock
VENV_PY=/usr/bin/python3
DAEMON="$NOVA_DIR/scripts/face_unlock_daemon.pyc"
GREETER="$NOVA_DIR/scripts/face_login_greeter.pyc"
PAM_SCRIPT_BIN=/usr/local/bin/nova_pam_auth.sh
CACHE_FILE=/var/lib/novaunlock/pam_cache.json
LOG_DIR=/var/log/novaunlock
PSCRIPT_DIR=/usr/share/libpam-script

log()  { echo "[NovaUnlock] $*"; }
ok()   { echo "[NovaUnlock] ✅ $*"; }
warn() { echo "[NovaUnlock] ⚠️  $*"; }

# ── Determine the human user that owns the desktop session ──────────────
detect_user() {
    REAL_USER="${SUDO_USER:-$USER}"
    [ "$REAL_USER" = "root" ] && REAL_USER="$(logname 2>/dev/null || true)"
    [ -z "$REAL_USER" ] && REAL_USER="$(ls -1 /home 2>/dev/null | grep -v -E 'lost\+found' | head -1)"
    [ -z "$REAL_USER" ] && REAL_USER="$(id -un 1000 2>/dev/null || echo root)"
    REAL_UID="$(id -u "$REAL_USER" 2>/dev/null || echo 1000)"
    REAL_HOME="/home/$REAL_USER"
    REAL_GROUP="$(id -gn "$REAL_USER" 2>/dev/null || echo "$REAL_USER")"
}

# ── Detect package manager / desktop / display manager ─────────────────
detect_env() {
    if   command -v apt-get >/dev/null 2>&1; then PKG_MGR="apt"
    elif command -v dnf     >/dev/null 2>&1; then PKG_MGR="dnf"
    elif command -v yum     >/dev/null 2>&1; then PKG_MGR="yum"
    elif command -v pacman  >/dev/null 2>&1; then PKG_MGR="pacman"
    elif command -v zypper  >/dev/null 2>&1; then PKG_MGR="zypper"
    else PKG_MGR="unknown"; fi

    DE="unknown"
    pgrep -x xfce4-session   >/dev/null 2>&1 && DE="xfce"
    pgrep -x gnome-session    >/dev/null 2>&1 && DE="gnome"
    pgrep -x plasmashell      >/dev/null 2>&1 && DE="kde"
    pgrep -x mate-session     >/dev/null 2>&1 && DE="mate"
    pgrep -x cinnamon-session >/dev/null 2>&1 && DE="cinnamon"
    pgrep -x lxsession        >/dev/null 2>&1 && DE="lxde"
    if [ "$DE" = "unknown" ]; then
        case "${XDG_CURRENT_DESKTOP:-}" in
            *XFCE*)     DE="xfce"     ;;
            *GNOME*)    DE="gnome"    ;;
            *KDE*)      DE="kde"      ;;
            *MATE*)     DE="mate"     ;;
            *Cinnamon*) DE="cinnamon" ;;
        esac
    fi

    DM="unknown"
    systemctl is-active --quiet lightdm 2>/dev/null && DM="lightdm"
    systemctl is-active --quiet gdm3    2>/dev/null && DM="gdm"
    systemctl is-active --quiet gdm     2>/dev/null && DM="gdm"
    systemctl is-active --quiet sddm    2>/dev/null && DM="sddm"
    systemctl is-active --quiet lxdm    2>/dev/null && DM="lxdm"

    case "$PKG_MGR" in
        apt|zypper) COMMON_AUTH="common-auth" ;;
        dnf|yum|pacman) COMMON_AUTH="system-auth" ;;
        *) COMMON_AUTH="common-auth" ;;
    esac

    mkdir -p "$LOG_DIR" "$(dirname "$CACHE_FILE")"
    log "pkg=$PKG_MGR de=$DE dm=$DM user=$REAL_USER"
}

# ── Ensure heavy runtime deps (dlib / face_recognition are pip-only) ───
# These are not available as OS packages on Debian / Kali / Fedora / Arch, so
# they are pip-installed into the SYSTEM site-packages (visible to the root / user
# daemon that actually runs them). This is best-effort and MUST NOT abort the
# package install — if it fails the app reports a clear message at runtime and
# the user's password remains a working fallback.
ensure_runtime_deps() {
    local py="${VENV_PY:-python3}"
    command -v "$py" >/dev/null 2>&1 || py="python3"

    local pyver
    pyver=$("$py" -c "import sys; print(f'cp{sys.version_info.major}{sys.version_info.minor}')" 2>/dev/null) \
        || { warn "Cannot determine Python version — cannot install bundled wheels."; record_deps_status 1 "dlib face_recognition face_recognition_models"; return 1; }

    local WHEELS_DIR="$NOVA_DIR/wheels/$pyver"
    if [ ! -d "$WHEELS_DIR" ] || [ -z "$(ls -A "$WHEELS_DIR" 2>/dev/null)" ]; then
        warn "Bundled wheels for $pyver are MISSING ($WHEELS_DIR)."
        warn "NovaUnlock cannot install its ML dependencies offline. Face unlock will NOT work."
        warn "This is a packaging defect — please report it. Remediation: reinstall a complete package."
        record_deps_status 1 "dlib face_recognition face_recognition_models"
        return 1
    fi

    log "Installing bundled ML dependencies for $pyver (offline) from $WHEELS_DIR ..."
    # --find-links points pip at the bundled wheelhouse; --no-index disables PyPI.
    # Without --find-links, --no-index leaves pip with NO source and the install
    # fails with "No matching distribution" (the dlib import failure in testing).
    # Named packages (not *.whl) let pip pick the version-compatible wheel and
    # ignore any stray cross-version wheels present in the same dir.
    if "$py" -m pip install --no-index --find-links "$WHEELS_DIR" --break-system-packages \
            dlib face_recognition face_recognition_models 2>&1 | sed 's/^/[NovaUnlock] /'; then
        ok "Bundled ML dependencies installed ($pyver)"
        record_deps_status 0
        return 0
    fi

    warn "Failed to install bundled wheels for $pyver from $WHEELS_DIR."
    warn "Face unlock will NOT work until this is resolved."
    record_deps_status 1 "dlib face_recognition face_recognition_models"
    return 1
}

# Persist a machine-readable dependency status so the app (and support) can
# report a clear, actionable state instead of a raw ImportError.
record_deps_status() {
    local ok="$1" missing="${2:-}"
    local f="/var/lib/novaunlock/deps_status.json"
    mkdir -p "$(dirname "$f")" 2>/dev/null || return 0
    local py="${VENV_PY:-python3}"
    "$py" - "$ok" "$missing" << 'PY' 2>/dev/null || true
import sys, json, os, time
ok = sys.argv[1] == "0"
missing = sys.argv[2].split() if sys.argv[2].strip() else []
p = "/var/lib/novaunlock/deps_status.json"
try:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump({
            "ok": ok,
            "missing": missing,
            "remediation": ("python3 -m pip install --break-system-packages " + " ".join(missing)) if missing else "",
            "checked_at": time.time(),
        }, fh, indent=2)
except Exception:
    pass
PY
}

# ── Canonical faces directory (single source of truth) ───────────────
# Every entrypoint (enrollment, greeter, lock-screen daemon) resolves faces
# via face_recognizer.get_faces_dir() → /var/lib/novaunlock/faces. We create
# that dir here (0700, owned by the human user) and migrate any profiles left
# behind in older locations so enrollment + recognition finally agree.
setup_faces_dir() {
    local FACES=/var/lib/novaunlock/faces
    mkdir -p "$FACES"
    chmod 700 "$FACES"
    if [ -n "${REAL_USER:-}" ] && id "$REAL_USER" >/dev/null 2>&1; then
        chown -R "$REAL_USER":"${REAL_GROUP:-$REAL_USER}" "$FACES" 2>/dev/null || true
    fi

    # Migrate existing profiles from any legacy location. cp -n (no-clobber)
    # never overwrites a newer canonical file.
    local src
    for src in \
        /opt/novaunlock/data/faces \
        "${REAL_HOME:-}/NovaUnlock/data/faces" \
        "${REAL_HOME:-}/Desktop/NovaUnlock/data/faces" \
        "$HOME/NovaUnlock/data/faces" \
        "$HOME/Desktop/NovaUnlock/data/faces" ; do
        [ -d "$src" ] || continue
        for f in "$src"/*.npy "$src"/users_meta.json; do
            [ -f "$f" ] || continue
            if cp -n "$f" "$FACES/" 2>/dev/null; then
                log "migrated face profile: $(basename "$f")"
            fi
        done
    done
    ok "Faces dir ready: $FACES"
}

# ── PAM auth script (reads the short-lived face-match cache) ───────────
write_pam_auth_script() {
    # Deploy the canonical rich PAM script from the package tree. It performs
    # the lock-screen cache check AND live face auth for sudo/su/pkexec/polkit
    # (face primary, password fallback), and always skips root.
    local src="$NOVA_DIR/nova_unlock/pam/pam_script_auth"
    if [ -f "$src" ]; then
        cp "$src" "$PAM_SCRIPT_BIN"
    else
        # Fallback (should not happen) — cache-only with root skip.
        cat > "$PAM_SCRIPT_BIN" << 'PAMSCRIPT'
#!/bin/bash
CACHE="/var/lib/novaunlock/pam_cache.json"
LOGFILE="/var/log/novaunlock/pam_auth.log"
echo "$(date) PAM called for: $PAM_USER" >> "$LOGFILE"
[ ! -f "$CACHE" ] && echo "$(date) NO CACHE" >> "$LOGFILE" && exit 1
CACHE_USER=$(python3 -c "
import json, sys, time
try:
    d = json.load(open('$CACHE'))
    u = str(d.get('user','')).strip().lower()
    ts = float(d.get('ts', 0))
    if u and (time.time() - ts) <= 15:
        print(u)
except Exception:
    pass
" 2>/dev/null)
PAM_CLEAN=$(echo "$PAM_USER" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
[ "$PAM_CLEAN" = "root" ] && exit 1
if [ -n "$CACHE_USER" ] && [ "$CACHE_USER" = "$PAM_CLEAN" ]; then
    echo "$(date) CACHE HIT: $PAM_CLEAN" >> "$LOGFILE"
    rm -f "$CACHE"
    exit 0
fi
echo "$(date) CACHE MISS: cache=$CACHE_USER pam=$PAM_CLEAN" >> "$LOGFILE"
rm -f "$CACHE"
exit 1
PAMSCRIPT
    fi
    chmod 755 "$PAM_SCRIPT_BIN"
}

# ── Idempotent PAM file editor ─────────────────────────────────────────
pam_method() {
    if find /lib /usr/lib /lib64 /usr/lib64 -name "pam_script.so" 2>/dev/null | grep -q .; then
        echo "pam_script"
    else
        echo "pam_exec"
    fi
}

configure_pam_lockscreen() {
    local pam_file="$1" label="$2" method="$3"
    [ -f "$pam_file" ] && sed -i '/nova_pam_auth\|pam_script\.so\|pam_exec\.so.*nova/d' "$pam_file" 2>/dev/null
    if [ -f "$pam_file" ]; then
        TMP=$(mktemp)
        if [ "$method" = "pam_script" ]; then
            printf '%s\n' "auth    sufficient    pam_script.so" > "$TMP"
        else
            printf '%s\n' "auth    [success=ok default=ignore]  pam_exec.so quiet $PAM_SCRIPT_BIN" > "$TMP"
        fi
        cat "$pam_file" >> "$TMP"
        mv "$TMP" "$pam_file"
        ok "PAM lockscreen: $label"
    fi
}

configure_pam_sudo() {
    local pam_file="$1" label="$2" method="$3"
    [ -f "$pam_file" ] && sed -i '/nova_pam_auth\|pam_script\.so\|pam_exec\.so.*nova/d' "$pam_file" 2>/dev/null
    if [ -f "$pam_file" ]; then
        TMP=$(mktemp)
        if [ "$method" = "pam_script" ]; then
            printf '%s\n' "auth    sufficient    pam_script.so" > "$TMP"
        else
            printf '%s\n' "auth    [success=ok default=ignore]  pam_exec.so quiet $PAM_SCRIPT_BIN" > "$TMP"
        fi
        cat "$pam_file" >> "$TMP"
        mv "$TMP" "$pam_file"
        ok "PAM privilege: $label"
    fi
}

configure_pam() {
    local method; method="$(pam_method)"
    log "PAM method: $method"

    # Lockscreen / greeter PAM for the detected DE
    case "$DE" in
        xfce)     configure_pam_lockscreen /etc/pam.d/xfce4-screensaver    "xfce4-screensaver" "$method" ;;
        gnome)    configure_pam_lockscreen /etc/pam.d/gnome-screensaver    "gnome-screensaver" "$method"
                 configure_pam_lockscreen /etc/pam.d/gdm-password         "gdm-password" "$method" ;;
        kde)      configure_pam_lockscreen /etc/pam.d/kde                  "kde" "$method"
                 configure_pam_lockscreen /etc/pam.d/sddm                 "sddm" "$method" ;;
        mate)     configure_pam_lockscreen /etc/pam.d/mate-screensaver     "mate-screensaver" "$method" ;;
        cinnamon) configure_pam_lockscreen /etc/pam.d/cinnamon-screensaver "cinnamon-screensaver" "$method" ;;
        *)        configure_pam_lockscreen /etc/pam.d/xfce4-screensaver    "xfce4-screensaver (default)" "$method"
                 configure_pam_lockscreen /etc/pam.d/gnome-screensaver    "gnome-screensaver" "$method" ;;
    esac

    # Privilege-escalation PAM hooks
    configure_pam_sudo /etc/pam.d/sudo     "sudo"     "$method"
    configure_pam_sudo /etc/pam.d/su       "su"       "$method"
    [ -f /etc/pam.d/polkit-1 ] && configure_pam_sudo /etc/pam.d/polkit-1 "polkit-1" "$method"
    [ -f /etc/pam.d/pkexec ]   && configure_pam_sudo /etc/pam.d/pkexec   "pkexec"   "$method"
}

# ── 30-day trial initialisation ───────────────────────────────────────
init_trial() {
    "$VENV_PY" -c "
import sys
sys.path.insert(0, '$NOVA_DIR')
from nova_unlock.licensing.storage import SecureStorage
s = SecureStorage()
if not s.get_trial_info():
    s.start_trial()
    print('trial started')
else:
    print('trial already present')
" 2>&1 | sed 's/^/[NovaUnlock] /'
}

# ── Guard service + autostart + watcher ───────────────────────────────
write_watcher() {
    cat > /usr/local/bin/nova_unlock_watcher.sh << 'WATCHER_EOF'
#!/bin/bash
export DISPLAY="${DISPLAY:-:0}"
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export PULSE_SERVER="unix:${XDG_RUNTIME_DIR}/pulse/native"
export NOVA_FACES_DIR="/var/lib/novaunlock/faces"

# ── Post-login "hello, {username}" greeting ──────────
# The lock-screen / login greeter writes /var/lib/novaunlock/last_login_user
# (matched user + timestamp) on a successful face unlock. Because lightdm
# restarts on login, the greeting must render HERE, inside the fresh user
# session. Shown once, only for the matching user, and only if fresh (<60s).
show_login_hello() {
    local MARKER="/var/lib/novaunlock/last_login_user"
    [ -f "$MARKER" ] || return 0
    local user ts now_s age
    user=$(sed -n '1p' "$MARKER" 2>/dev/null | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    ts=$(sed -n '2p'  "$MARKER" 2>/dev/null | tr -d '[:space:]')
    [ -n "$user" ] || { rm -f "$MARKER"; return 0; }
    case "$ts" in (*[!0-9]*) rm -f "$MARKER"; return 0 ;; esac
    now_s=$(date +%s)
    age=$(( now_s - ts ))
    [ "$age" -le 60 ] || { rm -f "$MARKER"; return 0; }
    [ "$user" = "$(id -un)" ] || { rm -f "$MARKER"; return 0; }
    rm -f "$MARKER"
    NOVA_ROOT="${NOVA_DIR:-/opt/novaunlock}" python3 - "$user" << 'HELLO'
import sys, os
sys.path.insert(0, os.environ.get("NOVA_ROOT", "/opt/novaunlock"))
try:
    from nova_unlock.ui.welcome_screen import show_welcome
    show_welcome(sys.argv[1])
except Exception as e:
    sys.stderr.write("hello overlay failed: %s\n" % e)
HELLO
}
show_login_hello

WLOG=/var/log/novaunlock/watcher.log
FLOG=/var/log/novaunlock/face_auth.log
VENV_PY=/usr/bin/python3
DAEMON=/opt/novaunlock/scripts/face_unlock_daemon.pyc
HELLO_MARKER=/var/lib/novaunlock/hello_shown

DBUS_IFACE="org.xfce.ScreenSaver"
case "${XDG_CURRENT_DESKTOP:-}" in
    *GNOME*)    DBUS_IFACE="org.gnome.ScreenSaver" ;;
    *KDE*)      DBUS_IFACE="org.freedesktop.ScreenSaver" ;;
    *MATE*)     DBUS_IFACE="org.mate.ScreenSaver" ;;
    *Cinnamon*) DBUS_IFACE="org.cinnamon.ScreenSaver" ;;
esac

# Begin a fresh unlock session: kill any running daemon, drop the lock file, and
# clear the "Hello <username>" greeting marker so the NEXT successful face match
# greets once. Called on screen-lock AND on resume-from-sleep, so facelock runs
# again whether the user locked manually, walked away (idle timeout), or closed
# the laptop lid.
start_unlock_session() {
    echo "$(date) UNLOCK SESSION START" >> "$WLOG"
    pkill -f "face_unlock_daemon.pyc" 2>/dev/null
    rm -f /tmp/nova_unlock_face.lock
    rm -f "$HELLO_MARKER"
    sleep 0.8
    "$VENV_PY" "$DAEMON" >> "$FLOG" 2>&1 &
}

if [ -z "$DBUS_SESSION_BUS_ADDRESS" ]; then
    for SM in xfce4-session gnome-session mate-session plasmashell cinnamon-session; do
        SM_PID=$(pgrep -u "$(id -un)" -x "$SM" 2>/dev/null | head -1)
        [ -z "$SM_PID" ] && continue
        DBUS=$(tr '\0' '\n' < /proc/$SM_PID/environ 2>/dev/null | grep ^DBUS_SESSION_BUS_ADDRESS= | cut -d= -f2-)
        [ -n "$DBUS" ] && export DBUS_SESSION_BUS_ADDRESS="$DBUS" && break
    done
fi

run_monitor() {
    dbus-monitor --session "type='signal',interface='$DBUS_IFACE',member='ActiveChanged'" 2>/dev/null | while read LINE; do
        if echo "$LINE" | grep -q "boolean true"; then
            echo "$(date) LOCKED" >> "$WLOG"
            pkill -f "face_unlock_daemon.pyc" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock
            rm -f "$HELLO_MARKER"
            sleep 0.8
            "$VENV_PY" "$DAEMON" >> "$FLOG" 2>&1 &
        elif echo "$LINE" | grep -q "boolean false"; then
            echo "$(date) UNLOCKED" >> "$WLOG"
            pkill -f "face_unlock_daemon.pyc" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock
        fi
    done
}

# ── systemd-logind monitor ──────────────────────────────────────────────
# Covers laptop lid-close + suspend/resume: when the machine wakes (PrepareForSleep
# "boolean false") we start a fresh unlock session, so facelock runs again even
# though no screensaver ActiveChanged fired. (Idle screen-blank is already handled
# by the ActiveChanged monitor above on XFCE/GNOME/KDE/MATE/Cinnamon.)
run_sleep_monitor() {
    dbus-monitor --system "type='signal',sender='org.freedesktop.login1',interface='org.freedesktop.login1.Manager',member='PrepareForSleep'" 2>/dev/null | while read LINE; do
        if echo "$LINE" | grep -q "boolean false"; then
            echo "$(date) RESUME (lid/suspend) — restarting facelock" >> "$WLOG"
            start_unlock_session
        fi
    done
}

echo "$(date) Watcher started (iface: $DBUS_IFACE)" >> "$WLOG"
# Launch the suspend/resume monitor alongside the screensaver monitor.
run_sleep_monitor &
while true; do
    run_monitor
    echo "$(date) dbus-monitor exited — restarting in 3s" >> "$WLOG"
    sleep 3
done
WATCHER_EOF
    chmod 755 /usr/local/bin/nova_unlock_watcher.sh
}

setup_service() {
    write_watcher
    # The watcher script + systemd unit + autostart desktop are shipped by the
    # native package; here we only enable the user service (best effort — needs
    # an active session at first login).
    systemctl --user enable nova-unlock-watcher.service 2>/dev/null || true
    ok "Guard service enabled"
}

# ── LightDM greeter (login-screen face unlock) ────────────────────────
setup_lightdm() {
    [ "$DM" = "lightdm" ] || return 0
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat > /usr/local/bin/nova_unlock_greeter_helper.sh << 'HELPER'
#!/bin/bash
LOG=/tmp/nova_unlock_greeter.log
LOCK=/tmp/nova_unlock_greeter.lock
RESULT=/tmp/nova_unlock_greeter_result
CACHE=/var/lib/novaunlock/pam_cache.json
TMPCONF=/etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
exec >>"$LOG" 2>&1
echo "==== $(date) ===="
exec 9>"$LOCK"
flock -n 9 || exit 0
[ -f "$TMPCONF" ] && exit 0
DISP="${DISPLAY:-:0}"; DISP="${DISP%%.*}"
XAUTH=""
for p in /var/run/lightdm/root/$DISP /var/run/lightdm/root/:0 /var/run/lightdm/root/:1 /var/lib/lightdm/.Xauthority; do
    [ -e "$p" ] && XAUTH="$p" && break
done
[ -z "$XAUTH" ] && echo "XAUTH not found, aborting" && exit 0
export DISPLAY="$DISP" XAUTHORITY="$XAUTH" XDG_RUNTIME_DIR=/tmp/runtime-nova-unlock HOME=/root
export NOVA_FACES_DIR="/var/lib/novaunlock/faces"
mkdir -p /tmp/runtime-nova-unlock; chmod 700 /tmp/runtime-nova-unlock
rm -f "$RESULT"
nohup /usr/bin/python3 /opt/novaunlock/scripts/face_login_greeter.pyc >/tmp/nova_unlock_greeter_ui.out 2>&1 &
UI_PID=$!
MATCHED=""
for i in $(seq 1 15); do
    [ -f "$RESULT" ] && MATCHED="$(tr -d '[:space:]' < "$RESULT")" && break
    sleep 1
done
kill "$UI_PID" 2>/dev/null; rm -f "$RESULT"
case "$MATCHED" in ""|*[!a-zA-Z0-9._-]*) echo "No valid match"; exit 0 ;; esac
NOVA_MATCHED="$MATCHED" python3 - << 'PY'
import json, time, os
u = os.environ.get("NOVA_MATCHED", "")
with open("/var/lib/novaunlock/pam_cache.json", "w") as f:
    json.dump({"user": u, "profile": u, "ts": time.time()}, f)
PY
chmod 600 "$CACHE"
cat > "$TMPCONF" << CONF
[Seat:*]
autologin-user=$MATCHED
autologin-user-timeout=0
CONF
chmod 644 "$TMPCONF"
echo "Autologin set for $MATCHED"
nohup bash -c 'sleep 1; systemctl restart lightdm' >/dev/null 2>&1 &
HELPER
    chmod 755 /usr/local/bin/nova_unlock_greeter_helper.sh

    cat > /usr/local/bin/nova_unlock_greeter_hook.sh << 'GREET'
#!/bin/bash
sleep 2
nohup /usr/local/bin/nova_unlock_greeter_helper.sh >>/tmp/nova_unlock_greeter_launcher.log 2>&1 &
exit 0
GREET
    chmod 755 /usr/local/bin/nova_unlock_greeter_hook.sh

    cat > /usr/local/bin/nova_unlock_session_cleanup.sh << 'CLEANUP'
#!/bin/bash
rm -f /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
rm -f /var/lib/novaunlock/pam_cache.json
exit 0
CLEANUP
    chmod 755 /usr/local/bin/nova_unlock_session_cleanup.sh

    cat > /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf << 'LDMEOF'
[Seat:*]
greeter-setup-script=/usr/local/bin/nova_unlock_greeter_hook.sh
session-setup-script=/usr/local/bin/nova_unlock_session_cleanup.sh
greeter-show-manual-login=true
greeter-hide-users=true
LDMEOF
    ok "LightDM greeter hooks configured"
}

# ── GDM greeter (login-screen face unlock, experimental) ──────────────
setup_gdm() {
    [ "$DM" = "gdm" ] || return 0
    GDM_POSTLOGIN_DIR=/etc/gdm3/PostLogin
    [ -d /etc/gdm/PostLogin ] && GDM_POSTLOGIN_DIR=/etc/gdm/PostLogin
    mkdir -p "$GDM_POSTLOGIN_DIR"
    cat > /usr/local/bin/nova_gdm_greeter_hook.sh << 'GDMHOOK'
#!/bin/bash
LOG=/tmp/nova_gdm_greeter.log
RESULT=/tmp/nova_unlock_greeter_result
CACHE=/var/lib/novaunlock/pam_cache.json
exec >>"$LOG" 2>&1
echo "==== $(date) GDM greeter hook ===="
sleep 3
DISP="${DISPLAY:-:0}"; export DISPLAY="$DISP"
export NOVA_FACES_DIR="/var/lib/novaunlock/faces"
for SESSION in /var/run/gdm3/*; do
    [ -d "$SESSION" ] && XAUTH="$SESSION/database" && [ -f "$XAUTH" ] && break
done
[ -z "$XAUTH" ] && XAUTH=/var/lib/gdm3/.Xauthority
[ ! -f "$XAUTH" ] && XAUTH=/var/lib/gdm/.Xauthority
[ -f "$XAUTH" ] && export XAUTHORITY="$XAUTH"
rm -f "$RESULT" "$CACHE"
if [ -x /usr/bin/python3 ] && [ -f /opt/novaunlock/scripts/face_login_greeter.pyc ]; then
    timeout 20 /usr/bin/python3 /opt/novaunlock/scripts/face_login_greeter.pyc >>/tmp/nova_gdm_greeter_ui.log 2>&1 &
    GUI_PID=$!
    for i in $(seq 1 15); do [ -f "$RESULT" ] && break; sleep 1; done
    kill "$GUI_PID" 2>/dev/null
fi
if [ -f "$RESULT" ]; then
    MATCHED=$(tr -d '[:space:]' < "$RESULT")
    case "$MATCHED" in ""|*[!a-zA-Z0-9._-]*) exit 0 ;; esac
    NOVA_MATCHED="$MATCHED" python3 - << 'PY'
import json, time, os
u = os.environ.get("NOVA_MATCHED", "")
with open("/var/lib/novaunlock/pam_cache.json", "w") as f:
    json.dump({"user": u, "profile": u, "ts": time.time()}, f)
PY
    chmod 600 "$CACHE"
    echo "Face matched: $MATCHED — cache written for PAM"
fi
GDMHOOK
    chmod 755 /usr/local/bin/nova_gdm_greeter_hook.sh
    cat > "$GDM_POSTLOGIN_DIR/Default" << 'POSTLOGIN'
#!/bin/bash
[ -x /usr/local/bin/nova_gdm_greeter_hook.sh ] && /usr/local/bin/nova_gdm_greeter_hook.sh &
exit 0
POSTLOGIN
    chmod 755 "$GDM_POSTLOGIN_DIR/Default"
    warn "GDM greeter face detection is experimental — password fallback recommended"
}

# ── Removal ────────────────────────────────────────────────────────────
remove_all() {
    detect_user
    for f in \
        /usr/local/bin/nova_pam_auth.sh \
        /usr/local/bin/nova_unlock_watcher.sh \
        /usr/local/bin/nova_unlock_greeter_hook.sh \
        /usr/local/bin/nova_unlock_greeter_helper.sh \
        /usr/local/bin/nova_unlock_session_cleanup.sh \
        /usr/local/bin/nova_xflock4_lock.sh \
        /usr/local/bin/nova_gdm_greeter_hook.sh ; do
        rm -f "$f"
    done
    rm -f /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf \
          /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf \
          /var/lib/novaunlock/pam_cache.json /tmp/nova_*
    for f in /etc/pam.d/xfce4-screensaver /etc/pam.d/gnome-screensaver \
             /etc/pam.d/gdm-password /etc/pam.d/kde /etc/pam.d/sddm \
             /etc/pam.d/mate-screensaver /etc/pam.d/cinnamon-screensaver \
             /etc/pam.d/sudo /etc/pam.d/su /etc/pam.d/polkit-1 /etc/pam.d/pkexec; do
        [ -f "$f" ] && sed -i '/nova_pam_auth\|pam_script\.so\|pam_exec\.so.*nova/d' "$f" 2>/dev/null
    done
    rm -f /etc/xdg/autostart/nova-unlock-watcher.desktop
    pkill -f nova_unlock_watcher 2>/dev/null || true
    pkill -f face_unlock_daemon 2>/dev/null || true
    systemctl --user disable nova-unlock-watcher.service 2>/dev/null || true
    ok "NovaUnlock integration removed"
}

# ── Compile shipped .py to .pyc on the TARGET's python, then strip .py ─
#    Supports every Debian-family Python (3.10–3.13) from one package.
compile_tree() {
    log "Compiling bytecode with $(python3 --version 2>&1) ..."
    python3 -m compileall -b -q "$NOVA_DIR/nova_unlock" "$NOVA_DIR/scripts" 2>/dev/null || true
    find "$NOVA_DIR" -type f -name '*.py' -delete
    find "$NOVA_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    ok "Bytecode compiled (no .py source left in tree)"
}

# ── Main ───────────────────────────────────────────────────────────────
case "$ACTION" in
    configure)
        detect_user
        detect_env
        ensure_runtime_deps
        setup_faces_dir
        compile_tree
        write_pam_auth_script
        configure_pam
        init_trial
        setup_service
        setup_lightdm
        setup_gdm
        ok "NovaUnlock integration complete"
        ;;
    remove)
        remove_all
        ;;
    *)
        echo "usage: $0 {configure|remove}" >&2
        exit 1
        ;;
esac
