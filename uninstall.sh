#!/bin/bash
echo "Removing NovaUnlock..."
[ "$EUID" -ne 0 ] && echo "Run with: sudo bash uninstall.sh" && exit 1

REAL_USER="${SUDO_USER:-$USER}"
[ "$REAL_USER" = "root" ] && REAL_USER=$(logname 2>/dev/null || echo "")
REAL_HOME="/home/$REAL_USER"

systemctl disable --now novaunlock.service nova-facelock.service 2>/dev/null || true
rm -f /etc/systemd/system/novaunlock.service /etc/systemd/system/nova-facelock.service /etc/novaunlock/facelock.enabled
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
    /etc/pam.d/cinnamon-screensaver; do
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
