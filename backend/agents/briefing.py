"""Post-date briefing and "ask my agent why".

`rankings` is a list of dicts sorted or sortable by score (0-10, higher better):
  {"person_id": "p02", "name": "Idris Brannock", "score": 7.8, "why": "...", "best_moment": "...", "friction": "..."}
Only `person_id` and `score` are required.
"""
import json

from common.llm import LLMClient, extract_json, get_client
from common.models import Briefing, Profile

from .lexicon import sensitive_categories

BRIEFING_SYSTEM = """You are a person's dating agent writing a private post-date briefing for the human you represent. You dated every other agent on their behalf. Using ONLY the rankings and profile summary provided, write:
- "introduce": the best matches to meet (up to 3), each {"person_id", "reason"} with a concrete reason grounded in the supplied "why"/"best_moment".
- "warn": matches to be wary of (up to 2, only when the data shows real friction or low fit), each {"person_id", "reason"}.
- "unsure": short strings naming what you were unsure you understood about your person (thin sources, low-confidence fields, persona gap).
Rank on compatibility only; never mention or infer religion, sexual orientation, gender identity, health, politics or ethnicity. Do not invent facts. Return ONE JSON object: {"introduce": [], "warn": [], "unsure": []}."""

ASK_SYSTEM = """You are a person's dating agent answering their question about why you ranked matches the way you did. Use ONLY the supplied rankings, date highlights and profile. Be honest about uncertainty and about any weak evidence. Rankings are by compatibility only; decline to speculate about or use religion, sexual orientation, gender identity, health, politics or ethnicity. Answer in 2-4 sentences of plain text."""

WARN_BELOW = 5.5


def _name(r: dict, names: dict | None) -> str:
    return r.get("name") or (names or {}).get(r["person_id"]) or r["person_id"]


def _reason(r: dict, names=None) -> str:
    bits = []
    if r.get("why"):
        bits.append(str(r["why"]))
    if r.get("best_moment"):
        bits.append(f'Best moment: "{r["best_moment"]}"')
    if not bits:
        bits.append(f"Pair score {float(r['score']):.1f}/10.")
    return " ".join(bits)


def _unsure(profile: dict | None) -> list[str]:
    out: list[str] = []
    if not profile:
        return ["I did not have a profile for you to cross-check my read against."]
    for s, st in (profile.get("source_status") or {}).items():
        if st != "ok":
            out.append(f"Your {s} was {st.replace('_', ' ')}, so I held those fields at lower confidence.")
    gap = (profile.get("persona_gap") or {}).get("score", 0)
    if gap >= 0.5:
        out.append("Your LinkedIn and Instagram personas differ a lot; I was not sure which better reflects what you want day to day.")
    if (profile.get("identity_match") or {}).get("score", 1) < 0.5:
        out.append("I could not confirm your Instagram belongs to the same person as your LinkedIn.")
    low = [c["value"] for f in ("needs", "values", "wants_in_partner", "lifestyle") for c in profile.get(f, []) or [] if c.get("confidence", 1) < 0.5]
    if low:
        out.append("Low-confidence reads: " + ", ".join(low[:4]) + ".")
    return out[:4] or ["Nothing major; my read of you rests on explicit statements in your profile."]


def heuristic_briefing(ctx: dict) -> dict:
    rows = sorted(ctx["rankings"], key=lambda r: -float(r["score"]))
    names = ctx.get("names")
    intro = [{"person_id": r["person_id"], "reason": f"{_name(r, names)}: {_reason(r)}"} for r in rows[:3]]
    warn_rows = [r for r in reversed(rows[3:] if len(rows) > 3 else []) if float(r["score"]) < WARN_BELOW][:2]
    warn = [
        {"person_id": r["person_id"],
         "reason": f"{_name(r, names)}: lower fit ({float(r['score']):.1f}/10)." + (f" Friction: {r['friction']}" if r.get("friction") else "")}
        for r in warn_rows
    ]
    return {"introduce": intro, "warn": warn, "unsure": _unsure(ctx.get("profile"))}


def make_briefing(person_id: str, rankings: list[dict], profile: Profile | dict | None = None,
                  names: dict | None = None, client: LLMClient | None = None) -> Briefing:
    client = client or get_client()
    prof = profile.model_dump() if isinstance(profile, Profile) else profile
    rows = [r for r in rankings if r["person_id"] != person_id]
    ctx = {"person_id": person_id, "rankings": rows, "profile": prof, "names": names or {}}
    user = json.dumps({"person_id": person_id, "rankings": rows, "profile_summary": (prof or {}).get("summary", ""),
                       "source_status": (prof or {}).get("source_status"), "persona_gap": (prof or {}).get("persona_gap"),
                       "identity_match": (prof or {}).get("identity_match"), "names": names or {}}, ensure_ascii=False)
    raw = extract_json(client.complete(system=BRIEFING_SYSTEM, user=user, tier="strong", task="briefing", context=ctx))
    valid = {r["person_id"] for r in rows}

    def clean(items):
        return [i for i in (items or []) if isinstance(i, dict) and i.get("person_id") in valid and not sensitive_categories(str(i.get("reason", "")))]

    return Briefing(introduce=clean(raw.get("introduce")), warn=clean(raw.get("warn")),
                    unsure=[u for u in (raw.get("unsure") or []) if isinstance(u, str) and not sensitive_categories(u)])


def heuristic_answer(ctx: dict) -> str:
    q = (ctx.get("question") or "").lower()
    if sensitive_categories(q):
        return ("I rank only on compatibility from the interests, values, communication and lifestyle shown in public profiles. "
                "I do not infer or use religion, orientation, gender identity, health, politics or ethnicity, so that cannot be part of my reasoning.")
    rows = sorted(ctx["rankings"], key=lambda r: -float(r["score"]))
    if not rows:
        return "I have no completed dates to base an answer on yet."
    names = ctx.get("names")
    target, rank = None, None
    for i, r in enumerate(rows):
        if r["person_id"].lower() in q or _name(r, names).lower() in q or _name(r, names).split()[0].lower() in q:
            target, rank = r, i + 1
            break
    if target is None:
        if any(w in q for w in ("last", "worst", "bottom", "lowest", "warn")):
            target, rank = rows[-1], len(rows)
        else:
            target, rank = rows[0], 1
    ans = f"I put {_name(target, names)} at #{rank} of {len(rows)} (score {float(target['score']):.1f}/10). {_reason(target)}"
    if target.get("friction"):
        ans += f" The sticking point was: {target['friction']}"
    unsure = _unsure(ctx.get("profile"))
    if unsure and not unsure[0].startswith("Nothing major"):
        ans += " Caveat: " + unsure[0]
    return ans


def answer_why(question: str, person_id: str, rankings: list[dict], profile: Profile | dict | None = None,
               names: dict | None = None, client: LLMClient | None = None) -> str:
    client = client or get_client()
    prof = profile.model_dump() if isinstance(profile, Profile) else profile
    rows = [r for r in rankings if r["person_id"] != person_id]
    ctx = {"question": question, "person_id": person_id, "rankings": rows, "profile": prof, "names": names or {}}
    user = json.dumps({"question": question, "rankings": rows, "profile_summary": (prof or {}).get("summary", ""), "names": names or {}},
                      ensure_ascii=False)
    out = client.complete(system=ASK_SYSTEM, user=user, tier="strong", task="ask", context=ctx).strip()
    if sensitive_categories(out):
        out = heuristic_answer({**ctx, "question": "religion"})
    return out
