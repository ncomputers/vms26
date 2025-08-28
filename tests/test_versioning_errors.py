from pathlib import Path

import pytest

from config.versioning import bump_version


def _version_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".version")


def test_bump_version_missing_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    vfile = _version_path(cfg)
    result = bump_version(cfg)
    assert result == 1
    assert vfile.read_text() == "1"


def test_bump_version_invalid_file(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    vfile = _version_path(cfg)
    vfile.write_text("not-an-int")
    result = bump_version(cfg)
    assert result == 1
    assert vfile.read_text() == "1"


def test_bump_version_unexpected_error(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    vfile = _version_path(cfg)
    vfile.mkdir()
    with pytest.raises(OSError):
        bump_version(cfg)
