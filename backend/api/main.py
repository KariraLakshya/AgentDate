"""FastAPI app. Run: uvicorn api.main:app --port 8000 (from backend/)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from db.store import get_store, new_person_id

from . import jobs, pipeline, scoring
from .ratelimit import ip_hash, limiter, limits

log = logging.getLogger("api")

CONSENT_STATEMENT = "This is me, or I have this person's permission"
DEMO_PATH = Path(os.getenv("DEMO_PATH") or Path(__file__).resolve().parents[2] / "data" / "demo" / "demo.json")

app = FastAPI(title="Agentic Dating")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    if os.getenv("SEED_ON_START") == "1":
        from db.seed import seed

        seed()


def _client_ip(request: Request) -> str:
    if os.getenv("TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate(request: Request, bucket: str) -> str:
    h = ip_hash(_client_ip(request))
    limit, window = limits(bucket)
    if not limiter.allow(bucket, h, limit, window):
        raise HTTPException(429, "Too many requests, try again later", headers={"Retry-After": str(int(window))})
    return h


def _validate_urls(linkedin_url: Any, instagram_url: Any) -> tuple[str, str]:
    from ingestion.urls import InvalidURL, validate_url

    allow_fixture = os.getenv("ALLOW_FIXTURE_URLS") == "1"
    try:
        return (validate_url(linkedin_url, "linkedin", allow_fixture), validate_url(instagram_url, "instagram", allow_fixture))
    except InvalidURL as e:
        raise HTTPException(422, f"Invalid profile URL: {e}")


def _require_person(person_id: str) -> dict:
    p = get_store().get_person(person_id)
    if not p:
        raise HTTPException(404, "Person not found")
    return p


# --------------------------------------------------------------------------- people
@app.post("/api/people")
def create_person(request: Request, payload: dict = Body(...)):
    # 1. consent gate: nothing below (rate-limit bookkeeping, DB, jobs) runs without explicit consent=true
    if payload.get("consent") is not True:
        raise HTTPException(403, "Consent is required: confirm this is you, or that you have this person's permission")
    h = _check_rate(request, "people")
    li, ig = _validate_urls(payload.get("linkedin_url"), payload.get("instagram_url"))
    name = payload.get("display_name")
    name = name.strip()[:80] if isinstance(name, str) and name.strip() else "New person"
    pid = new_person_id()
    get_store().create_person(person_id=pid, linkedin_url=li, instagram_url=ig, display_name=name,
                              consent_statement=CONSENT_STATEMENT, ip_hash=h)
    jobs.enqueue(pipeline.process_person, pid)
    return {"person_id": pid, "status": "pending"}


@app.get("/api/people/{person_id}")
def get_person(person_id: str):
    p = _require_person(person_id)
    st = get_store()
    return {"id": p["id"], "display_name": p.get("display_name"), "status": p["status"],
            "synthetic": bool(p.get("synthetic")), "profile": st.get_profile(person_id)}


@app.delete("/api/people/{person_id}")
def delete_person(person_id: str):
    if not get_store().delete_person(person_id):
        raise HTTPException(404, "Person not found")
    return {"deleted": True, "person_id": person_id}


@app.post("/api/people/{person_id}/date-pool")
def date_pool(person_id: str, request: Request, payload: dict = Body(default_factory=dict)):
    p = _require_person(person_id)
    st = get_store()
    if not st.get_profile(person_id):
        raise HTTPException(409, f"Profile not ready (status: {p['status']})")
    _check_rate(request, "pool")
    existing = {d["id"]: d for d in st.list_dates(person_id)}
    specs, out = [], []
    for o in st.list_people():
        if o["id"] == person_id or not st.get_profile(o["id"]):
            continue
        did = pipeline.date_id_for(person_id, o["id"])
        cur = existing.get(did)
        bus = pipeline.get_bus(did)
        if (cur and cur["status"] == "done") or (bus and not bus.finished):
            out.append({"date_id": did, "person_id": o["id"], "status": cur["status"] if cur else "running"})
            continue
        pipeline.open_bus(did)  # so /stream can attach before the worker starts
        specs.append((person_id, o["id"]))
        out.append({"date_id": did, "person_id": o["id"], "status": "queued"})
    scenario_top = 3 if payload.get("scenario") is True else 0
    if specs or scenario_top:
        jobs.enqueue(pipeline.run_pool, person_id, specs, scenario_top)
    return {"person_id": person_id, "dates": out}


# --------------------------------------------------------------------------- dates
@app.get("/api/dates/{date_id}")
def get_date(date_id: str):
    d = get_store().get_date(date_id)
    if not d:
        raise HTTPException(404, "Date not found")
    return d


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _replay(d: dict, start: int = 0):
    for t in d.get("turns", []):
        if t["idx"] < start:
            continue
        yield "turn", t
        yield "chemistry", {"idx": t["idx"], "speaker": t["speaker"], "chemistry": t["chemistry"]}
        for f in t.get("flags") or []:
            yield "flag", {"idx": t["idx"], **f}


@app.get("/api/dates/{date_id}/stream")
async def stream_date(date_id: str):
    store = get_store()
    d = store.get_date(date_id)
    if not d:
        raise HTTPException(404, "Date not found")

    async def gen():
        bus = pipeline.get_bus(date_id)
        if bus is not None:  # live, in-process
            i = 0
            while True:
                while i < len(bus.events):
                    ev = bus.events[i]
                    i += 1
                    yield _sse(ev["event"], ev["data"])
                    if ev["event"] == "done":
                        return
                if bus.finished and i >= len(bus.events):
                    return
                await asyncio.sleep(0.05)
        seen = 0
        waited = 0.0
        while True:  # stored date (finished, or progress persisted by an RQ worker)
            cur = store.get_date(date_id)
            if cur is None:
                return
            for ev, data in _replay(cur, seen):
                yield _sse(ev, data)
            seen = len(cur.get("turns", []))
            if cur["status"] in ("done", "failed"):
                yield _sse("done", {"date_id": date_id, "status": cur["status"], "turns": seen,
                                    "faithfulness_a": cur.get("faithfulness_a"),
                                    "faithfulness_b": cur.get("faithfulness_b"),
                                    "flagged_turns": cur.get("flagged_turns", [])})
                return
            waited += 0.5
            if waited > float(os.getenv("SSE_MAX_WAIT", "600")):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# --------------------------------------------------------------------------- rankings / pool / briefing
@app.get("/api/people/{person_id}/rankings")
def get_rankings(person_id: str, top_n: int | None = None):
    _require_person(person_id)
    return {"person_id": person_id, "rankings": scoring.rankings_for(person_id, top_n=top_n)}


@app.get("/api/pool/matrix")
def pool_matrix():
    return scoring.pool_matrix()


@app.get("/api/people/{person_id}/briefing")
def get_briefing(person_id: str):
    _require_person(person_id)
    st = get_store()
    b = st.get_briefing(person_id)
    if b is None:
        if not st.list_dates(person_id):
            raise HTTPException(404, "No briefing yet: no completed dates")
        b = scoring.build_briefing(person_id)
        st.save_briefing(person_id, b)
    return b


@app.post("/api/people/{person_id}/ask")
def ask(person_id: str, payload: dict = Body(...)):
    _require_person(person_id)
    q = payload.get("question")
    if not isinstance(q, str) or not q.strip():
        raise HTTPException(422, "question is required")
    return {"person_id": person_id, "question": q, "answer": scoring.ask_why(person_id, q.strip()[:1000])}


# --------------------------------------------------------------------------- misc
@app.get("/api/demo")
def demo():
    if not DEMO_PATH.exists():
        raise HTTPException(404, "Demo data not generated yet")
    return JSONResponse(json.loads(DEMO_PATH.read_text(encoding="utf-8")))


@app.get("/healthz")
def healthz():
    return {"ok": True}
