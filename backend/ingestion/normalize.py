"""Normalize raw actor output to the analyst shape, keeping only analyst-needed fields.

Everything else (followers, emails, phones, images, urls, ids...) is dropped by construction:
we build new dicts from an allow-list and never copy the raw item.
"""
import re
from typing import Any, Optional

MAX_TEXT = 2000
MAX_EXPERIENCE = 10
MAX_SKILLS = 30
MAX_POSTS = 12
THIN_LINKEDIN_CHARS = 150
THIN_INSTAGRAM_CHARS = 60

_WALL = re.compile(r"(log\s?in|sign\s?in|authwall|private|not\s+available|restricted|"
                   r"cookie|session|rate.?limit|forbidden|not\s+found)", re.I)


def _s(v: Any, limit: int = MAX_TEXT) -> str:
    if v is None:
        return ""
    if isinstance(v, dict):
        v = v.get("text") or v.get("name") or v.get("title") or ""
    if not isinstance(v, str):
        v = str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else ""
    return re.sub(r"\s+", " ", v).strip()[:limit]


def _first(d: dict, *keys) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return None


def _pick_item(raw: Any) -> Optional[dict]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict):
                return it
    return None


def _blocked(item: dict) -> bool:
    """Private / login-walled / error markers in the actor output."""
    for k in ("isPrivate", "is_private", "private", "loginRequired", "authwall"):
        if item.get(k) is True:
            return True
    err = _first(item, "error", "errorDescription", "error_message", "message")
    if isinstance(err, str) and _WALL.search(err):
        return True
    if item.get("error") and not _first(item, "headline", "about", "summary", "biography", "bio"):
        return True
    return False


def normalize_linkedin(raw: Any) -> tuple[Optional[dict], str, str]:
    item = _pick_item(raw)
    if item is None:
        return None, "not_readable", "empty"
    if _blocked(item):
        return None, "not_readable", "private_or_login_wall"
    exp_raw = _first(item, "experience", "experiences", "positions", "workExperience") or []
    experience = []
    if isinstance(exp_raw, list):
        for e in exp_raw[:MAX_EXPERIENCE]:
            if not isinstance(e, dict):
                continue
            row = {
                "title": _s(_first(e, "title", "position", "role", "jobTitle"), 200),
                "company": _s(_first(e, "company", "companyName", "organization"), 200),
                "description": _s(_first(e, "description", "summary")),
            }
            if any(row.values()):
                experience.append(row)
    skills_raw = _first(item, "skills", "topSkills") or []
    skills = []
    if isinstance(skills_raw, list):
        for sk in skills_raw[:MAX_SKILLS]:
            t = _s(sk, 100)
            if t:
                skills.append(t)
    data = {
        "headline": _s(_first(item, "headline", "occupation", "title"), 300),
        "about": _s(_first(item, "about", "summary", "bio")),
        "location": _s(_first(item, "location", "geoLocationName", "addressWithCountry", "city"), 200),
        "experience": experience,
        "skills": skills,
    }
    chars = len(data["headline"]) + len(data["about"]) + sum(
        len(e["title"]) + len(e["description"]) for e in experience)
    if chars == 0:
        return None, "not_readable", "empty"
    return data, ("thin" if chars < THIN_LINKEDIN_CHARS else "ok"), ""


def normalize_instagram(raw: Any) -> tuple[Optional[dict], str, str]:
    item = _pick_item(raw)
    if item is None:
        return None, "not_readable", "empty"
    if _blocked(item):
        return None, "not_readable", "private_or_login_wall"
    posts_raw = _first(item, "posts", "latestPosts", "latest_posts", "recentPosts") or []
    posts = []
    if isinstance(posts_raw, list):
        for p in posts_raw[:MAX_POSTS]:
            cap = _s(_first(p, "caption", "text", "description") if isinstance(p, dict) else p)
            if cap:
                posts.append({"caption": cap})
    data = {
        "bio": _s(_first(item, "bio", "biography"), 500),
        "location": _s(_first(item, "location", "locationName", "city"), 200),
        "posts": posts,
    }
    chars = len(data["bio"]) + sum(len(p["caption"]) for p in posts)
    if chars == 0:
        return None, "not_readable", "empty"
    return data, ("thin" if chars < THIN_INSTAGRAM_CHARS else "ok"), ""


def normalize(source: str, raw: Any) -> tuple[Optional[dict], str, str]:
    """Return (data|None, status, reason). Never raises on malformed input."""
    try:
        if source == "linkedin":
            return normalize_linkedin(raw)
        if source == "instagram":
            return normalize_instagram(raw)
    except Exception:
        return None, "not_readable", "malformed"
    raise ValueError(f"unknown source {source!r}")
