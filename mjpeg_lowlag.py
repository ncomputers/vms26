# mjpeg_single_core.py
import os
# --- Force single-core use by native libs ---
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"

import cv2, time
from flask import Flask, Response

app = Flask(__name__)

# OpenCV: single thread + no OpenCL (stick to one core)
cv2.setNumThreads(1)
try:
    cv2.ocl.setUseOpenCL(False)
except Exception:
    pass

# ---- Camera config (tune to your device) ----
# On Windows use: cv2.VideoCapture(0, cv2.CAP_DSHOW)
# On Linux use:   cv2.VideoCapture(0, cv2.CAP_V4L2)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # avoid stale frames

def grab_latest_frame(max_grabs=3):
    """
    Stay single-threaded but reduce lag:
    quickly 'grab' a few frames to flush the driver buffer,
    then 'retrieve' the newest one.
    """
    grabbed_any = False
    for _ in range(max_grabs):
        ok = cap.grab()
        if not ok:
            break
        grabbed_any = True
    if grabbed_any:
        ok, frame = cap.retrieve()
    else:
        ok, frame = cap.read()
    return ok, frame

def mjpeg_stream(quality=55, target_fps=24):
    boundary = b'--frame'
    period = 1.0 / float(target_fps)
    next_t = time.time()
    while True:
        ok, frame = grab_latest_frame(max_grabs=3)
        if not ok:
            time.sleep(0.005)
            continue

        ok, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            continue

        yield (boundary + b'\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Cache-Control: no-store\r\n\r\n' +
               buf.tobytes() + b'\r\n')

        # pace the loop so we don't overload the single core
        next_t += period
        sleep = next_t - time.time()
        if sleep > 0:
            time.sleep(sleep)
        else:
            next_t = time.time()

@app.route('/video_feed')
def video_feed():
    return Response(
        mjpeg_stream(quality=55, target_fps=24),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={'Cache-Control': 'no-store'}
    )

if __name__ == '__main__':
    try:
        # Single-threaded server; no reloader (keeps one process)
        app.run(host='0.0.0.0', port=5000, threaded=False, use_reloader=False)
    finally:
        cap.release()
