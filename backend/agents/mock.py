"""Offline handlers for MockClient (tasks: analyst, referee, briefing, ask).

plan / speak / rubric belong to the date engine and are registered elsewhere. Mock analysis is derived purely
from the fixture text by keyword matching; evidence is always a literal substring of the source text.
"""
import json
import re

from common.llm import MockClient

from . import briefing as _briefing
from . import referee as _referee
from .analyst import SOURCES, identity_check, source_statuses
from .lexicon import (
    COMM_STYLES,
    CONCEPTS,
    ENERGIES,
    FORMAL_TONE,
    HUMORS,
    PLAYFUL_TONE,
    WANTS_PATTERN,
    concepts_in,
)
from .personas_loader import source_text

MAX_PER_FIELD = 6
EVIDENCE_MAX = 170


def _sentence_around(text: str, start: int, end: int) -> str:
    """Literal substring of `text`: the sentence containing [start, end), trimmed to a readable window."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    le = len(text) if le < 0 else le
    a = ls
    for m in re.finditer(r"[.!?]\s", text[ls:start]):
        a = ls + m.end()
    m = re.search(r"[.!?](?:\s|$)", text[end:le])
    b = end + m.end() if m else le
    sent = text[a:b].strip()
    if len(sent) > EVIDENCE_MAX:
        a2 = max(ls, start - 70)
        b2 = min(le, end + 90)
        sent = text[a2:b2].strip()
    return sent


def _hits(rx, text: str):
    return list(rx.finditer(text)) if text else []


def _claims_for(category: str, texts: dict[str, str]) -> list[dict]:
    out = []
    for label, rx in CONCEPTS[category]:
        per = {s: _hits(rx, texts[s]) for s in SOURCES}
        total = sum(len(v) for v in per.values())
        if not total:
            continue
        src = max(SOURCES, key=lambda s: (len(per[s]), s == "linkedin"))
        m = per[src][0]
        conf = 0.5 + 0.1 * min(len(per[src]), 3)
        if all(per[s] for s in SOURCES):
            conf += 0.1  # corroborated by both sources
        out.append(
            {
                "value": label,
                "evidence": _sentence_around(texts[src], m.start(), m.end()),
                "source": src,
                "confidence": round(min(conf, 0.95), 2),
            }
        )
    out.sort(key=lambda c: -c["confidence"])
    return out[:MAX_PER_FIELD]


def _wants(texts: dict[str, str]) -> list[dict]:
    out = []
    for s in SOURCES:
        for m in WANTS_PATTERN.finditer(texts[s]):
            sent = _sentence_around(texts[s], m.start(), m.end())
            if sent and all(sent != o["evidence"] for o in out):
                out.append({"value": sent[:110], "evidence": sent, "source": s, "confidence": 0.8})
    return out[:3]


def _trait(options, texts: dict[str, str]) -> dict:
    best = None
    for label, rx in options:
        n = sum(len(_hits(rx, texts[s])) for s in SOURCES)
        if n and (best is None or n > best[1]):
            best = (label, n, rx)
    if not best:
        for s in SOURCES:
            for line in texts[s].splitlines():
                if line.strip():
                    return {"value": "not enough evidence", "evidence": line.strip()[:EVIDENCE_MAX], "confidence": 0.15}
        return {"value": "not enough evidence", "evidence": "", "confidence": 0.1}
    label, n, rx = best
    for s in SOURCES:
        ms = _hits(rx, texts[s])
        if ms:
            return {
                "value": label,
                "evidence": _sentence_around(texts[s], ms[0].start(), ms[0].end()),
                "confidence": round(min(0.45 + 0.1 * n, 0.9), 2),
            }
    raise AssertionError


def _tone(text: str):
    pl, fo = len(PLAYFUL_TONE.findall(text)), len(FORMAL_TONE.findall(text))
    return None if pl + fo == 0 else pl / (pl + fo)


def _flat(c: dict) -> set[str]:
    return set().union(*c.values())


def _persona(headline_line: str, claims: list[dict], src: str, status: str, label: str) -> dict:
    if status == "not_readable":
        return {"summary": f"No readable {label} content.", "evidence": []}
    mine = [c for c in claims if c["source"] == src]
    topics = ", ".join(c["value"] for c in mine[:4]) or "little that can be reliably read"
    ev = [headline_line] if headline_line else []
    ev += [c["evidence"] for c in mine[:2] if c["evidence"] != headline_line]
    return {"summary": f"{label.capitalize()} presence centres on: {topics}.", "evidence": ev}


def heuristic_profile(fixture: dict) -> dict:
    texts = {s: source_text(fixture, s) for s in SOURCES}
    status = source_statuses(texts, fixture)
    cats = {c: _claims_for(c, texts) for c in ("hobbies", "interests", "values", "lifestyle", "needs")}
    cats["wants_in_partner"] = _wants(texts)
    all_claims = [c for v in cats.values() for c in v]
    ca, cb = concepts_in(texts["linkedin"]), concepts_in(texts["instagram"])
    sa, sb = _flat(ca), _flat(cb)
    jac = len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0
    ta, tb = _tone(texts["linkedin"]), _tone(texts["instagram"])
    tone_diff = abs((0.5 if ta is None else ta) - (0.5 if tb is None else tb))
    gap = round(0.6 * (1 - jac) + 0.4 * tone_diff, 2)
    only_li, only_ig = sorted(sa - sb)[:3], sorted(sb - sa)[:3]
    if status["linkedin"] == "not_readable" or status["instagram"] != "ok":
        gap = min(gap, 0.25)
        gap_desc = "Instagram is too thin (or a source unreadable) to measure the gap reliably; treat as low confidence."
    else:
        tone_note = (
            "LinkedIn reads formal while Instagram reads playful. " if (ta is not None and tb is not None and tb - ta > 0.4)
            else "Tone is similar across both sources. "
        )
        gap_desc = f"{tone_note}Only on LinkedIn: {', '.join(only_li) or 'nothing distinctive'}. Only on Instagram: {', '.join(only_ig) or 'nothing distinctive'}."
    li_head = (fixture.get("linkedin") or {}).get("headline", "") if isinstance(fixture.get("linkedin"), dict) else ""
    ig_bio = (fixture.get("instagram") or {}).get("bio", "") if isinstance(fixture.get("instagram"), dict) else ""
    top = ", ".join(c["value"] for c in (cats["hobbies"] + cats["interests"])[:4]) or "limited public detail"
    ident = identity_check(fixture)
    return {
        "summary": f"{fixture.get('display_name', 'This person')}: {li_head or 'professional details unclear'}. Public text points to: {top}.",
        **cats,
        "communication_style": _trait(COMM_STYLES, texts),
        "humor": _trait(HUMORS, texts),
        "energy": _trait(ENERGIES, texts),
        "linkedin_persona": _persona(li_head, all_claims, "linkedin", status["linkedin"], "linkedin"),
        "instagram_persona": _persona(ig_bio, all_claims, "instagram", status["instagram"], "instagram"),
        "persona_gap": {"score": gap, "description": gap_desc},
        "identity_match": {"score": ident.score, "reason": ident.reason},
        "source_status": status,
    }


def _analyst(*, system, user, context):
    fixture = context.get("fixture")
    if not fixture:
        raise RuntimeError("mock analyst needs context['fixture']")
    return json.dumps(heuristic_profile(fixture))


def _referee_h(*, system, user, context):
    return json.dumps({"flags": _referee.heuristic_flags(context)})


def _briefing_h(*, system, user, context):
    return json.dumps(_briefing.heuristic_briefing(context))


def _ask_h(*, system, user, context):
    return _briefing.heuristic_answer(context)


MockClient.handlers.update({"analyst": _analyst, "referee": _referee_h, "briefing": _briefing_h, "ask": _ask_h})
