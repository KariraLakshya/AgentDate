"""Background execution. REDIS_URL set -> RQ queue; otherwise a daemon thread. `inline` runs synchronously
(tests). Every enqueue is recorded in ENQUEUED so tests can assert that nothing was queued."""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable

from common import config

log = logging.getLogger("api.jobs")
ENQUEUED: list[tuple[str, tuple]] = []
_mode_override: str | None = None


def mode() -> str:
    if _mode_override:
        return _mode_override
    env = os.getenv("JOBS_MODE")
    if env:
        return env
    return "rq" if config.REDIS_URL else "thread"


def set_mode(m: str | None) -> None:
    global _mode_override
    _mode_override = m


def reset() -> None:
    ENQUEUED.clear()


def _safe(fn: Callable, args: tuple):
    try:
        fn(*args)
    except Exception:
        log.exception("job %s failed", fn.__name__)


def enqueue(fn: Callable, *args) -> None:
    ENQUEUED.append((f"{fn.__module__}.{fn.__name__}", args))
    m = mode()
    if m == "inline":
        _safe(fn, args)
        return
    if m == "rq":
        try:
            from redis import Redis
            from rq import Queue

            Queue("dating", connection=Redis.from_url(config.REDIS_URL)).enqueue(fn, *args, job_timeout=3600)
            return
        except Exception:
            log.exception("RQ enqueue failed; falling back to a thread")
    threading.Thread(target=_safe, args=(fn, args), daemon=True).start()
