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
from astrology.timing import cross_technique_timing
from astrology.exceptions import BenchmarkIntegrityError, LineageMismatchError
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
    from astrology.benchmark_integrity import verify_artifacts
    return verify_artifacts(bench_dir)


def replay_chart3_benchmark(bench_dir: Path = BENCHMARK_DIR) -> bool:
    print("=== REPLAYING IMMUTABLE BENCHMARK FOR CHART 3 (MUTABLE EARTH/WATER) ===")
    
    # 1. Integrity Check
    print("\n==> [1/5] Verifying Benchmark Artifact Hashes against Manifest...")
    manifest = verify_benchmark_artifacts(bench_dir)
    if manifest.get("benchmark_status") == "invalidated":
        raise BenchmarkIntegrityError("Invalidated benchmark cannot pass publication replay")
    if manifest.get("artifact_generation_commit_sha"):
        from astrology.benchmark_integrity import verify_commit
        verify_commit(Path(__file__).resolve().parents[1], manifest["artifact_generation_commit_sha"])
    print(f"Verified {len(manifest['artifacts_sha256'])} benchmark artifacts.")

    if (bench_dir / "run.json").exists():
        from astrology.isolated_execution import RunStore
        from astrology.live_premium import verify_captured_derivation
        return verify_captured_derivation(RunStore(bench_dir))

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
    if not valid:
        raise BenchmarkIntegrityError(f"Author selection plan validation failed: {errors}")
    print("Author Selection Plan: VALIDATED (0 errors, fail-closed prospective gate passed).")

    # 3. Compile Prospective Block Plan and Re-verify against artifact
    print("\n==> [3/5] Compiling Prospective Block Plan from Selection Plan...")
    block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=author_selection_plan)


    versioned_block_plan_path = bench_dir / "01-prospective-block-plan.json"
    if versioned_block_plan_path.exists():
        versioned_bp = json.loads(versioned_block_plan_path.read_text(encoding="utf-8"))
        from astrology.benchmark_integrity import require_equal
        require_equal(block_plan, versioned_bp, "prospective block plan")
    else:
        raise BenchmarkIntegrityError("Missing prospective block plan")
    print("Prospective Block Plan: COMPILED and verified successfully.")

    # Appendix Re-rendering Check
    as_of_val = handoff["preparation_parameters"].get("effective_as_of")
    as_of_dt = datetime.fromisoformat(as_of_val) if isinstance(as_of_val, str) else as_of_val
    horizon_days = handoff["preparation_parameters"].get("horizon_days", 366)
    timing_data = handoff.get("timing")
    if timing_data is None and handoff["preparation_parameters"]["include_timing"]:
        raw_chart = calculate_chart(CHART_3_BIRTH)
        chart_view = build_safe_interpretive_view(raw_chart)
        timing_data = cross_technique_timing(chart_view.semantic_chart(), as_of_dt, horizon_days)

    re_rendered_appendix = render_canonical_technical_appendix(CHART_3_BIRTH, profile=PROFILE, timing=timing_data)
    appendix_file = (bench_dir / "canonical_technical_appendix.md").read_text(encoding="utf-8")
    if re_rendered_appendix != appendix_file:
        raise BenchmarkIntegrityError("Canonical technical appendix re-render does not match versioned benchmark artifact.")

    from astrology.benchmark_integrity import load_json, require_equal
    original_author = load_json(bench_dir / "02-author-bundle.json")
    original_reviewer = load_json(bench_dir / "04-reviewer-bundle.json")
    require_equal(original_author["draft_report"], author_draft, "Author draft")
    require_equal(original_reviewer["final_report"], final_reviewed_report, "Reviewer report")

    # 4. Provenance Guard on Authored Draft
    print("\n==> [4/5] Running Deterministic Provenance Guard on Author Draft...")
    sources, sections, trace = bind_prospective_plan_to_prose(author_draft, block_plan, domain_manifest)
    unmat = trace.get("unmaterialized_planned_sources", [])
    if len(unmat) != 0:
        raise BenchmarkIntegrityError(f"Unmaterialized planned sources detected: {unmat}")

    author_bundle = build_author_bundle(
        handoff=handoff,
        draft_report=author_draft,
        narrative_block_sources=original_author["narrative_block_sources"],
        reader_sections=original_author["reader_sections"],
        reasoned_syntheses=original_author["reasoned_syntheses"],
        synthesis_bundle_sha256=original_author["synthesis_bundle_sha256"],
        reader_selection_plan=author_selection_plan,
    )
    prov_result = validate_premium_author_bundle(
        CHART_3_BIRTH, author_bundle, profile=PROFILE, prepared_handoff=handoff,
    )
    if prov_result.get("approved") is not True:
        raise BenchmarkIntegrityError(f"Provenance Guard rejected draft: {prov_result.get('verification_errors')}")
    print(f"Provenance Guard: APPROVED (Total blocks: {len(sources)}, 0 unmaterialized mandatories).")

    # 5. Publication Guard, Editorial QA & Relationship Fidelity
    print("\n==> [5/5] Running Publication Guard, Editorial QA & Relationship Fidelity on Reviewed Report...")
    rev_sources, rev_sections, rev_trace = bind_prospective_plan_to_prose(final_reviewed_report, block_plan, domain_manifest)
    reviewer_bundle = build_reviewer_bundle(
        author_bundle=author_bundle,
        provenance_result=prov_result,
        final_report=final_reviewed_report,
        verdict=original_reviewer["verdict"],
        corrections_made=original_reviewer["corrections_made"],
        remaining_warnings=original_reviewer["remaining_warnings"],
        regeneration_request=original_reviewer.get("regeneration_request"),
        narrative_block_sources=original_reviewer["narrative_block_sources"],
        reader_sections=original_reviewer["reader_sections"],
    )
    pub_result = validate_premium_narrative(
        reviewer_bundle,
        prov_result,
        CHART_3_BIRTH,
        profile=PROFILE,
        prepared_handoff=handoff,
    )
    if pub_result.get("approved") is not True:
        raise BenchmarkIntegrityError(f"Publication Guard rejected final report: {pub_result.get('verification_errors')}")

    # Editorial QA
    b_risk = barnum_risk(final_reviewed_report)
    g_risk = grandiosity_and_flattery_risk(final_reviewed_report)
    m_risk = medicalization_risk(final_reviewed_report)
    chart = build_safe_interpretive_view(calculate_chart(CHART_3_BIRTH))
    f_errors = validate_technical_relationship_fidelity(final_reviewed_report, chart, lang=PROFILE.preferred_language)

    if b_risk["share"] != 0.0:
        raise BenchmarkIntegrityError(f"Barnum risk found: {b_risk}")
    if g_risk["share"] != 0.0:
        raise BenchmarkIntegrityError(f"Grandiosity risk found: {g_risk}")
    if m_risk["share"] != 0.0:
        raise BenchmarkIntegrityError(f"Medicalization risk found: {m_risk}")
    if len(f_errors) != 0:
        raise BenchmarkIntegrityError(f"Relationship fidelity errors found: {f_errors}")

    from astrology.benchmark_integrity import require_equal, load_json
    stored = {
        "02-author-bundle.json": author_bundle,
        "03-provenance-guard.json": prov_result,
        "04-reviewer-bundle.json": reviewer_bundle,
        "05-publication-guard.json": pub_result,
        "06-editorial-qa.json": {"barnum_risk": b_risk, "grandiosity_risk": g_risk, "medicalization_risk": m_risk, "relationship_fidelity_errors": f_errors, "publication_approved": pub_result["approved"]},
    }
    for name, actual in stored.items():
        path = bench_dir / name
        if not path.is_file():
            raise BenchmarkIntegrityError(f"Missing full replay output: {name}")
        require_equal(actual, load_json(path), name)
    print(f"Publication Guard: APPROVED.")
    print(f"Editorial QA: Barnum={b_risk['share']}, Grandiosity={g_risk['share']}, Medicalization={m_risk['share']}.")
    print(f"Relationship Fidelity: {len(f_errors)} errors.")
    print("\n==> Frozen benchmark artifacts passed deterministic integrity and publication replay.")
    return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    success = replay_chart3_benchmark(args.run_dir)
    if not success:
        sys.exit(1)
