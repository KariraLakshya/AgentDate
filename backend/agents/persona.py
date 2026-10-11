"""Persona dating agent: prompts, JSON parsing and the plan/speak/rubric steps for ONE person.

Isolation: a PersonaAgent is constructed with a single profile. Its prompts contain only that profile plus the
PUBLIC transcript. The other person's profile never reaches an agent (it is only handed to MockClient, never to a
real model, so mock scores can derive from real overlap)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from common.llm import extract_json
from common.models import DIMENSIONS, Profile, Rubric

STAGE_GUIDE = {
    "opening": "Introduce yourself warmly and ask one light opening question.",
    "shared_interests": "Explore hobbies and interests; find overlap with what the other person has said.",
    "friction": "Raise one honest friction topic (a lifestyle or habit difference) and see how they handle it.",
    "values": "Ask or share a values question: what matters most to you.",
    "what_do_you_want": "Say honestly what you want from a partner and ask what they want.",
    "close": "Close the date: say whether you'd like to meet again, honestly and kindly.",
}

RULES = (
    "RULES: You speak in first person as the person below. Use ONLY facts in your profile; never invent jobs, "
    "places, people, hobbies or history. If asked something your profile does not cover, say you'd rather "
    "not guess or turn it back to them. Never infer or discuss religion, sexual orientation, gender identity, "
    "health, politics or ethnicity. You have NOT seen the other person's profile: learn about them only from "
    "what they say. Be natural and brief (1-3 sentences)."
)


def _claims(items) -> str:
    return "; ".join(c.value for c in items) or "(none)"


def profile_brief(p: Profile) -> str:
    """Compact text view of ONE person's profile for their own agent."""
    return "\n".join(
        [
            f"Summary: {p.summary}",
            f"Needs: {_claims(p.needs)}",
            f"Hobbies: {_claims(p.hobbies)}",
            f"Interests: {_claims(p.interests)}",
            f"Values: {_claims(p.values)}",
            f"Lifestyle: {_claims(p.lifestyle)}",
            f"Wants in a partner: {_claims(p.wants_in_partner)}",
            f"Communication style: {p.communication_style.value}",
            f"Humor: {p.humor.value}",
            f"Energy: {p.energy.value}",
            f"Public (LinkedIn) self: {p.linkedin_persona.summary}",
            f"Off-duty (Instagram) self: {p.instagram_persona.summary}",
            f"Gap between the two: {p.persona_gap.description}",
        ]
    )


def system_prompt(name: str, profile: Profile, task: str | None = None) -> str:
    s = f"You are the dating agent for {name}, going on a first date with another person's agent.\n{RULES}\n\n"
    s += f"YOUR PERSON'S PROFILE ({name}):\n{profile_brief(profile)}\n"
    if task:
        s += f"\nSHARED TASK FOR THIS DATE: {task}\n"
    return s


def transcript_text(history: list[dict], names: dict[str, str]) -> str:
    if not history:
        return "(the date is just starting)"
    return "\n".join(f"{names.get(t['speaker'], t['speaker'])}: {t['public_text']}" for t in history)


def plan_user_prompt(stage: str, idx: int, total: int, history, names, prev_chem: float) -> str:
    return (
        f"Turn {idx + 1} of {total}. Stage: {stage} ({STAGE_GUIDE[stage]})\n"
        f"Public transcript so far:\n{transcript_text(history, names)}\n\n"
        f"Your running chemistry so far: {prev_chem:.1f}/10.\n"
        "Reflect on what the other person last said, then PLAN privately. Reply with JSON only:\n"
        '{"learned": "what I learned about them", "probe": "what to probe next", '
        '"private_note": "my private thoughts", "chemistry": <0-10 number>, "end_date": <true only if chemistry is clearly dead>}'
    )


def speak_user_prompt(stage: str, plan: dict, history, names) -> str:
    return (
        f"Stage: {stage} ({STAGE_GUIDE[stage]})\nYour private plan: probe={plan.get('probe', '')}\n"
        f"Public transcript so far:\n{transcript_text(history, names)}\n\n"
        'Now speak. Reply with JSON only: {"message": "<what you say out loud>"}'
    )


def rubric_user_prompt(history, names, other_name: str) -> str:
    return (
        f"The date is over. Public transcript:\n{transcript_text(history, names)}\n\n"
        f"Privately rate {other_name} for YOUR person. Reply with JSON only: "
        '{"interest_overlap":0-10,"values_alignment":0-10,"communication_chemistry":0-10,'
        '"lifestyle_fit":0-10,"growth_potential":0-10,"would_meet_again":true|false,"verdict":"one line"}'
    )


def _num(x, lo=0.0, hi=10.0, default=5.0) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def parse_plan(raw: str, prev_chem: float) -> dict:
    try:
        d = extract_json(raw)
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        d = {}
    return {
        "learned": str(d.get("learned", "")),
        "probe": str(d.get("probe", "")),
        "private_note": str(d.get("private_note") or "") or ("" if d else raw[:240]),
        "chemistry": _num(d.get("chemistry"), default=prev_chem),
        "end_date": bool(d.get("end_date", False)),
    }


def parse_speak(raw: str) -> str:
    try:
        d = extract_json(raw)
        if isinstance(d, dict) and d.get("message"):
            return str(d["message"]).strip()
    except Exception:
        pass
    return re.sub(r"\s+", " ", raw).strip().strip('"')[:600] or "..."


def parse_rubric(raw: str) -> Rubric:
    try:
        d = extract_json(raw)
        if not isinstance(d, dict):
            raise ValueError
    except Exception:
        d = {}
    vals = {k: _num(d.get(k)) for k in DIMENSIONS}
    wma = d.get("would_meet_again")
    if not isinstance(wma, bool):
        wma = sum(vals.values()) / len(DIMENSIONS) >= 6.0
    return Rubric(**vals, would_meet_again=wma, verdict=str(d.get("verdict") or "No verdict recorded.")[:300])


@dataclass
class PersonaAgent:
    person_id: str
    name: str
    profile: Profile
    client: object
    task: str | None = None
    chemistry: float = 5.0
    extra_ctx: dict = field(default_factory=dict)  # mock-only oracle; never in prompts

    def _ctx(self, **kw) -> dict:
        return {"self_id": self.person_id, "self_name": self.name, "self_profile": self.profile.model_dump(), "task": self.task, **self.extra_ctx, **kw}

    def plan(self, stage, idx, total, history, names) -> dict:
        raw = self.client.complete(
            system=system_prompt(self.name, self.profile, self.task),
            user=plan_user_prompt(stage, idx, total, history, names, self.chemistry),
            tier="fast", task="plan",
            context=self._ctx(stage=stage, idx=idx, total=total, history=history, names=names, prev_chem=self.chemistry),
        )
        p = parse_plan(raw, self.chemistry)
        self.chemistry = p["chemistry"]
        return p

    def speak(self, stage, idx, total, plan, history, names) -> str:
        raw = self.client.complete(
            system=system_prompt(self.name, self.profile, self.task),
            user=speak_user_prompt(stage, plan, history, names),
            tier="fast", task="speak",
            context=self._ctx(stage=stage, idx=idx, total=total, plan=plan, history=history, names=names),
        )
        return parse_speak(raw)

    def rate(self, history, names, other_id, other_name) -> Rubric:
        raw = self.client.complete(
            system=system_prompt(self.name, self.profile, self.task),
            user=rubric_user_prompt(history, names, other_name),
            tier="fast", task="rubric",
            context=self._ctx(history=history, names=names, other_id=other_id, other_name=other_name, final_chem=self.chemistry),
        )
        return parse_rubric(raw)
