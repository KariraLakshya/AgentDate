import json

import httpx
import pytest

from ingestion import (ApifyProvider, FixtureProvider, ForbiddenActorConfig, InvalidURL, UrlCache,
                       identity_signals, ingest, normalize, purge_raw, validate_url)
from ingestion.providers import assert_cookie_free

LI = "https://www.linkedin.com/in/jane-doe"
IG = "https://www.instagram.com/jane.doe"

LI_RAW = {
    "headline": "Product designer at Acme", "about": "I design calm tools. " * 20,
    "location": "Berlin, Germany", "email": "jane@x.com", "phone": "555", "followers": 9999,
    "profilePic": "http://img", "connections": [{"name": "Bob"}],
    "experiences": [{"position": "Designer", "companyName": "Acme", "description": "Led design", "logo": "x"}],
    "skills": [{"name": "Figma"}, "Research"],
}
IG_RAW = {
    "biography": "Berlin. Climbing, ceramics, coffee. Designer.", "followersCount": 12,
    "followers": ["a", "b"], "email": "j@x.com", "profilePicUrl": "http://p", "isPrivate": False,
    "latestPosts": [{"caption": "Sunday ceramics session", "likesCount": 3, "displayUrl": "http://i"}],
}


def mock_provider(handler, **kw):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return ApifyProvider(token="tok", linkedin_actor="org/li-public", instagram_actor="org/ig-public",
                         client=client, **kw)


def ok_handler(calls):
    def h(req):
        calls.append(req)
        if "li-public" in req.url.path:
            return httpx.Response(200, json=[LI_RAW])
        return httpx.Response(200, json=[IG_RAW])
    return h


# ---- URLs ----
@pytest.mark.parametrize("url,canon", [
    ("https://www.linkedin.com/in/Jane-Doe/", "https://www.linkedin.com/in/jane-doe"),
    ("http://linkedin.com/in/jane", "https://www.linkedin.com/in/jane"),
])
def test_linkedin_ok(url, canon):
    assert validate_url(url, "linkedin") == canon


@pytest.mark.parametrize("url", [
    "https://evil.com/in/jane", "https://linkedin.com.evil.com/in/jane", "https://www.linkedin.com/company/x",
    "https://www.linkedin.com/in/a/b", "https://user:pw@www.linkedin.com/in/jane", "https://www.linkedin.com:8080/in/j",
    "https://www.linkedin.com/in/jane?x=1", "ftp://www.linkedin.com/in/jane", "http://127.0.0.1/in/jane",
    "https://www.linkedin.com@evil.com/in/jane", "file:///etc/passwd", "", "https://www.linkedin.com/in/ja ne",
    "https://www.linkedin.com/login",
])
def test_linkedin_rejected(url):
    with pytest.raises(InvalidURL):
        validate_url(url, "linkedin")


def test_instagram_validation():
    assert validate_url("https://instagram.com/Jane.Doe/", "instagram") == IG
    for bad in ["https://instagram.com/p/abc", "https://instagram.com/a/b", "https://instagram.com/accounts/login",
                "https://instagram.com.evil.io/jane", "https://instagram.com/jane?igsh=1", "http://localhost/jane",
                "https://instagram.com/", "https://instagram.com/a..b"]:
        with pytest.raises(InvalidURL):
            validate_url(bad, "instagram")


def test_fixture_urls_only_when_allowed():
    assert validate_url("fixture://p01", "linkedin", allow_fixture=True) == "fixture://p01"
    with pytest.raises(InvalidURL):
        validate_url("fixture://p01", "linkedin")


# ---- cookie refusal ----
def test_cookie_bearing_input_refused_no_http():
    calls = []
    for bad in ({"cookie": "x"}, {"Session_Id": "x"}, {"nested": {"loginPassword": "x"}},
                {"opts": [{"li_at": "1", "credentials": {}}]}, {"authToken": "x"}):
        with pytest.raises(ForbiddenActorConfig):
            assert_cookie_free(bad)
    with pytest.raises(ForbiddenActorConfig):
        mock_provider(ok_handler(calls), extra_input={"cookies": [{"name": "li_at"}]})
    p = mock_provider(ok_handler(calls))
    with pytest.raises(ForbiddenActorConfig):
        p.fetch("linkedin", LI, extra_input={"sessionCookie": "abc"})
    with pytest.raises(ForbiddenActorConfig):
        ApifyProvider(token="t", linkedin_actor="someone/linkedin-cookie-scraper")
    assert calls == []


def test_ingest_with_cookie_config_is_not_readable_zero_calls():
    calls = []
    p = mock_provider(ok_handler(calls))
    p.extra_input = {"cookie": "x"}  # tampered after construction
    r = ingest("x", LI, IG, provider=p, cache=UrlCache())
    assert r["source_status"] == {"linkedin": "not_readable", "instagram": "not_readable"}
    assert "forbidden_actor_config" in r["reasons"]["linkedin"]
    assert calls == []


# ---- Apify provider / ingest ----
def test_ingest_happy_path_shape_and_drops_extras():
    calls = []
    p = mock_provider(ok_handler(calls))
    r = ingest("p1", LI, IG, provider=p, cache=UrlCache())
    assert len(calls) == 2
    req = calls[0]
    assert req.headers["authorization"] == "Bearer tok"
    assert req.url.path == "/v2/acts/org~li-public/run-sync-get-dataset-items"
    assert json.loads(req.content) == {"profileScraperMode": "Profile details no email ($4 per 1k)", "urls": [LI]}
    assert json.loads(calls[1].content) == {"usernames": ["jane.doe"]}
    assert r["source_status"] == {"linkedin": "ok", "instagram": "ok"}
    assert set(r["linkedin"]) == {"headline", "about", "location", "experience", "skills"}
    assert set(r["instagram"]) == {"bio", "location", "posts"}
    assert r["linkedin"]["experience"] == [{"title": "Designer", "company": "Acme", "description": "Led design"}]
    assert r["linkedin"]["skills"] == ["Figma", "Research"]
    assert r["instagram"]["posts"] == [{"caption": "Sunday ceramics session"}]
    blob = json.dumps(r)
    for leaked in ("jane@x.com", "555", "9999", "http://img", "Bob", "followers", "j@x.com", "http://i"):
        assert leaked not in blob
    assert r["identity"]["score"] > 0.5


def test_private_page_not_readable_with_exactly_one_call():
    calls = []

    def h(req):
        calls.append(req)
        return httpx.Response(200, json=[{"username": "jane.doe", "isPrivate": True, "followersCount": 4}])
    p = mock_provider(h)
    rec = ingest("p", LI, IG, provider=mock_provider(ok_handler([])), cache=UrlCache())  # sanity
    assert rec["source_status"]["instagram"] == "ok"
    r = ingest("p", "fixture-ignored", IG, provider=p, cache=UrlCache())
    assert r["source_status"]["instagram"] == "not_readable"
    assert r["instagram"] is None and r["readable"]["instagram"] is False
    ig_calls = [c for c in calls if True]
    assert len(ig_calls) == 1  # one call total (linkedin url invalid -> no call), no retry, no other route
    assert r["source_status"]["linkedin"] == "not_readable" and "invalid_url" in r["reasons"]["linkedin"]


@pytest.mark.parametrize("response", [
    httpx.Response(403, json={}), httpx.Response(401, json={}), httpx.Response(200, json=[]),
    httpx.Response(200, json=[{"error": "Login required to view this profile"}]),
    httpx.Response(200, text="not json"), httpx.Response(200, json=[{"headline": "", "about": ""}]),
])
def test_blocked_variants_one_call_each(response):
    calls = []

    def h(req):
        calls.append(req)
        return response
    r = ingest("p", LI, IG, provider=mock_provider(h), cache=UrlCache())
    assert r["source_status"]["linkedin"] == "not_readable"
    assert len(calls) == 2  # one per source, never more


def test_network_error_single_attempt():
    calls = []

    def h(req):
        calls.append(req)
        raise httpx.ConnectError("boom")
    r = ingest("p", LI, IG, provider=mock_provider(h), cache=UrlCache())
    assert r["source_status"] == {"linkedin": "not_readable", "instagram": "not_readable"}
    assert len(calls) == 2


def test_missing_token_or_actor():
    p = ApifyProvider(token="", linkedin_actor="", instagram_actor="")
    r = ingest("p", LI, IG, provider=p, cache=UrlCache())
    assert r["reasons"]["linkedin"] == "provider_not_configured"


def test_thin_status():
    d, s, _ = normalize("instagram", [{"biography": "hi", "latestPosts": []}])
    assert s == "thin" and d["bio"] == "hi"
    d, s, _ = normalize("linkedin", {"headline": "Dev"})
    assert s == "thin"


def test_login_wall_text_variants():
    for item in ({"error": "authwall"}, {"errorDescription": "Profile is private"}, {"loginRequired": True}):
        assert normalize("linkedin", [item])[1] == "not_readable"
    assert normalize("instagram", None)[1] == "not_readable"
    assert normalize("instagram", "garbage")[1] == "not_readable"


# ---- cache ----
def test_cache_24h_ttl_injectable_clock():
    now = [1000.0]
    cache = UrlCache(clock=lambda: now[0])
    calls = []
    p = mock_provider(ok_handler(calls))
    r1 = ingest("p", LI, IG, provider=p, cache=cache)
    r2 = ingest("p", "http://linkedin.com/in/Jane-Doe/", IG, provider=p, cache=cache)
    assert len(calls) == 2 and r2["cached"] == {"linkedin": True, "instagram": True}
    assert r2["linkedin"] == r1["linkedin"]
    now[0] += 24 * 3600 - 1
    ingest("p", LI, IG, provider=p, cache=cache)
    assert len(calls) == 2
    now[0] += 2
    r3 = ingest("p", LI, IG, provider=p, cache=cache)
    assert len(calls) == 4 and r3["cached"] == {"linkedin": False, "instagram": False}


def test_not_readable_is_cached_so_no_repeat_calls():
    calls = []

    def h(req):
        calls.append(req)
        return httpx.Response(200, json=[{"isPrivate": True}])
    cache, p = UrlCache(), mock_provider(h)
    ingest("p", LI, IG, provider=p, cache=cache)
    ingest("p", LI, IG, provider=p, cache=cache)
    assert len(calls) == 2


def test_cache_returns_copies():
    c = UrlCache()
    c.set("u", {"a": [1]})
    c.get("u")["a"].append(2)
    assert c.get("u") == {"a": [1]}


# ---- fixtures ----
def test_fixture_provider_and_private_fixture():
    personas = {
        "p01": {"linkedin": {"headline": "Chef", "about": "I cook " * 30, "location": "Lisbon",
                             "experience": [], "skills": []},
                "instagram": {"bio": "Lisbon food and surf, sunsets and long dinners with friends and family",
                              "location": "Lisbon", "posts": [{"caption": "paella night"}]}},
        "p02": {"linkedin": {"headline": "Dev", "about": "x" * 200}},
    }
    fp = FixtureProvider(personas=personas)
    r = ingest("p01", "fixture://p01", "fixture://p01", provider=fp, cache=UrlCache())
    assert r["source_status"] == {"linkedin": "ok", "instagram": "ok"}
    assert fp.calls == 2
    r = ingest("p02", "fixture://p02", "fixture://p02", provider=fp, cache=UrlCache())
    assert r["source_status"] == {"linkedin": "ok", "instagram": "not_readable"}
    r = ingest("p9", "fixture://nope", "fixture://nope", provider=fp, cache=UrlCache())
    assert r["source_status"]["linkedin"] == "not_readable"
    # Apify provider rejects fixture urls
    r = ingest("x", "fixture://p01", IG, provider=mock_provider(ok_handler([])), cache=UrlCache())
    assert "invalid_url" in r["reasons"]["linkedin"]


def test_fixture_provider_reads_files(tmp_path):
    (tmp_path / "p07.json").write_text(json.dumps(
        {"id": "p07", "name": "Synthetic", "linkedin": {"headline": "H" * 200}, "instagram": {"bio": "b" * 80}}))
    (tmp_path / "all.json").write_text(json.dumps([{"id": "p08", "linkedin": {"headline": "H" * 200}}]))
    fp = FixtureProvider(directory=tmp_path)
    assert ingest("a", "fixture://p07", "fixture://p07", provider=fp, cache=UrlCache())["linkedin"]["headline"]
    assert ingest("a", "fixture://p08", "fixture://p08", provider=fp, cache=UrlCache())["source_status"]["linkedin"] == "ok"


# ---- identity ----
def test_identity_signals():
    li = {"headline": "Product designer, climbing and ceramics", "about": "", "location": "Berlin, Germany", "skills": ["Figma"]}
    same = {"bio": "Berlin. climbing, ceramics. designer", "location": "Berlin", "posts": []}
    diff = {"bio": "Tokyo gamer, anime, streaming", "location": "Tokyo", "posts": [{"caption": "new console"}]}
    hi = identity_signals(li, same, "Jane Doe", "jane.doe")
    lo = identity_signals(li, diff, "Jane Doe", "xx_gamer99")
    assert hi["score"] > 0.7 > 0.4 > lo["score"]
    assert hi["reason"] and lo["reason"]
    none = identity_signals(None, same)
    assert none["score"] <= 0.3 and "not readable" in none["reason"]
    assert 0 <= identity_signals({}, {}, None, None)["score"] <= 1


# ---- purge ----
def test_purge_raw():
    r = ingest("p", LI, IG, provider=mock_provider(ok_handler([])), cache=UrlCache())
    assert r["raw_sources"][0]["payload_json"] is not None
    pr = purge_raw(r)
    assert pr["linkedin"] is None and pr["instagram"] is None
    assert all(x["payload_json"] is None and x["purged"] for x in pr["raw_sources"])
    assert pr["source_status"] == r["source_status"] and r["linkedin"] is not None  # original untouched
    lst = purge_raw(r["raw_sources"])
    assert all(x["payload_json"] is None for x in lst)


def test_harvestapi_shape_normalizes_and_drops_extras():
    from ingestion.normalize import normalize_linkedin

    raw = [{
        "firstName": "Test", "headline": "Head of Widgets at Example Co", "about": "I build widgets and mentor juniors." * 8,
        "emails": ["x@example.com"], "connectionsCount": 5, "photo": "http://img",
        "location": {"linkedinText": "Springfield, US", "parsed": {"city": "Springfield"}},
        "currentPosition": [{"position": "Head of Widgets", "companyName": "Example Co", "description": "Leads widget team"}],
    }]
    data, status, _ = normalize_linkedin(raw)
    assert status == "ok" and data["location"] == "Springfield, US"
    assert data["experience"] == [{"title": "Head of Widgets", "company": "Example Co", "description": "Leads widget team"}]
    assert set(data) == {"headline", "about", "location", "experience", "skills"}  # no emails / photos / counts
