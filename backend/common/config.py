"""Env-driven settings. LLM_MODE=mock runs everything offline and deterministically."""
import os

APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")  # empty -> in-memory store (dev/tests)
REDIS_URL = os.getenv("REDIS_URL", "")
LINKEDIN_ACTOR_ID = os.getenv("LINKEDIN_ACTOR_ID", "")
INSTAGRAM_ACTOR_ID = os.getenv("INSTAGRAM_ACTOR_ID", "")
ANTHROPIC_MODEL_STRONG = os.getenv("ANTHROPIC_MODEL_STRONG", "claude-opus-5-5")
ANTHROPIC_MODEL_FAST = os.getenv("ANTHROPIC_MODEL_FAST", "claude-haiku-5-5")
# Groq (OpenAI-compatible). Two keys so rate limits are spread: STRONG -> analyst/referee/briefing, FAST -> dates.
GROQ_API_KEY_STRONG = os.getenv("GROQ_API_KEY_STRONG", "")
GROQ_API_KEY_FAST = os.getenv("GROQ_API_KEY_FAST", "")
GROQ_MODEL_STRONG = os.getenv("GROQ_MODEL_STRONG", "openai/gpt-oss-120b")
GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# "groq" | "anthropic" | "mock"; default: first provider that has a key, else mock
LLM_MODE = os.getenv("LLM_MODE") or (
    "groq" if (GROQ_API_KEY_STRONG or GROQ_API_KEY_FAST) else "anthropic" if ANTHROPIC_API_KEY else "mock"
)
