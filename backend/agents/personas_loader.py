"""Load the 25 synthetic persona fixtures and render the exact source text evidence quotes must come from."""
import json
from pathlib import Path

PERSONA_DIR = Path(__file__).resolve().parents[2] / "data" / "personas"


def load_personas(directory: Path | str | None = None) -> list[dict]:
    d = Path(directory) if directory else PERSONA_DIR
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("p*.json"))]


def source_text(fixture: dict, source: str) -> str:
    """Canonical text of one source. Every evidence quote must be a literal substring of this string.

    Accepts the fixture shape ({"linkedin": {...}, "instagram": {...}}) or a source value that is already a string.
    Returns "" when the source is missing/unreadable.
    """
    data = fixture.get(source) if isinstance(fixture, dict) else None
    if not data:
        return ""
    if isinstance(data, str):
        return data
    lines: list[str] = []
    if source == "linkedin":
        lines += [data.get("headline", ""), data.get("about", ""), data.get("location", "")]
        for e in data.get("experience", []) or []:
            lines.append(f"{e.get('title', '')} - {e.get('company', '')}: {e.get('description', '')}")
        skills = data.get("skills") or []
        if skills:
            lines.append(", ".join(skills))
    elif source == "instagram":
        lines += [data.get("bio", ""), data.get("location", "")]
        for p in data.get("posts", []) or []:
            lines.append(p.get("caption", "") if isinstance(p, dict) else str(p))
    else:
        raise ValueError(f"unknown source {source}")
    return "\n".join(x for x in lines if x)
