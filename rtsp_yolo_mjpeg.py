#!/usr/bin/env python3
"""
Lightweight RTSP -> YOLOv8n -> MJPEG server with NO OpenCV.

- Grabs frames from RTSP using FFmpeg (subprocess pipe)
- Runs YOLOv8n for detection
- Streams MJPEG to browser
- Client-side overlay via SSE (canvas), or optional server-side drawing using Pillow

Requirements:
  pip install ultralytics pillow flask flask-cors numpy
And system FFmpeg must be installed and in PATH.

Edit STREAM_URL if needed.
"""

import os
import sys
import time
import json
import threading
import subprocess
from collections import deque
from io import BytesIO

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from flask import Flask, Response, request, render_template_string, stream_with_context
from flask_cors import CORS
from ultralytics import YOLO

# =================== CONFIG ===================
STREAM_URL = "rtsp://rapidmistryudr:Rapid1818@192.168.1.232:554/stream1"

MODEL_WEIGHTS = "yolov8s.pt"    # basic YOLO model
CONF_THRESH = 0.25
IOU_THRESH = 0.45

# Frame size pulled from FFmpeg. Keep it modest for latency/CPU.
FRAME_WIDTH = 640
FRAME_HEIGHT = 360
TARGET_FPS = 15                  # inference + stream throttle
JPEG_QUALITY = 80

# FFmpeg transport: try tcp for stability on RTSP
RTSP_TRANSPORT = "tcp"
# ==============================================

app = Flask(__name__)
CORS(app)

# Shared state
latest_frame_rgb = None         # numpy uint8 (H,W,3) RGB
latest_frame_ts = 0.0
latest_detections = []          # list of dicts
latest_lock = threading.Lock()

stop_event = threading.Event()

# Small buffer so HTTP streamers don't block capture
frame_queue = deque(maxlen=2)

def ffmpeg_reader():
    """
    Launch FFmpeg to read RTSP and output raw RGB frames to stdout.
    We force scale to FRAME_WIDTH x FRAME_HEIGHT for stable shape.
    """
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-rtsp_transport", RTSP_TRANSPORT,
        "-i", STREAM_URL,
        "-an",              # no audio
        "-vf", f"scale={FRAME_WIDTH}:{FRAME_HEIGHT},fps={TARGET_FPS}",
        "-pix_fmt", "rgb24",
        "-f", "rawvideo",
        "-"
    ]
    while not stop_event.is_set():
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=FRAME_WIDTH * FRAME_HEIGHT * 3 * 2
            )
        except FileNotFoundError:
            print("[FFmpeg] Not found. Install ffmpeg and ensure it's in PATH.", file=sys.stderr)
            stop_event.set()
            return

        frame_bytes = FRAME_WIDTH * FRAME_HEIGHT * 3
        print("[FFmpeg] Started.")
        try:
            while not stop_event.is_set():
                raw = proc.stdout.read(frame_bytes)
                if not raw or len(raw) < frame_bytes:
                    # stream ended or error; break to restart
                    break
                # Convert to numpy RGB
                frame = np.frombuffer(raw, dtype=np.uint8)
                frame = frame.reshape((FRAME_HEIGHT, FRAME_WIDTH, 3))
                ts = time.time()
                with latest_lock:
                    global latest_frame_rgb, latest_frame_ts
                    latest_frame_rgb = frame
                    latest_frame_ts = ts
                frame_queue.append((ts, frame))
        finally:
            try:
                proc.kill()
            except Exception:
                pass
            # Short backoff before retry
            if not stop_event.is_set():
                print("[FFmpeg] Restarting in 1s...")
                time.sleep(1.0)

def pillow_draw_boxes(img_rgb, detections):
    """
    Draw rectangles + labels on an RGB numpy image using Pillow.
    Returns a new numpy RGB image (copy).
    """
    img = Image.fromarray(img_rgb, mode="RGB").copy()
    draw = ImageDraw.Draw(img)
    # Try to get a reasonable font; fallback to default
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        label = f"{det['cls']} {det['conf']:.2f}"
        # Clamp
        x1 = max(0, min(FRAME_WIDTH - 1, int(x1)))
        y1 = max(0, min(FRAME_HEIGHT - 1, int(y1)))
        x2 = max(0, min(FRAME_WIDTH - 1, int(x2)))
        y2 = max(0, min(FRAME_HEIGHT - 1, int(y2)))

        # Box
        draw.rectangle([(x1, y1), (x2, y2)], outline=(0, 255, 0), width=2)

        # Label background
        tw, th = draw.textlength(label, font=font), (font.size if hasattr(font, "size") else 14)
        draw.rectangle([(x1, y1 - th - 4), (x1 + int(tw) + 6, y1)], fill=(0, 255, 0))
        # Label text
        draw.text((x1 + 3, y1 - th - 2), label, fill=(0, 0, 0), font=font)

    return np.array(img, dtype=np.uint8)

def encode_jpeg_pillow(img_rgb, quality=80):
    """
    Encode numpy RGB image to JPEG bytes using Pillow.
    """
    bio = BytesIO()
    Image.fromarray(img_rgb, mode="RGB").save(bio, format="JPEG", quality=int(quality), optimize=True)
    return bio.getvalue()

def inference_worker():
    """
    Run YOLO on the latest frame at ~TARGET_FPS.
    """
    model = YOLO(MODEL_WEIGHTS)
    min_interval = 1.0 / float(TARGET_FPS)
    last_t = 0.0

    while not stop_event.is_set():
        now = time.time()
        if now - last_t < min_interval:
            time.sleep(0.003)
            continue

        with latest_lock:
            frame = None if latest_frame_rgb is None else latest_frame_rgb.copy()
            ts = latest_frame_ts

        if frame is None:
            time.sleep(0.01)
            continue

        try:
            # Ultralytics accepts numpy RGB
            results = model.predict(
                source=frame,
                conf=CONF_THRESH,
                iou=IOU_THRESH,
                imgsz=640,
                verbose=False
            )
            res = results[0]
            dets = []
            if res.boxes is not None and len(res.boxes) > 0:
                xyxy = res.boxes.xyxy.cpu().numpy()
                confs = res.boxes.conf.cpu().numpy()
                classes = res.boxes.cls.cpu().numpy().astype(int)
                names = res.names
                for i in range(xyxy.shape[0]):
                    x1, y1, x2, y2 = xyxy[i].tolist()
                    c = float(confs[i])
                    cls_id = int(classes[i])
                    dets.append({
                        "bbox": [x1, y1, x2, y2],
                        "conf": c,
                        "cls": names.get(cls_id, str(cls_id)),
                        "cls_id": cls_id,
                        "ts": ts
                    })
            with latest_lock:
                global latest_detections
                latest_detections = dets
        except Exception as e:
            print("[Inference] Error:", e)
            time.sleep(0.05)
        last_t = now

@app.route("/")
def index():
    overlay_mode = request.args.get("overlay", "client")
    html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>RTSP ▶ MJPEG (light) + YOLOv8n</title>
  <style>
    :root {{ color-scheme: dark; }}
    body {{ margin:0; background:#111; color:#eee; font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Arial; }}
    .bar {{ padding:8px 12px; background:#1c1c1c; border-bottom:1px solid #2a2a2a; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }}
    .pill {{ background:#2a2a2a; padding:4px 8px; border-radius:999px; }}
    a, a:visited {{ color:#8bd; text-decoration:none; }}
    #wrap {{ position:relative; display:inline-block; }}
    #stream {{ display:block; max-width:100vw; height:auto; }}
    #overlay {{ position:absolute; left:0; top:0; pointer-events:none; }}
    .note {{ color:#aaa; font-size:0.9em; }}
  </style>
</head>
<body>
  <div class="bar">
    <div class="pill">Overlay: <b>{'browser (SSE)' if overlay_mode!='server' else 'server-drawn'}</b></div>
    <div class="pill">{FRAME_WIDTH}x{FRAME_HEIGHT}@{TARGET_FPS}fps</div>
    <div class="pill"><a href="/?overlay=client">Client overlay</a></div>
    <div class="pill"><a href="/?overlay=server">Server overlay</a></div>
  </div>

  <div id="wrap">
    <img id="stream" src="/video.mjpg?overlay={overlay_mode}" alt="stream"/>
    <canvas id="overlay"></canvas>
  </div>
  <div class="bar note">FFmpeg handles RTSP decode. No OpenCV installed. If laggy, try reducing FRAME_WIDTH/HEIGHT or FPS in the script.</div>

<script>
const overlayMode = "{overlay_mode}";
const img = document.getElementById('stream');
const canvas = document.getElementById('overlay');
const ctx = canvas.getContext('2d');

function resizeCanvas() {{
  // Use the natural dimensions of the JPEG if available
  const w = img.naturalWidth || {FRAME_WIDTH};
  const h = img.naturalHeight || {FRAME_HEIGHT};
  canvas.width = img.clientWidth;
  const ratio = h / w;
  canvas.height = Math.round(canvas.width * ratio);
}}
img.addEventListener('load', resizeCanvas);
window.addEventListener('resize', resizeCanvas);

// Draw loop for client overlay
let lastBoxes = [];
function draw() {{
  if (overlayMode === "server") {{
    ctx.clearRect(0,0,canvas.width,canvas.height);
    requestAnimationFrame(draw);
    return;
  }}
  ctx.clearRect(0,0,canvas.width,canvas.height);
  const iw = img.naturalWidth || {FRAME_WIDTH};
  const ih = img.naturalHeight || {FRAME_HEIGHT};
  const sx = canvas.width / iw;
  const sy = canvas.height / ih;

  ctx.lineWidth = 2;
  ctx.font = "14px system-ui, Arial";
  lastBoxes.forEach(det => {{
    const [x1,y1,x2,y2] = det.bbox;
    const label = det.cls + " " + det.conf.toFixed(2);
    const rx1 = x1 * sx, ry1 = y1 * sy, rw = (x2 - x1) * sx, rh = (y2 - y1) * sy;

    ctx.strokeStyle = "#00FF00";
    ctx.strokeRect(rx1, ry1, rw, rh);

    const tw = ctx.measureText(label).width + 8;
    const th = 18;
    ctx.fillStyle = "#00FF00";
    ctx.fillRect(rx1, ry1 - th, tw, th);
    ctx.fillStyle = "#000";
    ctx.fillText(label, rx1 + 4, ry1 - 4);
  }});
  requestAnimationFrame(draw);
}}
requestAnimationFrame(draw);

// SSE for detections
if (overlayMode !== "server") {{
  const ev = new EventSource("/events");
  ev.onmessage = (e) => {{
    try {{
      const payload = JSON.parse(e.data);
      lastBoxes = payload.detections || [];
    }} catch (err) {{
      console.error("Bad SSE JSON", err);
    }}
  }};
}}
</script>
</body>
</html>
"""
    return render_template_string(html)

@app.route("/video.mjpg")
def video_feed():
    overlay_mode = request.args.get("overlay", "client")
    server_draw = (overlay_mode == "server")

    @stream_with_context
    def generate():
        boundary = "frame"
        min_interval = 1.0 / float(TARGET_FPS)
        last_sent = 0.0
        while not stop_event.is_set():
            if not frame_queue:
                time.sleep(0.005)
                continue

            ts, frame_rgb = frame_queue[-1]  # most recent
            now = time.time()
            if now - last_sent < min_interval:
                time.sleep(0.002)
                continue

            if server_draw:
                with latest_lock:
                    dets = list(latest_detections)
                out_rgb = pillow_draw_boxes(frame_rgb, dets)
            else:
                out_rgb = frame_rgb

            jpg = encode_jpeg_pillow(out_rgb, JPEG_QUALITY)
            last_sent = now
            yield (
                b"--" + boundary.encode() + b"\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Content-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" +
                jpg + b"\r\n"
            )

    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Connection": "close",
    }
    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame", headers=headers)

@app.route("/events")
def sse_events():
    @stream_with_context
    def stream():
        min_interval = 1.0 / float(TARGET_FPS)
        last_push = 0.0
        while not stop_event.is_set():
            with latest_lock:
                dets = list(latest_detections)
                ts = latest_frame_ts
                w, h = FRAME_WIDTH, FRAME_HEIGHT
            now = time.time()
            if now - last_push < min_interval:
                time.sleep(0.01)
                continue
            payload = {"ts": ts, "width": w, "height": h, "detections": dets}
            yield f"data: {json.dumps(payload)}\n\n"
            last_push = now
    return Response(stream(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache"})

def main():
    t_cap = threading.Thread(target=ffmpeg_reader, daemon=True)
    t_inf = threading.Thread(target=inference_worker, daemon=True)
    t_cap.start()
    t_inf.start()
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        stop_event.set()
        t_cap.join(timeout=1.0)
        t_inf.join(timeout=1.0)

if __name__ == "__main__":
    main()



