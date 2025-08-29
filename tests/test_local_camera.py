from unittest.mock import patch

import modules.opencv_stream as opencv_stream


def test_local_camera_windows_backend():
    def fake_init(self, src):
        self.src = src

    with (
        patch.object(opencv_stream.BaseCameraStream, "__init__", fake_init),
        patch.object(opencv_stream.platform, "system", return_value="Windows"),
    ):
        opencv_stream.cv2.CAP_DSHOW = 0
        with patch.object(opencv_stream.cv2, "VideoCapture", create=True) as mock_capture:
            mock_capture.return_value.isOpened.return_value = True
            stream = opencv_stream.OpenCVCameraStream("0")
            stream.buffer_size = 3
            stream._init_stream()
            mock_capture.assert_called_once_with(0, opencv_stream.cv2.CAP_DSHOW)
