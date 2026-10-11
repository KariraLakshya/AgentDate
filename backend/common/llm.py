"""LLM abstraction. Agents depend only on LLMClient; MockClient lets everything run offline."""
import json
import re
from typing import Protocol

from . import config


class LLMClient(Protocol):
    def complete(self, *, system: str, user: str, tier: str = "fast", task: str = "", context: dict | None = None) -> str:
        """Return raw text. tier: 'strong' (analyst, referee) | 'fast' (dates).
        `task` names the job (analyst|plan|speak|rubric|referee|briefing|ask) and `context` carries the
        structured inputs; AnthropicClient ignores both, MockClient uses them to synthesise deterministic output."""
        ...


def extract_json(text: str):
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    return json.loads(m.group(0) if m else text)


class AnthropicClient:
    def __init__(self):
        import anthropic

        self._c = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def complete(self, *, system, user, tier="fast", task="", context=None) -> str:
        model = config.ANTHROPIC_MODEL_STRONG if tier == "strong" else config.ANTHROPIC_MODEL_FAST
        resp = self._c.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")


class GroqClient:
    """Groq chat-completions over httpx. Two keys: each tier prefers its own key and fails over to the
    other on 429/5xx, so one exhausted key does not stop the run. Retries with backoff honour Retry-After."""

    def __init__(self, transport=None, sleep=None):
        import time

        import httpx

        self._keys = {"strong": config.GROQ_API_KEY_STRONG, "fast": config.GROQ_API_KEY_FAST}
        if not any(self._keys.values()):
            raise RuntimeError("GROQ_API_KEY_STRONG / GROQ_API_KEY_FAST not set")
        self._http = httpx.Client(base_url=config.GROQ_BASE_URL, timeout=60, transport=transport)
        self._sleep = sleep or time.sleep

    def complete(self, *, system, user, tier="fast", task="", context=None) -> str:
        model = config.GROQ_MODEL_STRONG if tier == "strong" else config.GROQ_MODEL_FAST
        order = [tier, "fast" if tier == "strong" else "strong"]
        keys = [k for k in dict.fromkeys(self._keys[t] for t in order) if k]
        body = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        last = None
        for attempt in range(4):
            key = keys[attempt % len(keys)]
            r = self._http.post("/chat/completions", json=body, headers={"Authorization": f"Bearer {key}"})
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"] or ""
            last = r
            if r.status_code in (429, 500, 502, 503, 504):
                self._sleep(min(float(r.headers.get("retry-after", 2 ** attempt)), 20))
                continue
            break
        raise RuntimeError(f"Groq request failed: {last.status_code} {last.text[:200]}")


class MockClient:
    """Deterministic offline client. Handlers are registered by backend/agents/mock.py so mock outputs
    derive from real profile overlap and fixture text (never invented evidence)."""

    handlers: dict = {}

    def complete(self, *, system, user, tier="fast", task="", context=None) -> str:
        h = self.handlers.get(task)
        if not h:
            raise RuntimeError(f"MockClient has no handler for task '{task}'")
        return h(system=system, user=user, context=context or {})


def get_client() -> LLMClient:
    if config.LLM_MODE == "groq":
        return GroqClient()
    if config.LLM_MODE == "anthropic":
        return AnthropicClient()
    from agents import mock  # noqa: F401  registers handlers

    return MockClient()
