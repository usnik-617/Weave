#!/usr/bin/env python
from __future__ import annotations

import os


def main():
    redis_url = str(os.environ.get("WEAVE_REDIS_URL", "redis://127.0.0.1:6379/0") or "redis://127.0.0.1:6379/0").strip()
    queue_name = str(os.environ.get("WEAVE_MEDIA_QUEUE_NAME", "weave-media") or "weave-media").strip()

    from redis import Redis  # type: ignore
    from rq import Connection, Queue, Worker  # type: ignore

    redis_conn = Redis.from_url(redis_url)
    with Connection(redis_conn):
        worker = Worker([Queue(queue_name)])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
