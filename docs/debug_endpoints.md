# Debug Endpoints

The application exposes several unauthenticated routes intended for internal testing:

- `/debug` – basic runtime and stats overview.
- `/debug/camera` – lists all cameras with MJPEG previews, status, and pipeline information.
- `/debug/camera/{cam_id}` – deep dive into a single camera and allows pipeline overrides.
- `/debug/rtsp-probe` – probe an RTSP URL with `ffprobe` and suggest common fallback paths on 404 errors.

These endpoints bypass authentication and should never be exposed on a public network.
