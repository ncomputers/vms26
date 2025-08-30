# Web Server

The FastAPI application defined in [main.py](../main.py) exposes HTTP routes and serves the dashboard.

* Routes are organized under the [routers](../routers) package.
* Static assets and templates live in [static](../static) and [templates](../templates).

## HTTPS

Camera capture and other browser APIs that rely on `navigator.mediaDevices` require a
secure context. The server can be started with TLS by passing certificate and key paths
directly to Uvicorn:

```bash
uvicorn main:app --ssl-certfile cert.pem --ssl-keyfile key.pem
```

For local testing a self‑signed certificate can be generated with OpenSSL:

```bash
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout key.pem -out cert.pem
```

In production it is recommended to place the application behind an HTTPS‑enabled
reverse proxy such as Nginx or Apache. Regardless of approach, pages that access
`getUserMedia` **must** be served over HTTPS.

## Preview streams

Single-frame previews and MJPEG feeds are exposed via `/cameras/test` and
`/stream/preview/{cam_id}`. These endpoints should always be available over
HTTPS so browsers can fetch them without mixed-content warnings. When using a
reverse proxy, forward these paths through the TLS terminator and expose them on
the same external port (typically 443) in every environment to keep client
configuration consistent.

## Standalone capture API

A lightweight FastAPI application in [server/api.py](../server/api.py) exposes
camera previews without the full dashboard. Start it with Uvicorn:

```bash
uvicorn server.api:app
```

The server provides `/snapshot` for a single JPEG frame, `/stream.mjpeg` for a
multipart stream and `/health` with basic pipeline metrics. Optional `/config`
and `/restart` endpoints aid observability.
