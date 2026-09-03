#!/usr/bin/env python3
"""Preparation, prospective planning, and guard validation harness for the Premium Complete pipeline.

Executes and verifies the canonical sequence:
1. prepare_premium_handoff (Deterministic Handoff)
2. plan_prospective_narrative_blocks (Prospective Source-Aware Block Plan)
3. Author generation + prospective provenance binding + AuthorBundle v1.4 construction
4. validate_premium_author_bundle (Deterministic Provenance Guard)
5. Reviewer verification + ReviewerBundle v1.4 construction
6. validate_premium_narrative (Publication Guard)
7. editorial_qa (Barnum, Grandiosity, Medicalization lints)
8. validate_technical_relationship_fidelity (Relationship fidelity checks)
9. render_canonical_technical_appendix (Deterministic Swiss Ephemeris Appendix)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.models import BirthData, LocalizationProfile
from astrology.engine import calculate_chart
from astrology.pipeline import (
    analyse_birth_chart,
    prepare_premium_handoff,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_author_bundle,
    build_reviewer_bundle,
    validate_premium_author_bundle,
    validate_premium_narrative,
)
from astrology.report import (
    render_canonical_technical_appendix,
    validate_technical_relationship_fidelity,
)
from astrology.editorial_qa import (
    barnum_risk,
    grandiosity_and_flattery_risk,
    medicalization_risk,
)
from astrology.reasoning import (
    humanization_instructions,
    humanization_verifier_instructions,
)


def prepare_audit_run(
    birth: BirthData,
    profile: LocalizationProfile,
    output_dir: Path,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
) -> Dict[str, object]:
    """Prepares deterministic handoff, prospective block plan, and agent prompts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lang = profile.preferred_language

    # Stage 1: Deterministic Handoff
    print("==> [Stage 1] Preparing Deterministic Handoff...")
    handoff = prepare_premium_handoff(
        birth, profile=profile, report_depth="deep", include_timing=True,
        as_of=as_of, horizon_days=horizon_days,
    )
    analysis = analyse_birth_chart(
        birth, profile=profile, report_depth="deep", include_timing=True,
        as_of=as_of, horizon_days=horizon_days,
    )

    (output_dir / "01-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "01-analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    # Stage 2: Prospective Block Plan (Source selection precedes prose generation)
    print("==> [Stage 2] Generating Prospective Source-Aware Block Plan...")
    block_plan = plan_prospective_narrative_blocks(handoff)
    (output_dir / "01-prospective-block-plan.json").write_text(json.dumps(block_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate Prompts
    author_prompt = (
        f"=== AUTHOR INSTRUCTIONS ===\n{humanization_instructions(lang)}\n\n"
        f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(analysis['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "author_prompt.txt").write_text(author_prompt, encoding="utf-8")

    reviewer_prompt = (
        f"=== REVIEWER INSTRUCTIONS ===\n{humanization_verifier_instructions(lang)}\n\n"
        f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(analysis['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "reviewer_prompt.txt").write_text(reviewer_prompt, encoding="utf-8")

    # Render Technical Appendix
    appendix = render_canonical_technical_appendix(birth, profile=profile, timing=analysis.get("timing"))
    (output_dir / "canonical_technical_appendix.md").write_text(appendix, encoding="utf-8")

    return {
        "handoff": handoff,
        "analysis": analysis,
        "block_plan": block_plan,
        "packet_id": handoff["packet_id"],
    }


def validate_authored_draft(
    birth: BirthData,
    profile: LocalizationProfile,
    draft_report_path: Path,
    handoff_path: Path,
    block_plan_path: Path,
    output_dir: Path,
) -> Dict[str, object]:
    """Binds prose to prospective plan, builds AuthorBundle, and runs Provenance Guard."""
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    block_plan = json.loads(block_plan_path.read_text(encoding="utf-8"))
    draft_report = draft_report_path.read_text(encoding="utf-8")
    manifest = handoff["reader_domain_manifest"]

    sources, sections, audit_trace = bind_prospective_plan_to_prose(draft_report, block_plan, manifest)
    author_bundle = build_author_bundle(
        handoff, draft_report, sources, reader_sections=sections,
    )
    author_bundle["prospective_provenance_audit"] = audit_trace

    (output_dir / "02-author-bundle.json").write_text(json.dumps(author_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    provenance_result = validate_premium_author_bundle(birth, author_bundle, profile, prepared_handoff=handoff)
    (output_dir / "03-provenance-guard.json").write_text(json.dumps(provenance_result, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "author_bundle": author_bundle,
        "provenance_result": provenance_result,
        "approved": provenance_result.get("approved", False),
    }


def validate_reviewed_report(
    birth: BirthData,
    profile: LocalizationProfile,
    final_report_path: Path,
    author_bundle_path: Path,
    provenance_path: Path,
    output_dir: Path,
) -> Dict[str, object]:
    """Builds ReviewerBundle, runs Publication Guard, Editorial QA, and Relationship Fidelity checks."""
    author_bundle = json.loads(author_bundle_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    final_report = final_report_path.read_text(encoding="utf-8")

    reviewer_bundle = build_reviewer_bundle(
        author_bundle, provenance, final_report=final_report,
    )
    (output_dir / "04-reviewer-bundle.json").write_text(json.dumps(reviewer_bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    pub_result = validate_premium_narrative(reviewer_bundle, provenance, birth, profile)
    (output_dir / "05-publication-guard.json").write_text(json.dumps(pub_result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Editorial QA Lints
    barnum = barnum_risk(final_report)
    grandiosity = grandiosity_and_flattery_risk(final_report)
    medicalization = medicalization_risk(final_report)

    # Relationship Fidelity Check
    chart = calculate_chart(birth)
    fidelity_errors = validate_technical_relationship_fidelity(final_report, chart, lang=profile.preferred_language)

    qa_report = {
        "barnum_risk": barnum,
        "grandiosity_risk": grandiosity,
        "medicalization_risk": medicalization,
        "relationship_fidelity_errors": fidelity_errors,
        "publication_approved": pub_result.get("approved", False),
    }
    (output_dir / "06-editorial-qa.json").write_text(json.dumps(qa_report, ensure_ascii=False, indent=2), encoding="utf-8")

    return qa_report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harness for Premium Complete pipeline")
    parser.add_argument("--date", default="1989-11-01T12:08:00")
    parser.add_argument("--tz", default="America/Caracas")
    parser.add_argument("--lat", type=float, default=10.1620)
    parser.add_argument("--lon", type=float, default=-68.0077)
    parser.add_argument("--lang", default="pt-BR")
    parser.add_argument("--out", default="/tmp/run_valencia_1989_v22")
    args = parser.parse_args()

    b = BirthData(args.date, args.tz, args.lat, args.lon, birth_time_known=True)
    p = LocalizationProfile(preferred_language=args.lang)
    res = prepare_audit_run(b, p, Path(args.out))
    print(f"Handoff and prospective block plan ready. Packet ID: {res['packet_id']}")
