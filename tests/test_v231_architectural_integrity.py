"""Adversarial test suite for V2.3.1 architectural invariants.

Verifies:
1. Premium prospective narrative block planning fails closed without AuthorSelectionPlan.
2. Zero Python heuristics or domain_id rules decide represented/merged/omitted.
3. Forged or out-of-domain synthesis IDs fail in validate_author_selection_plan prior to prose generation.
4. Reviewer cannot inject new attribution; Publication Guard rejects.
5. Closest approach activations never populate exact_peak.
6. Chart 3 replay operates strictly from versioned artifacts with tamper detection, and no DRAFT_REPORT exists in the repo.
"""
import copy
import hashlib
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
    validate_author_selection_plan,
    build_canonical_selection_plan,
    _canonical_hash,
)
from astrology.report import format_canonical_timing_activation
from astrology.exceptions import (
    AstrologyError,
    BenchmarkIntegrityError,
    LineageMismatchError,
    SelectionPlanValidationError,
    ReviewerAuthorityBoundaryError,
)
from scripts.run_chart3_pipeline import (
    CHART_3_BIRTH,
    PROFILE,
    BENCHMARK_DIR,
    verify_benchmark_artifacts,
    replay_chart3_benchmark,
)


def test_v231_premium_fails_closed_without_author_selection_plan():
    """Requirement 1: Premium pipeline fails closed if author_selection_plan is missing."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=PROFILE)
    manifest = handoff["reader_domain_manifest"]

    # 1. plan_prospective_narrative_blocks fails closed
    with pytest.raises(ValueError, match="author_selection_plan is required"):
        plan_prospective_narrative_blocks(handoff)

    # 2. build_canonical_selection_plan fails closed
    with pytest.raises(ValueError, match="author_selection_plan is required"):
        build_canonical_selection_plan(manifest)


def test_v231_no_python_editorial_heuristics_for_selection():
    """Requirement 1 & 2: No Python function makes domain-based editorial decisions."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=PROFILE)
    manifest = handoff["reader_domain_manifest"]

    # In pipeline.py, ensure _DOMAIN_PRIMARY_HOUSES is completely deleted
    import astrology.pipeline as pipeline_mod
    assert not hasattr(pipeline_mod, "_DOMAIN_PRIMARY_HOUSES"), "_DOMAIN_PRIMARY_HOUSES must not exist in pipeline"

    # Conservative fallback must mark 100% of legal paths as represented with 0 merges and 0 omissions
    plan = build_canonical_selection_plan(manifest, allow_conservative_fallback=True)
    for domain in plan.get("domains", []):
        for path_entry in domain.get("paths", []):
            assert path_entry["decision"] == "represented", (
                f"Fallback must not decide merges or omissions in {domain['domain_id']}"
            )
            assert path_entry["merged_with_path_id"] is None
            assert path_entry["rationale"] is None
            assert len(path_entry["synthesis_ids"]) >= 1


def test_v231_forged_or_out_of_domain_synthesis_ids_fail_validation():
    """Requirement 3: Forged or out-of-domain synthesis IDs fail before prose generation."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=PROFILE)
    manifest = handoff["reader_domain_manifest"]
    sel_path = BENCHMARK_DIR / "01-author-selection-plan.json"
    valid_plan = json.loads(sel_path.read_text(encoding="utf-8"))

    # Baseline: valid plan passes with 0 errors
    is_valid, errors = validate_author_selection_plan(valid_plan, manifest, handoff=handoff)
    assert is_valid is True, f"Baseline plan failed validation: {errors}"
    assert len(errors) == 0

    # Adversarial Attack A: Forged synthesis ID injected into author selection plan
    forged_plan = copy.deepcopy(valid_plan)
    id_domain = next(d for d in forged_plan["domains"] if d["domain_id"] == "identity_presence")
    id_rep = next(p for p in id_domain["paths"] if p["decision"] == "represented")
    id_rep["synthesis_ids"].append("reasoned.forged_syntheses.attacker_controlled")
    valid_forged, forged_errors = validate_author_selection_plan(forged_plan, manifest, handoff=handoff)
    assert valid_forged is False
    assert any("unknown_synthesis_id" in e for e in forged_errors)

    # Adversarial Attack B: Out-of-domain synthesis ID injected into another domain represented path
    cross_plan = copy.deepcopy(valid_plan)
    emo_domain = next(d for d in cross_plan["domains"] if d["domain_id"] == "emotional_security")
    emo_rep = next(p for p in emo_domain["paths"] if p["decision"] == "represented")
    # Borrow Jupiter synthesis from work_vocation_visibility
    work_domain = next(d for d in cross_plan["domains"] if d["domain_id"] == "work_vocation_visibility")
    work_rep = next(p for p in work_domain["paths"] if p["decision"] == "represented")
    work_synth = work_rep["synthesis_ids"][0]
    emo_rep["synthesis_ids"].append(work_synth)
    valid_cross, cross_errors = validate_author_selection_plan(cross_plan, manifest, handoff=handoff)
    assert valid_cross is False
    assert any("reader_selection_insufficient_set_ancestry" in e or "reader_selection_noncontributing_synthesis_padding" in e for e in cross_errors)


def test_v231_reviewer_cannot_add_new_attribution():
    """Requirement 4: Reviewer cannot introduce new attribution without Publication Guard rejection."""
    handoff = json.loads((BENCHMARK_DIR / "01-handoff.json").read_text(encoding="utf-8"))
    author_selection_plan = json.loads((BENCHMARK_DIR / "01-author-selection-plan.json").read_text(encoding="utf-8"))
    author_draft = (BENCHMARK_DIR / "author_draft.md").read_text(encoding="utf-8")
    final_reviewed_report = (BENCHMARK_DIR / "final_reviewed_report.md").read_text(encoding="utf-8")
    domain_manifest = handoff["reader_domain_manifest"]

    block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=author_selection_plan)
    sources, sections, _ = bind_prospective_plan_to_prose(author_draft, block_plan, domain_manifest)

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

    # Reviewer attempts to forge sources by adding an unapproved synthesis attribution
    rev_sources, rev_sections, _ = bind_prospective_plan_to_prose(final_reviewed_report, block_plan, domain_manifest)
    forged_rev_sources = copy.deepcopy(rev_sources)
    forged_rev_sources[0]["synthesis_ids"].append("reasoned.forged_attribution.forbidden")

    reviewer_bundle = build_reviewer_bundle(
        author_bundle=author_bundle,
        provenance_result=prov_result,
        final_report=final_reviewed_report,
        verdict="approved",
        corrections_made=["Attempting unauthorized attribution insertion."],
        remaining_warnings=[],
        narrative_block_sources=forged_rev_sources,
        reader_sections=rev_sections,
    )

    pub_result = validate_premium_narrative(
        reviewer_bundle,
        prov_result,
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=handoff,
    )
    assert pub_result.get("approved") is False
    assert any(
        "untraceable_narrative_block_source" in err or "unapproved_synthesis" in err
        for err in pub_result.get("verification_errors", [])
    )


def test_v231_closest_approach_never_populates_exact_peak():
    """Requirement 5: Closest approach never contaminates exact_peak (strictly empty string)."""
    # 1. Perfection activation: exact_peak is populated with exact_at
    exact_activation = {
        "id": "transit.saturn_trine_moon.1",
        "technique": "Major Transit",
        "transit_body": "Saturno",
        "aspect": "trígono",
        "target": "Lua",
        "window_start": "2026-08-15",
        "window_end": "2026-10-15",
        "exact_at": "2026-09-10",
        "closest_approach_at": "2026-09-09",
        "primary_factors": ["aspect.saturn_trine_moon"],
    }
    fmt_exact = format_canonical_timing_activation(exact_activation, PROFILE)
    assert fmt_exact["perfected"] is True
    assert fmt_exact["exact_peak"] == "2026-09-10"
    assert fmt_exact["exact_at"] == "2026-09-10"
    assert fmt_exact["peak_type"] == "exact"
    assert fmt_exact["peak_date"] == "2026-09-10"

    # 2. Closest approach activation: exact_peak MUST BE strictly empty string ("")
    approach_activation = {
        "id": "transit.jupiter_quincunx_sun.2",
        "technique": "Major Transit",
        "transit_body": "Júpiter",
        "aspect": "quincúncio",
        "target": "Sol",
        "window_start": "2026-11-01",
        "window_end": "2027-01-15",
        "exact_at": None,
        "closest_approach_at": "2026-12-05",
        "primary_factors": ["aspect.jupiter_quincunx_sun"],
    }
    fmt_approach = format_canonical_timing_activation(approach_activation, PROFILE)
    assert fmt_approach["perfected"] is False
    assert fmt_approach["exact_peak"] == "", "Closest approach must never populate exact_peak!"
    assert fmt_approach["exact_at"] == ""
    assert fmt_approach["closest_approach_at"] == "2026-12-05"
    assert fmt_approach["peak_type"] == "closest_approach"
    assert fmt_approach["peak_date"] == "2026-12-05"


def test_v231_benchmark_tamper_detection_and_no_draft_report(tmp_path):
    """Requirement 6: Chart 3 benchmark replays cleanly and fails on any artifact tampering, with zero DRAFT_REPORT."""
    import shutil
    import scripts.run_chart3_pipeline as r3_mod
    assert not hasattr(r3_mod, "DRAFT_REPORT"), "scripts/run_chart3_pipeline.py must not define or export DRAFT_REPORT"

    # Full replay of immutable benchmark passes cleanly
    assert replay_chart3_benchmark(BENCHMARK_DIR) is True

    # Real on-disk tamper detection: copy BENCHMARK_DIR to tmp_path and mutate 1 byte
    tamper_dir = tmp_path / "chart3_tampered"
    shutil.copytree(BENCHMARK_DIR, tamper_dir)

    # Untampered copy passes verify_benchmark_artifacts
    assert verify_benchmark_artifacts(tamper_dir) is not None

    # Mutate 1 byte on disk in final_reviewed_report.md
    target_file = tamper_dir / "final_reviewed_report.md"
    orig_bytes = target_file.read_bytes()
    mutated_bytes = orig_bytes[:-1] + (b"X" if orig_bytes[-1:] != b"X" else b"Y")
    target_file.write_bytes(mutated_bytes)

    # verify_benchmark_artifacts on disk MUST raise BenchmarkIntegrityError
    with pytest.raises(BenchmarkIntegrityError, match="Hash mismatch for final_reviewed_report.md"):
        verify_benchmark_artifacts(tamper_dir)

    # replay_chart3_benchmark on disk MUST also raise BenchmarkIntegrityError
    with pytest.raises(BenchmarkIntegrityError):
        replay_chart3_benchmark(tamper_dir)


def test_v231_lineage_mismatch_raises_lineage_mismatch_error():
    """Requirement 7: Lineage mismatch between handoff and selection plan raises LineageMismatchError."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=PROFILE)
    manifest = handoff["reader_domain_manifest"]
    sel_path = BENCHMARK_DIR / "01-author-selection-plan.json"
    valid_plan = json.loads(sel_path.read_text(encoding="utf-8"))

    mismatched_plan = copy.deepcopy(valid_plan)
    mismatched_plan["packet_id"] = "forged_packet_id_00000000000000000000000000000000"

    with pytest.raises(LineageMismatchError, match="packet_id"):
        plan_prospective_narrative_blocks(handoff, author_selection_plan=mismatched_plan)


def test_v231_single_effective_as_of_resolution():
    """Requirement 8: effective_as_of is resolved exactly once and shared consistently."""
    from datetime import datetime, timezone
    from scripts.run_canonical_premium_pipeline import prepare_audit_run

    fixed_as_of = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=PROFILE, as_of=fixed_as_of)

    # Check that effective_as_of is captured in preparation_parameters
    assert handoff["preparation_parameters"]["effective_as_of"] == fixed_as_of.isoformat()
    # Check that timing matches this snapshot
    assert handoff.get("timing") is not None

    # Verify that plan_prospective_narrative_blocks retains the exact packet_id lineage
    sel_path = BENCHMARK_DIR / "01-author-selection-plan.json"
    sel_plan = json.loads(sel_path.read_text(encoding="utf-8"))
    sel_plan["packet_id"] = handoff["packet_id"]

    block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=sel_plan)
    assert block_plan["packet_id"] == handoff["packet_id"]


def test_v231_python_optimized_mode_integrity():
    """Requirement 9: Replay script and guards run safely under python3 -O without bypassed assertions."""
    import subprocess
    cmd = [
        "python3", "-O", "scripts/run_chart3_pipeline.py"
    ]
    res = subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent), capture_output=True, text=True)
    assert res.returncode == 0, f"Replay failed under -O mode:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "Frozen benchmark artifacts passed deterministic integrity and publication replay." in res.stdout
