"""Offline handlers for the date tasks: plan, speak, rubric.

Scores derive from REAL profile overlap (token overlap on interests/values/lifestyle/communication plus
need-fulfilment) with small deterministic per-pair noise seeded from the sorted ids. Spoken lines only use items
from the speaker's own profile (plus echoes of things the other side said publicly)."""
from __future__ import annotations

import hashlib
import json
import math
import random
import re

from common.llm import MockClient
from common.models import DIMENSIONS

_STOP = set(
    "that this with from have your about into over more most very been being their they them what when where which while "
    "also than then some such only just like love enjoy enjoys likes loves fond keen person people someone things thing "
    "time life work working".split()
)


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[a-z]{4,}", (text or "").lower()) if w not in _STOP}


def _bag(claims) -> set[str]:
    out: set[str] = set()
    for c in claims or []:
        out |= _stems(c if isinstance(c, str) else c["value"] if isinstance(c, dict) else c.value)
    return out


def _trait(t) -> set[str]:
    return _stems(t["value"] if isinstance(t, dict) else t.value)


def _p(profile, key):
    return profile[key] if isinstance(profile, dict) else getattr(profile, key)


def _all_text_bag(profile) -> set[str]:
    out: set[str] = set()
    for k in ("hobbies", "interests", "values", "lifestyle", "needs", "wants_in_partner"):
        out |= _bag(_p(profile, k))
    for k in ("communication_style", "humor", "energy"):
        out |= _trait(_p(profile, k))
    return out


def _jac(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _cov(a: set, b: set) -> float:
    """share of a's items that b also has (directional)"""
    return len(a & b) / len(a) if a else 0.0


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def _scale(s: float) -> float:
    """similarity 0..1 -> score 0..10 (concave so modest real overlap still shows)."""
    return 2.4 + 7.6 * min(1.0, math.sqrt(max(0.0, s)) * 1.5)


def components(pa, pb) -> dict:
    """Directional 0..1 similarity components for rater a about b. Pure function of the two profiles."""
    ia, ib = _bag(_p(pa, "hobbies")) | _bag(_p(pa, "interests")), _bag(_p(pb, "hobbies")) | _bag(_p(pb, "interests"))
    va, vb = _bag(_p(pa, "values")), _bag(_p(pb, "values"))
    la, lb = _bag(_p(pa, "lifestyle")), _bag(_p(pb, "lifestyle"))
    ca = _trait(_p(pa, "communication_style")) | _trait(_p(pa, "humor")) | _trait(_p(pa, "energy"))
    cb = _trait(_p(pb, "communication_style")) | _trait(_p(pb, "humor")) | _trait(_p(pb, "energy"))
    wants = _bag(_p(pa, "wants_in_partner")) | _bag(_p(pa, "needs"))
    return {
        "interest_overlap": 0.5 * _jac(ia, ib) + 0.5 * _cov(ia, ib),
        "values_alignment": 0.5 * _jac(va, vb) + 0.5 * _cov(va, vb),
        "communication_chemistry": 0.04 + 0.96 * (0.5 * _jac(ca, cb) + 0.5 * _cov(ca, cb)),
        "lifestyle_fit": 0.5 * _jac(la, lb) + 0.5 * _cov(la, lb),
        # growth: how much of what a wants/needs b's profile speaks to, plus a little shared-interest pull
        "growth_potential": 0.65 * _cov(wants, _all_text_bag(pb)) + 0.35 * _jac(ia | va, ib | vb),
    }


def directional_scores(pa, pb, id_a: str, id_b: str) -> dict[str, float]:
    """a's rating of b, 0..10 per dimension, with seeded noise (shared pair noise + small directional noise)."""
    comp = components(pa, pb)
    pair = random.Random(_seed("pair", *sorted([id_a, id_b])))
    direc = random.Random(_seed("dir", id_a, id_b))
    out = {}
    for d in DIMENSIONS:
        v = _scale(comp[d]) + pair.gauss(0, 1.2) + direc.gauss(0, 0.35)
        out[d] = round(max(0.0, min(10.0, v)), 2)
    return out


def _mean(d: dict) -> float:
    return sum(d.values()) / len(d)


def _first(name: str) -> str:
    return (name or "I").split()[0]


def _items(profile, key) -> list[str]:
    return [c["value"] if isinstance(c, dict) else c.value for c in (_p(profile, key) or [])]


def _pick(rng: random.Random, xs: list[str], default: str) -> str:
    return rng.choice(xs) if xs else default


def _mentioned(other_profile, history, other_id) -> list[str]:
    said = " ".join(t["public_text"].lower() for t in history if t["speaker"] == other_id)
    found = []
    for k in ("hobbies", "interests", "values", "lifestyle", "wants_in_partner"):
        for v in _items(other_profile, k):
            if v.lower() in said:
                found.append(v)
    return found


# ---------------------------------------------------------------- plan
def _plan(system: str, user: str, context: dict) -> str:
    ctx = context
    me = ctx["self_profile"]
    oracle = (ctx.get("mock_oracle") or {})
    other = oracle.get("other_profile")
    sid = ctx["self_id"]
    oid = next((i for i in ctx["names"] if i != sid), "other")
    stage, idx, total, prev = ctx["stage"], ctx["idx"], ctx["total"], ctx["prev_chem"]
    rng = random.Random(_seed("plan", *sorted([sid, oid]), sid, idx))
    scenario = oracle.get("kind") == "scenario"
    if other is None:  # no oracle: neutral behaviour
        chem = max(0.0, min(10.0, prev + rng.gauss(0, 0.5)))
        return json.dumps({"learned": "", "probe": "get to know them", "private_note": f"Chemistry {chem:.1f}.", "chemistry": chem, "end_date": False})
    dirs = directional_scores(me, other, sid, oid)
    comp = components(me, other)
    target = _mean(dirs)
    hist = ctx["history"]
    heard = _mentioned(other, hist, oid)
    shared = _shared_items(me, other)[:4]
    delta = 0.42 * (target - prev)  # drift toward real compatibility
    if stage == "friction":
        sev = 1.0 - min(1.0, comp["lifestyle_fit"] * 2.0)
        first = idx == 0 or ctx["history"][-1]["stage"] != "friction"
        if first:
            delta -= (0.7 + 1.5 * sev) * (1.4 if scenario else 1.0)
        else:  # repair depends on communication chemistry
            delta += 0.6 + 2.2 * comp["communication_chemistry"] * (1 - 0.4 * sev)
    elif stage == "values":
        delta += (comp["values_alignment"] - 0.2) * 3.0
    elif stage == "what_do_you_want":
        delta += (comp["growth_potential"] - 0.2) * 3.0
    elif stage == "shared_interests":
        delta += (comp["interest_overlap"] - 0.15) * 3.0
    delta += rng.gauss(0, 0.45)
    chem = max(0.0, min(10.0, prev + delta))
    if target < 3.0 and idx >= 2:  # clearly incompatible pairs go cold
        chem = max(0.0, min(chem, prev - 0.3 + rng.gauss(0, 0.2)))
    nxt = {"opening": "shared interests", "shared_interests": "a friction topic", "friction": "how they handle disagreement",
           "values": "what they want from a partner", "what_do_you_want": "whether to meet again", "close": "nothing more"}[stage]
    learned = ("they mentioned " + ", ".join(heard[:3])) if heard else ("nothing concrete yet" if idx < 2 else "they stayed fairly general")
    if shared:
        learned += f"; overlaps with my profile: {', '.join(shared[:3])}"
    mood = "warming up" if chem > prev + 0.5 else "cooling" if chem < prev - 0.5 else "steady"
    note = f"Chemistry {chem:.1f} ({mood}). Stage {stage}."
    if stage == "friction":
        note += " Testing how they react to a real difference."
    return json.dumps({"learned": learned, "probe": nxt, "private_note": note, "chemistry": round(chem, 2),
                       "end_date": bool(chem <= 1.5 and idx >= 3)})


def _shared_items(me, other) -> list[str]:
    """Values from ME's profile whose words also appear in the other's profile."""
    ob = _all_text_bag(other)
    return [v for v in _items_all(me) if _stems(v) & ob]


def _items_all(profile) -> list:
    out = []
    for k in ("hobbies", "interests", "values", "lifestyle"):
        out += _items(profile, k)
    return out


# ---------------------------------------------------------------- speak
def _speak(system: str, user: str, context: dict) -> str:
    ctx = context
    me = ctx["self_profile"]
    sid = ctx["self_id"]
    oid = next((i for i in ctx["names"] if i != sid), "other")
    stage, idx = ctx["stage"], ctx["idx"]
    plan = ctx.get("plan") or {}
    chem = ctx.get("plan", {}).get("chemistry", 5.0)
    rng = random.Random(_seed("speak", *sorted([sid, oid]), sid, idx))
    other_name = _first(ctx["names"].get(oid, "you"))
    me_name = _first(ctx["self_name"])
    hobby = _pick(rng, _items(me, "hobbies"), "")
    interest = _pick(rng, _items(me, "interests"), "")
    value = _pick(rng, _items(me, "values"), "")
    life = _pick(rng, _items(me, "lifestyle"), "")
    want = _pick(rng, _items(me, "wants_in_partner"), "")
    need = _pick(rng, _items(me, "needs"), "")
    prior = [t for t in ctx["history"] if t["speaker"] == oid]
    warm = chem >= 6
    cold = chem < 3.5
    reaction = "" if not prior else (rng.choice(["That's lovely to hear. ", "Nice, I like that. ", "Ha, that's great. "]) if warm else
                                      rng.choice(["Okay, I see. ", "Hm, fair enough. "]) if cold else rng.choice(["Interesting. ", "Got it. ", "Right. "]))
    task = ctx.get("task") or ""
    if task:
        return json.dumps({"message": _scenario_line(stage, rng, reaction, task, hobby, interest, life, value, want, other_name, warm, cold)})
    L = {
        "opening": [
            f"Hi {other_name}, I'm {me_name}. " + (f"{_first_sentence(me['summary'])} " if me.get("summary") and "|" not in me["summary"][:200] and len(_first_sentence(me["summary"])) < 160 else "") + "What are you hoping tonight turns into?",
            f"{reaction}Nice to meet you. I'm {me_name}" + (f", and {hobby} is usually how I unwind" if hobby else "") + ". What about you?",
        ],
        "shared_interests": [
            f"{reaction}" + (f"Outside of work I'm into {hobby}" if hobby else "I like keeping my free time simple") + (f", and I keep coming back to {interest}" if interest else "") + ". What do you do for fun?",
            f"{reaction}" + (f"I'm genuinely curious about {interest}. " if interest else "") + "Is there something you could talk about for hours?",
        ],
        "friction": [
            f"{reaction}Let me be upfront: " + (f"{life}" if life else "I have my routines") + ". Does that sound workable to you, or would it grate?",
            f"{reaction}Honestly, I can be set in my ways" + (f" (for me: {life})" if life else "") + ". How do you handle a difference like that?",
        ],
        "values": [
            f"{reaction}" + (f"For me, {value} matters a lot. " if value else "I care about being straightforward. ") + "What is non-negotiable for you?",
            f"{reaction}" + (f"I try to live by {value}. " if value else "") + "What do you try to live by?",
        ],
        "what_do_you_want": [
            f"{reaction}" + (f"In a partner I'm looking for {want}. " if want else "I'm looking for someone easy to be honest with. ") + "What do you want?",
            f"{reaction}" + (f"What I need is {need}. " if need else "") + "Where do you see something like this going?",
        ],
        "close": [
            (f"{reaction}I've really enjoyed this, {other_name}. I'd love to meet again." if warm else
             f"{reaction}Thanks for your time, {other_name}. I think we want different things, and I'd rather be honest about that." if cold else
             f"{reaction}Thanks, {other_name}. I'd be open to another conversation, and I'm still working out how we fit."),
        ],
    }
    return json.dumps({"message": " ".join(rng.choice(L[stage]).split())})


def _first_sentence(s: str) -> str:
    m = re.match(r"(.+?[.!?])(\s|$)", s.strip())
    return m.group(1) if m else s.strip()[:160]


def _scenario_line(stage, rng, reaction, task, hobby, interest, life, value, want, other_name, warm, cold) -> str:
    comfort = "comfort" in task.split("lean toward")[-1][:60]
    my_side = "comfort" if comfort else "experiences"
    split = "about 900 on comfort and 600 on experiences" if comfort else "about 600 on comfort and 900 on experiences"
    anchor = hobby or interest or "something we both enjoy"
    L = {
        "opening": f"{reaction}Hi {other_name}. Four days, 1500 total. I'd start by agreeing what we each care about. I tend to favour {my_side}.",
        "shared_interests": f"{reaction}I'd want at least one day built around {anchor}. What would you want to see or do?",
        "friction": f"{reaction}Here's where I disagree: I'd put {split}. " + (f"{life}. " if life else "") + "Can you move toward that?",
        "values": f"{reaction}" + (f"For me {value} matters when we spend money together. " if value else "") + "How do you think about splitting costs fairly?",
        "what_do_you_want": f"{reaction}" + ("Here's a compromise: split the difference and keep a 150 buffer. " if not cold else "I'm not sure we can bridge this, but here's a split-the-difference offer. ") + "Does that work?",
        "close": (f"{reaction}I like where we landed. I'd happily do this trip with you." if warm else f"{reaction}We found a rough plan, but I'm not sure this trip would work for us." if cold else f"{reaction}We have a workable plan, though it took compromise."),
    }
    return " ".join(L[stage].split())


# ---------------------------------------------------------------- rubric
def _rubric(system: str, user: str, context: dict) -> str:
    ctx = context
    me = ctx["self_profile"]
    oracle = ctx.get("mock_oracle") or {}
    other = oracle.get("other_profile")
    sid, oid = ctx["self_id"], ctx["other_id"]
    if other is None:
        return json.dumps({d: 5.0 for d in DIMENSIONS} | {"would_meet_again": False, "verdict": "Not enough information."})
    dirs = directional_scores(me, other, sid, oid)
    fc = ctx.get("final_chem", 5.0)
    out = {d: round(max(0.0, min(10.0, 0.8 * v + 0.2 * fc)), 2) for d, v in dirs.items()}
    avg = _mean(out)
    would = avg >= 5.8 and fc >= 4.5
    best = max(out, key=out.get).replace("_", " ")
    worst = min(out, key=out.get).replace("_", " ")
    name = _first(ctx["other_name"])
    shared = _shared_items(me, other)[:2]
    hook = f" (common ground: {', '.join(shared)})" if shared else ""
    if would:
        verdict = f"Would meet {name} again: strongest on {best}{hook}; watch {worst}."
    elif avg >= 4.5:
        verdict = f"Pleasant with {name} but unsure: {best} was fine, {worst} was thin."
    else:
        verdict = f"Not a fit with {name}: {worst} was the clearest gap."
    return json.dumps(out | {"would_meet_again": would, "verdict": verdict})


def register() -> None:
    """Idempotent: (re)install handlers even if another module replaced MockClient.handlers."""
    if not isinstance(MockClient.handlers, dict):
        MockClient.handlers = {}
    MockClient.handlers["plan"] = _plan
    MockClient.handlers["speak"] = _speak
    MockClient.handlers["rubric"] = _rubric


register()
