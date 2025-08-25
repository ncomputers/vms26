from __future__ import annotations

"""Redis stream aggregator for camera metrics.

This module polls the ``vms21:events`` Redis stream and aggregates
``in``/``out``/``inside`` metrics per ``camera_id`` and ``group``. Every
minute the collected counts are upserted into hourly ``summaries`` hashes in
Redis. The script can be executed via ``python -m app.runtime.aggregator`` and
supports resuming from the last processed stream ID.
"""

import argparse
import json
import os
import signal
import time
from collections import defaultdict
from datetime import datetime
from typing import DefaultDict, Dict

import redis
from loguru import logger

logger = logger.bind(module="runtime.aggregator")

STREAM = "vms21:events"
LAST_ID_KEY = "vms21:aggregator:last_id"
SUMMARY_PREFIX = "vms21:summaries"


class Aggregator:
    """Incrementally aggregate metrics from a Redis stream."""

    def __init__(self, client: redis.Redis, start_id: str) -> None:
        self.r = client
        self.last_id = start_id
        # counts[(camera_id, group)][metric]
        self.counts: DefaultDict[tuple[str, str], DefaultDict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._stop = False
        signal.signal(signal.SIGTERM, self._handle_stop)
        signal.signal(signal.SIGINT, self._handle_stop)

    def _handle_stop(self, signum, frame) -> None:  # pragma: no cover - signal handler
        self._stop = True

    def poll(self) -> None:
        """Start polling the Redis stream and aggregating counts."""
        next_flush = time.time() + 60
        while not self._stop:
            try:
                data = self.r.xread({STREAM: self.last_id}, block=1000, count=100)
            except redis.RedisError as exc:
                logger.warning("xread failed: {}", exc)
                time.sleep(1)
                continue
            if data:
                _, entries = data[0]
                for entry_id, fields in entries:
                    cam = fields.get("camera_id")
                    group = fields.get("group")
                    metric = fields.get("metric")
                    if cam and group and metric:
                        self.counts[(str(cam), str(group))][str(metric)] += 1
                        self.last_id = entry_id
            now = time.time()
            if now >= next_flush:
                self.flush()
                next_flush = now + 60
        # final flush on stop
        self.flush()

    def flush(self) -> None:
        """Write accumulated counts to Redis and reset."""
        if not self.counts:
            try:
                self.r.set(LAST_ID_KEY, self.last_id)
            except redis.RedisError:
                pass
            return
        hour = datetime.utcnow().strftime("%Y%m%d%H")
        pipe = self.r.pipeline()
        log_data: Dict[str, Dict[str, int]] = {}
        for (cam, group), metrics in self.counts.items():
            key = f"{SUMMARY_PREFIX}:{hour}:{cam}:{group}"
            log_data[f"{cam}:{group}"] = dict(metrics)
            for metric, value in metrics.items():
                pipe.hincrby(key, metric, value)
        try:
            pipe.set(LAST_ID_KEY, self.last_id)
            pipe.execute()
        except redis.RedisError as exc:
            logger.warning("failed to update summaries: {}", exc)
        else:
            logger.info(json.dumps({"hour": hour, "updates": log_data}))
        self.counts.clear()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate Redis stream metrics")
    start = parser.add_mutually_exclusive_group()
    start.add_argument("--from-beginning", action="store_true", help="start from 0-0")
    start.add_argument("--from-id", type=str, help="explicit starting stream ID")
    parser.add_argument(
        "--redis-url",
        default=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        help="Redis connection URL",
    )
    return parser.parse_args()


def main() -> None:  # pragma: no cover - CLI entry
    args = parse_args()
    client = redis.Redis.from_url(args.redis_url, decode_responses=True)
    if args.from_beginning:
        start_id = "0-0"
    elif args.from_id:
        start_id = args.from_id
    else:
        start_id = client.get(LAST_ID_KEY) or "0-0"
    agg = Aggregator(client, start_id)
    agg.poll()


if __name__ == "__main__":  # pragma: no cover - script entry
    main()
