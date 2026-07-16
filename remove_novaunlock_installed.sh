#!/bin/bash
# =============================================================================
# remove_novaunlock_installed.sh
# -----------------------------------------------------------------------------
# Uninstalls the OLD installed NovaUnlock build from this laptop and wipes the
# enrolled face profiles so you can re-enroll from a clean slate.
#
# WHAT THIS REMOVES (install-owned, never the source code):
#   - systemd USER service   : ~/.config/systemd/user/nova-unlock-watcher.service
#   - background daemons     : face_unlock_daemon / face_login_greeter / watcher
#   - PAM hooks              : lines added to /etc/pam.d/* , /usr/share/libpam-script
#   - helper binaries        : /usr/local/bin/nova_*
#   - lightdm / sudoers / autostart configs
#   - native install dir     : /opt/novaunlock   (deb/rpm/arch package)
#   - runtime state + FACES  : /var/lib/novaunlock  (enrolled faces live here)
#
# WHAT THIS NEVER TOUCHES ("don't touch code"):
#   - ~/Desktop/NovaUnlock  and  ~/NovaUnlock  (the source repositories)
#   - any *.py / *.sh / build scripts inside those repos
#   - per your choice, enrolled-face images that may sit inside the home repo
#     folder (e.g. ~/Desktop/NovaUnlock/data/faces) are LEFT in place.
#
# USAGE:
#   sudo bash remove_novaunlock_installed.sh            # actually remove
#   sudo bash remove_novaunlock_installed.sh --dry-run  # preview only, no deletes
# =============================================================================
set -uo pipefail

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

[ "$EUID" -ne 0 ] && { echo "Run as root:  sudo bash $0 [--dry-run]"; exit 1; }

REAL_USER="${SUDO_USER:-$USER}"
[ "$REAL_USER" = "root" ] && REAL_USER="$(logname 2>/dev/null || echo "")"
REAL_HOME="/home/$REAL_USER"
REAL_UID="$(id -u "$REAL_USER" 2>/dev/null || echo 1000)"

# --- safety: the two source-code repos we must NEVER delete -----------------
PROTECTED_DIRS=(
    "$REAL_HOME/Desktop/NovaUnlock"
    "$REAL_HOME/NovaUnlock"
    "$REAL_HOME/Desktop/NovaUnlock/remove_novaunlock_installed.sh"
)

# Enumerated, install-owned targets only. No globs that could reach the repo.
REMOVE_FILES=(
    /usr/local/bin/nova_xflock4_lock.sh
    /usr/local/bin/nova_unlock_greeter_hook.sh
    /usr/local/bin/nova_unlock_greeter_helper.sh
    /usr/local/bin/nova_unlock_session_cleanup.sh
    /usr/local/bin/nova_unlock_watcher.sh
    /usr/local/bin/nova_pam_auth.sh
    /usr/share/libpam-script/pam_script_auth
    /etc/lightdm/lightdm.conf.d/50-nova-unlock.conf
    /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
    /etc/sudoers.d/nova-unlock
    "$REAL_HOME/.config/autostart/nova-unlock-watcher.desktop"
    "$REAL_HOME/.config/systemd/user/nova-unlock-watcher.service"
)
REMOVE_DIRS=(
    /opt/novaunlock
    /var/lib/novaunlock
)

PAM_FILES=(
    /etc/pam.d/xfce4-screensaver
    /etc/pam.d/gnome-screensaver
    /etc/pam.d/gdm-password
    /etc/pam.d/kde
    /etc/pam.d/sddm
    /etc/pam.d/mate-screensaver
    /etc/pam.d/cinnamon-screensaver
)

run() { if [ "$DRY_RUN" -eq 1 ]; then echo "  [dry-run] $*"; else eval "$@"; fi; }

# --- guard: abort if any protected dir somehow appears in our targets --------
for p in "${REMOVE_FILES[@]}" "${REMOVE_DIRS[@]}"; do
    for prot in "${PROTECTED_DIRS[@]}"; do
        [ "$p" = "$prot" ] && { echo "ABORT: protected path in remove list: $p"; exit 1; }
    done
done

echo "==================================================================="
echo " NovaUnlock — remove OLD installed version + enrolled faces"
echo " User: $REAL_USER   Home: $REAL_HOME"
[ "$DRY_RUN" -eq 1 ] && echo " MODE: DRY RUN (nothing will be deleted)"
echo "==================================================================="

# --- 1. stop + disable systemd user service --------------------------------
echo "[1] Disabling systemd watcher service..."
run "timeout 20 su -s /bin/bash '$REAL_USER' -c 'XDG_RUNTIME_DIR=/run/user/$REAL_UID systemctl --user disable --now nova-unlock-watcher.service 2>/dev/null' || true"
run "systemctl disable --now nova-unlock-watcher.service 2>/dev/null || true"   # system-level (if any)
run "rm -f '$REAL_HOME/.config/systemd/user/nova-unlock-watcher.service'"
run "timeout 20 su -s /bin/bash '$REAL_USER' -c 'XDG_RUNTIME_DIR=/run/user/$REAL_UID systemctl --user daemon-reload 2>/dev/null' || true"

# --- 2. kill running daemons ------------------------------------------------
echo "[2] Killing NovaUnlock daemons..."
run "pkill -f face_unlock_daemon   2>/dev/null || true"
run "pkill -f face_login_greeter   2>/dev/null || true"
run "pkill -f nova_unlock_watcher  2>/dev/null || true"
run "pkill -f nova_pam_auth        2>/dev/null || true"

# --- 3. revert PAM hooks ----------------------------------------------------
echo "[3] Reverting PAM configuration..."
for f in "${PAM_FILES[@]}"; do
    [ -f "$f" ] && run "sed -i '/nova_pam_auth\|pam_script\.so/d' '$f' 2>/dev/null || true"
done

# --- 4. remove helper binaries / configs / tmp -----------------------------
echo "[4] Removing helper binaries, configs and temp files..."
for f in "${REMOVE_FILES[@]}"; do
    run "rm -f '$f'"
done
run "rm -f /tmp/nova_* 2>/dev/null || true"
run "timeout 15 su - '$REAL_USER' -c \"xfconf-query -c xfce4-session -p /general/LockCommand -r 2>/dev/null\" 2>/dev/null || true"

# --- 5. remove native install dir + runtime state (incl. ENROLLED FACES) ----
echo "[5] Removing installed app dir and runtime state (enrolled faces)..."
for d in "${REMOVE_DIRS[@]}"; do
    run "rm -rf '$d'"
done

# --- 6. report --------------------------------------------------------------
echo "==================================================================="
if [ "$DRY_RUN" -eq 1 ]; then
    echo " Dry run complete. Re-run WITHOUT --dry-run to actually remove."
else
    echo " Done. Old NovaUnlock install + enrolled faces removed."
fi
echo
echo " NOTE: per 'don't touch code', the source repos were NOT deleted:"
echo "        - $REAL_HOME/Desktop/NovaUnlock"
echo "        - $REAL_HOME/NovaUnlock"
echo "       If you originally installed with the in-place universal"
echo "       installer, those repos may still contain a .venv / data/faces /"
echo "       logs folder. Those are runtime artifacts inside the code dir and"
echo "       were left alone on purpose. Delete them manually if you want a"
echo "       fully clean slate, or just re-run the installer to re-enroll."
echo
echo " Next: reboot or 'sudo systemctl restart lightdm' (or your display"
echo "       manager), then re-install v2.014 and enroll fresh faces."
echo "==================================================================="
