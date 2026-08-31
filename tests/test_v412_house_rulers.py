from __future__ import annotations

from dataclasses import asdict, replace

from astrology.engine import calculate_chart
from astrology.hierarchy import calculate_hierarchy
from astrology.models import BirthData, Claim, ReasonedSynthesis
from astrology.pipeline import (
    _canonical_hash,
    _premium_handoff_contract,
    analyse_birth_chart,
    paragraph_source_template,
    prepare_premium_handoff,
    validate_premium_author_bundle,
    validate_premium_narrative,
    validate_premium_syntheses,
)
from astrology.reasoning import build_chart_signature, humanization_instructions, humanization_verifier_instructions, validate_reasoned_syntheses
from astrology.safe_view import build_safe_interpretive_view
from astrology.semantics import build_claims, verify_claims
from tests.v413_helpers import build_author_bundle, contract_fields, reviewer_bundle


def birth(**changes) -> BirthData:
    values = {
        "local_datetime": "1990-07-12T14:30:00",
        "timezone_name": "America/Sao_Paulo",
        "latitude": -23.5505,
        "longitude": -46.6333,
    }
    values.update(changes)
    return BirthData(**values)


def _contract_fields() -> dict[str, object]:
    return contract_fields()


def _claims_and_view(item: BirthData | None = None):
    view = build_safe_interpretive_view(calculate_chart(item or birth()))
    claims = verify_claims(build_claims(view.semantic_chart()), view.semantic_chart())
    return view, claims


def _ruler_context_claim(claims: list[Claim], ruler: str) -> Claim:
    return next(claim for claim in claims if claim.id.startswith(f"claim.position.{ruler}.") and claim.status == "allowed")


def _house_ruler_synthesis(claims: list[Claim], view, house: int = 2) -> ReasonedSynthesis:
    routing = next(claim for claim in claims if claim.id == f"claim.house_ruler.placidus.{house}")
    factor = next(item for item in view.factors if item.id == routing.evidence[0])
    ruler = str(factor.data["ruler"])
    context = _ruler_context_claim(claims, ruler)
    return ReasonedSynthesis(
        id=f"reasoned.house_ruler_context.placidus.{house}.{ruler}",
        observation=f"{routing.statement} {context.statement}",
        primary_factors=[routing.evidence[0], context.evidence[0]], modifiers=[], counterweights=[],
        reasoning_class="integrated_pattern", confidence_within_astrological_model="light",
        possible_expressions=[routing.statement], alternative_reading="", prohibited_extensions=[],
        source_claim_ids=[routing.id, context.id],
        source_motif_ids=[*routing.authorized_motifs, *context.authorized_motifs],
        composition_operations=["contextualization"],
        derived_propositions=[{"text": routing.statement, "sources": [routing.id, context.id]}],
    )


def _house_ruler_aspect_context_synthesis(claims: list[Claim], view, house: int = 2) -> tuple[ReasonedSynthesis, Claim]:
    """Use an existing same-ruler aspect Claim with its canonical counterweight."""
    routing = next(claim for claim in claims if claim.id == f"claim.house_ruler.placidus.{house}")
    factor = next(item for item in view.factors if item.id == routing.evidence[0])
    ruler = str(factor.data["ruler"])
    aspect_by_id = {item.id: item for item in view.aspects}
    context = next(
        claim for claim in claims
        if claim.status == "allowed"
        and claim.id.startswith("claim.aspect.")
        and claim.counterweights
        and ruler in {aspect_by_id[claim.evidence[0]].left, aspect_by_id[claim.evidence[0]].right}
    )
    return ReasonedSynthesis(
        id=f"reasoned.house_ruler_context.placidus.{house}.{ruler}",
        observation=f"{routing.statement} {context.statement}",
        primary_factors=[routing.evidence[0], context.evidence[0]], modifiers=[], counterweights=[context.counterweights[0]],
        reasoning_class="integrated_pattern", confidence_within_astrological_model="light",
        possible_expressions=[routing.statement], alternative_reading="", prohibited_extensions=[],
        source_claim_ids=[routing.id, context.id],
        source_motif_ids=[*routing.authorized_motifs, *context.authorized_motifs],
        composition_operations=["contextualization", "qualification"],
        derived_propositions=[{"text": routing.statement, "sources": [routing.id, context.id]}],
    ), context


def _ordinary_position_synthesis(claims: list[Claim]) -> tuple[ReasonedSynthesis, Claim]:
    """A normal, non-routing synthesis used to probe routing-factor escapes."""
    source = next(claim for claim in claims if claim.id.startswith("claim.position.sun.") and claim.status == "allowed")
    return ReasonedSynthesis(
        id="reasoned.ordinary.position",
        observation=source.statement,
        primary_factors=[source.evidence[0]], modifiers=[], counterweights=[],
        reasoning_class="single_structural_factor", confidence_within_astrological_model="light",
        possible_expressions=[source.statement], alternative_reading="", prohibited_extensions=[],
        source_claim_ids=[source.id], source_motif_ids=source.authorized_motifs,
        composition_operations=["contextualization"],
        derived_propositions=[{"text": source.statement, "sources": [source.id]}],
    ), source


def _coverage_author_with_direct_claim():
    return build_author_bundle(birth(), include_timing=False, add_direct_claim=True)


def test_v412_facts_are_traditional_placidus_routes_even_when_a_house_is_empty():
    raw = calculate_chart(birth())
    factors = [item for item in raw.factors if item.kind == "placidus_house_ruler"]
    assert len(factors) == 12
    occupied = {placement.placidus_house for placement in raw.house_placements.values() if placement.placidus_house is not None}
    empty_house = next(house for house in range(1, 13) if house not in occupied)
    factor = next(item for item in factors if item.id == f"house_ruler.placidus.{empty_house}")
    assert factor.data["house_system"] == "placidus"
    assert factor.data["rulership_system"] == "traditional_configured"
    assert factor.data["ruler_position_id"] == f"position.{factor.data['ruler']}"
    view, claims = _claims_and_view()
    assert any(claim.id == f"claim.house_ruler.placidus.{empty_house}" and claim.status == "allowed" for claim in claims)
    assert factor.id in {item.id for item in view.factors}


def test_v412_cusp_sign_reliability_is_independent_and_withholds_only_unstable_house():
    stable = calculate_chart(birth(time_uncertainty_minutes=1))
    assert stable.stability["unstable_placidus_house_ruler_houses"] == []
    unstable = calculate_chart(birth(time_uncertainty_minutes=15))
    withheld = set(unstable.stability["unstable_placidus_house_ruler_houses"])
    assert withheld and len(withheld) < 12
    view = build_safe_interpretive_view(unstable)
    safe_ids = {factor.id for factor in view.factors}
    assert all(f"house_ruler.placidus.{house}" not in safe_ids for house in withheld)
    retained = set(range(1, 13)) - withheld
    assert all(f"house_ruler.placidus.{house}" in safe_ids for house in retained)
    assert any(item.get("changed_placidus_cusp_sign_houses") is not None for item in calculate_chart(birth()).stability["sensitivity_tests"])


def test_v412_unknown_or_global_house_gate_withholds_all_house_rulers():
    unknown = build_safe_interpretive_view(calculate_chart(birth(birth_time_known=False)))
    wide_raw = calculate_chart(birth(time_uncertainty_minutes=240))
    wide = build_safe_interpretive_view(wide_raw)
    assert not any(item.kind == "placidus_house_ruler" for item in unknown.factors)
    assert not any(item.kind == "placidus_house_ruler" for item in wide.factors)


def test_v412_claim_verifier_rejects_forged_ruler_sign_link_modern_and_whole_sign_variants():
    raw = calculate_chart(birth())
    semantic = build_safe_interpretive_view(raw).semantic_chart()
    factor = next(item for item in semantic.factors if item.id == "house_ruler.placidus.2")
    forged = replace(factor, data={**factor.data, "ruler": "uranus", "ruler_position_id": "position.uranus"}, bodies=["uranus"])
    semantic.factors = [forged if item.id == forged.id else item for item in semantic.factors]
    claims = verify_claims(build_claims(semantic), semantic)
    claim = next(item for item in claims if item.id == "claim.house_ruler.placidus.2")
    assert claim.status == "blocked"
    assert "invalid_placidus_house_ruler_provenance" in claim.verification_errors
    raw_link = calculate_chart(birth())
    link_chart = build_safe_interpretive_view(raw_link).semantic_chart()
    link_factor = next(item for item in link_chart.factors if item.id == "house_ruler.placidus.2")
    forged_link = replace(link_factor, data={**link_factor.data, "ruler_position_id": "position.sun"})
    link_chart.factors = [forged_link if item.id == forged_link.id else item for item in link_chart.factors]
    link_claim = next(item for item in verify_claims(build_claims(link_chart), link_chart) if item.id == "claim.house_ruler.placidus.2")
    assert "invalid_placidus_house_ruler_provenance" in link_claim.verification_errors
    whole = Claim(
        id="claim.house_ruler.whole_sign.2", theme="security_exploration", type="placidus_house_ruler", statement="x",
        evidence=["house.whole_sign.sun"], evidence_families=["x"], counterweights=[], allowed_specificity="structural_tendency",
        allowed_examples=["x"], prohibited_inferences=[], astrological_support="light", authorized_motifs=["placidus_house_ruler_routing"], direct_paragraph_renderable=True,
    )
    assert whole.status == "allowed"
    checked = verify_claims([whole], semantic)[0]
    assert checked.status == "blocked" and "unknown_evidence" in checked.verification_errors


def test_v412_malformed_house_ruler_factor_is_blocked_without_claim_builder_crash():
    semantic = build_safe_interpretive_view(calculate_chart(birth())).semantic_chart()
    factor = next(item for item in semantic.factors if item.id == "house_ruler.placidus.2")
    malformed = replace(factor, data={**factor.data, "house": 99})
    semantic.factors = [malformed if item.id == factor.id else item for item in semantic.factors]
    claim = next(item for item in verify_claims(build_claims(semantic), semantic) if item.id == "claim.house_ruler.placidus.99")
    assert claim.status == "blocked"
    assert "invalid_placidus_house_ruler_provenance" in claim.verification_errors


def test_v412_house_ruler_context_synthesis_requires_the_matching_ruler_context():
    view, claims = _claims_and_view()
    valid = _house_ruler_synthesis(claims, view)
    assert validate_reasoned_syntheses([valid], view, claims)[0].status == "allowed"
    routing = next(claim for claim in claims if claim.id == "claim.house_ruler.placidus.2")
    wrong = next(claim for claim in claims if claim.id.startswith("claim.position.") and claim.id != valid.source_claim_ids[1])
    invalid = replace(valid, source_claim_ids=[routing.id, wrong.id], source_motif_ids=[*routing.authorized_motifs, *wrong.authorized_motifs], primary_factors=[routing.evidence[0], wrong.evidence[0]])
    assert "house_ruler_context_not_owned_by_ruler" in validate_reasoned_syntheses([invalid], view, claims)[0].verification_errors
    condition = next(item for item in view.factors if item.kind == "planetary_condition" and item.bodies == [next(item.data["ruler"] for item in view.factors if item.id == routing.evidence[0])])
    with_condition = replace(valid, modifiers=[condition.id])
    assert validate_reasoned_syntheses([with_condition], view, claims)[0].status == "allowed"
    only_condition = replace(valid, source_claim_ids=[routing.id], source_motif_ids=routing.authorized_motifs, primary_factors=[routing.evidence[0]], modifiers=[condition.id])
    assert "house_ruler_context_requires_authorized_ruler_claim" in validate_reasoned_syntheses([only_condition], view, claims)[0].verification_errors
    wrong_aspect = next(claim for claim in claims if claim.id.startswith("claim.aspect.") and next(item for item in view.aspects if item.id == claim.evidence[0]).left != next(item.data["ruler"] for item in view.factors if item.id == routing.evidence[0]) and next(item for item in view.aspects if item.id == claim.evidence[0]).right != next(item.data["ruler"] for item in view.factors if item.id == routing.evidence[0]))
    aspect_wrong = replace(valid, source_claim_ids=[routing.id, wrong_aspect.id], source_motif_ids=[*routing.authorized_motifs, *wrong_aspect.authorized_motifs], primary_factors=[routing.evidence[0], wrong_aspect.evidence[0]])
    assert "house_ruler_context_not_owned_by_ruler" in validate_reasoned_syntheses([aspect_wrong], view, claims)[0].verification_errors
    wrong_configuration = next(claim for claim in claims if claim.id.startswith("claim.configuration.") and next(item for item in view.factors if item.id == claim.evidence[0]).bodies and next(item.data["ruler"] for item in view.factors if item.id == routing.evidence[0]) not in next(item for item in view.factors if item.id == claim.evidence[0]).bodies)
    configuration_wrong = replace(valid, source_claim_ids=[routing.id, wrong_configuration.id], source_motif_ids=[*routing.authorized_motifs, *wrong_configuration.authorized_motifs], primary_factors=[routing.evidence[0], wrong_configuration.evidence[0]])
    assert "house_ruler_context_not_owned_by_ruler" in validate_reasoned_syntheses([configuration_wrong], view, claims)[0].verification_errors
    bad_id = replace(valid, id="reasoned.money")
    assert "noncanonical_house_ruler_context_id" in validate_reasoned_syntheses([bad_id], view, claims)[0].verification_errors


def test_v412_house_ruler_context_closes_modifier_and_counterweight_ancestry():
    view, claims = _claims_and_view()
    valid, aspect_claim = _house_ruler_aspect_context_synthesis(claims, view)
    assert validate_reasoned_syntheses([valid], view, claims)[0].status == "allowed"
    routing = next(claim for claim in claims if claim.id == "claim.house_ruler.placidus.2")
    ruler = next(item.data["ruler"] for item in view.factors if item.id == routing.evidence[0])
    same_ruler_condition = next(item for item in view.factors if item.kind == "planetary_condition" and item.bodies == [ruler])
    assert validate_reasoned_syntheses([replace(valid, modifiers=[same_ruler_condition.id])], view, claims)[0].status == "allowed"
    unrelated_position = "position.venus"
    assert "house_ruler_modifier_not_authorized" in validate_reasoned_syntheses([replace(valid, modifiers=[unrelated_position])], view, claims)[0].verification_errors
    assert "house_ruler_counterweight_not_owned_by_ruler" in validate_reasoned_syntheses([replace(valid, counterweights=[unrelated_position])], view, claims)[0].verification_errors
    unrelated_aspect = next(item.id for item in view.aspects if ruler not in {item.left, item.right})
    assert "house_ruler_modifier_not_authorized" in validate_reasoned_syntheses([replace(valid, modifiers=[unrelated_aspect])], view, claims)[0].verification_errors
    unrelated_configuration = next(item.id for item in view.factors if item.kind == "configuration" and ruler not in item.bodies)
    assert "house_ruler_counterweight_not_owned_by_ruler" in validate_reasoned_syntheses([replace(valid, counterweights=[unrelated_configuration])], view, claims)[0].verification_errors
    wrong_condition = next(item.id for item in view.factors if item.kind == "planetary_condition" and item.bodies != [ruler])
    assert "house_ruler_condition_not_owned_by_ruler" in validate_reasoned_syntheses([replace(valid, modifiers=[wrong_condition])], view, claims)[0].verification_errors
    assert "unknown_or_unsafe_factor" in validate_reasoned_syntheses([replace(valid, modifiers=["condition.forged"])], view, claims)[0].verification_errors
    assert "unknown_or_unsafe_factor" in validate_reasoned_syntheses([replace(valid, counterweights=["aspect.forged"])], view, claims)[0].verification_errors
    assert aspect_claim.counterweights[0] == valid.counterweights[0]


def test_v412_raw_house_ruler_factors_require_the_canonical_context_contract():
    view, claims = _claims_and_view()
    ordinary, source = _ordinary_position_synthesis(claims)
    routing = next(claim for claim in claims if claim.id == "claim.house_ruler.placidus.1")
    route = routing.evidence[0]
    ruler = next(item.data["ruler"] for item in view.factors if item.id == route)
    canonical_id = f"reasoned.house_ruler_context.placidus.1.{ruler}"

    raw_modifier = replace(ordinary, modifiers=[route])
    modifier_errors = validate_reasoned_syntheses([raw_modifier], view, claims)[0].verification_errors
    assert "house_ruler_factor_must_be_routing_primary" in modifier_errors
    assert "house_ruler_factor_requires_matching_routing_claim" in modifier_errors

    raw_counterweight = replace(ordinary, counterweights=[route], composition_operations=["contextualization", "qualification"])
    counterweight_errors = validate_reasoned_syntheses([raw_counterweight], view, claims)[0].verification_errors
    assert "house_ruler_factor_must_be_routing_primary" in counterweight_errors
    assert "house_ruler_factor_requires_matching_routing_claim" in counterweight_errors

    raw_primary = replace(ordinary, primary_factors=[route])
    primary_errors = validate_reasoned_syntheses([raw_primary], view, claims)[0].verification_errors
    assert "house_ruler_factor_requires_matching_routing_claim" in primary_errors
    assert "primary_factor_not_authorized_by_source_claim" in primary_errors

    wrong_role = replace(
        ordinary,
        id=canonical_id,
        reasoning_class="integrated_pattern",
        source_claim_ids=[routing.id, source.id],
        source_motif_ids=[*routing.authorized_motifs, *source.authorized_motifs],
        modifiers=[route],
    )
    wrong_role_errors = validate_reasoned_syntheses([wrong_role], view, claims)[0].verification_errors
    assert "house_ruler_factor_must_be_routing_primary" in wrong_role_errors
    assert "house_ruler_factor_missing_from_primary" in wrong_role_errors

    wrong_routing = next(claim for claim in claims if claim.id == "claim.house_ruler.placidus.2")
    wrong_claim = replace(
        ordinary,
        id=canonical_id,
        reasoning_class="integrated_pattern",
        primary_factors=[route, source.evidence[0]],
        source_claim_ids=[wrong_routing.id, source.id],
        source_motif_ids=[*wrong_routing.authorized_motifs, *source.authorized_motifs],
    )
    assert "house_ruler_factor_requires_matching_routing_claim" in validate_reasoned_syntheses([wrong_claim], view, claims)[0].verification_errors

    missing_context = replace(
        ordinary,
        id=canonical_id,
        reasoning_class="integrated_pattern",
        primary_factors=[route],
        source_claim_ids=[routing.id], source_motif_ids=routing.authorized_motifs,
        derived_propositions=[{"text": routing.statement, "sources": [routing.id]}],
    )
    assert "house_ruler_context_requires_authorized_ruler_claim" in validate_reasoned_syntheses([missing_context], view, claims)[0].verification_errors

    canonical_looking_bad = replace(missing_context, id=canonical_id, source_claim_ids=[routing.id, source.id])
    canonical_looking_bad.source_motif_ids = [*routing.authorized_motifs, *source.authorized_motifs]
    assert "house_ruler_context_factor_missing_from_primary" in validate_reasoned_syntheses([canonical_looking_bad], view, claims)[0].verification_errors

    ordinary_modifier = replace(ordinary, modifiers=["position.venus"])
    assert validate_reasoned_syntheses([ordinary_modifier], view, claims)[0].status == "allowed"
    assert validate_reasoned_syntheses([_house_ruler_synthesis(claims, view, 1)], view, claims)[0].status == "allowed"


def test_v412_raw_house_ruler_factors_are_structurally_non_scoring_defense_in_depth():
    view, claims = _claims_and_view()
    hierarchy = calculate_hierarchy(view.semantic_chart())
    baseline = build_chart_signature(view, hierarchy, {"configurations": []}, [])
    route = next(item.id for item in view.factors if item.id == "house_ruler.placidus.1")
    ordinary, _source = _ordinary_position_synthesis(claims)
    invalid_counterweight = replace(ordinary, counterweights=[route], composition_operations=["contextualization", "qualification"])
    assert validate_reasoned_syntheses([invalid_counterweight], view, claims)[0].status == "blocked"

    # This intentionally bypasses validation to assert the downstream boundary
    # itself cannot turn a raw routing fact into structural weight.
    raw_only = {
        "id": "reasoned.audit.raw_route",
        "status": "allowed",
        "primary_factors": [route],
        "counterweights": [route],
        "composition_operations": ["contextualization", "qualification"],
        "source_claim_ids": [],
        "reasoning_class": "single_structural_factor",
    }
    defended = build_chart_signature(view, hierarchy, {"configurations": []}, [raw_only])
    assert defended["counterweights"] == baseline["counterweights"]
    assert defended["core_factors"] == baseline["core_factors"]
    assert defended["structural_scores"] == baseline["structural_scores"]
    assert defended["theme_priorities"] == baseline["theme_priorities"]
    assert defended["central_dynamic"] == baseline["central_dynamic"]


def test_v412_direct_claim_mode_is_capability_gated_and_never_compositional_coverage():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, direct = _coverage_author_with_direct_claim()
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"]
    assert direct["id"] not in {item for values in provenance["coverage"]["required_evidence"].values() for item in values}
    direct_index = next(index for index, source in enumerate(author["paragraph_sources"]) if source["claim_ids"] == [direct["id"]])
    def changed_direct(**changes):
        rows = [dict(item) for item in author["paragraph_sources"]]
        rows[direct_index].update(changes)
        return dict(author, paragraph_sources=rows)
    bad_multiple = changed_direct(claim_ids=[direct["id"], direct["id"]])
    assert "invalid_direct_claim_paragraph_source" in validate_premium_author_bundle(birth(), bad_multiple, include_timing=False)["verification_errors"]
    bad_timing = changed_direct(timing_ids=["timing.invented"])
    errors = validate_premium_author_bundle(birth(), bad_timing, include_timing=False)["verification_errors"]
    assert "invalid_direct_claim_paragraph_source" in errors and "invented_or_unapproved_timing_evidence" in errors
    old_rows = [dict(item) for item in author["paragraph_sources"]]
    old_rows[direct_index].pop("claim_ids")
    old_row = dict(author, paragraph_sources=old_rows)
    assert "premium_handoff_source_row_missing_field" in validate_premium_author_bundle(birth(), old_row, include_timing=False)["verification_errors"]
    nonrenderable = next(claim for claim in analyse_birth_chart(birth(), include_timing=False)["claims"] if claim["id"].startswith("claim.position.") and claim["status"] == "allowed")
    bad_capability = changed_direct(claim_ids=[nonrenderable["id"]])
    assert "invalid_direct_claim_paragraph_source" in validate_premium_author_bundle(birth(), bad_capability, include_timing=False)["verification_errors"]
    bad_mixed = changed_direct(synthesis_ids=[author["reasoned_syntheses"][0]["id"]])
    assert "untraceable_paragraph_source" in validate_premium_author_bundle(birth(), bad_mixed, include_timing=False)["verification_errors"]
    semantic = build_safe_interpretive_view(calculate_chart(birth())).semantic_chart()
    forged_capability = next(claim for claim in build_claims(semantic) if claim.id.startswith("claim.position."))
    forged_capability.direct_paragraph_renderable = True
    assert "direct_paragraph_capability_not_authorized" in verify_claims([forged_capability], semantic)[0].verification_errors


def test_v412_handoff_contract_is_hashed_and_required_by_both_guards():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = _coverage_author_with_direct_claim()
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"]
    v10 = dict(author)
    v10.pop("premium_handoff_contract_version")
    assert "premium_handoff_contract_version_mismatch" in validate_premium_author_bundle(birth(), v10, include_timing=False)["verification_errors"]
    bad_hash = dict(author, premium_handoff_contract_sha256="bad")
    assert "premium_handoff_contract_hash_mismatch" in validate_premium_author_bundle(birth(), bad_hash, include_timing=False)["verification_errors"]
    reviewer = reviewer_bundle(author, provenance)
    assert validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff)["approved"]
    reviewer["premium_handoff_contract_version"] = "1.0"
    assert "premium_handoff_contract_version_mismatch" in validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff)["verification_errors"]
    reviewer = {key: value for key, value in reviewer.items() if key != "premium_handoff_contract_version"}
    assert "premium_handoff_contract_version_mismatch" in validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff)["verification_errors"]


def test_v412_handoff_contract_body_and_descriptive_contract_are_enforced_together():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = _coverage_author_with_direct_claim()
    assert validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)["approved"]
    altered_body = {**_premium_handoff_contract(), "version": "tampered"}
    altered = dict(author, premium_handoff_contract=altered_body)
    errors = validate_premium_author_bundle(birth(), altered, include_timing=False)["verification_errors"]
    assert "premium_handoff_contract_body_mismatch" in errors
    assert "premium_handoff_contract_body_hash_mismatch" in errors
    bad_version = dict(author, premium_handoff_contract_version="1.0")
    assert "premium_handoff_contract_version_mismatch" in validate_premium_author_bundle(birth(), bad_version, include_timing=False)["verification_errors"]
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    reviewer = reviewer_bundle(author, provenance)
    assert validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff)["approved"]
    reviewer_altered = dict(reviewer, premium_handoff_contract=altered_body)
    reviewer_errors = validate_premium_narrative(reviewer_altered, provenance, birth(), include_timing=False, prepared_handoff=handoff)["verification_errors"]
    assert "premium_handoff_contract_body_mismatch" in reviewer_errors
    assert "premium_handoff_contract_body_hash_mismatch" in reviewer_errors
    missing_corrections = {key: value for key, value in reviewer.items() if key != "corrections_made"}
    assert "premium_handoff_reviewer_bundle_missing_required_field:corrections_made" in validate_premium_narrative(missing_corrections, provenance, birth(), include_timing=False, prepared_handoff=handoff)["verification_errors"]
    contract = handoff["premium_handoff_contract"]
    assert set(handoff["author_bundle_contract"]) == set(contract["author_bundle_required_fields"])
    assert set(handoff["reviewer_bundle_contract"]) == set(contract["reviewer_bundle_required_fields"])


def test_v412_routing_facts_do_not_inflate_hierarchy_or_chart_ruler_overlap():
    raw = calculate_chart(birth())
    semantic = build_safe_interpretive_view(raw).semantic_chart()
    baseline = calculate_hierarchy(semantic)
    semantic.factors = [item for item in semantic.factors if item.kind != "placidus_house_ruler"]
    without_routes = calculate_hierarchy(semantic)
    assert baseline == without_routes
    first = next(item for item in raw.factors if item.id == "house_ruler.placidus.1")
    chart_ruler = next(item for item in raw.factors if item.id == "chart_ruler.natal")
    assert first.data["ruler"] == chart_ruler.data["ruler"]
    tenth = next(item for item in raw.factors if item.id == "house_ruler.placidus.10")
    assert tenth.data["ruler"] in raw.positions
    routed_chart = build_safe_interpretive_view(raw).semantic_chart()
    claims = verify_claims(build_claims(routed_chart), routed_chart)
    factor_by_id = {item.id: item for item in routed_chart.factors}
    saturn_routes = [claim for claim in claims if claim.type == "placidus_house_ruler" and factor_by_id[claim.evidence[0]].data["ruler"] == "saturn"]
    assert len(saturn_routes) >= 2
    assert {claim.evidence_families[0] for claim in saturn_routes} == {"placidus_house_ruler_context.saturn"}


def test_v412_house_ruler_context_syntheses_remain_provenance_usable_but_non_scoring():
    view, claims = _claims_and_view()
    hierarchy = calculate_hierarchy(view.semantic_chart())
    baseline = build_chart_signature(view, hierarchy, {"configurations": []}, [])
    factor_by_id = {item.id: item for item in view.factors}
    by_ruler = {}
    for factor in view.factors:
        if factor.kind == "placidus_house_ruler":
            by_ruler.setdefault(factor.data["ruler"], []).append(int(factor.data["house"]))
    repeated_ruler, repeated_houses = next((ruler, houses) for ruler, houses in by_ruler.items() if len(houses) >= 2)
    selected_houses = [repeated_houses[0], repeated_houses[1], 1, 10]
    syntheses = []
    for house in dict.fromkeys(selected_houses):
        synthesis = _house_ruler_synthesis(claims, view, house)
        checked = validate_reasoned_syntheses([synthesis], view, claims)[0]
        assert checked.status == "allowed"
        syntheses.append(asdict(checked))
    routed = build_chart_signature(view, hierarchy, {"configurations": []}, syntheses)
    assert routed["structural_scores"] == baseline["structural_scores"]
    assert routed["theme_priorities"] == baseline["theme_priorities"]
    assert routed["core_factors"] == baseline["core_factors"]
    assert repeated_ruler in factor_by_id[f"house_ruler.placidus.{repeated_houses[0]}"].bodies
    approved = validate_premium_syntheses(birth(), syntheses, include_timing=False)
    assert approved["approved"]
    assert {item["id"] for item in approved["reasoned_synthesis"] if item["status"] == "allowed"} == {item["id"] for item in syntheses}


def test_v412_direct_claim_author_and_reviewer_contracts_are_explicitly_atomic():
    author_instruction = humanization_instructions("en-US")
    reviewer_instruction = humanization_verifier_instructions("en-US")
    assert "direct Claim mode" in author_instruction
    assert "atomic Placidus house-ruler route" in author_instruction
    assert "direct-Claim paragraph" in reviewer_instruction
    assert "canonical Claim" in reviewer_instruction
    assert "ReasonedSynthesis" in reviewer_instruction
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    assert any(claim["type"] == "placidus_house_ruler" for claim in handoff["reasoning_packet"]["facts"]["allowed_claims"])
