# Capture error codes

The capture modules raise `FrameSourceError` with a short code indicating the
failure reason. Operators can use these codes to diagnose camera issues.

## CONNECT_FAILED
Raised when FFmpeg cannot reconnect after multiple attempts. The source stops
and surfaces the last few lines of stderr with credentials removed. Verify
network reachability and authentication details. When stderr contains
`Operation not permitted`, the failure typically stems from firewall rules,
invalid credentials, or camera permission settings. Ensure the host can reach
the camera, the supplied credentials are correct, and that the camera permits
connections from this device.

## INVALID_STREAM
Emitted when FFmpeg reports `Invalid data found when processing input`. This
usually points to bad credentials or an unsupported stream format. Confirm the
URL, credentials, and that the camera outputs a compatible codec.
