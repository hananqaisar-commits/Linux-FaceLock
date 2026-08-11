#!/bin/bash
set -e
SWITCH=/etc/novaunlock/facelock.enabled
CACHE=/var/lib/novaunlock/pam_cache.json
mkdir -p /etc/novaunlock /var/lib/novaunlock
case "${1:-}" in
  start) install -m 600 /dev/null "$SWITCH" ;;
  stop)  rm -f "$SWITCH" "$CACHE" ;;
  *)     echo "Usage: $0 {start|stop}" >&2; exit 1 ;;
esac
