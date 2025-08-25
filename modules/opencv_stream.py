import platform

import cv2


class BaseCameraStream:
    def __init__(self, src):
        self.src = src
        self.buffer_size = 1


class OpenCVCameraStream(BaseCameraStream):
    def __init__(self, src, *args, **kwargs):
        super().__init__(src)
        self.cap = None

    def _init_stream(self):
        src = int(self.src) if str(self.src).isdigit() else self.src
        if platform.system() == "Windows":
            self.cap = cv2.VideoCapture(src, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(src)
