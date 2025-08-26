class BadRequest(Exception):
    """Raised when the client sends a malformed request."""

    def __init__(self, message: str = "bad_request") -> None:
        super().__init__(message)


class Conflict(Exception):
    """Raised when a resource conflict occurs."""

    def __init__(self, message: str = "conflict") -> None:
        super().__init__(message)


class NotFound(Exception):
    """Raised when a requested resource cannot be located."""

    def __init__(self, message: str = "not_found") -> None:
        super().__init__(message)


def to_response(exc: Exception) -> tuple[int, dict]:
    """Convert known exceptions to an HTTP response tuple.

    Parameters
    ----------
    exc: Exception
        The exception to convert.

    Returns
    -------
    tuple[int, dict]
        A status code and JSON-serializable payload.
    """
    msg = str(exc)
    if isinstance(exc, BadRequest):
        return 400, {"ok": False, "error": msg}
    if isinstance(exc, Conflict):
        return 409, {"ok": False, "error": msg}
    if isinstance(exc, NotFound):
        return 404, {"ok": False, "error": msg}
    return 500, {"ok": False, "error": "internal_error"}
