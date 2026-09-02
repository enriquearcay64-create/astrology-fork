from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import asdict, replace
from types import SimpleNamespace
import pytest

from astrology.engine import calculate_chart
from astrology.models import Aspect, BirthData, Claim, Factor, ReasonedSynthesis
from astrology.pipeline import _canonical_hash, _premium_handoff_contract, analyse_birth_chart, paragraph_source_template, prepare_premium_handoff as _prepare_premium_handoff, validate_premium_author_bundle as _validate_premium_author_bundle, validate_premium_narrative as _validate_premium_narrative, validate_premium_syntheses
from astrology.reasoning import ASPECT_OPERATIONS, _promoted_configurations, build_chart_signature, build_narrative_plan, humanization_instructions, humanization_verifier_instructions, validate_reasoned_syntheses
from astrology.report import technical_appendix
from astrology.safe_view import build_safe_interpretive_view
from astrology.semantics import _claim_from_aspect, build_claims, verify_claims
from astrology.structure import detect_configurations
from astrology.timing import ORB_BOUNDARY_TOLERANCE_DEGREES, _cycle_occurrences, _deviation, _jd_for_datetime, _longitude, annual_profection, developmental_intervals
from tests.v413_helpers import build_author_bundle, contract_fields, prepare_legacy_premium_handoff_for_replay, reviewer_bundle


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def _contract_fields():
    return contract_fields()


# V4/V4.1 regressions retain the frozen Premium 1.3 fixture behavior.  The
# production preparation default is 1.4; these local adapters keep the old
# suite explicit without weakening the production dispatcher.
def prepare_premium_handoff(birth_data, profile=None, report_depth="deep", **kwargs):
    if report_depth != "deep":
        return _prepare_premium_handoff(birth_data, profile, report_depth=report_depth, **kwargs)
    kwargs.setdefault("include_timing", True)
    return prepare_legacy_premium_handoff_for_replay(birth_data, profile=profile, **kwargs)


def validate_premium_author_bundle(*args, **kwargs):
    if kwargs.get("prepared_handoff") is None:
        birth_data = args[0] if args else kwargs["birth"]
        profile = args[2] if len(args) > 2 else kwargs.get("profile")
        kwargs["prepared_handoff"] = prepare_legacy_premium_handoff_for_replay(
            birth_data, profile=profile, include_timing=kwargs.get("include_timing", True),
            as_of=kwargs.get("as_of"), horizon_days=kwargs.get("horizon_days", 366),
        )
    return _validate_premium_author_bundle(*args, **kwargs)


def validate_premium_narrative(*args, **kwargs):
    if kwargs.get("prepared_handoff") is None:
        birth_data = args[2] if len(args) > 2 else kwargs["birth"]
        profile = args[3] if len(args) > 3 else kwargs.get("profile")
        kwargs["prepared_handoff"] = prepare_legacy_premium_handoff_for_replay(
            birth_data, profile=profile, include_timing=kwargs.get("include_timing", True),
            as_of=kwargs.get("as_of"), horizon_days=kwargs.get("horizon_days", 366),
        )
    return _validate_premium_narrative(*args, **kwargs)


def _coverage_bundle(result):
    """Minimal synthetic AuthorBundle material for deterministic guard tests.

    This is provenance-only fixture text, not a generated premium report.
    """
    required = result["reasoning_packet"]["facts"]["coverage"]["required_evidence"]
    by_evidence = {
        evidence: claim
        for claim in result["claims"]
        if claim["status"] == "allowed"
        for evidence in claim["evidence"]
    }
    fallback_claim = next(claim for claim in result["claims"] if claim["status"] == "allowed" and claim["id"].startswith("claim.position."))
    syntheses = []
    for ordinal, evidence in enumerate(sorted({item for values in required.values() for item in values}), 1):
        claim = by_evidence.get(evidence, fallback_claim)
        timed = evidence.startswith("timing.")
        synthesis = ReasonedSynthesis(
            id=f"coverage.{ordinal}", observation=claim["statement"], primary_factors=[claim["evidence"][0], evidence] if timed else [evidence], modifiers=[], counterweights=[],
            reasoning_class="natal_timing_interaction" if timed else "single_structural_factor", confidence_within_astrological_model=claim["astrological_support"],
            possible_expressions=[claim["statement"]], alternative_reading="", prohibited_extensions=[],
            source_claim_ids=[claim["id"]], source_motif_ids=claim["authorized_motifs"], composition_operations=["contextualization", "timing_activation"] if timed else ["contextualization"],
            derived_propositions=[{"text": claim["statement"], "sources": [claim["id"]]}],
        )
        syntheses.append(asdict(synthesis))
    paragraphs = [f"Esta cobertura número {ordinal} usa somente a síntese autorizada correspondente e permanece uma hipótese simbólica, não uma certeza biográfica." for ordinal in range(1, len(syntheses) + 1)]
    draft = "\n\n".join(paragraphs)
    sources = paragraph_source_template(draft)
    for source, synthesis in zip(sources, syntheses):
        source["synthesis_ids"] = [synthesis["id"]]
        source["timing_ids"] = [item for item in synthesis["primary_factors"] if item.startswith("timing.")]
    return syntheses, draft, sources


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


def test_v41_placidus_gate_does_not_inherit_whole_sign_instability():
    raw = calculate_chart(birth())
    raw.stability.update({
        "allow_house_claims": True,
        "unstable_house_bodies": [],
        "unstable_placidus_house_bodies": [],
        "unstable_whole_sign_house_bodies": ["sun"],
        "whole_sign_topology_status": "conditional",
    })
    view = build_safe_interpretive_view(raw).semantic_chart()
    claims = verify_claims(build_claims(view), view)
    assert "house.placidus.sun" in {factor.id for factor in view.factors}
    assert any(claim.id.startswith("claim.house.sun") and claim.status == "allowed" for claim in claims)


def test_v41_nodal_axis_is_one_deterministic_factor_with_derived_south_node():
    raw = calculate_chart(birth())
    factor = next(item for item in raw.factors if item.id == "node_axis.natal")
    assert factor.data["south"]["longitude"] == pytest.approx((factor.data["north"]["longitude"] + 180) % 360)
    assert "south_node" not in raw.positions
    assert len(factor.data["contact_ids"]) == len(set(factor.data["contact_ids"]))
    view = build_safe_interpretive_view(raw).semantic_chart()
    claims = verify_claims(build_claims(view), view)
    node_claim = next(item for item in claims if item.id.startswith("claim.node_axis"))
    assert node_claim.evidence[0] == "node_axis.natal"
    assert set(node_claim.evidence[1:]) == set(factor.data["contact_ids"])
    assert node_claim.evidence_families == ["natal_node_axis"]


def test_v41_configuration_factor_has_stable_id_and_guard_rechecks_record():
    raw = calculate_chart(birth())
    view = build_safe_interpretive_view(raw)
    configuration = next(item for item in view.factors if item.kind == "configuration")
    assert configuration.id == configuration.data["id"]
    stellia = [item.data for item in view.factors if item.kind == "configuration" and str(item.data["kind"]).startswith("stellium_")]
    same_members = [item for item in stellia if item["bodies"] == stellia[0]["bodies"]]
    assert len({item["group_id"] for item in same_members}) == 1
    claims = verify_claims(build_claims(view.semantic_chart()), view.semantic_chart())
    claim = next(item for item in claims if item.evidence == [configuration.id])
    synthesis = ReasonedSynthesis(
        id="configuration.proof", observation=claim.statement, primary_factors=[configuration.id], modifiers=[], counterweights=[],
        reasoning_class="single_structural_factor", confidence_within_astrological_model=claim.astrological_support,
        possible_expressions=[claim.statement], alternative_reading="", prohibited_extensions=[], source_claim_ids=[claim.id],
        source_motif_ids=claim.authorized_motifs, composition_operations=["contextualization"],
        derived_propositions=[{"text": claim.statement, "sources": [claim.id]}],
    )
    assert validate_reasoned_syntheses([synthesis], view, claims)[0].status == "allowed"
    configuration.data["bodies"] = list(reversed(configuration.data["bodies"]))
    assert "invalid_configuration_provenance" in validate_reasoned_syntheses([synthesis], view, claims)[0].verification_errors


def test_v41_safe_view_withholds_configuration_when_a_required_aspect_is_unstable():
    raw = calculate_chart(birth())
    aspect_configuration = next(item for item in raw.factors if item.kind == "configuration" and not str(item.data["kind"]).startswith("stellium_"))
    raw.stability["unstable_aspect_ids"] = [aspect_configuration.data["evidence"][0]]
    view = build_safe_interpretive_view(raw)
    assert aspect_configuration.id not in {factor.id for factor in view.factors}
    assert any(factor.kind == "configuration" and str(factor.data["kind"]).startswith("stellium_") for factor in view.factors)


def test_v41_whole_sign_is_not_general_premium_evidence_but_profection_remains_available():
    raw = calculate_chart(birth())
    view = build_safe_interpretive_view(raw)
    assert not any(factor.kind == "whole_sign_house" for factor in view.factors)
    assert all("governs_whole_sign_houses" not in item for item in analyse_birth_chart(birth(), include_timing=False)["reasoning_packet"]["facts"]["structural_bodies"])
    claim = next(item for item in build_claims(view.semantic_chart()) if item.id.startswith("claim.position."))
    synthesis = ReasonedSynthesis(
        id="whole-sign-forbidden", observation=claim.statement, primary_factors=["house.whole_sign.sun"], modifiers=[], counterweights=[],
        reasoning_class="single_structural_factor", confidence_within_astrological_model="light", possible_expressions=[claim.statement],
        alternative_reading="", prohibited_extensions=[], source_claim_ids=[claim.id], source_motif_ids=claim.authorized_motifs,
        composition_operations=["contextualization"], derived_propositions=[{"text": claim.statement, "sources": [claim.id]}],
    )
    assert "unknown_or_unsafe_factor" in validate_reasoned_syntheses([synthesis], view, build_claims(view.semantic_chart()))[0].verification_errors
    assert annual_profection(raw)["time_lord"]


def test_v41_configuration_promotion_is_selective_and_deduplicates_a_structural_family():
    configurations = [
        {"id": "configuration.stellium_sign.none.moon.mars.sun", "kind": "stellium_sign", "bodies": ["sun", "moon", "mars"], "group_id": "configuration_group.stellium.mars.moon.sun"},
        {"id": "configuration.stellium_placidus_house.1.moon.mars.sun", "kind": "stellium_placidus_house", "bodies": ["sun", "moon", "mars"], "group_id": "configuration_group.stellium.mars.moon.sun"},
        {"id": "configuration.grand_trine.none.neptune.uranus.pluto", "kind": "grand_trine", "bodies": ["uranus", "neptune", "pluto"]},
    ]
    hierarchy = {
        "sun": {"prominence": "strong"}, "moon": {"prominence": "moderate"}, "mars": {"prominence": "light"},
        "uranus": {"prominence": "none"}, "neptune": {"prominence": "none"}, "pluto": {"prominence": "none"},
    }
    promoted = _promoted_configurations(configurations, hierarchy)
    assert [item["id"] for item in promoted] == ["configuration.stellium_placidus_house.1.moon.mars.sun"]
    result = analyse_birth_chart(birth(), include_timing=False)
    facts = result["reasoning_packet"]["facts"]
    mandatory = set(facts["coverage"]["promoted_configuration_ids"])
    assert mandatory.issubset(set(facts["coverage"]["detected_configuration_ids"]))
    assert set(facts["coverage"]["detected_configuration_ids"]) - mandatory


def test_v41_node_axis_contacts_have_one_authorised_semantic_ancestry_and_do_not_anchor():
    raw = calculate_chart(birth())
    view = build_safe_interpretive_view(raw)
    claims = verify_claims(build_claims(view.semantic_chart()), view.semantic_chart())
    claim = next(item for item in claims if item.id.startswith("claim.node_axis"))
    contact = next(item for item in view.aspects if item.id in claim.evidence[1:])
    synthesis = ReasonedSynthesis(
        id="node-contact", observation=claim.statement, primary_factors=["node_axis.natal", contact.id], modifiers=[], counterweights=[],
        reasoning_class="integrated_pattern", confidence_within_astrological_model="light", possible_expressions=[claim.statement],
        alternative_reading="", prohibited_extensions=[], source_claim_ids=[claim.id], source_motif_ids=claim.authorized_motifs,
        composition_operations=["contextualization", ASPECT_OPERATIONS[contact.kind]], derived_propositions=[{"text": claim.statement, "sources": [claim.id]}],
    )
    assert validate_reasoned_syntheses([synthesis], view, claims)[0].status == "allowed"
    hierarchy = analyse_birth_chart(birth(), include_timing=False)["hierarchy"]
    signature = build_chart_signature(view, hierarchy, {"configurations": []}, [{"id": "node-contact", "status": "allowed", "primary_factors": ["node_axis.natal", contact.id], "counterweights": [], "composition_operations": [ASPECT_OPERATIONS[contact.kind]]}])
    assert "true_node" not in signature["central_dynamic"]["bodies"]


def test_v41_source_map_requires_the_exact_substantive_paragraph_universe():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    syntheses, draft, mapping = author["reasoned_syntheses"], author["draft_report"], author["paragraph_sources"]
    assert validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)["approved"]
    orphan = dict(author, paragraph_sources=[*mapping, {"paragraph_sha256": "not-a-real-paragraph", "synthesis_ids": [syntheses[0]["id"]], "claim_ids": [], "timing_ids": []}])
    assert "orphan_paragraph_source_map" in validate_premium_author_bundle(birth(), orphan, include_timing=False)["verification_errors"]
    duplicate = dict(author, paragraph_sources=[*mapping, dict(mapping[0])])
    assert "duplicate_paragraph_source_map" in validate_premium_author_bundle(birth(), duplicate, include_timing=False)["verification_errors"]
    conflicting = dict(author, paragraph_sources=[*mapping, dict(mapping[0], synthesis_ids=[syntheses[-1]["id"]])])
    assert "conflicting_duplicate_paragraph_source_map" in validate_premium_author_bundle(birth(), conflicting, include_timing=False)["verification_errors"]
    missing = dict(author, paragraph_sources=mapping[1:])
    assert "interpretive_paragraph_without_source_map" in validate_premium_author_bundle(birth(), missing, include_timing=False)["verification_errors"]
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    shortened = draft.split("\n\n", 1)[0]
    reviewer = reviewer_bundle(author, provenance)
    reviewer.update(final_report=shortened, final_report_sha256=_canonical_hash(shortened))
    assert "orphan_paragraph_source_map" in validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff)["verification_errors"]


def test_v41_reused_configuration_family_does_not_inflate_theme_priority():
    group = "configuration_group.stellium.mars.moon.sun"
    sign = Factor("configuration.stellium_sign.aries.mars.moon.sun", "structure", "configuration", ["sun", "moon", "mars"], {"group_id": group})
    house = Factor("configuration.stellium_placidus_house.1.mars.moon.sun", "structure", "configuration", ["sun", "moon", "mars"], {"group_id": group})
    chart = SimpleNamespace(aspects=[], angle_contacts=[], factors=[sign, house], positions={body: object() for body in ("sun", "moon", "mars")}, house_placements={})
    hierarchy = {body: {"prominence": "strong", "roles": []} for body in chart.positions}
    syntheses = [
        {"id": "reasoned.first", "status": "allowed", "primary_factors": [sign.id], "counterweights": [], "composition_operations": []},
        {"id": "reasoned.second", "status": "allowed", "primary_factors": [house.id], "counterweights": [], "composition_operations": []},
    ]
    signature = build_chart_signature(chart, hierarchy, {"configurations": []}, syntheses)
    priorities = {item["theme"]: item["score"] for item in signature["theme_priorities"]}
    assert priorities["first"] > priorities["second"]


def test_v41_premium_deep_handoff_exposes_coverage_voice_and_existing_cycles():
    handoff = prepare_premium_handoff(birth(), include_timing=True)
    facts = handoff["reasoning_packet"]["facts"]
    assert set(facts["coverage"]["required_primary_planets"]) == {"sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"}
    assert facts["coverage"]["natal_node_axis_required"]
    assert handoff["timeline"] is not None and handoff["developmental_intervals"] is not None
    assert "predominantemente" in handoff["author_voice_instruction"]
    assert "The Pattern" not in handoff["author_voice_instruction"]


def test_v41_premium_prepare_rejects_non_deep_depth():
    with pytest.raises(ValueError, match="requires report_depth='deep'"):
        prepare_premium_handoff(birth(), report_depth="executive", include_timing=False)


def test_v41_timing_and_developmental_evidence_is_typed_and_validated_at_deep_depth():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    evidence = handoff["reasoning_packet"]["facts"]["timing_evidence"]
    ids = {item["id"] for item in evidence}
    assert any(item["kind"] == "annual_profection" for item in evidence)
    developmental_id = next(item["id"] for item in evidence if item["kind"] == "developmental_interval")
    assert {"id": developmental_id, "kind": "developmental_interval"} in handoff["reasoning_packet"]["facts"]["reader_timing_candidates"]
    assert "developmental_material" not in handoff["reasoning_packet"]["facts"]["coverage"]["required_evidence"]
    source = next(item for item in handoff["reasoning_packet"]["facts"]["allowed_claims"] if item["id"].startswith("claim.position."))
    synthesis = asdict(ReasonedSynthesis(
        id="developmental-proof", observation=source["statement"], primary_factors=[source["evidence"][0], developmental_id], modifiers=[], counterweights=[],
        reasoning_class="natal_timing_interaction", confidence_within_astrological_model="light", possible_expressions=[source["statement"]],
        alternative_reading="", prohibited_extensions=[], source_claim_ids=[source["id"]], source_motif_ids=source["authorized_motifs"],
        composition_operations=["contextualization", "timing_activation"], derived_propositions=[{"text": source["statement"], "sources": [source["id"]]}],
    ))
    checked = validate_premium_syntheses(birth(), [synthesis], as_of=as_of, horizon_days=45)
    assert checked["reasoned_synthesis"][0]["status"] == "allowed"
    assert set(checked["timing_evidence_ids"]) == ids
    synthesis["primary_factors"][-1] = "timing.developmental.fabricated"
    assert "unknown_or_unsafe_factor" in validate_premium_syntheses(birth(), [synthesis], as_of=as_of, horizon_days=45)["reasoned_synthesis"][0]["verification_errors"]


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
    author, _direct = build_author_bundle(birth(), include_timing=False)
    coverage_syntheses, draft, sources = author["reasoned_syntheses"], author["draft_report"], author["paragraph_sources"]
    judged = validate_premium_syntheses(birth(), coverage_syntheses, include_timing=False)
    assert judged["approved"]
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"]
    final_report = draft
    final = validate_premium_narrative(reviewer_bundle(author, provenance), provenance, birth(), include_timing=False, prepared_handoff=handoff)
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
    claims = [Claim(**item) for item in result["claims"] if item["status"] == "allowed" and item["id"].startswith("claim.aspect.")]
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
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    draft, mapping = author["draft_report"], author["paragraph_sources"]
    provenance = validate_premium_author_bundle(birth(), author, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45, prepared_handoff=handoff)
    assert provenance["approved"]
    bad_packet = dict(author, packet_id="other")
    assert "packet_id_mismatch" in validate_premium_author_bundle(birth(), bad_packet, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    bad_hash = dict(author, synthesis_bundle_sha256="bad")
    assert "synthesis_bundle_hash_mismatch" in validate_premium_author_bundle(birth(), bad_hash, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    no_sources = dict(author, paragraph_sources=[])
    assert "interpretive_paragraph_without_source_map" in validate_premium_author_bundle(birth(), no_sources, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)["verification_errors"]
    reviewer = reviewer_bundle(author, provenance)
    assert validate_premium_narrative(reviewer, provenance, birth(), as_of=as_of, horizon_days=45, prepared_handoff=handoff)["approved"]
    reviewer["paragraph_sources"] = [dict(mapping[0], timing_ids=["timing.activation.invented"])]
    assert "invented_or_unapproved_timing_evidence" in validate_premium_narrative(reviewer, provenance, birth(), as_of=as_of, horizon_days=45, prepared_handoff=handoff)["verification_errors"]


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


def test_v411_author_and_reviewer_instructions_require_depth_without_a_fixed_template():
    author = humanization_instructions("pt-BR")
    reviewer = humanization_verifier_instructions("pt-BR")

    assert "não force essa ordem" in author
    assert "sem transformar isso numa fórmula repetitiva" in author
    assert "campo humano ativado" in author
    assert "tecnicamente correto mas abstrato" in reviewer
    assert "fácil de trocar por outro mapa" in reviewer
    assert "corte-o em vez de preencher espaço" in reviewer


def test_v411_narrative_plan_allows_translated_aspect_names():
    result = analyse_birth_chart(birth(), include_timing=False)
    details = result["narrative_plan"]["technical_details_to_hide"]

    assert "aspect names" not in details
    assert any("immediately translated" in item for item in details)


def test_v411_timing_records_remain_auditable_without_becoming_mandatory_coverage():
    result = analyse_birth_chart(
        birth(), report_depth="deep", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45,
    )
    facts = result["reasoning_packet"]["facts"]
    timing = facts["timing_evidence"]

    assert timing
    assert facts["reader_timing_candidates"] == [
        {"id": item["id"], "kind": item["kind"]} for item in timing
    ]
    required = facts["coverage"]["required_evidence"]
    assert not {key for key in required if key.startswith(("current_phase", "developmental_material"))}
    assert all(key.startswith(("planet.", "ascendant", "chart_ruler", "natal_node_axis", "configuration.")) for key in required)


def test_v411_client_appendix_is_curated_and_prepare_keeps_full_audit_sidecar():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    result = analyse_birth_chart(birth(), report_depth="deep", as_of=as_of, horizon_days=45)
    chart = build_safe_interpretive_view(calculate_chart(birth()))
    client = technical_appendix(
        chart, result["hierarchy"], result["claims"], result["timing"], result["chart_structure"], None,
    )

    assert "## Condições" in client
    assert "## Eixo nodal" in client
    assert "## Aspectos" in client
    assert "## Estrutura e configurações" in client
    assert "- Registro semântico: 2.6.0" in client
    assert "- Metodologia de timing: 4.0.1" in client
    assert "- Template do relatório: 4.1.4-whole-person" in client
    assert "Profecção anual (técnica de Signo Inteiro)" in client
    positions = client.split("## Posições", 1)[1].split("## Ângulos", 1)[0]
    assert "Signo Inteiro" not in positions
    for internal_marker in ("Política versionada completa", "## Claims", "## Reasoned synthesis", "## Chart signature", "## Narrative plan", "evidence_family"):
        assert internal_marker not in client

    handoff = prepare_premium_handoff(birth(), as_of=as_of, horizon_days=45)
    assert handoff["technical_appendix"] == client
    assert "Política versionada completa" in handoff["audit_sidecar"]
    assert "## Chart signature" in handoff["audit_sidecar"]


def test_v413_versioning_updates_reader_contract_only():
    policy = calculate_chart(birth()).policy

    assert policy["methodology_version"] == "4.1.3"
    assert policy["report_template_version"] == "4.1.4-whole-person"
    assert policy["semantic_registry_version"] == "2.6.0"
    assert policy["timing_version"] == "4.0.1"
    assert policy["schema_version"] == "4.1.1"
