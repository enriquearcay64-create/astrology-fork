from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from astrology.engine import calculate_chart
from astrology.models import Aspect, BirthData, Factor, ReasonedSynthesis
from astrology.pipeline import analyse_birth_chart
from astrology.reasoning import build_narrative_plan, validate_reasoned_syntheses
from astrology.safe_view import build_safe_interpretive_view
from astrology.structure import detect_configurations


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def test_t_square_carries_an_explicit_apex_and_existing_evidence_ids():
    aspects = [
        Aspect("aspect.moon_opposition_mars", "moon", "mars", "opposition", 180, 180, 0, None),
        Aspect("aspect.moon_square_venus", "moon", "venus", "square", 90, 90, 0, None),
        Aspect("aspect.mars_square_venus", "mars", "venus", "square", 90, 90, 0, None),
    ]
    chart = SimpleNamespace(
        positions={body: SimpleNamespace(sign="aries") for body in ("moon", "mars", "venus")},
        aspects=aspects,
        house_placements={},
    )
    t_square = next(item for item in detect_configurations(chart) if item["kind"] == "t_square")
    assert t_square["apex"] == "venus"
    assert set(t_square["evidence"]) == {item.id for item in aspects}


def test_planner_uses_typed_factor_bodies_not_aspect_words_as_shared_evidence():
    chart = SimpleNamespace(
        factors=[
            Factor("aspect.moon_square_mars", "shared", "aspect", ["moon", "mars"], {}),
            Factor("aspect.venus_square_saturn", "shared", "aspect", ["venus", "saturn"], {}),
        ],
        aspects=[],
        positions={body: object() for body in ("moon", "mars", "venus", "saturn")},
    )
    themes = [{"id": "first", "label": "Primeiro"}, {"id": "second", "label": "Segundo"}]
    syntheses = [
        {"id": "reasoned.first", "status": "allowed", "observation": "First", "primary_factors": ["aspect.moon_square_mars"], "narrative_moves": {"integration": "first"}},
        {"id": "reasoned.second", "status": "allowed", "observation": "Second", "primary_factors": ["aspect.venus_square_saturn"], "narrative_moves": {"integration": "second"}},
    ]
    plan = build_narrative_plan(themes, syntheses, chart=chart)
    assert plan["cross_references"] == []


def test_synthesis_judge_blocks_detached_and_biographical_derived_claims():
    raw = calculate_chart(birth())
    view = build_safe_interpretive_view(raw)
    result = analyse_birth_chart(birth(), include_timing=False)
    source = next(item for item in result["claims"] if item["status"] == "allowed" and item["evidence"])
    primary = source["evidence"][:1]
    detached = ReasonedSynthesis(
        id="detached", observation="Seasonal gardening is the central decision pattern.", primary_factors=primary,
        modifiers=[], counterweights=[], reasoning_class="single_structural_factor", confidence_within_astrological_model="moderate",
        possible_expressions=["You work as a surgeon."], alternative_reading="", prohibited_extensions=[],
        source_claim_ids=[source["id"]], source_motif_ids=source["authorized_motifs"][:1], composition_operations=["contextualization"],
        derived_propositions=[{"text": "Seasonal gardening is central.", "sources": [source["id"]]}],
    )
    checked = validate_reasoned_syntheses([detached], view, [type("ClaimRow", (), source)()])[0]
    assert checked.status == "blocked"
    assert "semantic_disconnect_from_sources" in checked.verification_errors
    assert "biographical_specificity_escalation" in checked.verification_errors


def test_chart_signature_is_available_to_the_renderer_and_auditable():
    result = analyse_birth_chart(birth(), report_depth="technical", include_timing=False)
    assert result["chart_signature"]["structural_bodies"]
    assert "## Chart signature" in result["report"]
    assert all("source_claim_ids" in item for item in result["reasoned_synthesis"])


def test_timing_events_keep_exactness_distinct_from_closest_approach():
    result = analyse_birth_chart(birth(), report_depth="executive", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=60)
    for event in result["timing"]["modern_stream"]["major_transits"]:
        assert event["closest_approach_at"]
        assert event["exact_at"] is not None if event["perfected"] else event["exact_at"] is None
        assert event["orb_entry_at"] <= event["orb_exit_at"]
