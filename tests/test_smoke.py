"""Basic smoke tests for repository health."""

from pathlib import Path

import pytest
import redis


def test_repo_layout_exists() -> None:
    """Ensure fundamental project files are present."""
    assert Path("README.md").is_file()
    assert Path("tests").is_dir()


@pytest.mark.integration
def test_redis_connectivity(redis_url: str) -> None:
    """Verify a Redis server is reachable."""
    client = redis.Redis.from_url(redis_url)
    assert client.ping()
    client.close()


@pytest.mark.gpu
def test_gpu_dummy() -> None:
    """Placeholder GPU test."""
    assert True
