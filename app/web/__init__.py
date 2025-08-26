from functools import wraps

from fastapi.responses import JSONResponse

from app.core.errors import to_response


def handle_errors(func):
    """Wrap endpoint handlers to normalize error responses."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - thin wrapper
            status, payload = to_response(exc)
            return JSONResponse(status_code=status, content=payload)

    return wrapper
