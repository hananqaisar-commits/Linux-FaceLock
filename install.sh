#!/bin/bash

# ═══════════════════════════════════════════════════════════════
#  NovaUnlock Installer v3.2
#  Distros:  Debian / Ubuntu / Kali | Fedora / RHEL | Arch | openSUSE

#  Desktops: XFCE | GNOME | KDE | MATE | Cinnamon
#  DMs:      LightDM | GDM | SDDM
# ═══════════════════════════════════════════════════════════════

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

NOVA_DIR="$(cd "$(dirname "$0")" && pwd)"
NOVA_ROOT="$NOVA_DIR"
VENV="$NOVA_DIR/.venv"
LOG_DIR="$NOVA_DIR/logs"
FACES_DIR="$NOVA_DIR/data/faces"
INSTALL_LOG="$LOG_DIR/install.log"
CACHE_FILE="/tmp/nova_unlock_pam_cache.json"
PAM_SCRIPT_BIN="/usr/local/bin/nova_pam_auth.sh"

PASS=0; FAIL=0; WARN=0
ok()   { echo -e "  ${GREEN}✅${NC} $1" | tee -a "$INSTALL_LOG"; ((PASS++)); }
fail() { echo -e "  ${RED}❌${NC} $1" | tee -a "$INSTALL_LOG"; ((FAIL++)); }
warn() { echo -e "  ${YELLOW}⚠️ ${NC} $1" | tee -a "$INSTALL_LOG"; ((WARN++)); }
info() { echo -e "  ${CYAN}→${NC}  $1" | tee -a "$INSTALL_LOG"; }
nova_py_entry() {
    local rel="$1"
    local src="$NOVA_DIR/$rel"
    local pyc="${src%.py}.pyc"

    if [ -f "$src" ]; then
        printf '%s\n' "$src"
    elif [ -f "$pyc" ]; then
        printf '%s\n' "$pyc"
    else
        printf '%s\n' "$src"
    fi
}

# Retry a pip install up to 3 times (resilient to transient network / DNS errors,
# which are the usual reason a one-shot `pip install dlib` fails mid-build).
# Usage: nova_pip_install <venv-pip-path> <pip-args...>
nova_pip_install() {
    local pip="$1"; shift
    local attempt
    for attempt in 1 2 3; do
        info "pip install (attempt $attempt/3): $*"
        if su - "$REAL_USER" -c "'$pip' install $* 2>&1" | tee -a "$INSTALL_LOG"; then
            return 0
        fi
        warn "pip install attempt $attempt failed for: $*"
        [ "$attempt" -lt 3 ] && sleep 5
    done
    return 1
}

# Record a machine-readable ML-dependency status so the app can report a clear
# failure instead of a raw traceback if dlib / face_recognition are missing.
record_deps_status() {
    local ok="$1"; shift
    "$VENV/bin/python3" - "$ok" "$*" << 'PY' 2>/dev/null || true
import sys, json, os, time
ok = sys.argv[1] == "0"
missing = sys.argv[2].split() if len(sys.argv) > 2 and sys.argv[2].strip() else []
p = "/var/lib/novaunlock/deps_status.json"
try:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        json.dump({"ok": ok, "missing": missing,
                   "remediation": ("python3 -m pip install --break-system-packages " + " ".join(missing)) if missing else "",
                   "checked_at": time.time()}, fh, indent=2)
except Exception:
    pass
PY
}

# BUG 1 FIX: Remove exec tee redirect — use explicit tee per function instead
# tee process substitution inside sudo causes hangs and dropped output
# All logging is now done inline per ok/fail/warn/info functions above

echo
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     NovaUnlock — Installer v2.112             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo

# ── Root check ──────────────────────────────────────────────────
[ "$EUID" -ne 0 ] && echo -e "${RED}Run with sudo: sudo bash install.sh${NC}" && exit 1

REAL_USER="${SUDO_USER:-$USER}"
[ "$REAL_USER" = "root" ] && REAL_USER=$(logname 2>/dev/null || echo "")
[ -z "$REAL_USER" ] && read -rp "  Enter your Linux username: " REAL_USER
REAL_HOME="/home/$REAL_USER"
REAL_UID=$(id -u "$REAL_USER" 2>/dev/null || echo "1000")
# Issue 3 FIX: group name alag ho sakta hai username se (custom setups, LDAP, etc.)
REAL_GROUP=$(id -gn "$REAL_USER" 2>/dev/null || echo "$REAL_USER")

mkdir -p "$LOG_DIR" "$FACES_DIR"
touch "$INSTALL_LOG" 2>/dev/null || true

echo -e "  User:     ${BOLD}$REAL_USER${NC}"
echo -e "  Home:     ${BOLD}$REAL_HOME${NC}"
echo -e "  Project:  ${BOLD}$NOVA_DIR${NC}"
echo -e "  Log:      ${BOLD}$INSTALL_LOG${NC}"
echo

ENROLL_WIZARD_SCRIPT="$(nova_py_entry nova_unlock/ui/enrollment_wizard.py)"
GREETER_SCRIPT_PATH="$(nova_py_entry scripts/face_login_greeter.pyc)"
DAEMON_SCRIPT_PATH="$(nova_py_entry scripts/face_unlock_daemon.pyc)"
DEMO_SCRIPT_PATH="$(nova_py_entry nova_unlock/ui/face_id_screen.py)"

# ═══════════════════════════════════════════════════════════════
# STEP 1 — Detect System
# ═══════════════════════════════════════════════════════════════
echo -e "${CYAN}[1/8] Detecting system...${NC}"

if   command -v apt-get >/dev/null 2>&1; then PKG_MGR="apt"
elif command -v dnf     >/dev/null 2>&1; then PKG_MGR="dnf"
elif command -v pacman  >/dev/null 2>&1; then PKG_MGR="pacman"
elif command -v zypper  >/dev/null 2>&1; then PKG_MGR="zypper"
elif command -v yum     >/dev/null 2>&1; then PKG_MGR="yum"
else fail "No supported package manager (apt/dnf/pacman/zypper)"; exit 1
fi

DISTRO_ID=""
[ -f /etc/os-release ] && DISTRO_ID=$(. /etc/os-release && echo "$ID")

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

info "Package manager : $PKG_MGR"
info "Distro          : ${DISTRO_ID:-unknown}"
info "Desktop         : $DE"
info "Display manager : $DM"

# ── Wayland Auto-Fix (CRITICAL for face unlock) ──
SESSION_TYPE="${XDG_SESSION_TYPE:-}"
if [ -z "$SESSION_TYPE" ] && [ -n "$REAL_USER" ]; then
    SESSION_TYPE=$(su - "$REAL_USER" -c 'echo $XDG_SESSION_TYPE' 2>/dev/null)
fi
if [ -z "$SESSION_TYPE" ]; then
    SESSION_ID=$(loginctl 2>/dev/null | grep -E "^\s*[0-9]+ +$REAL_USER" | awk '{print $1}' | head -1)
    [ -n "$SESSION_ID" ] && SESSION_TYPE=$(loginctl show-session "$SESSION_ID" -p Type --value 2>/dev/null)
fi
info "Session type    : ${SESSION_TYPE:-unknown}"

if [ "$SESSION_TYPE" = "wayland" ]; then
    info ""
    info "ℹ️  WAYLAND SESSION DETECTED"
    info "NovaUnlock runs on Wayland via XWayland (the Qt GUI uses the xcb platform"
    info "plugin inside XWayland), so your Wayland session is left ENABLED — no"
    info "display-manager changes are required."
    # This Wayland compatibility path does NOT touch PAM; PAM is configured
    # later by the explicit authentication setup step.

    # Ensure XWayland is present so the X11/Qt lock-screen GUI and camera preview
    # get a DISPLAY under a Wayland session.
    case "$PKG_MGR" in
        apt)    apt-get install -y xwayland >>"$INSTALL_LOG" 2>&1 || true ;;
        dnf|yum) $PKG_MGR install -y xorg-x11-server-Xwayland >>"$INSTALL_LOG" 2>&1 || true ;;
        pacman) pacman -S --noconfirm xorg-xwayland >>"$INSTALL_LOG" 2>&1 || true ;;
        zypper) zypper install -y xwayland >>"$INSTALL_LOG" 2>&1 || true ;;
    esac

    # Kept as an explicit capability marker for installer diagnostics and
    # downstream release checks; Wayland remains enabled.
    GDM_WAYLAND_ON=1
    NOVA_WAYLAND_OK=1
    info ""
fi

ok "System detected"

# ═══════════════════════════════════════════════════════════════
# STEP 2 — System Packages
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[2/8] Installing system packages...${NC}"

case "$PKG_MGR" in
    apt)
        apt-get update -qq 2>>"$INSTALL_LOG"
        DEBIAN_FRONTEND=noninteractive apt-get install -y \
            xdotool \
            wmctrl \
            alsa-utils \
            pulseaudio-utils \
            x11-utils \
            python3-venv \
            python3-pip \
            python3-dev \
            cmake \
            build-essential \
            libboost-python-dev \
            libboost-thread-dev \
            libopenblas-dev \
            liblapack-dev \
            libx11-dev \
            libgtk-3-dev \
            python3-xlib \
            >>"$INSTALL_LOG" 2>&1

        apt-get install -y libpam-script >>"$INSTALL_LOG" 2>&1 || \
        apt-get install -y libpam-runtime >>"$INSTALL_LOG" 2>&1 || \
        warn "libpam-script not found — pam_exec fallback will be used"
        ;;

    dnf|yum)
        $PKG_MGR install -y \
            xdotool \
            wmctrl \
            alsa-utils \
            pulseaudio-utils \
            xorg-x11-utils \
            python3-pip \
            python3-devel \
            python3-virtualenv \
            cmake \
            gcc-c++ \
            make \
            boost-devel \
            openblas-devel \
            lapack-devel \
            gtk3-devel \
            >>"$INSTALL_LOG" 2>&1 || true
        warn "libpam-script not in Fedora repos — pam_exec will be used"
        ;;

    pacman)
        # BUG 8 FIX: -Sy without -u = partial upgrade = system breakage on Arch
        # Use -S only (no sync) — user should have run -Syu themselves
        pacman -S --noconfirm --needed \
            xdotool \
            wmctrl \
            alsa-utils \
            pulseaudio \
            xorg-xdpyinfo \
            python-pip \
            cmake \
            base-devel \
            boost \
            openblas \
            lapack \
            gtk3 \
            python-xlib \
            >>"$INSTALL_LOG" 2>&1 || true
        # Note: python -m venv is built-in (Python 3.3+), no extra package needed on Arch

        if command -v yay >/dev/null 2>&1; then
            su - "$REAL_USER" -c "yay -S --noconfirm --needed libpam-script" >>"$INSTALL_LOG" 2>&1 || \
            warn "libpam-script AUR install failed — pam_exec will be used"
        elif command -v paru >/dev/null 2>&1; then
            su - "$REAL_USER" -c "paru -S --noconfirm --needed libpam-script" >>"$INSTALL_LOG" 2>&1 || \
            warn "libpam-script AUR install failed — pam_exec will be used"
        else
            warn "No AUR helper — libpam-script skipped (install yay, then: yay -S libpam-script)"
        fi
        ;;

    zypper)
        zypper --non-interactive refresh >>"$INSTALL_LOG" 2>&1
        zypper --non-interactive install \
            xdotool \
            wmctrl \
            alsa-utils \
            pulseaudio-utils \
            xdpyinfo \
            python3-pip \
            python3-devel \
            python3-virtualenv \
            cmake \
            gcc-c++ \
            make \
            boost-devel \
            openblas-devel \
            lapack-devel \
            python3-xlib \
            >>"$INSTALL_LOG" 2>&1 || true

        zypper --non-interactive install pam-script >>"$INSTALL_LOG" 2>&1 || \
        warn "pam-script not found — pam_exec will be used"
        ;;
esac
ok "System packages done"

# ═══════════════════════════════════════════════════════════════
# STEP 3 — Python 3.13 + venv + pip packages
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[3/8] Setting up Python 3.13 environment...${NC}"

# ── Ensure Python 3.13 is available (REQUIRED for binary compatibility) ──
PYTHON_BIN=""
if command -v python3.13 >/dev/null 2>&1; then
    PYTHON_BIN="python3.13"
    info "Python 3.13 already installed: $(python3.13 --version)"
else
    info "Python 3.13 not found — installing..."

    case "$PKG_MGR" in
        apt)
            # Ubuntu/Debian/Kali — use deadsnakes PPA
            if [ "$DISTRO_ID" = "ubuntu" ] || [ "$DISTRO_ID" = "linuxmint" ] || [ "$DISTRO_ID" = "pop" ]; then
                info "Adding deadsnakes PPA for Python 3.13..."
                apt-get install -y software-properties-common >>"$INSTALL_LOG" 2>&1
                add-apt-repository -y ppa:deadsnakes/ppa >>"$INSTALL_LOG" 2>&1
                apt-get update -qq >>"$INSTALL_LOG" 2>&1
                DEBIAN_FRONTEND=noninteractive apt-get install -y                     python3.13 python3.13-venv python3.13-dev                     >>"$INSTALL_LOG" 2>&1
            else
                # Debian/Kali — try direct install
                DEBIAN_FRONTEND=noninteractive apt-get install -y                     python3.13 python3.13-venv python3.13-dev                     >>"$INSTALL_LOG" 2>&1 || true
            fi
            ;;
        dnf|yum)
            $PKG_MGR install -y python3.13 python3.13-devel                 >>"$INSTALL_LOG" 2>&1 || true
            ;;
        pacman)
            pacman -S --noconfirm --needed python313                 >>"$INSTALL_LOG" 2>&1 || true
            ;;
        zypper)
            zypper --non-interactive install python313 python313-devel                 >>"$INSTALL_LOG" 2>&1 || true
            ;;
    esac

    if command -v python3.13 >/dev/null 2>&1; then
        PYTHON_BIN="python3.13"
        ok "Python 3.13 installed: $(python3.13 --version)"
    else
        # Fallback: build from source (slow but works everywhere)
        warn "Python 3.13 not available via package manager"
        info "Attempting to build Python 3.13 from source (10-15 min)..."

        cd /tmp
        wget -q https://www.python.org/ftp/python/3.13.0/Python-3.13.0.tgz
        tar xzf Python-3.13.0.tgz
        cd Python-3.13.0
        ./configure --enable-optimizations --prefix=/usr/local >>"$INSTALL_LOG" 2>&1
        make -j$(nproc) >>"$INSTALL_LOG" 2>&1
        make altinstall >>"$INSTALL_LOG" 2>&1
        cd "$NOVA_DIR"
        rm -rf /tmp/Python-3.13*

        if command -v python3.13 >/dev/null 2>&1; then
            PYTHON_BIN="python3.13"
            ok "Python 3.13 built from source"
        else
            fail "Could not install Python 3.13 — installation cannot continue"
            exit 1
        fi
    fi
fi

# Verify Python 3.13
"$PYTHON_BIN" --version >>"$INSTALL_LOG" 2>&1 || {
    fail "Python 3.13 verification failed"
    exit 1
}

# BUG 2 FIX: chown project dir FIRST so REAL_USER can write, THEN create venv as that user
chown -R "$REAL_USER:$REAL_GROUP" "$NOVA_DIR" 2>/dev/null

if [ ! -d "$VENV" ]; then
    info "Creating Python 3.13 virtual environment..."
    su - "$REAL_USER" -c "$PYTHON_BIN -m venv '$VENV'" >>"$INSTALL_LOG" 2>&1 || {
        fail "venv creation failed with $PYTHON_BIN"
        exit 1
    }
    ok "Virtual environment created with Python 3.13"
fi

# STEP 3 — Install Python deps OFFLINE from bundled wheels (no PyPI, no build)
# dlib has no PyPI wheel, so wheels are prebuilt and shipped inside the package
# (nova_bundle/wheels/<pyver>). Offline install means a normal user gets a working
# face-unlock env with no network and no C++ toolchain. opencv-python-headless is
# bundled (NOT the GUI opencv-python) so it cannot clash with PyQt5's Qt.
VENV_PY=""
for _candidate in "$PROJECT_DIR/.venv/bin/python3" "$HOME/NovaUnlock/.venv/bin/python3" "/home/$REAL_USER/NovaUnlock/.venv/bin/python3"; do
    [ -f "$_candidate" ] && VENV_PY="$_candidate" && break
done
[ -z "$VENV_PY" ] && VENV_PY="$VENV/bin/python3"

PYVER="$("$VENV_PY" -c 'import sys; print(f"cp{sys.version_info.major}{sys.version_info.minor}")' 2>/dev/null)"
WHEELS_DIR="$NOVA_DIR/wheels/$PYVER"

if [ ! -d "$WHEELS_DIR" ] || [ -z "$(ls -A "$WHEELS_DIR" 2>/dev/null)" ]; then
    fail "Bundled wheels missing for $PYVER ($WHEELS_DIR). Cannot install dependencies offline."
    warn "This is a packaging defect — please report it."
    record_deps_status 1 dlib face_recognition face_recognition_models
else
    info "Installing bundled dependencies for $PYVER (offline)..."
    su - "$REAL_USER" -c "'$VENV/bin/pip' install --no-index --upgrade pip wheel setuptools 2>&1" >>"$INSTALL_LOG" 2>&1 \
        && ok "pip/wheel/setuptools upgraded" || warn "pip self-upgrade skipped"
    if su - "$REAL_USER" -c "'$VENV/bin/pip' install --no-index '$WHEELS_DIR'/*.whl 2>&1" >>"$INSTALL_LOG" 2>&1; then
        ok "Bundled dependencies installed ($PYVER)"
        record_deps_status 0
    else
        fail "Bundled wheel install failed for $PYVER — check $INSTALL_LOG"
        record_deps_status 1 dlib face_recognition face_recognition_models
    fi
fi

PYVER_DOT="$("$VENV_PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)"
VENV_DIR="$(dirname "$(dirname "$VENV_PY")")"
export PYTHONPATH="${PYTHONPATH}:$VENV_DIR/lib/python${PYVER_DOT}/site-packages"

[ "$FAIL" -eq 0 ] && ok "Python environment ready: $VENV" || warn "Python environment set up with some failures — check $INSTALL_LOG"

# ═══════════════════════════════════════════════════════════════
# STEP 4 — PAM Setup
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[4/8] Configuring PAM authentication...${NC}"

PAM_METHOD="pam_exec"
if find /lib /usr/lib /lib64 /usr/lib64 -name "pam_script.so" 2>/dev/null | grep -q .; then
    PAM_METHOD="pam_script"
fi
info "PAM method: $PAM_METHOD"

# Unified PAM auth script
cat > "$PAM_SCRIPT_BIN" << PAMSCRIPT
#!/bin/bash
CACHE="$CACHE_FILE"
LOGFILE="$LOG_DIR/pam_auth.log"
VENV_PY="$VENV/bin/python3"
PAM_PY="$NOVA_DIR/scripts/nova_pam_auth.py"

echo "\$(date) PAM called for: \$PAM_USER" >> "\$LOGFILE" 2>/dev/null

PAM_CLEAN=\$(echo "\$PAM_USER" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')

# Root always uses the password (face is primary for normal users only)
[ "\$PAM_CLEAN" = "root" ] && { echo "\$(date) ROOT SKIP" >> "\$LOGFILE" 2>/dev/null; exit 1; }

# Fast path: check short-lived PAM cache written by UI daemon / greeter
if [ -f "\$CACHE" ]; then
    CACHE_USER=\$("
\$VENV_PY" -c "
import json, sys, time
try:
    d = json.load(open('\$CACHE'))
    u = str(d.get('user','')).strip().lower()
    ts = float(d.get('ts', 0))
    if u and (time.time() - ts) <= 15:
        print(u)
except Exception:
    pass
" 2>/dev/null)

    if [ -n "\$CACHE_USER" ] && [ "\$CACHE_USER" = "\$PAM_CLEAN" ]; then
        echo "\$(date) CACHE HIT: \$PAM_CLEAN" >> "\$LOGFILE" 2>/dev/null
        rm -f "\$CACHE"
        exit 0
    fi
fi

# Fallback path: live camera face scan for sudo / lockscreen unlock
if [ -x "\$VENV_PY" ] && [ -f "\$PAM_PY" ]; then
    echo "\$(date) LIVE FACE SCAN START: \$PAM_CLEAN" >> "\$LOGFILE" 2>/dev/null
    if "\$VENV_PY" "\$PAM_PY" unlock "\$PAM_CLEAN" >> "\$LOGFILE" 2>&1; then
        echo "\$(date) LIVE MATCH SUCCESS: \$PAM_CLEAN" >> "\$LOGFILE" 2>/dev/null
        rm -f "\$CACHE"
        exit 0
    fi
fi

echo "\$(date) CACHE/LIVE MISS: cache=\$CACHE_USER pam=\$PAM_CLEAN" >> "\$LOGFILE" 2>/dev/null
rm -f "\$CACHE"
exit 1
PAMSCRIPT
chmod +x "$PAM_SCRIPT_BIN"

if [ "$PAM_METHOD" = "pam_script" ]; then
    PSCRIPT_DIR="/usr/share/libpam-script"
    mkdir -p "$PSCRIPT_DIR"
    for f in pam_script_acct pam_script_ses_open pam_script_ses_close; do
        [ ! -f "$PSCRIPT_DIR/$f" ] && \
        printf '#!/bin/bash\nexit 0\n' > "$PSCRIPT_DIR/$f" && \
        chmod +x "$PSCRIPT_DIR/$f"
    done
    cp "$PAM_SCRIPT_BIN" "$PSCRIPT_DIR/pam_script_auth"
    chmod +x "$PSCRIPT_DIR/pam_script_auth"
fi

if [ "$PAM_METHOD" = "pam_script" ]; then
    AUTH_LINE="auth    sufficient    pam_script.so"
else
    AUTH_LINE="auth    sufficient    pam_exec.so quiet $PAM_SCRIPT_BIN"
fi

case "$PKG_MGR" in
    apt)             COMMON_AUTH="common-auth"  ;;
    dnf|yum|pacman)  COMMON_AUTH="system-auth"  ;;
    zypper)          COMMON_AUTH="common-auth"  ;;
    *)               COMMON_AUTH="common-auth"  ;;
esac


configure_pam_gdm_safe() {
    # Safe GDM PAM config — password login preserved via @include
    local pam_file="$1"
    local label="$2"
    [ -f "$pam_file" ] && sed -i '/nova_pam_auth\|pam_script\.so\|pam_exec\.so.*nova/d' "$pam_file" 2>/dev/null
    if [ -f "$pam_file" ]; then
        TMPFILE=$(mktemp)
        printf '%s\n' "auth    [success=ok default=ignore]  pam_exec.so quiet $PAM_SCRIPT_BIN" > "$TMPFILE"
        cat "$pam_file" >> "$TMPFILE"
        mv "$TMPFILE" "$pam_file"
    else
        cat > "$pam_file" << GDMPAMEOF
#%PAM-1.0
# password login preserved — NovaUnlock adds face auth on top
auth    [success=ok default=ignore]  pam_exec.so quiet $PAM_SCRIPT_BIN
@include common-auth
@include common-account
@include common-session
GDMPAMEOF
    fi
    ok "PAM GDM-safe: $label (password login preserved)"
}

configure_pam_lockscreen() {
    local pam_file="$1"
    local label="$2"

    # BUG 4 FIX: sed -i "1s|^|...\n|" is not portable across GNU/BSD sed
    # Use a temp file + printf approach that works on all distros
    [ -f "$pam_file" ] && sed -i '/nova_pam_auth\|pam_script\.so/d' "$pam_file" 2>/dev/null

    if [ -f "$pam_file" ]; then
        TMPFILE=$(mktemp)
        printf '%s\n' "$AUTH_LINE" > "$TMPFILE"
        cat "$pam_file" >> "$TMPFILE"
        mv "$TMPFILE" "$pam_file"
    else
        cat > "$pam_file" << PAMEOF
#%PAM-1.0
auth    [success=ok default=ignore]  pam_exec.so quiet $PAM_SCRIPT_BIN
@include common-auth
@include common-account
@include common-session
PAMEOF
    fi
    ok "PAM: $label"
}

case "$DE" in
    xfce)     configure_pam_lockscreen "/etc/pam.d/xfce4-screensaver"    "xfce4-screensaver" ;;
    gnome)    configure_pam_lockscreen "/etc/pam.d/gnome-screensaver"    "gnome-screensaver"
              configure_pam_lockscreen "/etc/pam.d/gdm-password"         "gdm-password"      ;;
    kde)      configure_pam_lockscreen "/etc/pam.d/kde"                  "kde"
              configure_pam_lockscreen "/etc/pam.d/sddm"                 "sddm"              ;;
    mate)     configure_pam_lockscreen "/etc/pam.d/mate-screensaver"     "mate-screensaver"  ;;
    cinnamon) configure_pam_lockscreen "/etc/pam.d/cinnamon-screensaver" "cinnamon-screensaver" ;;
    *)        configure_pam_lockscreen "/etc/pam.d/xfce4-screensaver"    "xfce4-screensaver"
              configure_pam_lockscreen "/etc/pam.d/gnome-screensaver"    "gnome-screensaver"
              warn "Unknown DE — configured common PAM files"                      ;;
esac

# ── STEP 4 ADDON: sudo/polkit PAM hook (v1.32) ──────────────────────
configure_pam_sudo() {
    local pam_file="$1"
    local label="$2"
    [ -f "$pam_file" ] && sed -i '/nova_pam_auth\|pam_script\.so\|pam_exec\.so.*nova/d' "$pam_file" 2>/dev/null
    if [ -f "$pam_file" ]; then
        TMPFILE=$(mktemp)
        printf '%s\n' "$AUTH_LINE" > "$TMPFILE"
        cat "$pam_file" >> "$TMPFILE"
        mv "$TMPFILE" "$pam_file"
    else
        printf '#%%PAM-1.0\n%s\n@include common-auth\n' "$AUTH_LINE" > "$pam_file"
    fi
    ok "PAM privilege: $label"
}

NOVA_PAM_SCRIPT="$NOVA_DIR/nova_unlock/pam/pam_script_auth"
if [ -f "$NOVA_PAM_SCRIPT" ]; then
    if [ "$PAM_METHOD" = "pam_script" ]; then
        cp "$NOVA_PAM_SCRIPT" /usr/share/libpam-script/pam_script_auth
        chmod +x /usr/share/libpam-script/pam_script_auth
    else
        cp "$NOVA_PAM_SCRIPT" "$PAM_SCRIPT_BIN"
        chmod +x "$PAM_SCRIPT_BIN"
    fi
    ok "Nova PAM script deployed for privilege auth"
fi

configure_pam_sudo "/etc/pam.d/sudo" "sudo"
configure_pam_sudo "/etc/pam.d/su" "su"
[ -f "/etc/pam.d/polkit-1" ] && configure_pam_sudo "/etc/pam.d/polkit-1" "polkit-1"
[ -f "/etc/pam.d/pkexec" ]   && configure_pam_sudo "/etc/pam.d/pkexec"   "pkexec"
ok "Privilege auth PAM hooks installed (sudo/su/polkit)"

# ═══════════════════════════════════════════════════════════════
# STEP 5 — Display Manager Integration
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[5/8] Configuring display manager...${NC}"

if [ "$DM" = "lightdm" ]; then
    mkdir -p /etc/lightdm/lightdm.conf.d

    # BUG 6 FIX: Heredoc uses single-quoted delimiter (HELPER) so nothing expands
    # All runtime variables are written as literal $VAR with explicit escaping
    # CACHE_FILE path is written once as a literal string inside the script
    cat > /usr/local/bin/nova_unlock_greeter_helper.sh << 'HELPER_START'
#!/bin/bash
LOG=/tmp/nova_unlock_greeter.log
LOCK=/tmp/nova_unlock_greeter.lock
RESULT=/tmp/nova_unlock_greeter_result
CACHE=/tmp/nova_unlock_pam_cache.json
TMPCONF=/etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
HELPER_START

    # Now append the parts that DO need installer-time variable expansion
    cat >> /usr/local/bin/nova_unlock_greeter_helper.sh << HELPER_EXPAND
VENV_PYTHON="$VENV/bin/python3"
GREETER_SCRIPT="$GREETER_SCRIPT_PATH"
HELPER_EXPAND

    # Rest is pure runtime — single-quoted, no expansion
    cat >> /usr/local/bin/nova_unlock_greeter_helper.sh << 'HELPER_END'

exec >>"$LOG" 2>&1
echo "==== $(date) ===="

exec 9>"$LOCK"
flock -n 9 || exit 0
[ -f "$TMPCONF" ] && exit 0

DISP="${DISPLAY:-:0}"
DISP="${DISP%%.*}"
XAUTH=""
for p in \
    "/var/run/lightdm/root/$DISP" \
    "/var/run/lightdm/root/:0" \
    "/var/run/lightdm/root/:1" \
    "/var/lib/lightdm/.Xauthority"; do
    [ -e "$p" ] && XAUTH="$p" && break
done

[ -z "$XAUTH" ] && echo "XAUTH not found, aborting" && exit 0

export DISPLAY="$DISP"
export XAUTHORITY="$XAUTH"
export XDG_RUNTIME_DIR=/tmp/runtime-nova-unlock
export HOME=/root
mkdir -p /tmp/runtime-nova-unlock
chmod 700 /tmp/runtime-nova-unlock

rm -f "$RESULT"

nohup "$VENV_PYTHON" "$GREETER_SCRIPT" \
    >/tmp/nova_unlock_greeter_ui.out 2>/tmp/nova_unlock_greeter_ui.err &
UI_PID=$!
echo "Greeter UI pid=$UI_PID"

MATCHED=""
for i in $(seq 1 15); do
    [ -f "$RESULT" ] && MATCHED="$(tr -d '[:space:]' < "$RESULT")" && break
    sleep 1
done

kill "$UI_PID" 2>/dev/null
rm -f "$RESULT"

case "$MATCHED" in
    ""|*[!a-zA-Z0-9._-]*) echo "No valid match"; exit 0 ;;
esac

# Issue 2 FIX: never interpolate $MATCHED into python -c string
# a username with quotes/backslash would break or inject code
# pass via environment variable instead — safe regardless of username content
NOVA_MATCHED="$MATCHED" python3 - << 'PY'
import json, time, os
u = os.environ.get("NOVA_MATCHED", "")
with open("/tmp/nova_unlock_pam_cache.json", "w") as f:
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
HELPER_END

    chmod +x /usr/local/bin/nova_unlock_greeter_helper.sh

    cat > /usr/local/bin/nova_unlock_greeter_hook.sh << 'GREET'
#!/bin/bash
sleep 2
nohup /usr/local/bin/nova_unlock_greeter_helper.sh \
    >>/tmp/nova_unlock_greeter_launcher.log 2>&1 &
exit 0
GREET
    chmod +x /usr/local/bin/nova_unlock_greeter_hook.sh

    cat > /usr/local/bin/nova_unlock_session_cleanup.sh << 'CLEANUP'
#!/bin/bash
rm -f /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
rm -f /tmp/nova_unlock_pam_cache.json
exit 0
CLEANUP
    chmod +x /usr/local/bin/nova_unlock_session_cleanup.sh

    cat > /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf << 'LDMEOF'
[Seat:*]
greeter-setup-script=/usr/local/bin/nova_unlock_greeter_hook.sh
session-setup-script=/usr/local/bin/nova_unlock_session_cleanup.sh
greeter-show-manual-login=true
greeter-hide-users=true
LDMEOF
    ok "LightDM greeter hooks configured"

elif [ "$DM" = "gdm" ]; then
    # GDM greeter face login (PostLogin script approach)
    info "Configuring GDM greeter integration..."

    GDM_POSTLOGIN_DIR="/etc/gdm3/PostLogin"
    [ -d "/etc/gdm/PostLogin" ] && GDM_POSTLOGIN_DIR="/etc/gdm/PostLogin"
    mkdir -p "$GDM_POSTLOGIN_DIR"

    # Create greeter face detection hook
    cat > /usr/local/bin/nova_gdm_greeter_hook.sh << 'GDMHOOK'
#!/bin/bash
# Triggered by GDM after greeter starts
# IMPORTANT: Do NOT auto-submit password — only write PAM cache for face match
LOG=/tmp/nova_gdm_greeter.log
RESULT=/tmp/nova_unlock_greeter_result
CACHE=/tmp/nova_unlock_pam_cache.json

exec >>"$LOG" 2>&1
echo "==== $(date) GDM greeter hook ===="

# Wait for greeter to fully initialize
sleep 3

# Try to detect face for any enrolled user
DISP="${DISPLAY:-:0}"
export DISPLAY="$DISP"

# Find gdm-x-session display
for SESSION in /var/run/gdm3/*; do
    [ -d "$SESSION" ] && XAUTH="$SESSION/database" && [ -f "$XAUTH" ] && break
done

[ -z "$XAUTH" ] && XAUTH="/var/lib/gdm3/.Xauthority"
[ ! -f "$XAUTH" ] && XAUTH="/var/lib/gdm/.Xauthority"
[ -f "$XAUTH" ] && export XAUTHORITY="$XAUTH"

VENV_PY="NOVA_VENV_PYTHON_PLACEHOLDER"
GREETER="NOVA_GREETER_SCRIPT_PLACEHOLDER"

rm -f "$RESULT" "$CACHE"

if [ -x "$VENV_PY" ] && [ -f "$GREETER" ]; then
    timeout 20 "$VENV_PY" "$GREETER" >>/tmp/nova_gdm_greeter_ui.log 2>&1 &
    GUI_PID=$!

    # Wait up to 15s for face match
    for i in $(seq 1 15); do
        [ -f "$RESULT" ] && break
        sleep 1
    done

    kill "$GUI_PID" 2>/dev/null
fi

if [ -f "$RESULT" ]; then
    MATCHED=$(tr -d '[:space:]' < "$RESULT")
    case "$MATCHED" in
        ""|*[!a-zA-Z0-9._-]*) exit 0 ;;
    esac
    # Write PAM cache
    NOVA_MATCHED="$MATCHED" python3 - << 'PY'
import json, time, os
u = os.environ.get("NOVA_MATCHED", "")
with open("/tmp/nova_unlock_pam_cache.json", "w") as f:
    json.dump({"user": u, "profile": u, "ts": time.time()}, f)
PY
    chmod 600 "$CACHE"
    echo "Face matched: $MATCHED — cache written for PAM"
fi
GDMHOOK

    # Replace placeholders with real paths
    sed -i "s|NOVA_VENV_PYTHON_PLACEHOLDER|$VENV/bin/python3|g" /usr/local/bin/nova_gdm_greeter_hook.sh
    sed -i "s|NOVA_GREETER_SCRIPT_PLACEHOLDER|$NOVA_DIR/scripts/face_login_greeter.pyc|g" /usr/local/bin/nova_gdm_greeter_hook.sh
    chmod +x /usr/local/bin/nova_gdm_greeter_hook.sh

    # Hook via PostLogin (runs after greeter, before login complete)
    cat > "$GDM_POSTLOGIN_DIR/Default" << 'POSTLOGIN'
#!/bin/bash
[ -x /usr/local/bin/nova_gdm_greeter_hook.sh ] &&     /usr/local/bin/nova_gdm_greeter_hook.sh &
exit 0
POSTLOGIN
    chmod +x "$GDM_POSTLOGIN_DIR/Default"

    ok "GDM greeter hook installed (experimental)"
    warn "GDM: Greeter face detection is experimental — password fallback recommended"
elif [ "$DM" = "sddm" ]; then
    warn "SDDM — greeter face login not supported yet (lock screen unlock works)"
else
    warn "Display manager not detected — skipping greeter integration"
fi

# ═══════════════════════════════════════════════════════════════
# STEP 6 — Lock Screen Wrapper
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[6/8] Installing lock screen wrapper...${NC}"

# BUG 5 FIX: DE_LOCK was set at installer-time and baked into the script
# Now the wrapper detects DE at runtime from XDG_CURRENT_DESKTOP + pgrep
cat > /usr/local/bin/nova_xflock4_lock.sh << XFEOF
#!/bin/bash
LOG=/tmp/nova_xflock4.log
echo "==== \$(date) nova_lock start ====" >> "\$LOG"

LOCK_USER="$REAL_USER"
LOCK_HOME="$REAL_HOME"
LOCK_UID="$REAL_UID"
NOVA_VENV="$VENV"
NOVA_DAEMON="$DAEMON_SCRIPT_PATH"

(
    sleep 1.2
    export DISPLAY=:0
    export XAUTHORITY="\$LOCK_HOME/.Xauthority"
    export XDG_RUNTIME_DIR="/run/user/\$LOCK_UID"
    export PULSE_SERVER="unix:\${XDG_RUNTIME_DIR}/pulse/native"

    # Issue 4 FIX: target session manager processes specifically for DBUS
    for SM in xfce4-session gnome-session mate-session plasmashell cinnamon-session; do
        SM_PID=\$(pgrep -u "\$LOCK_USER" -x "\$SM" 2>/dev/null | head -1)
        [ -z "\$SM_PID" ] && continue
        DBUS=\$(tr '\0' '\n' < /proc/\$SM_PID/environ 2>/dev/null \
            | grep ^DBUS_SESSION_BUS_ADDRESS= | cut -d= -f2-)
        [ -n "\$DBUS" ] && export DBUS_SESSION_BUS_ADDRESS="\$DBUS" && break
    done

    xfconf-query -c xfwm4 -p /general/use_compositing -s true 2>/dev/null

    launch_face_ui() {
        nohup "\$NOVA_VENV/bin/python3" "\$NOVA_DAEMON" \
            >>/tmp/nova_lock_ui.out 2>>/tmp/nova_lock_ui.err &
        echo "Daemon pid=\$!" >> "\$LOG"
    }
    launch_face_ui
) &

# BUG 5 FIX: Detect DE at runtime, not baked-in installer time
RUNTIME_DE="unknown"
pgrep -x xfce4-session   >/dev/null 2>&1 && RUNTIME_DE="xfce"
pgrep -x gnome-session    >/dev/null 2>&1 && RUNTIME_DE="gnome"
pgrep -x plasmashell      >/dev/null 2>&1 && RUNTIME_DE="kde"
pgrep -x mate-session     >/dev/null 2>&1 && RUNTIME_DE="mate"
pgrep -x cinnamon-session >/dev/null 2>&1 && RUNTIME_DE="cinnamon"
[ "\$RUNTIME_DE" = "unknown" ] && case "\${XDG_CURRENT_DESKTOP:-}" in
    *XFCE*)     RUNTIME_DE="xfce"     ;;
    *GNOME*)    RUNTIME_DE="gnome"    ;;
    *KDE*)      RUNTIME_DE="kde"      ;;
    *MATE*)     RUNTIME_DE="mate"     ;;
    *Cinnamon*) RUNTIME_DE="cinnamon" ;;
esac

case "\$RUNTIME_DE" in
    xfce)
        pgrep -x xfce4-screensaver >/dev/null 2>&1 && xfce4-screensaver-command --lock
        pgrep -x light-locker      >/dev/null 2>&1 && light-locker-command --lock
        ;;
    gnome)
        exec dbus-send --type=method_call \
            --dest=org.gnome.ScreenSaver \
            /org/gnome/ScreenSaver \
            org.gnome.ScreenSaver.Lock 2>/dev/null || \
        exec gnome-screensaver-command -l 2>/dev/null
        ;;
    kde)
        exec qdbus org.kde.screensaver /ScreenSaver Lock 2>/dev/null || \
        exec loginctl lock-session
        ;;
    mate)
        exec mate-screensaver-command -l 2>/dev/null
        ;;
    cinnamon)
        exec cinnamon-screensaver-command -l 2>/dev/null
        ;;
esac

command -v dm-tool >/dev/null 2>&1 && exec dm-tool lock
exec loginctl lock-session
XFEOF
chmod +x /usr/local/bin/nova_xflock4_lock.sh

case "$DE" in
    xfce)
        su - "$REAL_USER" -c \
            "xfconf-query -c xfce4-session -p /general/LockCommand \
             -n -t string -s '/usr/local/bin/nova_xflock4_lock.sh' 2>/dev/null || \
             xfconf-query -c xfce4-session -p /general/LockCommand \
             -t string -s '/usr/local/bin/nova_xflock4_lock.sh' 2>/dev/null" 2>/dev/null
        ok "Lock command registered (XFCE)"
        ;;
    gnome)
        # Auto-bind Super+L to NovaUnlock via gsettings
        su - "$REAL_USER" -c "
            export DISPLAY=:0
            export DBUS_SESSION_BUS_ADDRESS=\"unix:path=/run/user/\$(id -u)/bus\"
            # Disable GNOME default screensaver shortcut
            gsettings set org.gnome.settings-daemon.plugins.media-keys screensaver \"[]\" 2>/dev/null
            # Register custom shortcut
            SP=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/nova-unlock/
            gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings \"['\$SP']\" 2>/dev/null
            gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\$SP name 'NovaUnlock Face Lock' 2>/dev/null
            gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\$SP command '/usr/local/bin/nova_xflock4_lock.sh' 2>/dev/null
            gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\$SP binding '<Super>l' 2>/dev/null
        " 2>/dev/null && ok "GNOME: Super+L bound to NovaUnlock" || \
        warn "GNOME: Auto-bind failed — set Super+L manually in Settings → Keyboard"
        ;;
    kde)
        # KDE: auto-bind via kwriteconfig5
        su - "$REAL_USER" -c "
            kwriteconfig5 --file kglobalshortcutsrc --group 'nova-unlock' --key '_k_friendly_name' 'NovaUnlock' 2>/dev/null
            kwriteconfig5 --file kglobalshortcutsrc --group 'nova-unlock' --key 'lock' 'Meta+L,none,NovaUnlock Lock' 2>/dev/null
        " 2>/dev/null && ok "KDE: Meta+L registered (logout to apply)" || \
        warn "KDE: Bind lock shortcut → /usr/local/bin/nova_xflock4_lock.sh manually"
        ;;
    *)
        warn "Unknown DE — lock wrapper at /usr/local/bin/nova_xflock4_lock.sh (bind manually)"
        ;;
esac

# ═══════════════════════════════════════════════════════════════
# STEP 7 — Lock Screen Watcher (with auto-restart)
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[7/8] Setting up lock screen watcher...${NC}"

detect_dbus_iface() {
    case "$DE" in
        gnome)    echo "org.gnome.ScreenSaver"      ;;
        kde)      echo "org.freedesktop.ScreenSaver" ;;
        mate)     echo "org.mate.ScreenSaver"        ;;
        cinnamon) echo "org.cinnamon.ScreenSaver"    ;;
        *)        echo "org.xfce.ScreenSaver"        ;;
    esac
}

case "$DE" in
    gnome)    DBUS_IFACE="org.gnome.ScreenSaver"      ;;
    kde)      DBUS_IFACE="org.freedesktop.ScreenSaver" ;;
    mate)     DBUS_IFACE="org.mate.ScreenSaver"        ;;
    cinnamon) DBUS_IFACE="org.cinnamon.ScreenSaver"    ;;
    *)        DBUS_IFACE="org.xfce.ScreenSaver"        ;;
esac

WATCHER_SCRIPT="/usr/local/bin/nova_unlock_watcher.sh"
cat > "$WATCHER_SCRIPT" << WATCHER_EOF
#!/bin/bash
export DISPLAY=:0
export XAUTHORITY="$REAL_HOME/.Xauthority"
export XDG_RUNTIME_DIR="/run/user/$REAL_UID"
export PULSE_SERVER="unix:\${XDG_RUNTIME_DIR}/pulse/native"

# Ensure the log dir exists (otherwise the redirect below silently drops all
# watcher output and "watcher not running" becomes undebuggable).
mkdir -p "$LOG_DIR" 2>/dev/null || true

# Clear any stale unlock-daemon lock file so a crashed previous session can't
# block the next one from starting.
rm -f /tmp/nova_unlock_face.lock 2>/dev/null || true

WLOG="$LOG_DIR/watcher.log"
FLOG="$LOG_DIR/face_auth.log"
VENV_PY="$VENV/bin/python3"
DAEMON="$DAEMON_SCRIPT_PATH"
DBUS_IFACE="$DBUS_IFACE"

# ── Post-login "hello, {username}" greeting ──────────
# The greeter writes /var/lib/novaunlock/last_login_user (matched user +
# timestamp) on a successful face unlock. lightdm restarts on login, so the
# greeting renders HERE, in the fresh user session — once, for the matching
# user, only if the marker is fresh (<60s).
show_login_hello() {
    local MARKER="/var/lib/novaunlock/last_login_user"
    [ -f "\$MARKER" ] || return 0
    local user ts now_s age
    user=\$(sed -n '1p' "\$MARKER" 2>/dev/null | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    ts=\$(sed -n '2p'  "\$MARKER" 2>/dev/null | tr -d '[:space:]')
    [ -n "\$user" ] || { rm -f "\$MARKER"; return 0; }
    case "\$ts" in (*[!0-9]*) rm -f "\$MARKER"; return 0 ;; esac
    now_s=\$(date +%s)
    age=\$(( now_s - ts ))
    [ "\$age" -le 60 ] || { rm -f "\$MARKER"; return 0; }
    [ "\$user" = "\$(id -un)" ] || { rm -f "\$MARKER"; return 0; }
    rm -f "\$MARKER"
    NOVA_ROOT="${NOVA_DIR:-/opt/novaunlock}" "$VENV/bin/python3" - "\$user" << 'HELLO'
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

# Issue 4 FIX: pgrep -u USER | head -5 is too broad — scans any random process
# Target session manager processes specifically by name; they always have DBUS in environ
if [ -z "\$DBUS_SESSION_BUS_ADDRESS" ]; then
    for SM in xfce4-session gnome-session mate-session plasmashell cinnamon-session; do
        SM_PID=\$(pgrep -u "$REAL_USER" -x "\$SM" 2>/dev/null | head -1)
        [ -z "\$SM_PID" ] && continue
        DBUS=\$(tr '\0' '\n' < /proc/\$SM_PID/environ 2>/dev/null \
            | grep ^DBUS_SESSION_BUS_ADDRESS= | cut -d= -f2-)
        [ -n "\$DBUS" ] && export DBUS_SESSION_BUS_ADDRESS="\$DBUS" && break
    done
fi

run_monitor() {
    dbus-monitor --session \\
        "type='signal',interface='\$DBUS_IFACE',member='ActiveChanged'" \\
        2>/dev/null | while read LINE; do

        if echo "\$LINE" | grep -q "boolean true"; then
            echo "\$(date) LOCKED" >> "\$WLOG"
            pkill -f "face_unlock_daemon" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock
            sleep 0.8
            "\$VENV_PY" "\$DAEMON" >> "\$FLOG" 2>&1 &

        elif echo "\$LINE" | grep -q "boolean false"; then
            echo "\$(date) UNLOCKED" >> "\$WLOG"
            pkill -f "face_unlock_daemon" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock
        fi
    done
}

# BUG 7 FIX: dbus-monitor pipe can silently die (DBus restart, session glitch)
# Watcher now loops forever with restart on failure
echo "\$(date) Watcher started (iface: \$DBUS_IFACE)" >> "\$WLOG"
while true; do
    run_monitor
    echo "\$(date) dbus-monitor exited — restarting in 3s" >> "\$WLOG"
    sleep 3
done
WATCHER_EOF
chmod +x "$WATCHER_SCRIPT"

AUTOSTART_DIR="$REAL_HOME/.config/autostart"
mkdir -p "$AUTOSTART_DIR"
cat > "$AUTOSTART_DIR/nova-unlock-watcher.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=NovaUnlock Watcher
Exec=/usr/local/bin/nova_unlock_watcher.sh
Comment=NovaUnlock face authentication watcher
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
DESKTOP
chown "$REAL_USER:$REAL_GROUP" "$AUTOSTART_DIR/nova-unlock-watcher.desktop"

pkill -f nova_unlock_watcher.sh 2>/dev/null; sleep 0.3
# Log dir MUST exist before the nohup redirect below, otherwise the parent
# shell's ">> $LOG_DIR/watcher.log" fails and all output is lost.
mkdir -p "$LOG_DIR"
chown "$REAL_USER:$REAL_GROUP" "$LOG_DIR" 2>/dev/null || true
su -s /bin/bash "$REAL_USER" -c "
    export DISPLAY=:0
    export XAUTHORITY=$REAL_HOME/.Xauthority
    export XDG_RUNTIME_DIR=/run/user/$REAL_UID
    nohup $WATCHER_SCRIPT >> $LOG_DIR/watcher.log 2>&1 &
    disown
" 2>/dev/null || true
ok "Watcher installed (dbus: $DBUS_IFACE, auto-restart: enabled)"

# ── Background presence-guard daemon (systemd user service) ───────────────
# The XDG-autostart watcher above launches the unlock UI on screen-lock. This
# systemd user service keeps the persistent FacePresenceGuard (auto-lock when
# you walk away) running in the background across reboots/logins. Paths are
# resolved to the real install dir (the repo's systemd/nova-unlock-watcher.service
# is only a template and hard-codes the dev tree).
SYSTEMD_USER_DIR="$REAL_HOME/.config/systemd/user"
mkdir -p "$SYSTEMD_USER_DIR"
cat > "$SYSTEMD_USER_DIR/nova-unlock-watcher.service" << SVC
[Unit]
Description=NovaUnlock Face Presence Guard
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
ExecStart=$VENV/bin/python3 $NOVA_DIR/scripts/face_unlock_daemon.pyc --guard
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=$REAL_HOME/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/$REAL_UID

[Install]
WantedBy=graphical-session.target
SVC
chown "$REAL_USER:$REAL_GROUP" "$SYSTEMD_USER_DIR/nova-unlock-watcher.service"
# Enable + start as the real user (needs the user's systemd session running).
su -s /bin/bash "$REAL_USER" -c "XDG_RUNTIME_DIR=/run/user/$REAL_UID systemctl --user daemon-reload && systemctl --user enable --now nova-unlock-watcher.service" 2>/dev/null || \
    warn "Could not enable systemd user service (no active user session yet). It will start on next login."
ok "Presence-guard background service registered (systemd user service)"

# ═══════════════════════════════════════════════════════════════
# STEP 8 — Permissions + Sudoers + Uninstaller
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[8/8] Finalizing...${NC}"

cat > /etc/sudoers.d/nova-unlock << SUEOF
$REAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart lightdm
$REAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart gdm
$REAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart gdm3
$REAL_USER ALL=(ALL) NOPASSWD: /bin/systemctl restart sddm
SUEOF
chmod 440 /etc/sudoers.d/nova-unlock
ok "Sudoers configured"

# System-level enable/disable switch.  The old watcher was a user service, so
# `sudo systemctl enable nova-facelock` could never control boot greeter or PAM
# behavior.  This unit is intentionally a small lifecycle switch; the per-user
# watcher remains responsible for in-session lock notifications.
cat > /usr/local/bin/nova_facelock_service.sh << 'FACEOFSERVICE'
#!/bin/bash
set -eu
FLAG=/etc/novaunlock/facelock.enabled
LDM_CONF=/etc/lightdm/lightdm.conf.d/50-nova-unlock.conf
case "${1:-}" in
  start)
    install -d -m 0755 /etc/novaunlock
    install -m 0600 /dev/null "$FLAG"
    if command -v lightdm >/dev/null 2>&1 && [ -x /usr/local/bin/nova_unlock_greeter_hook.sh ]; then
      install -d -m 0755 /etc/lightdm/lightdm.conf.d
      cat > "$LDM_CONF" << 'LDMEOF'
[Seat:*]
greeter-setup-script=/usr/local/bin/nova_unlock_greeter_hook.sh
session-setup-script=/usr/local/bin/nova_unlock_session_cleanup.sh
greeter-show-manual-login=true
greeter-hide-users=true
LDMEOF
      chmod 0644 "$LDM_CONF"
    fi
    ;;
  stop)
    rm -f "$FLAG" "$LDM_CONF" /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
    rm -f /tmp/nova_unlock_pam_cache.json /var/lib/novaunlock/pam_cache.json
    pkill -f face_login_greeter 2>/dev/null || true
    ;;
  *) echo "usage: $0 {start|stop}" >&2; exit 2 ;;
esac
FACEOFSERVICE
chmod 755 /usr/local/bin/nova_facelock_service.sh

cat > /etc/systemd/system/novaunlock.service << 'FACEUNIT'
[Unit]
Description=NovaUnlock FaceLock System Authentication & Greeter Service
After=local-fs.target network.target
Before=display-manager.service
Alias=nova-facelock.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/nova_facelock_service.sh start
ExecStop=/usr/local/bin/nova_facelock_service.sh stop
ExecReload=/usr/local/bin/nova_facelock_service.sh restart

[Install]
WantedBy=multi-user.target
FACEUNIT
ln -sf /etc/systemd/system/novaunlock.service /etc/systemd/system/nova-facelock.service 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now novaunlock.service || warn "Could not start novaunlock.service; enable it after installation"
ok "FaceLock system service registered (novaunlock / nova-facelock)"


chown -R "$REAL_USER:$REAL_GROUP" "$NOVA_DIR"

cat > "$NOVA_DIR/uninstall.sh" << 'UNEOF'
#!/bin/bash
echo "Removing NovaUnlock..."
[ "$EUID" -ne 0 ] && echo "Run with: sudo bash uninstall.sh" && exit 1

REAL_USER="${SUDO_USER:-$USER}"
[ "$REAL_USER" = "root" ] && REAL_USER=$(logname 2>/dev/null || echo "")
REAL_HOME="/home/$REAL_USER"

systemctl disable --now nova-facelock.service 2>/dev/null || true
rm -f /etc/systemd/system/nova-facelock.service /etc/novaunlock/facelock.enabled
systemctl daemon-reload 2>/dev/null || true

rm -f \
    /usr/local/bin/nova_xflock4_lock.sh \
    /usr/local/bin/nova_unlock_greeter_hook.sh \
    /usr/local/bin/nova_unlock_greeter_helper.sh \
    /usr/local/bin/nova_facelock_service.sh \
    /usr/local/bin/nova_unlock_session_cleanup.sh \
    /usr/local/bin/nova_unlock_watcher.sh \
    /usr/local/bin/nova_pam_auth.sh \
    /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf \
    /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf \
    /etc/sudoers.d/nova-unlock \
    /tmp/nova_*

for f in \
    /etc/pam.d/xfce4-screensaver \
    /etc/pam.d/gnome-screensaver \
    /etc/pam.d/gdm-password \
    /etc/pam.d/kde \
    /etc/pam.d/sddm \
    /etc/pam.d/mate-screensaver \
    /etc/pam.d/cinnamon-screensaver \
    /etc/pam.d/sudo \
    /etc/pam.d/su \
    /etc/pam.d/polkit-1 \
    /etc/pam.d/pkexec; do
    [ -f "$f" ] && sed -i '/nova_pam_auth\|pam_script\.so/d' "$f" 2>/dev/null
done

PSCRIPT_DIR="/usr/share/libpam-script"
[ -f "$PSCRIPT_DIR/pam_script_auth" ] && rm -f "$PSCRIPT_DIR/pam_script_auth"

rm -f "$REAL_HOME/.config/autostart/nova-unlock-watcher.desktop"
pkill -f nova_unlock_watcher  2>/dev/null || true
pkill -f face_unlock_daemon   2>/dev/null || true
pkill -f face_login_greeter   2>/dev/null || true

su - "$REAL_USER" -c \
    "xfconf-query -c xfce4-session -p /general/LockCommand -r 2>/dev/null" 2>/dev/null || true

echo "✅ NovaUnlock removed. Run: sudo systemctl restart lightdm"
UNEOF
chmod +x "$NOVA_DIR/uninstall.sh"
chown "$REAL_USER:$REAL_GROUP" "$NOVA_DIR/uninstall.sh"
ok "Uninstaller created"

# ═══════════════════════════════════════════════════════════════
# STEP 9 — Post-Install Verification
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${CYAN}[9/9] Verifying installation...${NC}"
[ -f "$PAM_SCRIPT_BIN" ]          && ok "PAM script exists"          || fail "PAM script missing"
[ -x "$PAM_SCRIPT_BIN" ]          && ok "PAM script executable"      || fail "PAM script not executable"
[ -d "$VENV" ]                    && ok "Python venv exists"         || fail "Python venv missing"
[ -f "$VENV/bin/python3" ]        && ok "Python binary in venv"      || fail "Python binary missing"
[ -f "$WATCHER_SCRIPT" ]          && ok "Watcher script exists"      || fail "Watcher script missing"
pgrep -f nova_unlock_watcher >/dev/null 2>&1 && ok "Watcher is running" || warn "Watcher not running yet"
if "$VENV/bin/python3" -c "import face_recognition, cv2, numpy" 2>/dev/null; then
    ok "Python deps verified"
    record_deps_status 0
else
    warn "Python deps check failed — face unlock may not work; re-run the installer"
    record_deps_status 1 dlib face_recognition face_recognition_models
fi
echo

# ═══════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ═══════════════════════════════════════════════════════════════
echo
echo -e "${BOLD}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║     NovaUnlock — Installation Complete       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════╝${NC}"
echo
echo -e "  ${GREEN}✅ Passed :${NC}   $PASS"
[ "$WARN" -gt 0 ] && echo -e "  ${YELLOW}⚠️  Warnings:${NC}  $WARN"
[ "$FAIL" -gt 0 ] && echo -e "  ${RED}❌ Failed :${NC}   $FAIL"
echo
echo "  System:"
echo "    Distro   : ${DISTRO_ID:-unknown}"
echo "    Desktop  : $DE"
echo "    DM       : $DM"
echo "    PAM      : $PAM_METHOD"
echo "    DBus     : $DBUS_IFACE"
echo
echo "  Next steps:"
echo "    1. Enroll your face:"
echo "       cd $NOVA_DIR && source .venv/bin/activate"
echo "       python3 $ENROLL_WIZARD_SCRIPT --user $REAL_USER"
echo
echo "    2. Test demo UI:"
echo "       $VENV/bin/python3 $DEMO_SCRIPT_PATH --demo"
echo
echo "    3. Test lock screen:"
echo "       xflock4"
echo
echo "    4. Uninstall:"
echo "       sudo bash $NOVA_DIR/uninstall.sh"
echo
if [ "${NOVA_WAYLAND_OK:-0}" = "1" ]; then
    echo
    echo -e "  ${GREEN}ℹ️  Wayland session detected — supported out of the box.${NC}"
    echo
    echo "  NovaUnlock runs on Wayland via XWayland; no display-manager changes"
    echo "  were made. Face unlock will work after enrolling your face."
    echo
fi
[ "$FAIL" -gt 0 ] && echo -e "  ${YELLOW}Full log: $INSTALL_LOG${NC}" && echo
