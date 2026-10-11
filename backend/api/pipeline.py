"""Background work: ingestion -> analysis for a person, dating against the pool, briefings, SSE event bus."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from common.models import Profile
from db.store import get_store

from . import adapters, jobs

log = logging.getLogger("api.pipeline")

SOURCES = ("linkedin", "instagram")


# --------------------------------------------------------------------------- SSE event bus (in-process)
class Bus:
    def __init__(self):
        self.events: list[dict] = []
        self.finished = False


_buses: dict[str, Bus] = {}
_buses_lock = threading.Lock()


def open_bus(date_id: str) -> Bus:
    with _buses_lock:
        b = _buses.get(date_id)
        if b is None or b.finished:
            b = _buses[date_id] = Bus()
        return b


def get_bus(date_id: str) -> Optional[Bus]:
    with _buses_lock:
        return _buses.get(date_id)


def close_bus(date_id: str) -> None:
    with _buses_lock:
        b = _buses.get(date_id)
        if b:
            b.finished = True


# --------------------------------------------------------------------------- ingestion + analysis
def fetch_sources(person: dict) -> dict[str, tuple[Optional[dict], str]]:
    """Return {source: (normalized_data|None, status)}. 24h URL cache: if both URLs are cached no fetch is made."""
    store = get_store()
    urls = {"linkedin": person.get("linkedin_url"), "instagram": person.get("instagram_url")}
    cached = {s: store.cache_get(u) if u else None for s, u in urls.items()}
    if all(cached[s] is not None for s in SOURCES if urls[s]) and any(urls.values()):
        return {s: ((cached[s] or {}).get("data"), (cached[s] or {}).get("status", "not_readable")) for s in SOURCES}
    result = adapters.unpack_sources(adapters.ingest(person["id"], urls["linkedin"], urls["instagram"]))
    for s, (data, status) in result.items():
        if urls.get(s) and data is not None and status != "not_readable":  # never cache failures
            store.cache_put(urls[s], {"data": data, "status": status})
    return result


def process_person(person_id: str) -> None:
    """Job: ingest both sources, analyse, store the profile, purge raw payloads."""
    store = get_store()
    person = store.get_person(person_id)
    if not person:
        return
    try:
        store.update_person(person_id, status="ingesting")
        sources = fetch_sources(person)
        if not store.get_person(person_id):  # deleted while we were fetching
            return
        for s, (data, status) in sources.items():
            store.save_raw_source(person_id, s, person.get(f"{s}_url"), data, status != "not_readable")
        statuses = {s: st for s, (_, st) in sources.items()}
        if all(st == "not_readable" for st in statuses.values()):
            store.purge_raw(person_id)
            store.update_person(person_id, status="not_readable")
            return
        store.update_person(person_id, status="analyzing")
        profile = adapters.analyze_profile(sources["linkedin"][0], sources["instagram"][0], person_id=person_id)
        profile = Profile.model_validate(profile).model_dump(mode="json")  # enforce the contract
        profile["source_status"] = {**profile.get("source_status", {}), **{s: st for s, st in statuses.items()
                                                                           if st == "not_readable"}}
        if store.get_person(person_id):
            store.save_profile(person_id, profile)
            store.update_person(person_id, status="ready")
        store.purge_raw(person_id)  # data handling: raw scrape is dropped once analysis is done
    except Exception:
        log.exception("process_person %s failed", person_id)
        store.purge_raw(person_id)
        store.update_person(person_id, status="failed")


# --------------------------------------------------------------------------- dates
def date_id_for(a: str, b: str, kind: str = "standard") -> str:
    lo, hi = sorted((a, b))
    return f"{lo}__{hi}" + ("__scenario" if kind == "scenario" else "")


def _names() -> dict[str, str]:
    return {p["id"]: (p.get("display_name") or p["id"]) for p in get_store().list_people()}


def run_one_date(a: str, b: str, kind: str = "standard") -> Optional[dict]:
    store = get_store()
    lo, hi = sorted((a, b))
    did = date_id_for(lo, hi, kind)
    bus = open_bus(did)
    pa, pb = store.get_profile(lo), store.get_profile(hi)
    if not pa or not pb:
        bus.events.append({"event": "done", "data": {"date_id": did, "status": "failed", "turns": 0}})
        close_bus(did)
        return None
    persist_progress = jobs.mode() == "rq"
    partial = {"id": did, "person_a": lo, "person_b": hi, "kind": kind, "status": "running", "turns": [],
               "score_a": None, "score_b": None, "faithfulness_a": None, "faithfulness_b": None, "flagged_turns": []}
    store.save_date(partial)
    prof_a, prof_b = Profile.model_validate(pa), Profile.model_validate(pb)
    held: dict = {}

    def on_event(ev):
        ev = adapters.dump(ev)
        if ev.get("event") == "done":  # emitted after the referee has audited the transcript
            held["done"] = ev
            return
        if ev.get("event") == "turn" and not ev["data"].get("event_start"):
            partial["turns"].append(ev["data"])
            if persist_progress:
                store.save_date(partial)
        bus.events.append(ev)

    try:
        record = adapters.run_date(prof_a, prof_b, (lo, hi), kind=kind, on_event=on_event, names=_names(), date_id=did)
        if getattr(record, "status", None) == "done":
            record = adapters.referee(record, prof_a, prof_b)
        d = adapters.dump(record)
        d["id"] = did
        store.save_date(d)
        done = held.get("done", {"event": "done", "data": {}})
        done["data"] = {**done["data"], "date_id": did, "status": d["status"], "turns": len(d["turns"]),
                        "faithfulness_a": d.get("faithfulness_a"), "faithfulness_b": d.get("faithfulness_b"),
                        "flagged_turns": d.get("flagged_turns", [])}
        for idx in d.get("flagged_turns", []):
            bus.events.append({"event": "flag", "data": {"idx": idx, "type": "unsupported_claim",
                                                         "note": "Referee: claim not supported by the profile"}})
        bus.events.append(done)
        return d
    except Exception:
        log.exception("date %s failed", did)
        partial["status"] = "failed"
        store.save_date(partial)
        bus.events.append({"event": "done", "data": {"date_id": did, "status": "failed", "turns": len(partial["turns"])}})
        return None
    finally:
        close_bus(did)


def run_pool(person_id: str, specs: list[tuple[str, str]], scenario_top: int = 0, workers: int = 4) -> None:
    """Job: run the listed (a, b, kind) dates, then optional scenario dates for the top matches, then briefings."""
    store = get_store()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda s: run_one_date(s[0], s[1], "standard"), specs))
    if scenario_top and store.get_person(person_id):
        from .scoring import rankings_for

        for row in rankings_for(person_id, top_n=scenario_top):
            open_bus(date_id_for(person_id, row["person_id"], "scenario"))
            run_one_date(person_id, row["person_id"], "scenario")
    if store.get_person(person_id):
        try:
            from .scoring import build_briefing

            store.save_briefing(person_id, build_briefing(person_id))
        except Exception:
            log.exception("briefing for %s failed", person_id)
