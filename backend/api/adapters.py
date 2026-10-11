"""Thin adapters over modules written by other agents. Imports are lazy so the app boots (and tests run)
when a module is missing or has a slightly different signature; tests monkeypatch these functions."""
from __future__ import annotations

import importlib
import inspect
import logging
from typing import Any, Callable, Optional

log = logging.getLogger("api.adapters")


def _import(*candidates: str) -> Optional[Any]:
    for c in candidates:
        mod, _, attr = c.partition(":")
        try:
            m = importlib.import_module(mod)
        except ImportError:
            continue
        if not attr:
            return m
        if hasattr(m, attr):
            return getattr(m, attr)
    return None


def call_flex(fn: Callable, **candidates):
    """Call fn passing only the keyword candidates its signature accepts (by name).
    If no names match but it needs positionals, pass candidates in the given order."""
    sig = inspect.signature(fn)
    params = sig.parameters
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return fn(**candidates)
    kwargs = {k: v for k, v in candidates.items() if k in params}
    required = [n for n, p in params.items() if p.default is p.empty and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if all(n in kwargs for n in required):
        return fn(**kwargs)
    return fn(*list(candidates.values())[: len(required)])


def dump(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


# ---- ingestion ---------------------------------------------------------------
def ingest(person_id: str, linkedin_url: str, instagram_url: str):
    fn = _import("ingestion:ingest", "ingestion.provider:ingest", "ingestion.service:ingest", "ingestion.pipeline:ingest")
    if fn is None:
        raise RuntimeError("ingestion.ingest is not available")
    return fn(person_id, linkedin_url, instagram_url)


def unpack_sources(result) -> dict[str, tuple[Optional[dict], str]]:
    """Tolerantly turn ingest()'s return value into {source: (data|None, status)}."""
    result = dump(result)
    out: dict[str, tuple[Optional[dict], str]] = {}
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], dict):
        srcs, statuses = result
    elif isinstance(result, dict):
        srcs = result.get("sources", result)
        statuses = result.get("status") or result.get("source_status") or result.get("statuses") or {}
    else:
        srcs, statuses = {}, {}
    for s in ("linkedin", "instagram"):
        entry = dump(srcs.get(s)) if isinstance(srcs, dict) else None
        status = statuses.get(s) if isinstance(statuses, dict) else None
        data = entry
        if isinstance(entry, (tuple, list)) and entry:
            data = entry[0]
            status = status or (entry[1] if len(entry) > 1 else None)
        elif isinstance(entry, dict) and "data" in entry and ("status" in entry or len(entry) <= 3):
            data = entry["data"]
            status = status or entry.get("status")
        if data is None:
            status = "not_readable"
        out[s] = (data, status or "ok")
    return out


# ---- agents ------------------------------------------------------------------
def analyze_profile(linkedin: Optional[dict], instagram: Optional[dict], person_id: str = ""):
    fn = _import("agents.analyst:analyze")
    if fn is None:
        raise RuntimeError("agents.analyst.analyze is not available")
    return dump(call_flex(fn, linkedin=linkedin, instagram=instagram, person_id=person_id))


def referee(record, profile_a, profile_b):
    try:
        from agents.dating import apply_referee
    except ImportError:
        return record
    try:
        return apply_referee(record, profile_a, profile_b)
    except Exception:
        log.exception("referee failed; keeping unaudited transcript")
        return record


def run_date(profile_a, profile_b, ids, kind="standard", on_event=None, names=None, date_id=None):
    from agents.dating import run_date as rd

    return call_flex(rd, profile_a=profile_a, profile_b=profile_b, ids=ids, kind=kind, on_event=on_event,
                     names=names, date_id=date_id)


def make_briefing(person_id: str, **ctx):
    fn = _import("agents.briefing:make_briefing")
    if fn is None:
        return None
    try:
        return dump(call_flex(fn, person_id=person_id, **ctx))
    except Exception:
        log.exception("make_briefing failed; using fallback")
        return None


def answer_why(person_id: str, question: str, **ctx):
    fn = _import("agents.briefing:answer_why")
    if fn is None:
        return None
    try:
        r = dump(call_flex(fn, person_id=person_id, question=question, **ctx))
        return r if isinstance(r, str) else (r.get("answer") if isinstance(r, dict) else str(r))
    except Exception:
        log.exception("answer_why failed; using fallback")
        return None
