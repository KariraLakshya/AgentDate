import httpx

from common import config
from common.llm import GroqClient


def _client(handler, monkeypatch):
    monkeypatch.setattr(config, "GROQ_API_KEY_STRONG", "key-strong")
    monkeypatch.setattr(config, "GROQ_API_KEY_FAST", "key-fast")
    return GroqClient(transport=httpx.MockTransport(handler), sleep=lambda s: None)


def ok(content="hi"):
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_tier_uses_its_own_key_and_model(monkeypatch):
    seen = []

    def h(req):
        seen.append((req.headers["authorization"], req.read()))
        return ok()

    c = _client(h, monkeypatch)
    c.complete(system="s", user="u", tier="strong")
    c.complete(system="s", user="u", tier="fast")
    assert seen[0][0] == "Bearer key-strong" and b"120b" in seen[0][1]
    assert seen[1][0] == "Bearer key-fast" and b"20b" in seen[1][1]


def test_rate_limit_fails_over_to_other_key(monkeypatch):
    auth = []

    def h(req):
        auth.append(req.headers["authorization"])
        return httpx.Response(429, headers={"retry-after": "0"}) if len(auth) == 1 else ok("done")

    assert _client(h, monkeypatch).complete(system="s", user="u", tier="fast") == "done"
    assert auth == ["Bearer key-fast", "Bearer key-strong"]
