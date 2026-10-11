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
# "anthropic" | "mock"; default: anthropic if a key is present, else mock
LLM_MODE = os.getenv("LLM_MODE") or ("anthropic" if ANTHROPIC_API_KEY else "mock")
