from __future__ import annotations

import queue
import threading
import time
from typing import Any, Dict

from weave import core
from weave import media_jobs


_MEDIA_STATS_LOCK = threading.Lock()
_MEDIA_STATS: Dict[str, int] = {
    "enqueued": 0,
    "processed": 0,
    "failed": 0,
}

_LOCAL_QUEUE: "queue.Queue[dict]" = queue.Queue()
_LOCAL_WORKERS = []
_LOCAL_WORKERS_STARTED = False


def _backend_name() -> str:
    text = str(core.os.environ.get("WEAVE_MEDIA_QUEUE_BACKEND", "rq") or "rq").strip().lower()
    if text in {"rq", "local", "inline"}:
        return text
    return "rq"


def _local_worker_loop():
    while True:
        job = _LOCAL_QUEUE.get()
        if not isinstance(job, dict):
            _LOCAL_QUEUE.task_done()
            continue
        try:
            media_jobs.generate_cover_derivatives(int(job["post_id"]), str(job["stored_path"]))
            with _MEDIA_STATS_LOCK:
                _MEDIA_STATS["processed"] += 1
        except Exception:
            with _MEDIA_STATS_LOCK:
                _MEDIA_STATS["failed"] += 1
        finally:
            _LOCAL_QUEUE.task_done()


def _ensure_local_workers():
    global _LOCAL_WORKERS_STARTED
    if _LOCAL_WORKERS_STARTED:
        return
    worker_count = int(core.os.environ.get("WEAVE_MEDIA_WORKER_COUNT", "2") or "2")
    worker_count = max(1, min(worker_count, 8))
    for _ in range(worker_count):
        thread = threading.Thread(target=_local_worker_loop, daemon=True)
        thread.start()
        _LOCAL_WORKERS.append(thread)
    _LOCAL_WORKERS_STARTED = True


def _enqueue_rq(post_id: int, stored_path: str):
    try:
        from redis import Redis  # type: ignore
        from rq import Queue  # type: ignore
    except Exception as exc:
        raise RuntimeError("rq/redis 패키지가 없어 RQ 큐를 사용할 수 없습니다.") from exc

    redis_url = str(core.os.environ.get("WEAVE_REDIS_URL", "") or "").strip()
    if not redis_url:
        raise RuntimeError("WEAVE_REDIS_URL 환경변수가 비어 있습니다.")

    conn = Redis.from_url(redis_url)
    queue_name = str(core.os.environ.get("WEAVE_MEDIA_QUEUE_NAME", "weave-media") or "weave-media").strip()
    q = Queue(queue_name, connection=conn)
    job = q.enqueue(
        "weave.media_jobs.generate_cover_derivatives",
        int(post_id),
        str(stored_path),
        retry=2,
        result_ttl=600,
        failure_ttl=86400,
    )
    return str(job.id or "")


def enqueue_cover_derivatives(post_id: int, stored_path: str) -> Dict[str, Any]:
    backend = _backend_name()
    with _MEDIA_STATS_LOCK:
        _MEDIA_STATS["enqueued"] += 1

    if backend == "inline":
        try:
            media_jobs.generate_cover_derivatives(int(post_id), str(stored_path))
            with _MEDIA_STATS_LOCK:
                _MEDIA_STATS["processed"] += 1
            return {"queued": False, "backend": "inline", "job_id": ""}
        except Exception as exc:
            with _MEDIA_STATS_LOCK:
                _MEDIA_STATS["failed"] += 1
            return {"queued": False, "backend": "inline", "job_id": "", "error": str(exc)}

    if backend == "local":
        _ensure_local_workers()
        _LOCAL_QUEUE.put({"post_id": int(post_id), "stored_path": str(stored_path)})
        return {"queued": True, "backend": "local", "job_id": f"local-{int(time.time()*1000)}"}

    try:
        job_id = _enqueue_rq(int(post_id), str(stored_path))
        return {"queued": True, "backend": "rq", "job_id": job_id}
    except Exception:
        # 안전 폴백: 로컬 큐
        _ensure_local_workers()
        _LOCAL_QUEUE.put({"post_id": int(post_id), "stored_path": str(stored_path)})
        return {"queued": True, "backend": "local", "job_id": f"local-{int(time.time()*1000)}", "fallback": "rq_to_local"}


def get_queue_metrics() -> Dict[str, Any]:
    with _MEDIA_STATS_LOCK:
        stats = dict(_MEDIA_STATS)
    return {
        "backend": _backend_name(),
        "local_queue_depth": int(_LOCAL_QUEUE.qsize()),
        "local_worker_count": int(len(_LOCAL_WORKERS)),
        "stats": stats,
    }


def ensure_background_workers_started():
    if _backend_name() == "local":
        _ensure_local_workers()
