"""Queue jobs. Plain top-level functions with JSON-serialisable args/results, so RQ can run them
(`queue.enqueue(run_date_job, payload)`) and they also work inline when REDIS_URL is empty.

Payload for a date: {"profile_a": dict, "profile_b": dict, "ids": [a, b], "names": {id: name},
                     "kind": "standard"|"scenario", "date_id": optional, "n_turns": optional}
When REDIS_URL is set, every SSE-style event is also published to Redis channel `date:{date_id}` as JSON
(the API can subscribe to stream it); inline callers can pass `on_event` directly instead."""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from common import config
from common.models import Profile

log = logging.getLogger(__name__)


def _publisher(date_id: str):
    if not config.REDIS_URL:
        return None
    try:
        import redis

        r = redis.Redis.from_url(config.REDIS_URL)
        channel = f"date:{date_id}"

        def pub(ev: dict):
            r.publish(channel, json.dumps(ev, default=str))

        return pub
    except Exception:  # redis optional: never block a date on it
        log.exception("redis publisher unavailable")
        return None


def run_date_job(payload: dict, on_event=None) -> dict:
    from agents.dating import apply_referee, run_date

    a, b = payload["ids"]
    pa, pb = Profile.model_validate(payload["profile_a"]), Profile.model_validate(payload["profile_b"])
    kind = payload.get("kind", "standard")
    date_id = payload.get("date_id") or (f"{a}__{b}" + ("__scenario" if kind == "scenario" else ""))
    pub = _publisher(date_id)

    def fan(ev):
        if pub:
            pub(ev)
        if on_event:
            on_event(ev)

    rec = run_date(pa, pb, (a, b), kind=kind, on_event=fan, names=payload.get("names"),
                   n_turns=payload.get("n_turns", 10), date_id=date_id)
    if payload.get("referee", True) and rec.status == "done":
        rec = apply_referee(rec, pa, pb)
    return rec.model_dump()


def run_pool_job(person_id: str, profiles: dict, names: dict | None = None, kind: str = "standard",
                 max_workers: int = 8) -> list[dict]:
    """Date `person_id` against every other id in `profiles` ({id: profile dict}); returns date dicts."""
    others = [i for i in profiles if i != person_id]

    def one(o):
        a, b = sorted([person_id, o])
        return run_date_job({"profile_a": profiles[a], "profile_b": profiles[b], "ids": [a, b],
                             "names": names or {}, "kind": kind})

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return list(ex.map(one, others))


def enqueue(fn, *args, **kwargs):
    """Run via RQ when REDIS_URL is set, else inline. Returns the RQ Job or the function result."""
    if not config.REDIS_URL:
        return fn(*args, **kwargs)
    from redis import Redis
    from rq import Queue

    return Queue("dating", connection=Redis.from_url(config.REDIS_URL)).enqueue(fn, *args, **kwargs)
