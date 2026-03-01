#!/bin/sh
DSP=/dev/dsp1
VDSP=/dev/vdsp.0
RATE=48000

echo "starting rigctld" 

rigctld -m 3073 -s 9600 -r /dev/cuaU0 &



echo "Starting virtual_oss mixer..."
virtual_oss -C 2 -c 2 -r $RATE -b 16 -s 4ms -f $DSP -m 0,0,1,1 -d vdsp.0 &
VOSS_PID=$!
sleep 2
mixer vol 100:100
mixer pcm 100:100
if [ ! -e $VDSP ]; then
  echo "ERROR: $VDSP did not get created"
  exit 1
fi

echo "virtual_oss started, $VDSP is ready"

echo "Starting RX stream on port 9000..."
while true; do
  sox -t oss $VDSP -r $RATE -c 2 -b 16 -e signed-integer -t wav - | nc -l 9000
  echo "RX client disconnected, restarting..."
  sleep 1
done &
RX_PID=$!

echo "Starting TX stream on port 8766..."
while true; do
  nc -l 8766 | play -q --buffer 1024 -t raw -r $RATE -c 1 -b 16 -e signed-integer  - -v 15.0  -t oss $VDSP
  echo "TX client disconnected, restarting..."
  sleep 1
done &
TX_PID=$!

echo "Audio streaming started."
echo "virtual_oss PID=$VOSS_PID"
echo "RX PID=$RX_PID  TX PID=$TX_PID"
wait
