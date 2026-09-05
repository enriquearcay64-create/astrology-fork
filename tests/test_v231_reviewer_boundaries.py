"""Adversarial test suite for Reviewer Authority Boundaries (V2.3.1 Invariant 4).

Verifies that the Publication Guard rigorously enforces:
1. Cross-domain synthesis injection rejection (Reviewer inserts a valid synthesis from another domain).
2. Unmaterialized planned source rejection (Reviewer uses a planned synthesis never materialized by Author).
3. Attribution expansion rejection (Reviewer adds new attribution keeping old source row).
4. Positive control: Reviewer polishes and deepens prose without expanding authority (Approved).
"""
import copy
import json
from pathlib import Path
import pytest

from astrology.models import BirthData, LocalizationProfile
from astrology.pipeline import (
    prepare_premium_handoff,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_author_bundle,
    validate_premium_author_bundle,
    build_reviewer_bundle,
    validate_premium_narrative,
    _parse_premium_narrative,
)
from scripts.run_chart3_pipeline import (
    CHART_3_BIRTH,
    PROFILE,
    BENCHMARK_DIR,
)


@pytest.fixture
def chart3_baseline():
    """Load baseline artifacts and produce validated author bundle and provenance."""
    handoff = json.loads((BENCHMARK_DIR / "01-handoff.json").read_text(encoding="utf-8"))
    author_selection_plan = json.loads((BENCHMARK_DIR / "01-author-selection-plan.json").read_text(encoding="utf-8"))
    author_draft = (BENCHMARK_DIR / "author_draft.md").read_text(encoding="utf-8")
    final_reviewed_report = (BENCHMARK_DIR / "final_reviewed_report.md").read_text(encoding="utf-8")
    domain_manifest = handoff["reader_domain_manifest"]

    block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=author_selection_plan)
    sources, sections, trace = bind_prospective_plan_to_prose(author_draft, block_plan, domain_manifest)

    author_bundle = build_author_bundle(
        handoff=handoff,
        draft_report=author_draft,
        narrative_block_sources=sources,
        reader_sections=sections,
        reader_selection_plan=author_selection_plan,
    )
    prov_result = validate_premium_author_bundle(
        CHART_3_BIRTH, author_bundle, profile=PROFILE, prepared_handoff=handoff,
    )
    assert prov_result.get("approved") is True

    return {
        "handoff": handoff,
        "domain_manifest": domain_manifest,
        "block_plan": block_plan,
        "author_bundle": author_bundle,
        "prov_result": prov_result,
        "final_reviewed_report": final_reviewed_report,
    }


def test_reviewer_cross_domain_synthesis_rejected(chart3_baseline):
    """Adversarial Attack 1: Reviewer inserts claim with valid synthesis from another domain."""
    b = chart3_baseline
    rev_sources, rev_sections, _ = bind_prospective_plan_to_prose(
        b["final_reviewed_report"], b["block_plan"], b["domain_manifest"]
    )
    parsed = _parse_premium_narrative(b["final_reviewed_report"], b["domain_manifest"])
    entry_by_hash = {
        str(item.get("narrative_block_sha256")): item
        for item in parsed.get("authored", [])
        if isinstance(item, dict)
    }

    # Find a block belonging to emotional_security
    emo_block_hash = next(
        h for h, item in entry_by_hash.items()
        if item.get("section") == "emotional_security"
    )
    emo_src_idx = next(
        i for i, s in enumerate(rev_sources)
        if str(s.get("narrative_block_sha256")) == emo_block_hash
    )

    # Find a work_vocation_visibility synthesis materialized by author
    work_synth_id = next(
        s_id for s in b["author_bundle"]["narrative_block_sources"]
        if entry_by_hash.get(str(s.get("narrative_block_sha256")), {}).get("section") == "work_vocation_visibility"
        for s_id in s.get("synthesis_ids", [])
    )

    tampered_rev_sources = copy.deepcopy(rev_sources)
    tampered_rev_sources[emo_src_idx]["synthesis_ids"].append(work_synth_id)

    reviewer_bundle = build_reviewer_bundle(
        author_bundle=b["author_bundle"],
        provenance_result=b["prov_result"],
        final_report=b["final_reviewed_report"],
        verdict="approved",
        corrections_made=["Injected cross-domain synthesis into emotional security block."],
        remaining_warnings=[],
        narrative_block_sources=tampered_rev_sources,
        reader_sections=rev_sections,
    )

    pub_result = validate_premium_narrative(
        reviewer_bundle,
        b["prov_result"],
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=b["handoff"],
    )

    assert pub_result.get("approved") is False
    errors = pub_result.get("verification_errors", [])
    assert any("reviewer_unauthorized_cross_domain_synthesis" in err for err in errors), f"Expected cross-domain error, got: {errors}"


def test_reviewer_unmaterialized_planned_source_rejected(chart3_baseline):
    """Adversarial Attack 2: Reviewer uses a planned source that Author never materialized."""
    b = chart3_baseline
    rev_sources, rev_sections, _ = bind_prospective_plan_to_prose(
        b["final_reviewed_report"], b["block_plan"], b["domain_manifest"]
    )

    author_mat = set(b["prov_result"].get("author_materialized_synthesis_ids", []))
    all_approved = [s["id"] for s in b["prov_result"].get("approved_reasoned_syntheses", [])]
    unmat_approved = [s_id for s_id in all_approved if s_id not in author_mat]
    assert len(unmat_approved) > 0, "Expected at least one unmaterialized approved synthesis in benchmark baseline"
    target_synth_id = unmat_approved[0]

    tampered_rev_sources = copy.deepcopy(rev_sources)
    tampered_rev_sources[0]["synthesis_ids"].append(target_synth_id)

    reviewer_bundle = build_reviewer_bundle(
        author_bundle=b["author_bundle"],
        provenance_result=b["prov_result"],
        final_report=b["final_reviewed_report"],
        verdict="approved",
        corrections_made=["Reviewer introduced unmaterialized planned synthesis."],
        remaining_warnings=[],
        narrative_block_sources=tampered_rev_sources,
        reader_sections=rev_sections,
    )

    pub_result = validate_premium_narrative(
        reviewer_bundle,
        b["prov_result"],
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=b["handoff"],
    )

    assert pub_result.get("approved") is False
    errors = pub_result.get("verification_errors", [])
    assert any("reviewer_unauthorized_synthesis_expansion" in err for err in errors), f"Expected expansion error, got: {errors}"


def test_reviewer_new_attribution_keeping_old_source_row_rejected(chart3_baseline):
    """Adversarial Attack 3: Reviewer adds new attribution while keeping old source row."""
    b = chart3_baseline
    rev_sources, rev_sections, _ = bind_prospective_plan_to_prose(
        b["final_reviewed_report"], b["block_plan"], b["domain_manifest"]
    )

    tampered_rev_sources = copy.deepcopy(rev_sources)
    tampered_rev_sources[0]["synthesis_ids"].append("reasoned.attacker_injected_attribution")

    reviewer_bundle = build_reviewer_bundle(
        author_bundle=b["author_bundle"],
        provenance_result=b["prov_result"],
        final_report=b["final_reviewed_report"],
        verdict="approved",
        corrections_made=["Reviewer added unauthorized attribution keeping old source row."],
        remaining_warnings=[],
        narrative_block_sources=tampered_rev_sources,
        reader_sections=rev_sections,
    )

    pub_result = validate_premium_narrative(
        reviewer_bundle,
        b["prov_result"],
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=b["handoff"],
    )

    assert pub_result.get("approved") is False
    errors = pub_result.get("verification_errors", [])
    assert any(
        "reviewer_unauthorized_synthesis_expansion" in err or "untraceable_narrative_block_source" in err or "unapproved_synthesis" in err
        for err in errors
    ), f"Expected boundary or provenance error, got: {errors}"


def test_reviewer_positive_control_polishes_prose_approved(chart3_baseline):
    """Positive Control 4: Reviewer polishes and deepens prose without expanding authority (approved)."""
    b = chart3_baseline
    rev_sources, rev_sections, _ = bind_prospective_plan_to_prose(
        b["final_reviewed_report"], b["block_plan"], b["domain_manifest"]
    )

    reviewer_bundle = build_reviewer_bundle(
        author_bundle=b["author_bundle"],
        provenance_result=b["prov_result"],
        final_report=b["final_reviewed_report"],
        verdict="approved",
        corrections_made=["Polished and tightened prose without adding new astrological claims."],
        remaining_warnings=[],
        narrative_block_sources=rev_sources,
        reader_sections=rev_sections,
    )

    pub_result = validate_premium_narrative(
        reviewer_bundle,
        b["prov_result"],
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=b["handoff"],
    )

    assert pub_result.get("approved") is True, f"Positive control failed: {pub_result.get('verification_errors')}"
