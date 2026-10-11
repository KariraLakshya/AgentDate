"""Shared contracts. Mirrored by frontend/lib/types.ts - change both together."""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Source = Literal["linkedin", "instagram"]
SourceStatus = Literal["ok", "thin", "not_readable"]
DIMENSIONS = ["interest_overlap", "values_alignment", "communication_chemistry", "lifestyle_fit", "growth_potential"]
STAGES = ["opening", "shared_interests", "friction", "values", "what_do_you_want", "close"]


class Claim(BaseModel):
    value: str
    evidence: str  # literal quote from the source text
    source: Source
    confidence: float = Field(ge=0, le=1)


class Trait(BaseModel):
    value: str
    evidence: str
    confidence: float = Field(ge=0, le=1)


class Persona(BaseModel):
    summary: str
    evidence: list[str] = []


class PersonaGap(BaseModel):
    score: float = Field(ge=0, le=1)
    description: str


class IdentityMatch(BaseModel):
    score: float = Field(ge=0, le=1)
    reason: str


class Profile(BaseModel):
    summary: str
    needs: list[Claim] = []
    hobbies: list[Claim] = []
    interests: list[Claim] = []
    values: list[Claim] = []
    communication_style: Trait
    humor: Trait
    energy: Trait
    lifestyle: list[Claim] = []
    wants_in_partner: list[Claim] = []
    linkedin_persona: Persona
    instagram_persona: Persona
    persona_gap: PersonaGap
    identity_match: IdentityMatch
    source_status: dict[Source, SourceStatus]


class Rubric(BaseModel):
    interest_overlap: float = Field(ge=0, le=10)
    values_alignment: float = Field(ge=0, le=10)
    communication_chemistry: float = Field(ge=0, le=10)
    lifestyle_fit: float = Field(ge=0, le=10)
    growth_potential: float = Field(ge=0, le=10)
    would_meet_again: bool
    verdict: str


class DateTurn(BaseModel):
    idx: int
    speaker: str  # person id
    stage: str
    public_text: str
    private_note: str
    chemistry: float = Field(ge=0, le=10)
    flags: list[dict] = []  # {"type": "unsupported_claim|spark|friction|repair", "note": ""}


class DateRecord(BaseModel):
    id: str
    person_a: str
    person_b: str
    kind: Literal["standard", "scenario"] = "standard"
    status: Literal["pending", "running", "done", "failed"] = "pending"
    turns: list[DateTurn] = []
    score_a: Optional[Rubric] = None  # a's rating of b
    score_b: Optional[Rubric] = None  # b's rating of a
    faithfulness_a: Optional[float] = None
    faithfulness_b: Optional[float] = None
    flagged_turns: list[int] = []


class SSEEvent(BaseModel):
    """Event names on /api/dates/{id}/stream: turn | chemistry | flag | done."""
    event: Literal["turn", "chemistry", "flag", "done"]
    data: dict


class Briefing(BaseModel):
    introduce: list[dict]  # {person_id, reason}
    warn: list[dict]
    unsure: list[str]


class PersonSummary(BaseModel):
    id: str
    display_name: str
    synthetic: bool = True
    profile: Optional[Profile] = None


class DemoBundle(BaseModel):
    """data/demo/demo.json - consumed by /demo with no backend, produced by the round-robin script."""
    people: list[PersonSummary]
    dates: list[DateRecord]
    # matrix[i][j] = directional score person i gives person j (mean of dimensions, 0-10); diagonal null
    matrix: list[list[Optional[float]]]
    order: list[str]  # person ids, row/col order of matrix
    stable_pairs: list[tuple[str, str]] = []
    briefings: dict[str, Briefing] = {}
    best_moments: dict[str, str] = {}  # "a|b" -> quoted line
