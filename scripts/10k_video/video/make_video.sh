#!/bin/bash
# Render the full video in parallel chunks, concatenate, and mux the song (padded with silence for the ending card).
# usage: make_video.sh <python-with-PySide6> <song audio> <out.mp4> [jobs]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
PY=$1; SONG=$2; OUT=$3; JOBS=${4:-4}
TMP=$(mktemp -d "${TMPDIR:-/tmp}/gdvideo.XXXX")
TOTAL=$("$PY" -I -c "import sys; sys.path.insert(0, '$HERE'); import render; print(int(render.DURATION * render.FPS))")
DUR=$("$PY" -I -c "import sys; sys.path.insert(0, '$HERE'); import render; print(render.DURATION)")
STEP=$(( (TOTAL + JOBS - 1) / JOBS ))
pids=()
for ((i = 0; i < JOBS; i++)); do
  a=$((i * STEP)); b=$(( (i + 1) * STEP )); [ $b -gt $TOTAL ] && b=$TOTAL
  (cd "$HERE" && "$PY" -I render.py --frames $a $b --out "$TMP/part$i.mp4" > "$TMP/log$i.txt" 2>&1) &
  pids+=($!)
  echo "file '$TMP/part$i.mp4'" >> "$TMP/list.txt"
done
for p in "${pids[@]}"; do wait $p; done
ffmpeg -hide_banner -loglevel error -y -f concat -safe 0 -i "$TMP/list.txt" -i "$SONG" \
  -map 0:v -map 1:a -c:v copy -af "apad=whole_dur=$DUR" -t "$DUR" -c:a aac -b:a 320k -ar 48000 \
  -movflags +faststart "$OUT"
rm -rf "$TMP"
echo "wrote $OUT"
