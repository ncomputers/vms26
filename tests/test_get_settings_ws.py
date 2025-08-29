import sys

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.websockets import WebSocket

sys.modules.setdefault("cv2", type("cv2", (), {}))
from utils.deps import get_settings


def test_get_settings_http_and_ws():
    app = Starlette()
    app.state.config = {"a": 1}
    req = Request({"type": "http", "app": app})
    assert get_settings(req) == {"a": 1}

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        pass

    ws = WebSocket({"type": "websocket", "app": app}, receive, send)
    assert get_settings(ws) == {"a": 1}
