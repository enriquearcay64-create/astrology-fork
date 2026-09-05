"""Deterministic, immutable replay and guard verification for Chart 3 (Mutable Earth/Water).

Replays and verifies the versioned benchmark run from benchmarks/chart3_mutable_earth_water:
1. Verifies artifact hashes against benchmark_manifest.json.
2. Validates the Author Selection Plan with prospective ancestry and legality checks.
3. Compiles the prospective SourceAwareBlockPlan from the validated selection.
4. Validates the Authored Draft through the Provenance Guard.
5. Validates the Reviewed Report through the Publication Guard.
6. Validates Editorial QA (0.0% Barnum, 0.0% Grandiosity, 0.0% Medicalization).
7. Validates Technical Relationship Fidelity (0 errors).
"""
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone
import json
import hashlib
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from astrology.models import BirthData, LocalizationProfile
from astrology.engine import calculate_chart
from astrology.safe_view import build_safe_interpretive_view
from astrology.pipeline import (
    validate_author_selection_plan,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_author_bundle,
    validate_premium_author_bundle,
    build_reviewer_bundle,
    validate_premium_narrative,
)
from astrology.report import (
    validate_technical_relationship_fidelity,
    render_canonical_technical_appendix,
)
from astrology.editorial_qa import (
    barnum_risk,
    grandiosity_and_flattery_risk,
    medicalization_risk,
)

CHART_3_BIRTH = BirthData("1995-09-08T19:45:00", "Europe/Paris", 48.8566, 2.3522, birth_time_known=True)
PROFILE = LocalizationProfile(preferred_language="pt-BR")
BENCHMARK_DIR = Path("benchmarks/chart3_mutable_earth_water")


def verify_benchmark_artifacts(bench_dir: Path = BENCHMARK_DIR) -> Dict[str, object]:
    """Verify SHA-256 integrity of all versioned benchmark artifacts."""
    manifest_path = bench_dir / "benchmark_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing benchmark manifest: {manifest_path}")
    
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hashes = manifest.get("artifacts_sha256", {})
    
    for filename, expected_hash in expected_hashes.items():
        artifact_path = bench_dir / filename
        if not artifact_path.exists():
            raise FileNotFoundError(f"Missing expected benchmark artifact: {artifact_path}")
        content = artifact_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        assert actual_hash == expected_hash, f"Hash mismatch for {filename}: expected {expected_hash}, got {actual_hash}"
    
    return manifest


def replay_chart3_benchmark(bench_dir: Path = BENCHMARK_DIR) -> bool:
    print("=== REPLAYING IMMUTABLE BENCHMARK FOR CHART 3 (MUTABLE EARTH/WATER) ===")
    
    # 1. Integrity Check
    print("\n==> [1/5] Verifying Benchmark Artifact Hashes against Manifest...")
    manifest = verify_benchmark_artifacts(bench_dir)
    print(f"Verified {len(manifest['artifacts_sha256'])} benchmark artifacts against commit {manifest['git_commit_sha'][:8]}.")

    # Load versioned artifacts
    handoff = json.loads((bench_dir / "01-handoff.json").read_text(encoding="utf-8"))
    author_selection_plan = json.loads((bench_dir / "01-author-selection-plan.json").read_text(encoding="utf-8"))
    author_draft = (bench_dir / "author_draft.md").read_text(encoding="utf-8")
    final_reviewed_report = (bench_dir / "final_reviewed_report.md").read_text(encoding="utf-8")
    
    domain_manifest = handoff["reader_domain_manifest"]

    # 2. Prospective Selection Plan Validation
    print("\n==> [2/5] Validating Author Selection Plan (Legality & Ancestry)...")
    valid, errors = validate_author_selection_plan(
        author_selection_plan, domain_manifest, handoff=handoff
    )
    assert valid is True, f"Author selection plan validation failed: {errors}"
    print("Author Selection Plan: VALIDATED (0 errors, fail-closed prospective gate passed).")

    # 3. Compile Prospective Block Plan
    print("\n==> [3/5] Compiling Prospective Block Plan from Selection Plan...")
    block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=author_selection_plan)
    assert len(block_plan.get("sections", {})) == 18, "Expected 18 planned sections (opening + 16 domains + integration)"
    print("Prospective Block Plan: COMPILED successfully.")

    # 4. Provenance Guard on Authored Draft
    print("\n==> [4/5] Running Deterministic Provenance Guard on Author Draft...")
    sources, sections, trace = bind_prospective_plan_to_prose(author_draft, block_plan, domain_manifest)
    unmat = trace.get("unmaterialized_planned_sources", [])
    assert len(unmat) == 0, f"Unmaterialized planned sources detected: {unmat}"

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
    assert prov_result.get("approved") is True, f"Provenance Guard rejected draft: {prov_result.get('verification_errors')}"
    print(f"Provenance Guard: APPROVED (Total blocks: {len(sources)}, 0 unmaterialized mandatories).")

    # 5. Publication Guard, Editorial QA & Relationship Fidelity
    print("\n==> [5/5] Running Publication Guard, Editorial QA & Relationship Fidelity on Reviewed Report...")
    rev_sources, rev_sections, rev_trace = bind_prospective_plan_to_prose(final_reviewed_report, block_plan, domain_manifest)
    reviewer_bundle = build_reviewer_bundle(
        author_bundle=author_bundle,
        provenance_result=prov_result,
        final_report=final_reviewed_report,
        verdict="approved",
        corrections_made=["Audited technical precision and affirmative multi-paragraph cadence."],
        remaining_warnings=[],
        narrative_block_sources=rev_sources,
        reader_sections=rev_sections,
    )
    pub_result = validate_premium_narrative(
        reviewer_bundle,
        prov_result,
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=handoff,
    )
    assert pub_result.get("approved") is True, f"Publication Guard rejected final report: {pub_result.get('verification_errors')}"

    # Editorial QA
    b_risk = barnum_risk(final_reviewed_report)
    g_risk = grandiosity_and_flattery_risk(final_reviewed_report)
    m_risk = medicalization_risk(final_reviewed_report)
    chart = build_safe_interpretive_view(calculate_chart(CHART_3_BIRTH))
    f_errors = validate_technical_relationship_fidelity(final_reviewed_report, chart, lang=PROFILE.preferred_language)

    assert b_risk["share"] == 0.0, f"Barnum risk found: {b_risk}"
    assert g_risk["share"] == 0.0, f"Grandiosity risk found: {g_risk}"
    assert m_risk["share"] == 0.0, f"Medicalization risk found: {m_risk}"
    assert len(f_errors) == 0, f"Relationship fidelity errors found: {f_errors}"

    print(f"Publication Guard: APPROVED.")
    print(f"Editorial QA: Barnum={b_risk['share']}, Grandiosity={g_risk['share']}, Medicalization={m_risk['share']}.")
    print(f"Relationship Fidelity: {len(f_errors)} errors.")
    print("\n==> ALL GATES PASSED! Chart 3 benchmark is 100% reproducible and auditable from Git.")
    return True


if __name__ == "__main__":
    success = replay_chart3_benchmark()
    if not success:
        sys.exit(1)
