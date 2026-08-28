from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from astrology.engine import calculate_chart
from astrology.models import Aspect, BirthData, Factor, ReasonedSynthesis
from astrology.pipeline import analyse_birth_chart, prepare_premium_handoff, validate_premium_narrative, validate_premium_syntheses
from astrology.reasoning import ASPECT_OPERATIONS, build_chart_signature, build_narrative_plan, validate_reasoned_syntheses
from astrology.safe_view import build_safe_interpretive_view
from astrology.semantics import _claim_from_aspect
from astrology.structure import detect_configurations
from astrology.timing import ORB_BOUNDARY_TOLERANCE_DEGREES, _deviation, _jd_for_datetime, _longitude


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
        assert "near_exact_within_tolerance" in event
        assert event["orb_entry_at"] <= event["orb_exit_at"]


def test_signature_leads_planner_and_ablation_changes_only_dependent_story():
    result = analyse_birth_chart(birth(), include_timing=False)
    chart = build_safe_interpretive_view(calculate_chart(birth()))
    signature = result["chart_signature"]
    plan = result["narrative_plan"]
    assert signature["mode"] == "central"
    anchors = set(signature["central_dynamic"]["bodies"])
    assert anchors
    assert plan["opening"]["source_syntheses"][0] == f"reasoned.{plan['themes'][0]}"
    assert all(any(anchors.intersection({body for aspect in chart.aspects if aspect.id == factor for body in (aspect.left, aspect.right)}) for factor in next(item for item in result["reasoned_synthesis"] if item["id"] == f"reasoned.{theme}")["primary_factors"] if factor.startswith("aspect.")) for theme in plan["themes"])
    by_aspect = {aspect.id: {aspect.left, aspect.right} for aspect in chart.aspects}
    ablated = [item for item in result["reasoned_synthesis"] if all("sun" not in by_aspect.get(factor, set()) for factor in item["primary_factors"])]
    altered_signature = build_chart_signature(chart, result["hierarchy"], result["chart_structure"], ablated)
    altered_plan = build_narrative_plan(result["themes"], ablated, chart=chart, chart_signature=altered_signature)
    assert altered_signature["mode"] == "distributed"
    assert altered_plan["themes"] != plan["themes"]
    # The renderer must preserve the planner order, not merely filter a
    # theme-sorted list after the signature has done its work.
    report = analyse_birth_chart(birth(), report_depth="deep", include_timing=False)["report"]
    labels = {item["id"]: item["label"] for item in result["themes"]}
    first_label = labels[plan["themes"][0]]
    second_label = labels[plan["themes"][1]]
    assert report.index(f"### 1. {first_label}") < report.index(f"### 2. {second_label}")


def test_distributed_signature_does_not_force_one_totalising_opening():
    unknown_time = BirthData("1978-09-19T12:00:00", "America/Argentina/Buenos_Aires", -34.6037, -58.3816, birth_time_known=False)
    result = analyse_birth_chart(unknown_time, include_timing=False)
    assert result["chart_signature"]["mode"] == "distributed"
    assert len(result["narrative_plan"]["themes"]) <= 4
    assert "não pede uma explicação única" in result["narrative_plan"]["opening"]["observation"]


def test_generic_pair_primitives_and_aspect_dynamics_are_not_body_shortcuts():
    mercury_uranus = Aspect("aspect.mercury_square_uranus", "mercury", "uranus", "square", 90, 92, 2, True)
    venus_uranus = Aspect("aspect.venus_square_uranus", "venus", "uranus", "square", 90, 92, 2, True)
    first = _claim_from_aspect(mercury_uranus, 1, "pt-BR")
    second = _claim_from_aspect(venus_uranus, 2, "pt-BR")
    assert first.theme == "stability_change"
    assert second.theme == "autonomy_closeness"
    assert "cognição" in first.statement and "linguagem" in first.statement
    assert "vínculo" in second.statement and "liberdade" in second.statement
    assert first.statement != second.statement


def test_aspect_geometry_is_neutral_before_narrative_value_is_chosen():
    assert ASPECT_OPERATIONS["trine"] == "low_resistance"
    assert ASPECT_OPERATIONS["square"] == "friction"
    result = analyse_birth_chart(birth(), include_timing=False)
    moves = [item["narrative_moves"] for item in result["reasoned_synthesis"] if item["status"] == "allowed"]
    assert any("padrão deixa de ser examinado" in item["pressure"] for item in moves)
    assert any("aperfeiçoar uma escolha" in item["constructive"] for item in moves)


def test_refined_orb_edges_sit_on_the_configured_boundary():
    result = analyse_birth_chart(birth(), as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=60)
    event = result["timing"]["modern_stream"]["major_transits"][0]
    target = calculate_chart(birth()).positions[event["target"]].longitude
    for key in ("orb_entry_at", "orb_exit_at"):
        jd = _jd_for_datetime(datetime.fromisoformat(event[key]))
        deviation = _deviation(_longitude(jd, event["transit_body"]), target, {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "quincunx": 150, "opposition": 180}[event["aspect"]])
        assert abs(deviation - 1.0) <= ORB_BOUNDARY_TOLERANCE_DEGREES * 2


def test_manual_premium_workflow_has_separate_synthesis_and_narrative_gates():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    assert handoff["premium_required_for_publication"]
    assert handoff["workflow"][4].startswith("5. Sol High")
    fallback = analyse_birth_chart(birth(), include_timing=False)
    judged = validate_premium_syntheses(birth(), fallback["reasoned_synthesis"])
    assert judged["approved"]
    final = validate_premium_narrative({
        "report": "Uma hipótese simbólica, não uma certeza.",
        "paragraph_sources": [{"section": "opening", "synthesis_ids": [judged["reasoned_synthesis"][0]["id"]]}],
        "narrative_judge": {"model": "gpt-5.6-sol", "verdict": "approved", "notes": "reviewed"},
    }, judged["reasoned_synthesis"])
    assert final["approved"]
    assert final["semantic_status"] == "high_judge_attested_not_deterministically_proven"
