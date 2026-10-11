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
    if config.LLM_MODE == "anthropic":
        return AnthropicClient()
    from agents import mock  # noqa: F401  registers handlers

    return MockClient()
