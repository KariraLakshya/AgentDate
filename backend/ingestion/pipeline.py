"""ingest(): validate -> cache -> one provider call per source -> normalize -> cross-check."""
import copy
from typing import Optional

from ingestion.cache import UrlCache
from ingestion.identity import identity_signals
from ingestion.normalize import normalize
from ingestion.providers import ApifyProvider, ForbiddenActorConfig
from ingestion.urls import InvalidURL, instagram_handle, linkedin_slug, validate_url

SOURCES = ("linkedin", "instagram")

_default_cache = UrlCache()


def _name_from_slug(slug: Optional[str]) -> Optional[str]:
    if not slug:
        return None
    parts = [p for p in slug.replace("%", "-").split("-") if p.isalpha()]
    return " ".join(parts[:3]) or None


def _ingest_source(source: str, url: str, provider, cache: UrlCache) -> dict:
    """Return {"url","data","status","readable","reason","cached"}. Never raises."""
    rec = {"url": url, "data": None, "status": "not_readable", "readable": False, "reason": "", "cached": False}
    try:
        canon = validate_url(url, source, allow_fixture=getattr(provider, "allow_fixture", False))
    except InvalidURL as e:
        rec["reason"] = f"invalid_url: {e}"
        return rec
    rec["url"] = canon
    key = f"{source}|{canon}"  # fixture:// urls are shared across sources
    hit = cache.get(key)
    if hit is not None:
        out = dict(hit)
        out["cached"] = True
        return out
    try:
        res = provider.fetch(source, canon)  # exactly one call; no retry / alternative route
    except ForbiddenActorConfig as e:
        rec["reason"] = f"forbidden_actor_config: {e}"
        return rec  # not cached: config problem, not a property of the page
    except Exception as e:  # provider blew up: treat as unreadable, do not try another route
        rec["reason"] = f"provider_error: {type(e).__name__}"
        return rec
    if res.error:
        rec["reason"] = res.error
        if res.error.startswith("http_error") or res.error in ("provider_not_configured", "empty_dataset"):
            return rec  # transient/config: do not cache
    else:
        data, status, reason = normalize(source, res.items)
        rec.update(data=data, status=status, readable=status != "not_readable", reason=reason)
    del res  # raw scrape data is dropped here
    cache.set(key, {k: v for k, v in rec.items() if k != "cached"})
    return rec


def ingest(person_id: str, linkedin_url: str, instagram_url: str, provider=None,
           cache: Optional[UrlCache] = None) -> dict:
    """Fetch and normalize both sources. Result:

    {"person_id", "linkedin": {...}|None, "instagram": {...}|None,
     "source_status": {"linkedin","instagram"}, "readable": {...}, "reasons": {...},
     "cached": {...}, "identity": {"score","reason",...},
     "raw_sources": [raw_source-shaped records: source, payload_json, readable]}
    """
    provider = provider or ApifyProvider()
    cache = cache if cache is not None else _default_cache
    recs = {
        "linkedin": _ingest_source("linkedin", linkedin_url, provider, cache),
        "instagram": _ingest_source("instagram", instagram_url, provider, cache),
    }
    li, ig = recs["linkedin"], recs["instagram"]
    identity = identity_signals(
        li["data"], ig["data"],
        linkedin_name=_name_from_slug(linkedin_slug(li["url"])),
        instagram_handle=instagram_handle(ig["url"]),
    )
    return {
        "person_id": person_id,
        "linkedin": copy.deepcopy(li["data"]),
        "instagram": copy.deepcopy(ig["data"]),
        "source_status": {s: recs[s]["status"] for s in SOURCES},
        "readable": {s: recs[s]["readable"] for s in SOURCES},
        "reasons": {s: recs[s]["reason"] for s in SOURCES},
        "cached": {s: recs[s]["cached"] for s in SOURCES},
        "identity": identity,
        "raw_sources": [
            {"person_id": person_id, "source": s, "payload_json": copy.deepcopy(recs[s]["data"]),
             "readable": recs[s]["readable"], "purged": False}
            for s in SOURCES
        ],
    }


def purge_raw(records):
    """Return payload-less copies of raw_source records (call after analysis).

    Accepts an ingest() result (returns a copy with the payloads and the normalized
    linkedin/instagram data removed) or a list of raw_source records.
    """
    def _purge(r: dict) -> dict:
        r = dict(r)
        r["payload_json"] = None
        r["purged"] = True
        return r

    if isinstance(records, dict) and "raw_sources" in records:
        out = {k: v for k, v in records.items() if k not in ("linkedin", "instagram", "raw_sources")}
        out["linkedin"] = None
        out["instagram"] = None
        out["raw_sources"] = [_purge(r) for r in records["raw_sources"]]
        return out
    return [_purge(r) for r in records]
