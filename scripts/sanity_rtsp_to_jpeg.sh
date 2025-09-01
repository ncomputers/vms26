#!/bin/bash
# Quick sanity check: grab a single frame from an RTSP stream using ffmpeg.
# Usage: ./scripts/sanity_rtsp_to_jpeg.sh rtsp://camera/stream [outfile]
set -e
URL="$1"
OUT="${2:-frame.jpg}"
ffmpeg -nostdin -hide_banner -loglevel error \
  -rtsp_transport tcp -stimeout 20000000 \
  -fflags nobuffer -flags low_delay -probesize 1000000 -analyzeduration 0 \
  -max_delay 500000 -reorder_queue_size 0 -avioflags direct -an \
  -i "$URL" -frames:v 1 -f image2 "$OUT"
echo "Saved $OUT"
