#!/bin/bash
# Capture timed screenshots of face_id_screen demo
# Demo cycles: IDLE(0.6s) → SCAN(2s) → SUCCESS(0.45s) → reset → IDLE → SCAN → FAIL(1.2s) → reset ...

DIR="/home/hanan/Desktop/NovaUnlock/assets/raw"
mkdir -p "$DIR"

echo "=== Starting demo in background ==="
cd /home/hanan/Desktop/NovaUnlock
.venv/bin/python3 -m nova_unlock.ui.face_id_screen &
DEMO_PID=$!
echo "Demo PID: $DEMO_PID"

# Wait for window to appear
sleep 1.5

# Screenshot 1: SCANNING state (lock + face ID icon visible) 
# At ~1.5s we should be in SCAN phase
echo "📸 Capturing SCANNING state..."
scrot "$DIR/scan_full.png"
sleep 1.0

# Screenshot 2: SUCCESS state (green sphere + unlocked lock)
# Success triggers at ~2.6s into demo, animation runs 0.45s
echo "📸 Capturing SUCCESS state..."
scrot "$DIR/success_full.png"
sleep 0.3
scrot "$DIR/success_full2.png"

# Wait for hello overlay to appear
sleep 1.0
echo "📸 Capturing HELLO overlay..."
scrot "$DIR/hello_full.png"
sleep 0.5
scrot "$DIR/hello_full2.png"

# Wait for next cycle: IDLE → SCAN → FAIL
sleep 3.0
echo "📸 Capturing FAIL state..."
scrot "$DIR/fail_full.png"
sleep 0.2
scrot "$DIR/fail_full2.png"

# Kill the demo
sleep 1
kill $DEMO_PID 2>/dev/null
pkill -f hello_overlay 2>/dev/null

echo "=== All screenshots captured in $DIR ==="
ls -la "$DIR"
