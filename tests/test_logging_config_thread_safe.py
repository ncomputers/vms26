import threading

from logging_config import logger, set_log_level


def test_configure_thread_safe():
    errors = []

    def worker():
        try:
            set_log_level("DEBUG")
        except Exception as exc:  # pragma: no cover - capturing unexpected errors
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors


def test_set_log_level_missing_handler():
    """set_log_level should handle external sink removal gracefully."""
    set_log_level("INFO")
    # Remove all handlers directly via loguru, leaving stale sink ids
    logger.remove()
    # Should not raise even though previous sink ids are invalid
    set_log_level("DEBUG")
