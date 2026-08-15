#!/bin/bash
set -euo pipefail

FLAG=/etc/novaunlock/facelock.enabled
LDM_CONF=/etc/lightdm/lightdm.conf.d/50-nova-unlock.conf
CACHE_VAR=/var/lib/novaunlock/pam_cache.json
CACHE_TMP=/tmp/nova_unlock_pam_cache.json

case "${1:-}" in
  start|restart)
    install -d -m 0755 /etc/novaunlock /var/lib/novaunlock /var/log/novaunlock
    install -m 0600 /dev/null "$FLAG"
    echo "true" > "$FLAG"

    # Configure LightDM greeter hook if LightDM is present
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
    echo "NovaUnlock FaceLock service started (enabled)."
    ;;
  stop)
    rm -f "$FLAG" "$LDM_CONF" /etc/lightdm/lightdm.conf.d/99-nova-unlock-autologin.conf
    rm -f "$CACHE_VAR" "$CACHE_TMP"
    pkill -f face_login_greeter 2>/dev/null || true
    pkill -f face_unlock_daemon 2>/dev/null || true
    echo "NovaUnlock FaceLock service stopped (disabled)."
    ;;
  status)
    if [ -f "$FLAG" ]; then
      echo "NovaUnlock FaceLock is ENABLED and ACTIVE."
      exit 0
    else
      echo "NovaUnlock FaceLock is DISABLED."
      exit 3
    fi
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}" >&2
    exit 2
    ;;
esac
