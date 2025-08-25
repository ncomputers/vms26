import os
import cv2
import subprocess
import atexit
import time

# Limit Python/OpenCV to single core
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
cv2.setNumThreads(1)
try:
    cv2.ocl.setUseOpenCL(False)
except:
    pass

# Camera settings
W, H, FPS = 640, 480, 15  # lower FPS to reduce lag
cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS, FPS)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# RTSP output URL (local machine)
# VLC will open this
RTSP_URL = "rtsp://localhost:8554/live.stream"

print(f"[INFO] Start VLC and open: {RTSP_URL}")
print("[INFO] Make sure you open with TCP transport: rtsp-tcp://localhost:8554/live.stream")

# FFmpeg command: encode + push RTSP over TCP
ffmpeg_cmd = [
    "ffmpeg",
    "-hide_banner", "-loglevel", "error",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", f"{W}x{H}",
    "-r", str(FPS),
    "-i", "-",  # stdin from Python frames
    "-c:v", "libx264",            # or h264_nvenc/h264_qsv/h264_amf for hardware accel
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-threads", "4",              # allow multi-thread encoding
    "-pix_fmt", "yuv420p",
    "-f", "rtsp",
    "-rtsp_transport", "tcp",     # TCP protocol for RTSP
    RTSP_URL
]

ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)
atexit.register(lambda: ffmpeg_proc.terminate())

# Capture loop
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.005)
            continue
        ffmpeg_proc.stdin.write(frame.tobytes())
except KeyboardInterrupt:
    pass
finally:
    cap.release()
    try:
        ffmpeg_proc.stdin.close()
    except:
        pass
    ffmpeg_proc.terminate()
