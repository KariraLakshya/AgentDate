import json

from api import adapters, jobs, pipeline
from db.store import CACHE_TTL_SECONDS, MemoryStore
from api.tests.conftest import GOOD, make_profile

ZERO = {k: 0 for k in MemoryStore().counts()}


def sse_events(text):
    out = []
    for block in text.strip().split("\n\n"):
        ev = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((ev["event"], json.loads(ev["data"])))
    return out


def add_person(mem, pid, name):
    mem.upsert_synthetic_person(person_id=pid, display_name=name)
    mem.save_profile(pid, make_profile())


def test_consent_missing_403_no_rows_no_jobs(client, mem):
    no_consent = {k: v for k, v in GOOD.items() if k != "consent"}
    for body in (no_consent, {**GOOD, "consent": False}, {**GOOD, "consent": "true"}):
        assert client.post("/api/people", json=body).status_code == 403
    assert mem.counts() == ZERO
    assert jobs.ENQUEUED == [] and client.calls["ingest"] == 0


def test_consent_ok_creates_person_consent_and_profile(client, mem):
    r = client.post("/api/people", json=GOOD)
    assert r.status_code == 200
    pid = r.json()["person_id"]
    c = mem.counts()
    assert c["person"] == 1 and c["consent"] == 1
    assert len(mem.consents[0]["ip_hash"]) == 64 and "testclient" not in mem.consents[0]["ip_hash"]
    g = client.get(f"/api/people/{pid}").json()
    assert g["status"] == "ready" and g["profile"]["summary"] == "s"
    assert all(x["payload_json"] is None for x in mem.raw)  # raw purged after analysis
    assert jobs.ENQUEUED[0][1] == (pid,)


def test_bad_url_422_after_consent(client, mem):
    r = client.post("/api/people", json={**GOOD, "linkedin_url": "http://evil.example/in/x"})
    assert r.status_code == 422 and mem.counts() == ZERO


def test_delete_removes_everything(client, mem):
    pid = client.post("/api/people", json=GOOD).json()["person_id"]
    add_person(mem, "other", "Other")
    client.post(f"/api/people/{pid}/date-pool")
    assert mem.counts()["date"] == 1 and mem.counts()["url_cache"] == 2
    assert client.delete(f"/api/people/{pid}").status_code == 200
    c = mem.counts()
    assert c["person"] == 1 and c["consent"] == 0 and c["raw_source"] == 0 and c["profile"] == 1
    assert c["date"] == 0 and c["date_turn"] == 0 and c["match_score"] == 0 and c["briefing"] == 0
    assert c["url_cache"] == 0
    assert client.get(f"/api/people/{pid}").status_code == 404
    assert client.delete(f"/api/people/{pid}").status_code == 404


def test_rate_limit(client, mem, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PEOPLE_MAX", "2")
    assert client.post("/api/people", json=GOOD).status_code == 200
    assert client.post("/api/people", json=GOOD).status_code == 200
    assert client.post("/api/people", json=GOOD).status_code == 429
    assert mem.counts()["person"] == 2
    # consent failures are rejected before the limiter
    assert client.post("/api/people", json={**GOOD, "consent": False}).status_code == 403


def test_url_cache_24h(mem):
    mem.cache_put("u", {"a": 1}, now=1000.0)
    assert mem.cache_get("u", now=1000.0 + CACHE_TTL_SECONDS - 1) == {"a": 1}
    assert mem.cache_get("u", now=1000.0 + CACHE_TTL_SECONDS + 1) is None
    assert mem.counts()["url_cache"] == 0


def test_pipeline_uses_cache_for_same_urls(client, mem):
    client.post("/api/people", json=GOOD)
    client.post("/api/people", json=GOOD)
    assert client.calls["ingest"] == 1


def test_not_readable_both_sources(client, mem, monkeypatch):
    monkeypatch.setattr(adapters, "ingest",
                        lambda *a: {"linkedin": (None, "not_readable"), "instagram": (None, "not_readable")})
    pid = client.post("/api/people", json=GOOD).json()["person_id"]
    g = client.get(f"/api/people/{pid}").json()
    assert g["status"] == "not_readable" and g["profile"] is None and mem.counts()["url_cache"] == 0


def test_sse_turns_then_done(client, mem):
    pid = client.post("/api/people", json=GOOD).json()["person_id"]
    add_person(mem, "other", "Other")
    d = client.post(f"/api/people/{pid}/date-pool").json()["dates"]
    assert len(d) == 1
    did = d[0]["date_id"]
    for _ in range(2):  # live bus, then replay from the store once the bus is gone
        r = client.get(f"/api/dates/{did}/stream")
        assert r.headers["content-type"].startswith("text/event-stream")
        names = [e for e, _ in sse_events(r.text)]
        assert names.count("turn") >= 3 and "chemistry" in names and names[-1] == "done"
        assert names.index("turn") < names.index("done")
        pipeline._buses.clear()
    assert client.get(f"/api/dates/{did}").json()["status"] == "done"
    assert client.get("/api/dates/nope").status_code == 404
    assert client.get("/api/dates/nope/stream").status_code == 404


def test_rankings_matrix_briefing_ask(client, mem):
    pid = client.post("/api/people", json=GOOD).json()["person_id"]
    add_person(mem, "other", "Other")
    client.post(f"/api/people/{pid}/date-pool")
    rk = client.get(f"/api/people/{pid}/rankings").json()["rankings"]
    assert len(rk) == 1 and rk[0]["person_id"] == "other" and rk[0]["display_name"] == "Other"
    m = client.get("/api/pool/matrix").json()
    assert len(m["order"]) == 2 and m["stable_pairs"] and m["matrix"][0][0] is None
    b = client.get(f"/api/people/{pid}/briefing").json()
    assert {"introduce", "warn", "unsure"} <= set(b)
    a = client.post(f"/api/people/{pid}/ask", json={"question": "why Other?"}).json()
    assert "Other" in a["answer"]
    assert client.post(f"/api/people/{pid}/ask", json={}).status_code == 422
    assert client.post(f"/api/people/{pid}/date-pool").json()["dates"][0]["status"] == "done"


def test_date_pool_requires_profile(client, mem):
    mem.create_person(person_id="x", linkedin_url=None, instagram_url=None, display_name="x",
                      consent_statement="s", ip_hash="h")
    assert client.post("/api/people/x/date-pool").status_code == 409
    assert client.post("/api/people/missing/date-pool").status_code == 404


def test_demo_healthz_cors(client, monkeypatch, tmp_path):
    import api.main as m
    assert client.get("/healthz").json() == {"ok": True}
    f = tmp_path / "demo.json"
    f.write_text('{"people": []}')
    monkeypatch.setattr(m, "DEMO_PATH", f)
    assert client.get("/api/demo").json() == {"people": []}
    monkeypatch.setattr(m, "DEMO_PATH", tmp_path / "none.json")
    assert client.get("/api/demo").status_code == 404
    r = client.options("/api/people", headers={"Origin": "http://x", "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "*"


def test_date_pool_opponents_restricts_to_chosen_list(client, mem):
    pid = client.post("/api/people", json=GOOD).json()["person_id"]
    add_person(mem, "a", "A")
    add_person(mem, "b", "B")
    d = client.post(f"/api/people/{pid}/date-pool", json={"opponents": ["b"]}).json()["dates"]
    assert [x["person_id"] for x in d] == ["b"]
    assert mem.counts()["date"] == 1
    assert client.post(f"/api/people/{pid}/date-pool", json={"opponents": "b"}).status_code == 422
    assert len(client.post(f"/api/people/{pid}/date-pool").json()["dates"]) == 2  # default unchanged
