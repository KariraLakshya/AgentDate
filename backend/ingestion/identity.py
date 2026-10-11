"""LLM-free identity cross-check: does the Instagram plausibly belong to the LinkedIn person?"""
import re
from typing import Optional

_STOP = set("""the and for with from this that about all more love life living live work working
based lover official page account""".split())


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2 and t not in _STOP}


def _name_score(name: Optional[str], handle: Optional[str], ig_bio: str) -> Optional[float]:
    if not name:
        return None
    parts = [p for p in re.findall(r"[a-z]+", name.lower()) if len(p) > 1]
    if not parts:
        return None
    h = re.sub(r"[^a-z0-9]", "", (handle or "").lower())
    bio = (ig_bio or "").lower()
    hits = sum(1 for p in parts if (p in h) or re.search(rf"\b{re.escape(p)}\b", bio))
    if hits == len(parts) and len(parts) > 1:
        return 1.0
    if hits >= 1 and len(parts) > 1:
        return 0.6
    if hits == 1:
        return 0.8
    return 0.2  # handles are often unrelated to real names; weak negative only


def _overlap(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return min(1.0, inter / min(len(a), len(b)) * 1.5) if inter else 0.0


def identity_signals(linkedin: Optional[dict], instagram: Optional[dict],
                     linkedin_name: Optional[str] = None,
                     instagram_handle: Optional[str] = None) -> dict:
    """Return {"score": 0..1, "reason": str, "name": x|None, "bio": x|None, "location": x|None}.

    Missing signals are excluded and the remaining weights renormalised. If either source is
    unreadable the score is a low neutral 0.3 (identity cannot be confirmed).
    """
    out = {"score": 0.3, "reason": "", "name": None, "bio": None, "location": None}
    if not linkedin or not instagram:
        out["reason"] = "Cannot cross-check: one source is not readable."
        return out
    parts = []
    name = _name_score(linkedin_name, instagram_handle, instagram.get("bio", ""))
    if name is not None:
        out["name"] = name
        parts.append((0.4, name, "name"))
    li_loc, ig_loc = _tokens(linkedin.get("location", "")), _tokens(instagram.get("location", ""))
    if li_loc and ig_loc:
        loc = 1.0 if li_loc & ig_loc else 0.0
        out["location"] = loc
        parts.append((0.3, loc, "location"))
    ig_text = instagram.get("bio", "") + " " + " ".join(p.get("caption", "") for p in instagram.get("posts", [])[:5])
    li_tok = _tokens(f"{linkedin.get('headline', '')} {linkedin.get('about', '')}")
    li_tok |= {t for s in linkedin.get("skills", []) for t in _tokens(s)}
    ig_tok = _tokens(ig_text)
    if li_tok and ig_tok:
        bio = _overlap(li_tok, ig_tok)
        out["bio"] = bio
        parts.append((0.3, bio, "bio"))
    if not parts:
        out["reason"] = "No comparable name, bio or location signals; identity unconfirmed."
        return out
    total = sum(w for w, _, _ in parts)
    score = sum(w * s for w, s, _ in parts) / total
    if len(parts) == 1:
        score = min(score, 0.6)  # one signal alone cannot give high confidence
    out["score"] = round(score, 3)
    out["reason"] = "Overlap by " + ", ".join(f"{label}={s:.2f}" for _, s, label in parts) + "."
    return out
