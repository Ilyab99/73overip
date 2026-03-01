@echo off
echo Starting Radio RX...
start "" "C:\Program Files\VideoLAN\VLC\vlc.exe" -I dummy --network-caching=200 tcp://192.168.0.91:9000

echo Starting Radio TX...
start "" "ffmpeg.exe" -f dshow -thread_queue_size 512 -i audio="CABLE-C Output (VB-Audio Cable D)" -ar 48000 -ac 1 -f s16le tcp://192.168.0.91:8766

echo Radio started! RX via VLC, TX via ffmpeg.
pause