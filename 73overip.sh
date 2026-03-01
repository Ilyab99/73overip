#!/usr/local/bin/bash
# 73overip.sh - IC-7300 Remote Audio Streaming
# MM7IBG - GPL v3

DSP=/dev/dsp1
VDSP=/dev/vdsp.0
RATE=48000
RX_PORT=9000
TX_PORT=8766
LOGFILE=/tmp/73overip.log

# ── Redirect all output to log file AND terminal ──────────────────────────────
exec > >(tee -a "$LOGFILE") 2>&1

echo "========================================="
echo " 73overip starting at $(date)"
echo "========================================="

# ── Cleanup any previous run ──────────────────────────────────────────────────
echo "Cleaning up any previous processes..."
killall -9 rigctld virtual_oss nc sox play 2>/dev/null
sleep 2

# ── Start rigctld ─────────────────────────────────────────────────────────────
echo "Starting rigctld..."
nohup rigctld -m 3073 -s 9600 -r /dev/cuaU0 > /tmp/rigctld.log 2>&1 &
RIGCTLD_PID=$!
echo "rigctld PID=$RIGCTLD_PID"
sleep 1

# ── Start virtual_oss ─────────────────────────────────────────────────────────
echo "Starting virtual_oss..."
nohup virtual_oss -C 2 -c 2 -r $RATE -b 16 -s 4ms -f $DSP -m 0,0,1,1 -d vdsp.0 > /tmp/voss.log 2>&1 &
VOSS_PID=$!
echo "virtual_oss PID=$VOSS_PID"
sleep 3

# ── Set mixer levels ──────────────────────────────────────────────────────────
mixer vol 100:100
mixer pcm 100:100

# ── Verify virtual device exists ──────────────────────────────────────────────
if [ ! -e "$VDSP" ]; then
    echo "ERROR: $VDSP did not get created — check DSP=$DSP is correct"
    exit 1
fi
echo "$VDSP is ready"

# ── RX loop (Pi → Windows) ───────────────────────────────────────────────────
rx_loop() {
    echo "RX loop started on port $RX_PORT"
    while true; do
        echo "RX waiting for connection on port $RX_PORT..."
        sox -t oss $VDSP -r $RATE -c 2 -b 16 -e signed-integer -t wav - 2>/dev/null \
            | nc -l $RX_PORT 2>/dev/null
        echo "RX client disconnected at $(date), restarting in 1s..."
        # Make sure no zombie sox is left behind
        killall -9 sox 2>/dev/null
        sleep 1
    done
}

# ── TX loop (Windows → Pi) ───────────────────────────────────────────────────
tx_loop() {
    echo "TX loop started on port $TX_PORT"
    while true; do
        echo "TX waiting for connection on port $TX_PORT..."
        nc -l $TX_PORT 2>/dev/null \
            | play -q --buffer 1024 -t raw -r $RATE -c 1 -b 16 -e signed-integer - \
              -v 15.0 -t oss $VDSP 2>/dev/null
        echo "TX client disconnected at $(date), restarting in 1s..."
        # Make sure no zombie play/sox is left behind
        killall -9 play sox 2>/dev/null
        sleep 1
    done
}

# ── Watchdog — restarts loops if they die ────────────────────────────────────
watchdog() {
    echo "Watchdog started"
    while true; do
        sleep 10

        # Check virtual_oss is still alive
        if ! kill -0 $VOSS_PID 2>/dev/null; then
            echo "WATCHDOG: virtual_oss died! Restarting..."
            nohup virtual_oss -C 2 -c 2 -r $RATE -b 16 -s 4ms -f $DSP -m 0,0,1,1 -d vdsp.0 > /tmp/voss.log 2>&1 &
            VOSS_PID=$!
            sleep 3
            mixer vol 100:100
            mixer pcm 100:100
        fi

        # Check rigctld is still alive
        if ! kill -0 $RIGCTLD_PID 2>/dev/null; then
            echo "WATCHDOG: rigctld died! Restarting..."
            nohup rigctld -m 3073 -s 9600 -r /dev/cuaU0 > /tmp/rigctld.log 2>&1 &
            RIGCTLD_PID=$!
        fi

        # Check RX loop is still alive
        if ! kill -0 $RX_PID 2>/dev/null; then
            echo "WATCHDOG: RX loop died! Restarting..."
            rx_loop &
            RX_PID=$!
        fi

        # Check TX loop is still alive
        if ! kill -0 $TX_PID 2>/dev/null; then
            echo "WATCHDOG: TX loop died! Restarting..."
            tx_loop &
            TX_PID=$!
        fi
    done
}

# ── Launch everything in background, detached from terminal ──────────────────
rx_loop &
RX_PID=$!

tx_loop &
TX_PID=$!

watchdog &
WATCH_PID=$!

echo "========================================="
echo " All services running"
echo " virtual_oss PID : $VOSS_PID"
echo " rigctld PID     : $RIGCTLD_PID"
echo " RX PID          : $RX_PID"
echo " TX PID          : $TX_PID"
echo " Watchdog PID    : $WATCH_PID"
echo " Log file        : $LOGFILE"
echo "========================================="
echo "You can safely close this terminal."
echo "To stop everything: sudo killall -9 nc sox play virtual_oss rigctld"

# ── Detach from terminal so closing PuTTY can't kill anything ────────────────
disown $VOSS_PID $RIGCTLD_PID $RX_PID $TX_PID $WATCH_PID 2>/dev/null

wait