"""
Capture a specific Windows window ONLY (not the whole screen), even when it's occluded.
No OpenCV, no HTTP/RTSP. Optional local recording via ffmpeg.

Requires:
  pip install pillow pywin32 mss
Optional for recording:
  FFmpeg in PATH for --record out.mp4

Note:
  Occluded/covered windows capture fine.
  Minimized windows may appear blank due to app/OS behavior; use Windows Graphics Capture for that case.
"""

import sys
import time
import argparse
import subprocess

import ctypes
from ctypes import wintypes

import win32gui
import win32con
import win32process
import win32ui

from PIL import Image, ImageTk
import tkinter as tk

# --- Win32 constants & setup ---
DWMWA_EXTENDED_FRAME_BOUNDS = 9
PW_RENDERFULLCONTENT = 0x00000002  # ask app/DWM to render full content
user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
gdi32 = ctypes.windll.gdi32

user32.SetProcessDPIAware()

RECT = wintypes.RECT

def get_window_title(hwnd: int) -> str:
    try:
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""

def is_window_interesting(hwnd: int) -> bool:
    if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
        return False
    if win32gui.IsIconic(hwnd):  # minimized
        # we still list it so the user can choose; PrintWindow likely won't show content though
        pass
    title = get_window_title(hwnd)
    if not title.strip():
        return False
    cls = win32gui.GetClassName(hwnd)
    if cls in {"Progman", "Button", "Shell_TrayWnd"}:
        return False
    return True

def list_windows():
    out = []
    def _enum(hwnd, _):
        if is_window_interesting(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            out.append((hwnd, f"{get_window_title(hwnd)}  (PID {pid}, HWND {hwnd})"))
    win32gui.EnumWindows(_enum, None)
    return out

def get_extended_bounds(hwnd: int):
    rect = RECT()
    res = dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(hwnd),
        ctypes.c_uint(DWMWA_EXTENDED_FRAME_BOUNDS),
        ctypes.byref(rect),
        ctypes.sizeof(rect),
    )
    if res != 0:  # fallback
        l, t, r, b = win32gui.GetWindowRect(hwnd)
        return l, t, r, b
    return rect.left, rect.top, rect.right, rect.bottom

def printwindow_capture(hwnd: int):
    """
    Capture the exact window using PrintWindow (renders occluded content).
    Returns a PIL Image (RGBA) or None on failure.
    """
    # Get window rect (including frame)
    l, t, r, b = get_extended_bounds(hwnd)
    width, height = r - l, b - t
    if width <= 0 or height <= 0:
        return None

    # Create a device context compatible with the screen
    hwndDC = win32gui.GetWindowDC(hwnd)      # DC for the whole window
    mfcDC  = win32ui.CreateDCFromHandle(hwndDC)
    saveDC = mfcDC.CreateCompatibleDC()

    # Create a bitmap we can write to
    saveBitMap = win32ui.CreateBitmap()
    saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
    saveDC.SelectObject(saveBitMap)

    # Ask the window/DWM to draw itself into our DC
    # NOTE: PW_RENDERFULLCONTENT helps capture full client even if occluded
    result = user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), PW_RENDERFULLCONTENT)

    # If PrintWindow failed, clean up and return
    if result != 1:
        # clean up
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        return None

    # Convert bitmap to raw bytes
    bmpinfo = saveBitMap.GetInfo()
    bmpstr  = saveBitMap.GetBitmapBits(True)

    # Clean up GDI objects
    win32gui.DeleteObject(saveBitMap.GetHandle())
    saveDC.DeleteDC()
    mfcDC.DeleteDC()
    win32gui.ReleaseDC(hwnd, hwndDC)

    # Build a PIL Image from the raw data (Windows bitmaps are BGRA)
    img = Image.frombuffer(
        "RGBA",
        (bmpinfo["bmWidth"], bmpinfo["bmHeight"]),
        bmpstr,
        "raw",
        "BGRA",
        0,
        1
    )
    return img

# --- Optional: recording with ffmpeg to a local file ---
def start_ffmpeg_writer(width: int, height: int, fps: int, outfile: str):
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-pix_fmt", "bgra",
        "-s", f"{width}x{height}",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-vcodec", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        outfile
    ]
    try:
        return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print("FFmpeg not found. Remove --record or install FFmpeg.", file=sys.stderr)
        return None

class WindowMirror:
    def __init__(self, hwnd: int, fps: int = 15, record_path: str | None = None):
        self.hwnd = hwnd
        self.fps = max(1, min(fps, 60))
        self.interval = int(1000 / self.fps)
        self.record_path = record_path
        self.ff = None
        self.size = None

        self.root = tk.Tk()
        self.root.title(f"Capturing: {get_window_title(hwnd)}")
        self.lbl = tk.Label(self.root)
        self.lbl.pack()
        self.tkimg = None

        self.frames = 0
        self.t0 = time.time()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tick()

    def tick(self):
        img = printwindow_capture(self.hwnd)
        if img is not None:
            # Init / re-init recorder if size changed
            if self.record_path:
                w, h = img.size
                if (self.ff is None) or (self.size != (w, h)):
                    if self.ff and self.ff.stdin:
                        try:
                            self.ff.stdin.close()
                        except Exception:
                            pass
                    self.ff = start_ffmpeg_writer(w, h, self.fps, self.record_path)
                    self.size = (w, h)

            self.tkimg = ImageTk.PhotoImage(img)
            self.lbl.configure(image=self.tkimg)

            # write to ffmpeg (BGRA)
            if self.ff and self.ff.stdin:
                try:
                    self.ff.stdin.write(img.tobytes("raw", "BGRA"))
                except BrokenPipeError:
                    self.ff = None

            # fps in title
            self.frames += 1
            now = time.time()
            if now - self.t0 >= 1:
                self.root.title(f"Capturing: {get_window_title(self.hwnd)}  |  ~{self.frames} fps")
                self.frames = 0
                self.t0 = now
        else:
            # Nothing captured; window might be minimized or protected
            self.root.title(f"Capturing: {get_window_title(self.hwnd)}  |  (no frame)")

        self.root.after(self.interval, self.tick)

    def on_close(self):
        try:
            if self.ff and self.ff.stdin:
                self.ff.stdin.close()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()

def choose_window():
    wins = list_windows()
    if not wins:
        print("No visible windows found.")
        sys.exit(1)
    print("Select a window to capture:\n")
    for i, (_, title) in enumerate(wins, 1):
        print(f"[{i}] {title}")
    print()
    while True:
        try:
            idx = int(input(f"Enter number (1-{len(wins)}): ").strip())
            if 1 <= idx <= len(wins):
                return wins[idx - 1][0]
        except ValueError:
            pass
        print("Invalid selection. Try again.")

def main():
    ap = argparse.ArgumentParser(description="Capture a specific window only (occluded OK), no OpenCV/HTTP/RTSP.")
    ap.add_argument("--fps", type=int, default=15, help="Capture FPS (1-60). Default 15.")
    ap.add_argument("--record", type=str, default=None, help="Optional output file path (e.g., out.mp4).")
    args = ap.parse_args()

    if sys.platform != "win32":
        print("This script runs on Windows.", file=sys.stderr)
        sys.exit(1)

    hwnd = choose_window()
    # Optional: bring it to front once (doesn't need to stay on top to capture)
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass

    app = WindowMirror(hwnd, fps=args.fps, record_path=args.record)
    app.run()

if __name__ == "__main__":
    main()
