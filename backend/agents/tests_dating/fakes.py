"""Synthetic Profile generator for tests (so tests do not depend on agent B's analyst)."""
import random

from common.models import Claim, IdentityMatch, Persona, PersonaGap, Profile, Trait

HOBBIES = ["trail running", "rock climbing", "pottery", "baking sourdough", "board games", "film photography",
           "salsa dancing", "gardening", "chess", "surfing", "knitting", "cycling", "birdwatching", "painting"]
INTERESTS = ["machine learning", "urban planning", "jazz music", "ancient history", "climate policy", "astronomy",
             "street food", "poetry", "robotics", "architecture", "cooking", "travel writing"]
VALUES = ["honesty", "curiosity", "family closeness", "ambition", "kindness", "independence", "stability", "adventure"]
LIFE = ["early riser", "night owl", "homebody", "frequent traveller", "vegetarian cooking", "social weekends", "quiet evenings", "city living"]
COMM = ["direct and warm", "playful and teasing", "thoughtful and slow", "enthusiastic storyteller", "dry and understated"]
HUM = ["dry wit", "playful puns", "self-deprecating", "absurdist"]
EN = ["high energy", "calm and steady", "moderate energy"]
WANT = ["someone curious", "a calm companion", "an adventurous partner", "someone ambitious", "a kind listener"]


def _c(v, s="linkedin"):
    return Claim(value=v, evidence=f"quote: {v}", source=s, confidence=0.8)


def make_profile(seed: int) -> Profile:
    r = random.Random(seed)
    t = lambda v: Trait(value=v, evidence=f"quote: {v}", confidence=0.7)
    return Profile(
        summary=f"Person {seed} is a synthetic persona. They like to keep things real.",
        needs=[_c(r.choice(WANT))],
        hobbies=[_c(h, "instagram") for h in r.sample(HOBBIES, 3)],
        interests=[_c(h) for h in r.sample(INTERESTS, 2)],
        values=[_c(h) for h in r.sample(VALUES, 2)],
        communication_style=t(r.choice(COMM)), humor=t(r.choice(HUM)), energy=t(r.choice(EN)),
        lifestyle=[_c(h, "instagram") for h in r.sample(LIFE, 2)],
        wants_in_partner=[_c(r.choice(WANT)), _c(r.choice(VALUES))],
        linkedin_persona=Persona(summary="Professional and focused."), instagram_persona=Persona(summary="Relaxed off duty."),
        persona_gap=PersonaGap(score=0.3, description="Mild gap."), identity_match=IdentityMatch(score=0.9, reason="ok"),
        source_status={"linkedin": "ok", "instagram": "ok"},
    )


def make_pool(n=25):
    return [(f"p{i+1:02d}", f"Person {i+1}", make_profile(i)) for i in range(n)]
