import httpx

from ingestion.cache import UrlCache
from ingestion.pipeline import ingest
from ingestion.providers import ApifyProvider


def test_empty_dataset_is_not_readable_but_not_cached():
    calls = []

    def h(req):
        calls.append(1)
        return httpx.Response(201, json=[])

    prov = ApifyProvider(token="t", linkedin_actor="a~b", instagram_actor="c~d",
                         client=httpx.Client(transport=httpx.MockTransport(h)))
    cache = UrlCache()
    for _ in range(2):
        r = ingest("p", "https://www.linkedin.com/in/someone", "https://www.instagram.com/someone", provider=prov, cache=cache)
        assert r["source_status"] == {"linkedin": "not_readable", "instagram": "not_readable"}
    assert len(calls) == 4  # second submit re-asks the actor instead of serving a 24h false negative
