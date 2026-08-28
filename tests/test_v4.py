from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace
import pytest

from astrology.engine import calculate_chart
from astrology.models import Aspect, BirthData, Claim, Factor, ReasonedSynthesis
from astrology.pipeline import _canonical_hash, analyse_birth_chart, paragraph_source_template, prepare_premium_handoff, validate_premium_author_bundle, validate_premium_narrative, validate_premium_syntheses
from astrology.reasoning import ASPECT_OPERATIONS, build_chart_signature, build_narrative_plan, validate_reasoned_syntheses
from astrology.safe_view import build_safe_interpretive_view
from astrology.semantics import _claim_from_aspect
from astrology.structure import detect_configurations
from astrology.timing import ORB_BOUNDARY_TOLERANCE_DEGREES, _cycle_occurrences, _deviation, _jd_for_datetime, _longitude, developmental_intervals


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
    assert handoff["workflow"][1].startswith("2. Premium Author")
    fallback = analyse_birth_chart(birth(), include_timing=False)
    judged = validate_premium_syntheses(birth(), fallback["reasoned_synthesis"], include_timing=False)
    assert judged["approved"]
    draft = "Uma hipótese simbólica, não uma certeza, ligada aos fatores autorizados neste mapa."
    sources = paragraph_source_template(draft)
    sources[0]["synthesis_ids"] = [judged["reasoned_synthesis"][0]["id"]]
    author = {
        "packet_id": judged["packet_id"], "reasoned_syntheses": fallback["reasoned_synthesis"], "draft_report": draft,
        "paragraph_sources": sources, "synthesis_bundle_sha256": judged["synthesis_bundle_sha256"], "draft_report_sha256": _canonical_hash(draft),
    }
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False)
    assert provenance["approved"]
    final_report = "Uma hipótese simbólica, não uma certeza, ligada aos fatores autorizados neste mapa."
    final = validate_premium_narrative({
        "packet_id": provenance["packet_id"], "synthesis_bundle_sha256": provenance["synthesis_bundle_sha256"], "reviewed_draft_sha256": provenance["draft_report_sha256"],
        "verdict": "approved", "final_report": final_report, "final_report_sha256": _canonical_hash(final_report),
        "paragraph_sources": sources, "corrections_made": [], "remaining_warnings": [],
    }, provenance)
    assert final["approved"]
    assert final["semantic_status"] == "reviewer_attested_not_deterministically_proven"


def _single_claim_synthesis(source: Claim, view) -> ReasonedSynthesis:
    aspect = next(item for item in view.aspects if item.id == source.evidence[0])
    return ReasonedSynthesis(
        id="test.single", observation=source.statement, primary_factors=[source.evidence[0]], modifiers=[f"hierarchy.{aspect.left}"], counterweights=[],
        reasoning_class="integrated_pattern", confidence_within_astrological_model=source.astrological_support,
        possible_expressions=[source.statement], alternative_reading="", prohibited_extensions=[], source_claim_ids=[source.id],
        source_motif_ids=source.authorized_motifs[:1], composition_operations=[ASPECT_OPERATIONS[aspect.kind]],
        derived_propositions=[{"text": source.statement, "sources": [source.id]}],
    )


def test_provenance_guard_closes_claim_motif_factor_operation_and_confidence_contracts():
    result = analyse_birth_chart(birth(), include_timing=False)
    view = build_safe_interpretive_view(calculate_chart(birth()))
    claims = [Claim(**item) for item in result["claims"] if item["status"] == "allowed" and item["type"] == "symbolic_tendency"]
    source, other = next((a, b) for a in claims for b in claims if a.astrological_support != "strong" and a.id != b.id and a.evidence != b.evidence and set(a.authorized_motifs).isdisjoint(b.authorized_motifs))
    valid = _single_claim_synthesis(source, view)
    assert validate_reasoned_syntheses([valid], view, claims)[0].status == "allowed"
    wrong_motif = replace(valid, source_motif_ids=other.authorized_motifs[:1])
    assert "source_motif_not_authorized_by_source_claim" in validate_reasoned_syntheses([wrong_motif], view, claims)[0].verification_errors
    wrong_factor = replace(valid, primary_factors=[other.evidence[0]])
    assert "primary_factor_not_authorized_by_source_claim" in validate_reasoned_syntheses([wrong_factor], view, claims)[0].verification_errors
    wrong_operation = replace(valid, composition_operations=["polarity" if valid.composition_operations[0] != "polarity" else "friction"])
    assert "composition_operation_not_supported_by_factor" in validate_reasoned_syntheses([wrong_operation], view, claims)[0].verification_errors
    inflated = replace(valid, confidence_within_astrological_model="strong")
    assert "confidence_exceeds_source_ceiling" in validate_reasoned_syntheses([inflated], view, claims)[0].verification_errors


def test_premium_guards_block_identity_hash_source_coverage_and_timing_mismatches():
    fallback = analyse_birth_chart(birth(), as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)
    judged = validate_premium_syntheses(birth(), fallback["reasoned_synthesis"], as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)
    draft = "Esta é uma hipótese interpretativa substancial ligada a evidência autorizada e pode ser testada em contexto."
    mapping = paragraph_source_template(draft)
    mapping[0]["synthesis_ids"] = [judged["reasoned_synthesis"][0]["id"]]
    author = {"packet_id": judged["packet_id"], "reasoned_syntheses": fallback["reasoned_synthesis"], "draft_report": draft, "paragraph_sources": mapping, "synthesis_bundle_sha256": judged["synthesis_bundle_sha256"], "draft_report_sha256": _canonical_hash(draft)}
    provenance = validate_premium_author_bundle(birth(), author, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)
    assert provenance["approved"]
    bad_packet = dict(author, packet_id="other")
    assert "packet_id_mismatch" in validate_premium_author_bundle(birth(), bad_packet, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    bad_hash = dict(author, synthesis_bundle_sha256="bad")
    assert "synthesis_bundle_hash_mismatch" in validate_premium_author_bundle(birth(), bad_hash, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    no_sources = dict(author, paragraph_sources=[])
    assert "interpretive_paragraph_without_source_map" in validate_premium_author_bundle(birth(), no_sources, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    reviewer = {"packet_id": provenance["packet_id"], "synthesis_bundle_sha256": provenance["synthesis_bundle_sha256"], "reviewed_draft_sha256": provenance["draft_report_sha256"], "verdict": "approved", "final_report": draft, "final_report_sha256": _canonical_hash(draft), "paragraph_sources": mapping}
    assert validate_premium_narrative(reviewer, provenance)["approved"]
    reviewer["paragraph_sources"] = [dict(mapping[0], timing_ids=["timing.activation.invented"])]
    assert "invented_or_unapproved_timing_evidence" in validate_premium_narrative(reviewer, provenance)["verification_errors"]


def test_signature_score_has_no_rulership_count_bias_and_nested_intervals_remain_continuous():
    chart = SimpleNamespace(aspects=[], factors=[], positions={"sun": object(), "mercury": object()}, house_placements={})
    hierarchy = {
        "sun": {"prominence": "strong", "roles": [], "governs_whole_sign_houses": [1]},
        "mercury": {"prominence": "strong", "roles": [], "governs_whole_sign_houses": [3, 6]},
    }
    signature = build_chart_signature(chart, hierarchy, {"configurations": []}, [])
    assert signature["structural_scores"]["sun"] == signature["structural_scores"]["mercury"]
    timeline = [{"activations": [
        {"body": "saturn", "window_start": "2025-01-01T00:00:00+00:00", "window_end": "2030-01-01T00:00:00+00:00"},
        {"body": "jupiter", "window_start": "2026-01-01T00:00:00+00:00", "window_end": "2027-01-01T00:00:00+00:00"},
        {"body": "uranus", "window_start": "2029-01-01T00:00:00+00:00", "window_end": "2031-01-01T00:00:00+00:00"},
    ]}]
    intervals = developmental_intervals(SimpleNamespace(utc_datetime="2000-01-01T00:00:00+00:00"), timeline)
    assert len(intervals) == 1 and intervals[0]["window_end"].startswith("2031-01-01")


def test_outer_planet_needs_a_personalizing_link_to_anchor_chart_signature():
    outer_aspects = [
        Aspect("aspect.uranus_conjunction_neptune", "uranus", "neptune", "conjunction", 0, 0, 0, None),
        Aspect("aspect.uranus_sextile_pluto", "uranus", "pluto", "sextile", 60, 60, 0, None),
        Aspect("aspect.jupiter_trine_uranus", "jupiter", "uranus", "trine", 120, 120, 0, None),
    ]
    chart = SimpleNamespace(
        aspects=outer_aspects,
        angle_contacts=[],
        factors=[],
        positions={body: object() for body in ("jupiter", "uranus", "neptune", "pluto", "sun")},
        house_placements={},
    )
    hierarchy = {
        body: {"prominence": "light", "roles": [], "governs_whole_sign_houses": []}
        for body in chart.positions
    }
    hierarchy["uranus"] = {"prominence": "strong", "roles": ["configuration_focal"], "governs_whole_sign_houses": []}
    syntheses = [
        {"id": f"reasoned.outer_{index}", "status": "allowed", "primary_factors": [aspect.id], "counterweights": [], "composition_operations": []}
        for index, aspect in enumerate(outer_aspects, 1)
    ]
    unpersonalized = build_chart_signature(chart, hierarchy, {"configurations": []}, syntheses)
    assert unpersonalized["mode"] == "distributed"

    chart.aspects.append(Aspect("aspect.sun_square_uranus", "sun", "uranus", "square", 90, 90, 0, None))
    personalized = build_chart_signature(chart, hierarchy, {"configurations": []}, syntheses)
    assert personalized["mode"] == "central"
    assert personalized["central_dynamic"]["bodies"] == ["uranus"]


def test_cycle_opposition_keeps_closest_approach_without_false_exactness():
    events = _cycle_occurrences(calculate_chart(birth()), "jupiter", "opposition", 1, 20)
    assert any(item["minimum_orb"] <= 0.01 and not item["perfected"] and item["exact_at"] is None for item in events)


def test_premium_beta_requires_a_known_birth_time_without_blocking_safe_readings():
    unknown = BirthData("1978-09-19T12:00:00", "America/Argentina/Buenos_Aires", -34.6037, -58.3816, birth_time_known=False)
    assert analyse_birth_chart(unknown, include_timing=False)["chart_signature"]["mode"] == "distributed"
    with pytest.raises(ValueError, match="Premium beta requires"):
        prepare_premium_handoff(unknown, include_timing=False)
