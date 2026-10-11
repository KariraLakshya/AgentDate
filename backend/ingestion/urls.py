"""URL validation. Only linkedin.com/in/<slug> and instagram.com/<handle> are accepted.

Nothing here fetches anything; URLs are validated strictly (SSRF-safe) and canonicalised
before they are handed to a provider or used as a cache key.
"""
import re
from typing import Optional
from urllib.parse import unquote, urlsplit

FIXTURE_SCHEME = "fixture"

_LI_HOST = re.compile(r"^(?:www\.|[a-z]{2}\.)?linkedin\.com$")
_IG_HOST = re.compile(r"^(?:www\.)?instagram\.com$")
_LI_SLUG = re.compile(r"^[A-Za-z0-9_\-%]{1,100}$")
_IG_HANDLE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9._]{1,30}$")
_IG_RESERVED = {
    "p", "reel", "reels", "tv", "stories", "explore", "accounts", "direct", "about",
    "legal", "developer", "directory", "web", "challenge", "login", "oauth", "api",
}


class InvalidURL(ValueError):
    pass


def _split(url: str):
    if not isinstance(url, str) or not url.strip() or len(url) > 300:
        raise InvalidURL("empty or too long")
    url = url.strip()
    if any(ord(c) < 33 or ord(c) > 126 for c in url):
        raise InvalidURL("illegal characters")
    return urlsplit(url)


def _check_netloc(parts):
    if parts.username is not None or parts.password is not None or "@" in parts.netloc:
        raise InvalidURL("credentials in URL")
    try:
        port = parts.port
    except ValueError:
        raise InvalidURL("bad port")
    if port is not None:
        raise InvalidURL("explicit port not allowed")
    # query / fragment (?hl=en, #...) are dropped: the canonical URL is rebuilt from host + handle only


_IG_TABS = {"reels", "tagged", "reel", "posts"}


def validate_linkedin_url(url: str) -> str:
    parts = _split(url)
    if parts.scheme not in ("http", "https"):
        raise InvalidURL("scheme must be http(s)")
    _check_netloc(parts)
    host = (parts.hostname or "").lower()
    if not _LI_HOST.match(host):
        raise InvalidURL("not a linkedin.com host")
    segs = [s for s in parts.path.split("/") if s != ""]
    if len(segs) < 2 or segs[0] != "in" or not _LI_SLUG.match(segs[1]):  # trailing /details/... tabs are ignored
        raise InvalidURL("path must be /in/<slug>")
    if ".." in unquote(segs[1]):
        raise InvalidURL("bad slug")
    return f"https://www.linkedin.com/in/{segs[1].lower()}"


def validate_instagram_url(url: str) -> str:
    parts = _split(url)
    if parts.scheme not in ("http", "https"):
        raise InvalidURL("scheme must be http(s)")
    _check_netloc(parts)
    host = (parts.hostname or "").lower()
    if not _IG_HOST.match(host):
        raise InvalidURL("not an instagram.com host")
    segs = [s for s in parts.path.split("/") if s != ""]
    # trailing profile tabs (/reels/, /tagged/) are ignored; only the handle is used
    if not segs or len(segs) > 2 or not _IG_HANDLE.match(segs[0]) or segs[0].lower() in _IG_RESERVED or (
            len(segs) == 2 and segs[1].lower() not in _IG_TABS):
        raise InvalidURL("path must be /<handle>")
    return f"https://www.instagram.com/{segs[0].lower()}"


def validate_fixture_url(url: str) -> str:
    parts = _split(url)
    if parts.scheme != FIXTURE_SCHEME:
        raise InvalidURL("not a fixture url")
    pid = parts.netloc.lower()
    if not re.fullmatch(r"[a-z0-9_\-]{1,40}", pid) or parts.path.strip("/") or parts.query or parts.fragment:
        raise InvalidURL("bad fixture id")
    return f"{FIXTURE_SCHEME}://{pid}"


def validate_url(url: str, source: str, allow_fixture: bool = False) -> str:
    """Return the canonical URL or raise InvalidURL."""
    if allow_fixture and isinstance(url, str) and url.strip().lower().startswith(FIXTURE_SCHEME + "://"):
        return validate_fixture_url(url)
    if source == "linkedin":
        return validate_linkedin_url(url)
    if source == "instagram":
        return validate_instagram_url(url)
    raise InvalidURL(f"unknown source {source!r}")


def instagram_handle(canonical_url: str) -> Optional[str]:
    m = re.match(r"^https://www\.instagram\.com/([^/]+)$", canonical_url)
    return m.group(1) if m else None


def linkedin_slug(canonical_url: str) -> Optional[str]:
    m = re.match(r"^https://www\.linkedin\.com/in/([^/]+)$", canonical_url)
    return m.group(1) if m else None
