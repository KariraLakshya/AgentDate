"""Storage layer. `get_store()` picks Postgres when DATABASE_URL is set, else an in-memory store.

All values crossing the interface are plain dicts / pydantic-dumped dicts so both backends behave alike.
Data handling: raw payloads are purged after analysis (`purge_raw`), the URL cache expires after 24h, and
`delete_person` removes every row (and cached URL payloads) for the person.
"""
from __future__ import annotations

import copy
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional, Protocol

CACHE_TTL_SECONDS = 24 * 3600
DIMS = ["interest_overlap", "values_alignment", "communication_chemistry", "lifestyle_fit", "growth_potential"]
TABLES = ["person", "consent", "raw_source", "profile", "date", "date_turn", "match_score", "briefing", "url_cache"]


class Store(Protocol):
    def create_person(self, *, person_id: str, linkedin_url: Optional[str], instagram_url: Optional[str],
                      display_name: Optional[str], consent_statement: str, ip_hash: Optional[str],
                      synthetic: bool = False) -> dict: ...
    def upsert_synthetic_person(self, *, person_id: str, display_name: str) -> dict: ...
    def get_person(self, person_id: str) -> Optional[dict]: ...
    def list_people(self) -> list[dict]: ...
    def update_person(self, person_id: str, **fields) -> None: ...
    def delete_person(self, person_id: str) -> bool: ...
    def save_raw_source(self, person_id: str, source: str, url: Optional[str], payload: Any, readable: bool) -> None: ...
    def purge_raw(self, person_id: str) -> None: ...
    def cache_get(self, url: str, now: Optional[float] = None) -> Optional[Any]: ...
    def cache_put(self, url: str, payload: Any, now: Optional[float] = None) -> None: ...
    def save_profile(self, person_id: str, profile: dict) -> None: ...
    def get_profile(self, person_id: str) -> Optional[dict]: ...
    def save_date(self, date: dict) -> None: ...
    def get_date(self, date_id: str) -> Optional[dict]: ...
    def list_dates(self, person_id: Optional[str] = None) -> list[dict]: ...
    def save_briefing(self, person_id: str, briefing: dict) -> None: ...
    def get_briefing(self, person_id: str) -> Optional[dict]: ...
    def counts(self) -> dict[str, int]: ...


def _now() -> float:
    return time.time()


def _flagged(turns: list[dict]) -> list[int]:
    return sorted({t["idx"] for t in turns for f in (t.get("flags") or []) if f.get("type") == "unsupported_claim"})


# --------------------------------------------------------------------------- in-memory
class MemoryStore:
    def __init__(self):
        self._lock = threading.RLock()
        self.reset()

    def reset(self):
        with self._lock:
            self.people: dict[str, dict] = {}
            self.consents: list[dict] = []
            self.raw: list[dict] = []
            self.profiles: dict[str, dict] = {}
            self.dates: dict[str, dict] = {}
            self.briefings: dict[str, dict] = {}
            self.url_cache: dict[str, dict] = {}

    def create_person(self, *, person_id, linkedin_url, instagram_url, display_name, consent_statement,
                      ip_hash, synthetic=False):
        with self._lock:
            p = {"id": person_id, "linkedin_url": linkedin_url, "instagram_url": instagram_url,
                 "display_name": display_name, "status": "pending", "synthetic": synthetic, "created_at": _now()}
            self.people[person_id] = p
            self.consents.append({"person_id": person_id, "statement": consent_statement, "ip_hash": ip_hash,
                                  "created_at": _now()})
            return copy.deepcopy(p)

    def upsert_synthetic_person(self, *, person_id, display_name):
        with self._lock:
            p = self.people.setdefault(person_id, {"id": person_id, "linkedin_url": None, "instagram_url": None,
                                                   "created_at": _now()})
            p.update(display_name=display_name, status="ready", synthetic=True)
            return copy.deepcopy(p)

    def get_person(self, person_id):
        with self._lock:
            p = self.people.get(person_id)
            return copy.deepcopy(p) if p else None

    def list_people(self):
        with self._lock:
            return [copy.deepcopy(p) for p in sorted(self.people.values(), key=lambda p: (p["created_at"], p["id"]))]

    def update_person(self, person_id, **fields):
        with self._lock:
            if person_id in self.people:
                self.people[person_id].update(fields)

    def delete_person(self, person_id):
        with self._lock:
            p = self.people.pop(person_id, None)
            if p is None:
                return False
            for u in (p.get("linkedin_url"), p.get("instagram_url")):
                if u:
                    self.url_cache.pop(u, None)
            self.consents = [c for c in self.consents if c["person_id"] != person_id]
            self.raw = [r for r in self.raw if r["person_id"] != person_id]
            self.profiles.pop(person_id, None)
            self.briefings.pop(person_id, None)
            # briefings of others may name this person; drop the references
            for b in self.briefings.values():
                for k in ("introduce", "warn"):
                    b[k] = [x for x in b.get(k, []) if x.get("person_id") != person_id]
            self.dates = {k: d for k, d in self.dates.items() if person_id not in (d["person_a"], d["person_b"])}
            return True

    def save_raw_source(self, person_id, source, url, payload, readable):
        with self._lock:
            if person_id not in self.people:  # deleted mid-pipeline: never resurrect rows
                return
            self.raw.append({"person_id": person_id, "source": source, "url": url,
                             "payload_json": copy.deepcopy(payload), "readable": readable, "fetched_at": _now()})

    def purge_raw(self, person_id):
        with self._lock:
            for r in self.raw:
                if r["person_id"] == person_id:
                    r["payload_json"] = None

    def cache_get(self, url, now=None):
        with self._lock:
            e = self.url_cache.get(url)
            if not e:
                return None
            if (now if now is not None else _now()) - e["fetched_at"] > CACHE_TTL_SECONDS:
                self.url_cache.pop(url, None)
                return None
            return copy.deepcopy(e["payload"])

    def cache_put(self, url, payload, now=None):
        with self._lock:
            self.url_cache[url] = {"payload": copy.deepcopy(payload),
                                   "fetched_at": now if now is not None else _now()}

    def save_profile(self, person_id, profile):
        with self._lock:
            if person_id not in self.people:
                return
            self.profiles[person_id] = copy.deepcopy(profile)

    def get_profile(self, person_id):
        with self._lock:
            p = self.profiles.get(person_id)
            return copy.deepcopy(p) if p else None

    def save_date(self, date):
        with self._lock:
            if date["person_a"] not in self.people or date["person_b"] not in self.people:
                return
            d = copy.deepcopy(date)
            d["flagged_turns"] = d.get("flagged_turns") or _flagged(d.get("turns", []))
            self.dates[d["id"]] = d

    def get_date(self, date_id):
        with self._lock:
            d = self.dates.get(date_id)
            return copy.deepcopy(d) if d else None

    def list_dates(self, person_id=None):
        with self._lock:
            return [copy.deepcopy(d) for d in self.dates.values()
                    if person_id is None or person_id in (d["person_a"], d["person_b"])]

    def save_briefing(self, person_id, briefing):
        with self._lock:
            if person_id not in self.people:
                return
            self.briefings[person_id] = copy.deepcopy(briefing)

    def get_briefing(self, person_id):
        with self._lock:
            b = self.briefings.get(person_id)
            return copy.deepcopy(b) if b else None

    def counts(self):
        with self._lock:
            return {
                "person": len(self.people), "consent": len(self.consents), "raw_source": len(self.raw),
                "profile": len(self.profiles), "date": len(self.dates),
                "date_turn": sum(len(d.get("turns", [])) for d in self.dates.values()),
                "match_score": sum(1 for d in self.dates.values() for k in ("score_a", "score_b") if d.get(k)),
                "briefing": len(self.briefings), "url_cache": len(self.url_cache),
            }


# --------------------------------------------------------------------------- postgres
class PostgresStore:
    def __init__(self, dsn: str):
        import psycopg  # noqa: F401

        self.dsn = dsn
        self._init_schema()

    def _conn(self):
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(self.dsn, row_factory=dict_row, autocommit=False)

    def _init_schema(self):
        here = Path(__file__).parent
        files = [here / "schema.sql"] + sorted((here / "migrations").glob("*.sql"))
        with self._conn() as c:
            for f in files:
                if f.exists():
                    c.execute(f.read_text(encoding="utf-8"))

    @staticmethod
    def _person(r) -> dict:
        r = dict(r)
        ca = r.get("created_at")
        r["created_at"] = ca.timestamp() if hasattr(ca, "timestamp") else ca
        return r

    def create_person(self, *, person_id, linkedin_url, instagram_url, display_name, consent_statement,
                      ip_hash, synthetic=False):
        with self._conn() as c:  # one transaction: person + consent together or not at all
            r = c.execute(
                "INSERT INTO person(id,linkedin_url,instagram_url,display_name,synthetic) VALUES (%s,%s,%s,%s,%s) "
                "RETURNING *", (person_id, linkedin_url, instagram_url, display_name, synthetic)).fetchone()
            c.execute("INSERT INTO consent(person_id,statement,ip_hash) VALUES (%s,%s,%s)",
                      (person_id, consent_statement, ip_hash))
            return self._person(r)

    def upsert_synthetic_person(self, *, person_id, display_name):
        with self._conn() as c:
            r = c.execute(
                "INSERT INTO person(id,display_name,status,synthetic) VALUES (%s,%s,'ready',TRUE) "
                "ON CONFLICT (id) DO UPDATE SET display_name=EXCLUDED.display_name,status='ready',synthetic=TRUE "
                "RETURNING *", (person_id, display_name)).fetchone()
            return self._person(r)

    def get_person(self, person_id):
        with self._conn() as c:
            r = c.execute("SELECT * FROM person WHERE id=%s", (person_id,)).fetchone()
            return self._person(r) if r else None

    def list_people(self):
        with self._conn() as c:
            return [self._person(r) for r in c.execute("SELECT * FROM person ORDER BY created_at, id").fetchall()]

    def update_person(self, person_id, **fields):
        allowed = {"status", "display_name", "linkedin_url", "instagram_url"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return
        sets = ",".join(f"{k}=%s" for k in fields)
        with self._conn() as c:
            c.execute(f"UPDATE person SET {sets} WHERE id=%s", (*fields.values(), person_id))

    def delete_person(self, person_id):
        with self._conn() as c:
            p = c.execute("SELECT linkedin_url, instagram_url FROM person WHERE id=%s", (person_id,)).fetchone()
            if not p:
                return False
            urls = [u for u in (p["linkedin_url"], p["instagram_url"]) if u]
            if urls:
                c.execute("DELETE FROM url_cache WHERE url = ANY(%s)", (urls,))
            # briefings of other people may reference this person
            for r in c.execute("SELECT id, json FROM briefing WHERE person_id<>%s", (person_id,)).fetchall():
                b = r["json"]
                nb = dict(b)
                for k in ("introduce", "warn"):
                    nb[k] = [x for x in b.get(k, []) if x.get("person_id") != person_id]
                if nb != b:
                    c.execute("UPDATE briefing SET json=%s WHERE id=%s", (json.dumps(nb), r["id"]))
            c.execute("DELETE FROM person WHERE id=%s", (person_id,))  # cascades everything else
            return True

    def save_raw_source(self, person_id, source, url, payload, readable):
        with self._conn() as c:
            c.execute("INSERT INTO raw_source(person_id,source,url,payload_json,readable) VALUES (%s,%s,%s,%s,%s)",
                      (person_id, source, url, json.dumps(payload) if payload is not None else None, readable))

    def purge_raw(self, person_id):
        with self._conn() as c:
            c.execute("UPDATE raw_source SET payload_json=NULL WHERE person_id=%s", (person_id,))

    def cache_get(self, url, now=None):
        with self._conn() as c:
            r = c.execute("SELECT payload_json, extract(epoch from fetched_at) AS ts FROM url_cache WHERE url=%s",
                          (url,)).fetchone()
            if not r:
                return None
            if (now if now is not None else _now()) - float(r["ts"]) > CACHE_TTL_SECONDS:
                c.execute("DELETE FROM url_cache WHERE url=%s", (url,))
                return None
            return r["payload_json"]

    def cache_put(self, url, payload, now=None):
        ts = now if now is not None else _now()
        with self._conn() as c:
            c.execute("INSERT INTO url_cache(url,payload_json,fetched_at) VALUES (%s,%s,to_timestamp(%s)) "
                      "ON CONFLICT (url) DO UPDATE SET payload_json=EXCLUDED.payload_json,fetched_at=EXCLUDED.fetched_at",
                      (url, json.dumps(payload), ts))

    def save_profile(self, person_id, profile):
        with self._conn() as c:
            v = c.execute("SELECT COALESCE(MAX(version),0)+1 AS v FROM profile WHERE person_id=%s",
                          (person_id,)).fetchone()["v"]
            c.execute("DELETE FROM profile WHERE person_id=%s", (person_id,))
            c.execute(
                "INSERT INTO profile(person_id,json,linkedin_persona,instagram_persona,gap_score,identity_match_score,version) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (person_id, json.dumps(profile), (profile.get("linkedin_persona") or {}).get("summary"),
                 (profile.get("instagram_persona") or {}).get("summary"),
                 (profile.get("persona_gap") or {}).get("score"),
                 (profile.get("identity_match") or {}).get("score"), v))

    def get_profile(self, person_id):
        with self._conn() as c:
            r = c.execute("SELECT json FROM profile WHERE person_id=%s ORDER BY version DESC LIMIT 1",
                          (person_id,)).fetchone()
            return r["json"] if r else None

    def save_date(self, date):
        with self._conn() as c:
            c.execute(
                "INSERT INTO date(id,person_a,person_b,kind,status,faithfulness_a,faithfulness_b) VALUES (%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (id) DO UPDATE SET kind=EXCLUDED.kind,status=EXCLUDED.status,"
                "faithfulness_a=EXCLUDED.faithfulness_a,faithfulness_b=EXCLUDED.faithfulness_b",
                (date["id"], date["person_a"], date["person_b"], date.get("kind", "standard"),
                 date.get("status", "pending"), date.get("faithfulness_a"), date.get("faithfulness_b")))
            c.execute("DELETE FROM date_turn WHERE date_id=%s", (date["id"],))
            c.execute("DELETE FROM match_score WHERE date_id=%s", (date["id"],))
            for t in date.get("turns", []):
                c.execute(
                    "INSERT INTO date_turn(date_id,idx,speaker,stage,public_text,private_note,chemistry,flags_json) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (date["id"], t["idx"], t["speaker"], t.get("stage"), t.get("public_text"), t.get("private_note"),
                     t.get("chemistry"), json.dumps(t.get("flags") or [])))
            for key, rater in (("score_a", date["person_a"]), ("score_b", date["person_b"])):
                s = date.get(key)
                if s:
                    dims = {d: s[d] for d in DIMS}
                    c.execute("INSERT INTO match_score(date_id,rater_person,dimension_scores_json,would_meet_again,verdict) "
                              "VALUES (%s,%s,%s,%s,%s)",
                              (date["id"], rater, json.dumps(dims), s.get("would_meet_again"), s.get("verdict")))

    def _hydrate_dates(self, c, rows) -> list[dict]:
        out = []
        for r in rows:
            turns = [{"idx": t["idx"], "speaker": t["speaker"], "stage": t["stage"] or "",
                      "public_text": t["public_text"] or "", "private_note": t["private_note"] or "",
                      "chemistry": t["chemistry"] if t["chemistry"] is not None else 0,
                      "flags": t["flags_json"] or []}
                     for t in c.execute("SELECT * FROM date_turn WHERE date_id=%s ORDER BY idx", (r["id"],)).fetchall()]
            d = {"id": r["id"], "person_a": r["person_a"], "person_b": r["person_b"], "kind": r["kind"],
                 "status": r["status"], "turns": turns, "score_a": None, "score_b": None,
                 "faithfulness_a": r["faithfulness_a"], "faithfulness_b": r["faithfulness_b"],
                 "flagged_turns": _flagged(turns)}
            for m in c.execute("SELECT * FROM match_score WHERE date_id=%s", (r["id"],)).fetchall():
                s = dict(m["dimension_scores_json"])
                s.update(would_meet_again=bool(m["would_meet_again"]), verdict=m["verdict"] or "")
                d["score_a" if m["rater_person"] == r["person_a"] else "score_b"] = s
            out.append(d)
        return out

    def get_date(self, date_id):
        with self._conn() as c:
            rows = c.execute("SELECT * FROM date WHERE id=%s", (date_id,)).fetchall()
            h = self._hydrate_dates(c, rows)
            return h[0] if h else None

    def list_dates(self, person_id=None):
        with self._conn() as c:
            if person_id is None:
                rows = c.execute("SELECT * FROM date ORDER BY id").fetchall()
            else:
                rows = c.execute("SELECT * FROM date WHERE person_a=%s OR person_b=%s ORDER BY id",
                                 (person_id, person_id)).fetchall()
            return self._hydrate_dates(c, rows)

    def save_briefing(self, person_id, briefing):
        with self._conn() as c:
            c.execute("DELETE FROM briefing WHERE person_id=%s", (person_id,))
            c.execute("INSERT INTO briefing(person_id,json) VALUES (%s,%s)", (person_id, json.dumps(briefing)))

    def get_briefing(self, person_id):
        with self._conn() as c:
            r = c.execute("SELECT json FROM briefing WHERE person_id=%s ORDER BY id DESC LIMIT 1",
                          (person_id,)).fetchone()
            return r["json"] if r else None

    def counts(self):
        with self._conn() as c:
            return {t: c.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in TABLES}


# --------------------------------------------------------------------------- selection
_store: Optional[Store] = None
_store_lock = threading.Lock()


def get_store() -> Store:
    global _store
    with _store_lock:
        if _store is None:
            from common import config

            _store = PostgresStore(config.DATABASE_URL) if config.DATABASE_URL else MemoryStore()
        return _store


def set_store(s: Optional[Store]) -> None:
    """Swap the process-wide store (tests)."""
    global _store
    with _store_lock:
        _store = s


def new_person_id() -> str:
    return uuid.uuid4().hex
