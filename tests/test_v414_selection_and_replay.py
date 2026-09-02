from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

import astrology.pipeline as pipeline
from tests.test_v414_narrative_blocks import birth
from tests.v413_helpers import _synthesis_for_path
from tests.v414_helpers import (
    build_author_bundle_v13_for_replay,
    build_author_bundle_v14,
    prepare_legacy_premium_handoff_for_replay,
    reviewer_bundle_v13_for_replay,
    reviewer_bundle_v14,
)


def _approved_v14():
    handoff = pipeline.prepare_premium_handoff(birth(), include_timing=False)
    author, meta = build_author_bundle_v14(birth(), include_timing=False)
    provenance = pipeline.validate_premium_author_bundle(
        birth(), author, include_timing=False, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    return handoff, author, meta, provenance


def test_v414_selection_never_fabricates_a_path_from_partial_syntheses():
    path = {
        "source_claim_ids": ["claim.one", "claim.two"],
        "primary_factor_ids": ["position.one", "position.two"],
        "reasoning_class": "integrated_pattern",
        "composition_operations": ["contrast", "integration"],
    }
    claims_only = {
        "id": "synthesis.claims_only",
        "status": "allowed",
        "source_claim_ids": ["claim.one", "claim.two"],
        "primary_factors": ["position.one", "position.two"],
        "reasoning_class": "single_structural_factor",
        "composition_operations": ["contrast", "integration"],
    }
    class_only = {
        "id": "synthesis.class_only",
        "status": "allowed",
        "source_claim_ids": ["unrelated"],
        "primary_factors": ["unrelated"],
        "reasoning_class": "integrated_pattern",
        "composition_operations": [],
    }
    matched, contributors = pipeline._selection_synthesis_set_matches_path(
        [claims_only, class_only], path,
    )
    assert not matched
    assert contributors == set()


def test_v414_selection_accepts_independent_syntheses_for_different_paths():
    path_one = {
        "source_claim_ids": ["claim.one"],
        "primary_factor_ids": ["position.one"],
        "reasoning_class": "class.one",
        "composition_operations": ["operation.one"],
    }
    path_two = {
        "source_claim_ids": ["claim.two"],
        "primary_factor_ids": ["position.two"],
        "reasoning_class": "class.two",
        "composition_operations": ["operation.two"],
    }
    first = {
        "id": "synthesis.one", "status": "allowed",
        "source_claim_ids": ["claim.one"], "primary_factors": ["position.one"],
        "reasoning_class": "class.one", "composition_operations": ["operation.one"],
    }
    second = {
        "id": "synthesis.two", "status": "allowed",
        "source_claim_ids": ["claim.two"], "primary_factors": ["position.two"],
        "reasoning_class": "class.two", "composition_operations": ["operation.two"],
    }
    assert pipeline._selection_synthesis_set_matches_path([first, second], path_one)[0]
    assert pipeline._selection_synthesis_set_matches_path([first, second], path_two)[0]


def test_v414_selection_allows_two_independent_legal_syntheses_in_one_merge_cluster():
    handoff, author, meta, _provenance = _approved_v14()
    core = pipeline.analyse_birth_chart(birth(), include_timing=False)
    domain = next(item for item in core["reader_domain_manifest"]["domains"] if item["id"] == "identity_presence")
    first_path, second_path = domain["legal_coverage_paths"][:2]
    claims = {item["id"]: item for item in core["claims"] if item["status"] == "allowed"}
    second = asdict(_synthesis_for_path(second_path, claims, domain["id"]))
    second["id"] = "reasoned.reader.identity_presence.second"

    altered = deepcopy(author)
    altered["reasoned_syntheses"].append(second)
    new_text = (
        "A second authorised identity mechanism is developed separately, so the reader can meet "
        "its distinct way of beginning without forcing it into one artificial synthesis."
    )
    next_heading = core["reader_domain_manifest"]["domains"][1]["heading"]
    altered["draft_report"] = altered["draft_report"].replace(
        f"## {next_heading}", f"{new_text}\n\n## {next_heading}", 1,
    )
    altered["draft_report_sha256"] = pipeline._canonical_hash(altered["draft_report"])
    parsed = pipeline._parse_premium_narrative(altered["draft_report"], meta["manifest"])
    new_hash = next(
        item["narrative_block_sha256"]
        for item in parsed["sections"]["identity_presence"]["prose"]
        if item["content"] == new_text
    )
    identity_section = next(
        item for item in altered["reader_sections"]["domains"] if item["domain_id"] == "identity_presence"
    )
    identity_section["narrative_block_sha256s"].append(new_hash)
    source_row = {
        "narrative_block_sha256": new_hash,
        "synthesis_ids": [second["id"]],
        "claim_ids": [],
        "timing_ids": [],
    }
    last_identity_hash = identity_section["narrative_block_sha256s"][-2]
    source_index = next(
        index for index, row in enumerate(altered["narrative_block_sources"])
        if row["narrative_block_sha256"] == last_identity_hash
    )
    altered["narrative_block_sources"].insert(source_index + 1, source_row)

    plan_domain = next(
        item for item in altered["reader_selection_plan"]["domains"]
        if item["domain_id"] == "identity_presence"
    )
    represented, merged = plan_domain["paths"][:2]
    represented.update({
        "decision": "represented",
        "synthesis_ids": [represented["synthesis_ids"][0], second["id"]],
        "merged_with_path_id": None,
        "rationale": None,
    })
    merged.update({
        "decision": "merged_with_represented",
        "synthesis_ids": [],
        "merged_with_path_id": first_path["id"],
        "rationale": "The two valid syntheses form one reader-facing identity cluster.",
    })
    judged = pipeline.validate_premium_syntheses(
        birth(), altered["reasoned_syntheses"], include_timing=False,
    )
    assert judged["approved"], judged["reasoned_synthesis"]
    altered["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]
    altered["reader_selection_plan_sha256"] = pipeline._canonical_hash(altered["reader_selection_plan"])

    result = pipeline.validate_premium_author_bundle(
        birth(), altered, include_timing=False, prepared_handoff=handoff,
    )
    assert result["approved"], result["verification_errors"]


def test_v414_selection_rejects_approved_padding_even_when_domain_provenance_exists():
    handoff, author, _meta, _provenance = _approved_v14()
    altered = deepcopy(author)
    identity_plan = next(
        item for item in altered["reader_selection_plan"]["domains"] if item["domain_id"] == "identity_presence"
    )
    emotional = next(
        row for row in altered["narrative_block_sources"]
        if row["synthesis_ids"] and str(row["synthesis_ids"][0]).startswith("reasoned.reader.emotional_security")
    )
    padding_id = emotional["synthesis_ids"][0]
    identity_plan["paths"][0]["synthesis_ids"].append(padding_id)
    # Make the otherwise unrelated approved synthesis genuinely present in
    # the same domain, so the failure proves padding is checked after source
    # ownership rather than being a domain-mismatch shortcut.
    identity_row = next(
        row for row in altered["narrative_block_sources"]
        if row["synthesis_ids"] and row["synthesis_ids"][0] == identity_plan["paths"][0]["synthesis_ids"][0]
    )
    identity_row["synthesis_ids"].append(padding_id)
    altered["reader_selection_plan_sha256"] = pipeline._canonical_hash(altered["reader_selection_plan"])
    result = pipeline.validate_premium_author_bundle(
        birth(), altered, include_timing=False, prepared_handoff=handoff,
    )
    assert not result["approved"]
    assert "reader_selection_noncontributing_synthesis_padding:" + identity_plan["paths"][0]["path_id"] in result["verification_errors"]


def test_v413_replay_is_explicit_and_packet_identity_is_version_bound():
    handoff = prepare_legacy_premium_handoff_for_replay(birth(), include_timing=False)
    author, _meta = build_author_bundle_v13_for_replay(birth(), include_timing=False)
    provenance = pipeline.validate_premium_author_bundle(
        birth(), author, include_timing=False, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    reviewer = reviewer_bundle_v13_for_replay(author, provenance)
    published = pipeline.validate_premium_narrative(
        reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff,
    )
    assert published["approved"], published["verification_errors"]
    assert handoff["premium_handoff_contract_version"] == "1.3"
    current = pipeline.prepare_premium_handoff(birth(), include_timing=False)
    assert current["premium_handoff_contract_version"] == "1.4"
    v14 = pipeline.analyse_birth_chart(birth(), include_timing=False)
    v13 = pipeline.analyse_birth_chart(
        birth(), include_timing=False,
        premium_contract_version=pipeline.LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    assert v14["packet_id"] != v13["packet_id"]


def test_v413_and_v414_bundles_cannot_cross_the_author_or_publication_dispatch():
    handoff14, author14, _meta14, provenance14 = _approved_v14()
    handoff13 = prepare_legacy_premium_handoff_for_replay(birth(), include_timing=False)
    author13, _meta13 = build_author_bundle_v13_for_replay(birth(), include_timing=False)
    author_cross = pipeline.validate_premium_author_bundle(
        birth(), author13, include_timing=False, prepared_handoff=handoff14,
    )
    assert not author_cross["approved"]
    assert any("paragraph" in error or "contract" in error for error in author_cross["verification_errors"])
    provenance13 = pipeline.validate_premium_author_bundle(
        birth(), author13, include_timing=False, prepared_handoff=handoff13,
    )
    assert provenance13["approved"], provenance13["verification_errors"]
    reviewer13 = reviewer_bundle_v13_for_replay(author13, provenance13)
    publication_cross = pipeline.validate_premium_narrative(
        reviewer13, provenance13, birth(), include_timing=False, prepared_handoff=handoff14,
    )
    assert not publication_cross["approved"]
    assert any("paragraph" in error or "contract" in error for error in publication_cross["verification_errors"])
    reviewer14 = reviewer_bundle_v14(author14, provenance14)
    publication_cross2 = pipeline.validate_premium_narrative(
        reviewer14, provenance14, birth(), include_timing=False, prepared_handoff=handoff13,
    )
    assert not publication_cross2["approved"]
    assert any("narrative" in error or "contract" in error for error in publication_cross2["verification_errors"])
