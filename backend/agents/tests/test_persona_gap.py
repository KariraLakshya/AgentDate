from agents.analyst import analyze
from agents.personas_loader import load_personas


def test_gap_is_not_reported_when_a_source_is_missing():
    p = load_personas()[8]  # a high-gap persona when both sources are present
    both = analyze(p)
    one = analyze({**p, "linkedin": None})
    assert both.persona_gap.score > 0.5
    assert one.source_status["linkedin"] == "not_readable"
    assert one.persona_gap.score == 0.0 and one.persona_gap.description.startswith("Not enough data")
