import asyncio
import json
import os
from pathlib import Path
from typing import Callable

from loguru import logger

from .storage import load_config

DEFAULT_CONFIG_PATH = Path(os.getenv("CONFIG_PATH", "config.json"))
VERSION_FILE_SUFFIX = ".version"


def _version_path(config_path: str | os.PathLike[str]) -> Path:
    path = Path(config_path)
    return path.with_suffix(path.suffix + VERSION_FILE_SUFFIX)


def bump_version(config_path: str | os.PathLike[str] | None = None) -> int:
    """Increment and persist the configuration version number.

    Parameters
    ----------
    config_path:
        Path to the configuration file. Defaults to ``CONFIG_PATH`` env or
        ``config.json``.

    Returns
    -------
    int
        The new version number.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    vfile = _version_path(path)
    try:
        current = int(vfile.read_text())
    except (FileNotFoundError, ValueError):
        current = 0
    except OSError:
        logger.exception("Failed to read version file %s", vfile)
        raise
    new = current + 1
    vfile.write_text(str(new))
    try:
        os.utime(vfile, None)
    except OSError:
        pass
    return new


async def watch_config(
    callback: Callable[[dict], None],
    *,
    config_path: str | os.PathLike[str] | None = None,
    interval: float = 1.0,
) -> None:
    """Poll for configuration changes and invoke ``callback``.

    The function watches a sidecar ``.version`` file next to the configuration
    file. Whenever the version number increases, the configuration is reloaded
    and ``callback`` is executed with the new data.
    """

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    vfile = _version_path(path)
    last = None
    try:
        last = int(vfile.read_text())
    except (FileNotFoundError, ValueError):
        last = None
    except OSError:
        logger.exception("Failed to read version file %s", vfile)
        raise
    try:
        while True:
            await asyncio.sleep(interval)
            try:
                cur = int(vfile.read_text())
            except (FileNotFoundError, ValueError):
                cur = None
            except OSError:
                logger.exception("Failed to read version file %s", vfile)
                raise
            if cur != last:
                last = cur
                try:
                    cfg = load_config(str(path), None)
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    logger.exception("Failed to reload config from %s", path)
                else:
                    try:
                        callback(cfg)
                    except Exception:
                        logger.exception("Config callback failed")
                        raise
    except asyncio.CancelledError:
        logger.info("Config watcher stopped for %s", path)
        raise
