"""Providers: ApifyProvider (cookie-free public actors only) and FixtureProvider (demo/tests).

A provider makes exactly ONE attempt per (source, url). It never retries, never falls back to a
different actor/route, and refuses any configuration that carries cookies/session/login/credentials.
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

from common import config
from ingestion.urls import FIXTURE_SCHEME, instagram_handle

APIFY_BASE = "https://api.apify.com"

# Any input key / actor id containing one of these (case/punctuation-insensitive) is refused.
FORBIDDEN_MARKERS = ("cookie", "session", "login", "password", "passwd", "credential",
                     "auth", "token", "secret", "apikey", "bearer")


class ForbiddenActorConfig(ValueError):
    """Raised when an actor id or input would require cookies/session/login/credentials."""


def _norm_key(k: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def assert_cookie_free(obj: Any, path: str = "input") -> None:
    """Recursively reject any key that smells like a cookie/session/login/credential field."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = _norm_key(k)
            if any(m in nk for m in FORBIDDEN_MARKERS):
                raise ForbiddenActorConfig(f"forbidden field {k!r} in {path}: cookie-free public actors only")
            assert_cookie_free(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            assert_cookie_free(v, f"{path}[{i}]")


def assert_actor_id_ok(actor_id: str) -> str:
    nk = _norm_key(actor_id)
    if any(m in nk for m in FORBIDDEN_MARKERS):
        raise ForbiddenActorConfig(f"actor id {actor_id!r} looks cookie/login based")
    if not re.fullmatch(r"[A-Za-z0-9_.\-]+([/~][A-Za-z0-9_.\-]+)?", actor_id or ""):
        raise ForbiddenActorConfig(f"invalid actor id {actor_id!r}")
    return actor_id.replace("/", "~")


@dataclass
class RawResult:
    items: Any = None          # raw actor output (to be normalized, then dropped)
    error: Optional[str] = None  # provider-level failure -> not_readable


class ApifyProvider:
    allow_fixture = False

    def __init__(self, token: Optional[str] = None, linkedin_actor: Optional[str] = None,
                 instagram_actor: Optional[str] = None, client: Optional[httpx.Client] = None,
                 extra_input: Optional[dict] = None, timeout: float = 120.0):
        self.token = token if token is not None else config.APIFY_TOKEN
        self.actors = {
            "linkedin": linkedin_actor if linkedin_actor is not None else config.LINKEDIN_ACTOR_ID,
            "instagram": instagram_actor if instagram_actor is not None else config.INSTAGRAM_ACTOR_ID,
        }
        for a in self.actors.values():
            if a:
                assert_actor_id_ok(a)
        self.extra_input = dict(extra_input or {})
        assert_cookie_free(self.extra_input, "extra_input")
        self._client = client
        self.timeout = timeout
        self.calls = 0

    def build_input(self, source: str, url: str, extra: Optional[dict] = None) -> dict:
        if source == "linkedin":
            body: dict = {"profileUrls": [url]}
        elif source == "instagram":
            body = {"usernames": [instagram_handle(url) or ""]}
        else:
            raise ValueError(f"unknown source {source!r}")
        body.update(self.extra_input)
        if extra:
            body.update(extra)
        assert_cookie_free(body)
        return body

    def fetch(self, source: str, url: str, extra_input: Optional[dict] = None) -> RawResult:
        actor = self.actors.get(source, "")
        if not self.token or not actor:
            return RawResult(error="provider_not_configured")
        actor_path = assert_actor_id_ok(actor)
        body = self.build_input(source, url, extra_input)  # raises ForbiddenActorConfig before any HTTP
        endpoint = f"{APIFY_BASE}/v2/acts/{actor_path}/run-sync-get-dataset-items"
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        client = self._client or httpx.Client(timeout=self.timeout)
        self.calls += 1  # single attempt, no retry, no alternative route
        try:
            resp = client.post(endpoint, json=body, headers=headers, timeout=self.timeout)
        except httpx.HTTPError as e:
            return RawResult(error=f"http_error:{type(e).__name__}")
        finally:
            if self._client is None:
                client.close()
        if resp.status_code >= 400:
            return RawResult(error=f"http_{resp.status_code}")
        try:
            return RawResult(items=resp.json())
        except ValueError:
            return RawResult(error="bad_json")


def _personas_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "personas"


class FixtureProvider:
    """Serves synthetic persona fixtures by url like fixture://p01."""
    allow_fixture = True

    def __init__(self, personas: Optional[dict] = None, directory: Optional[Path] = None):
        self._injected = personas
        self.directory = Path(directory) if directory else _personas_dir()
        self.calls = 0

    def _find(self, pid: str) -> Optional[dict]:
        if self._injected is not None:
            return self._injected.get(pid)
        direct = self.directory / f"{pid}.json"
        candidates = [direct] if direct.exists() else sorted(self.directory.glob("*.json"))
        for f in candidates:
            try:
                doc = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            found = self._search(doc, pid, f.stem == pid)
            if found is not None:
                return found
        return None

    @staticmethod
    def _search(doc: Any, pid: str, whole_file: bool) -> Optional[dict]:
        if isinstance(doc, dict):
            if whole_file and ("linkedin" in doc or "instagram" in doc):
                return doc
            if pid in doc and isinstance(doc[pid], dict):
                return doc[pid]
            for key in ("personas", "people"):
                if key in doc:
                    return FixtureProvider._search(doc[key], pid, False)
            if doc.get("id") == pid:
                return doc
        elif isinstance(doc, list):
            for p in doc:
                if isinstance(p, dict) and p.get("id") == pid:
                    return p
        return None

    def fetch(self, source: str, url: str, extra_input: Optional[dict] = None) -> RawResult:
        self.calls += 1
        if not url.startswith(FIXTURE_SCHEME + "://"):
            return RawResult(error="not_a_fixture_url")
        pid = url[len(FIXTURE_SCHEME) + 3:]
        persona = self._find(pid)
        if persona is None:
            return RawResult(error="fixture_not_found")
        part = persona.get(source)
        if not part:
            return RawResult(items=None)  # absent source -> not_readable
        return RawResult(items=part)
