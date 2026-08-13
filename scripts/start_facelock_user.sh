#!/bin/bash
# Linux-FaceLock User Autostart Watcher & Presence Guard

export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python3"
DAEMON="$PROJECT_ROOT/scripts/face_unlock_daemon.py"

if [ ! -f "$VENV_PYTHON" ]; then
    VENV_PYTHON="python3"
fi

mkdir -p "$HOME/.cache/linux_facelock"
LOG="$HOME/.cache/linux_facelock/watcher.log"

echo "==== $(date) Linux-FaceLock Autostart Active ====" >> "$LOG"

# Detect DBus ScreenSaver interface
DE_IFACE="org.xfce.ScreenSaver"
case "${XDG_CURRENT_DESKTOP:-}" in
    *GNOME*)    DE_IFACE="org.gnome.ScreenSaver"      ;;
    *KDE*)      DE_IFACE="org.freedesktop.ScreenSaver" ;;
    *MATE*)     DE_IFACE="org.mate.ScreenSaver"        ;;
    *Cinnamon*) DE_IFACE="org.cinnamon.ScreenSaver"    ;;
esac

# Clean stale lock files on startup
rm -f /tmp/nova_unlock_face.lock 2>/dev/null || true

run_dbus_monitor() {
    dbus-monitor --session \
        "type='signal',interface='$DE_IFACE',member='ActiveChanged'" 2>/dev/null | \
    while read -r line; do
        if echo "$line" | grep -q "boolean true"; then
            echo "$(date) Screen Locked — Launching Face ID daemon" >> "$LOG"
            pkill -f "face_unlock_daemon.py" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock 2>/dev/null
            sleep 0.5
            "$VENV_PYTHON" "$DAEMON" >> "$LOG" 2>&1 &
        elif echo "$line" | grep -q "boolean false"; then
            echo "$(date) Screen Unlocked" >> "$LOG"
            pkill -f "face_unlock_daemon.py" 2>/dev/null
            rm -f /tmp/nova_unlock_face.lock 2>/dev/null
        fi
    done
}

while true; do
    run_dbus_monitor
    sleep 3
done
