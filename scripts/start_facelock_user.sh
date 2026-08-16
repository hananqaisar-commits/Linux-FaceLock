#!/bin/bash
# Linux-FaceLock User Autostart Watcher & Presence Guard

export DISPLAY=${DISPLAY:-:0}
export XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="/usr/bin/python3"
DAEMON="$PROJECT_ROOT/scripts/face_unlock_daemon.py"


mkdir -p "$HOME/.cache/linux_facelock"
LOG="$HOME/.cache/linux_facelock/watcher.log"

echo "==== $(date) Linux-FaceLock Autostart Active ====" >> "$LOG"

# Detect DBus ScreenSaver interface
DE_SERVICE="org.freedesktop.ScreenSaver"
DE_IFACE="org.freedesktop.ScreenSaver"
case "${XDG_CURRENT_DESKTOP:-}" in
    *GNOME*)
        DE_SERVICE="org.gnome.ScreenSaver"
        DE_IFACE="org.gnome.ScreenSaver"
        ;;
    *KDE*)
        DE_SERVICE="org.kde.screensaver"
        DE_IFACE="org.freedesktop.ScreenSaver"
        ;;
    *MATE*)
        DE_SERVICE="org.mate.ScreenSaver"
        DE_IFACE="org.mate.ScreenSaver"
        ;;
    *Cinnamon*)
        DE_SERVICE="org.cinnamon.ScreenSaver"
        DE_IFACE="org.cinnamon.ScreenSaver"
        ;;
esac

# Clean stale lock files on startup
rm -f /tmp/nova_unlock_face.lock 2>/dev/null || true

run_dbus_monitor() {
    dbus-monitor --session \
        "type='signal',sender='$DE_SERVICE',path='/ScreenSaver',interface='$DE_IFACE',member='ActiveChanged'" 2>/dev/null | \
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
