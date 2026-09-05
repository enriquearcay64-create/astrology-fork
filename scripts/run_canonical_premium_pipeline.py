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
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.models import BirthData, LocalizationProfile
from astrology.engine import calculate_chart
from astrology.pipeline import (
    prepare_premium_handoff,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_author_bundle,
    build_reviewer_bundle,
    build_canonical_selection_plan,
    validate_author_selection_plan,
    validate_premium_author_bundle,
    validate_premium_narrative,
)
from astrology.exceptions import (
    BenchmarkIntegrityError,
    LineageMismatchError,
    SelectionPlanValidationError,
    ReviewerAuthorityBoundaryError,
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


def build_author_selection_prompt(handoff: Dict[str, object], lang: str = "pt-BR") -> str:
    """Generate prompt instructing the Author to build the ReaderSelectionPlan."""
    manifest = handoff["reader_domain_manifest"]
    catalog = handoff.get("candidate_catalog") or {}
    approved_synths = handoff.get("approved_reasoned_syntheses") or handoff.get("prepared_signature_syntheses", [])
    packet_id = handoff.get("packet_id", "")
    return (
        f"=== AUTHOR SELECTION INSTRUCTIONS ===\n"
        f"You are the Premium Astrological Author. Before drafting prose, you must evaluate all candidate legal coverage paths\n"
        f"in the Selection Candidate Catalog and Reader Domain Manifest, and produce the Author Selection Plan (ReaderSelectionPlan v1.0).\n\n"
        f"For each available domain in the manifest:\n"
        f"- Classify each legal path as: 'represented', 'merged_with_represented', or 'omitted_no_distinct_reader_value'.\n"
        f"- Coverage contract: Every available domain MUST have at least one 'represented' path.\n"
        f"- For 'represented': assign the approved synthesis ID(s) from the candidate catalog that materialize this path's distinct human mechanism.\n"
        f"- For 'merged_with_represented': specify the 'merged_with_path_id' (must be a represented path in the same domain) and a non-empty rationale explaining how the mechanisms converge.\n"
        f"- For 'omitted_no_distinct_reader_value': specify a non-empty rationale explaining why this path provides no distinct reader value.\n"
        f"- Lineage invariant: Include 'packet_id': '{packet_id}' in the selection plan.\n"
        f"- Output strictly valid JSON matching the ReaderSelectionPlan v1.0 schema.\n\n"
        f"=== SELECTION CANDIDATE CATALOG ===\n{json.dumps(catalog, ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(manifest, ensure_ascii=False, indent=2)}\n\n"
        f"=== APPROVED SYNTHESES ===\n{json.dumps(approved_synths, ensure_ascii=False, indent=2)}\n"
    )


def prepare_audit_run(
    birth: BirthData,
    profile: LocalizationProfile,
    output_dir: Path,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    author_selection_plan: Optional[Dict[str, object]] = None,
    *,
    allow_conservative_fallback: bool = False,
) -> Dict[str, object]:
    """Prepares deterministic handoff, prospective block plan, and agent prompts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lang = profile.preferred_language

    # Stage 1: Deterministic Handoff from a single authoritative snapshot
    print("==> [Stage 1] Preparing Deterministic Handoff...")
    effective_as_of = as_of or datetime.now(timezone.utc)
    handoff = prepare_premium_handoff(
        birth, profile=profile, report_depth="deep", include_timing=True,
        as_of=effective_as_of, horizon_days=horizon_days,
    )

    (output_dir / "01-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    if handoff.get("candidate_catalog"):
        (output_dir / "01-candidate-catalog.json").write_text(
            json.dumps(handoff["candidate_catalog"], ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Generate selection prompt
    selection_prompt = build_author_selection_prompt(handoff, lang)
    (output_dir / "author_selection_prompt.txt").write_text(selection_prompt, encoding="utf-8")

    # Stage 2: Prospective Block Plan (Source selection precedes prose generation)
    print("==> [Stage 2] Generating Prospective Source-Aware Block Plan...")
    if author_selection_plan is not None:
        if author_selection_plan.get("packet_id") and author_selection_plan["packet_id"] != handoff["packet_id"]:
            raise LineageMismatchError(
                f"Author selection plan packet_id ({author_selection_plan.get('packet_id')}) "
                f"does not match handoff packet_id ({handoff['packet_id']})"
            )
        valid, errors = validate_author_selection_plan(
            author_selection_plan, handoff["reader_domain_manifest"], handoff=handoff
        )
        if not valid:
            raise SelectionPlanValidationError(f"Invalid author selection plan: {', '.join(errors)}")

        (output_dir / "01-author-selection-plan.json").write_text(
            json.dumps(author_selection_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=author_selection_plan)
    elif allow_conservative_fallback:
        block_plan = plan_prospective_narrative_blocks(handoff, allow_conservative_fallback=True)
    else:
        # Fails closed in production if AuthorSelectionPlan is missing
        raise SelectionPlanValidationError(
            "author_selection_plan is required: Premium Complete fails closed without an Author-owned selection plan. "
            "Prompt the Author using author_selection_prompt.txt before block plan generation."
        )

    # Lineage invariant assertion
    if block_plan.get("packet_id") != handoff["packet_id"]:
        raise LineageMismatchError(
            f"Block plan packet_id ({block_plan.get('packet_id')}) does not match handoff packet_id ({handoff['packet_id']})"
        )

    (output_dir / "01-prospective-block-plan.json").write_text(json.dumps(block_plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # Generate Prompts using single authoritative reasoning packet from handoff
    author_prompt = (
        f"=== AUTHOR INSTRUCTIONS ===\n{humanization_instructions(lang)}\n\n"
        f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(handoff['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "author_prompt.txt").write_text(author_prompt, encoding="utf-8")

    reviewer_prompt = (
        f"=== REVIEWER INSTRUCTIONS ===\n{humanization_verifier_instructions(lang)}\n\n"
        f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(handoff['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "reviewer_prompt.txt").write_text(reviewer_prompt, encoding="utf-8")

    # Render Technical Appendix
    appendix = render_canonical_technical_appendix(birth, profile=profile, timing=handoff.get("timing"))
    (output_dir / "canonical_technical_appendix.md").write_text(appendix, encoding="utf-8")

    return {
        "handoff": handoff,
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

    all_synths = list(block_plan.get("composed_syntheses", []))

    for ps in handoff.get("prepared_signature_syntheses", []):
        if ps["id"] not in [x["id"] for x in all_synths]:
            all_synths.append(ps)

    from datetime import datetime
    effective_as_of = handoff["preparation_parameters"]["effective_as_of"]
    parsed_as_of = datetime.fromisoformat(str(effective_as_of).replace("Z", "+00:00"))
    from astrology.pipeline import validate_premium_syntheses, _canonical_hash
    checked = validate_premium_syntheses(birth, all_synths, profile, parsed_as_of, 366, True, premium_contract_version="1.4")
    approved_synths = [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"]
    expected_synthesis_hash = _canonical_hash(approved_synths)

    sel_plan = block_plan.get("selection_plan") or build_canonical_selection_plan(manifest)

    author_bundle = build_author_bundle(
        handoff, draft_report, sources,
        reader_selection_plan=sel_plan,
        reasoned_syntheses=all_synths,
        reader_sections=sections,
        synthesis_bundle_sha256=expected_synthesis_hash,
    )

    (output_dir / "02-author-bundle.json").write_text(json.dumps(author_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "02-prospective-audit.json").write_text(json.dumps(audit_trace, ensure_ascii=False, indent=2), encoding="utf-8")

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
    handoff_path: Path,
    block_plan_path: Path,
    output_dir: Path,
) -> Dict[str, object]:
    """Builds ReviewerBundle, runs Publication Guard, Editorial QA, and Relationship Fidelity checks."""
    author_bundle = json.loads(author_bundle_path.read_text(encoding="utf-8"))
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    block_plan = json.loads(block_plan_path.read_text(encoding="utf-8"))
    final_report = final_report_path.read_text(encoding="utf-8")
    manifest = handoff["reader_domain_manifest"]

    # In Contract 1.4, when prose undergoes reviewer layout/language edits,
    # physical hashes and block ownership must be rebound to preserve exact physical provenance
    final_sources, final_sections, audit_trace = bind_prospective_plan_to_prose(final_report, block_plan, manifest)

    reviewer_bundle = build_reviewer_bundle(
        author_bundle, provenance,
        final_report=final_report,
        narrative_block_sources=final_sources,
        reader_sections=final_sections,
    )
    (output_dir / "04-reviewer-bundle.json").write_text(json.dumps(reviewer_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "04-prospective-final-audit.json").write_text(json.dumps(audit_trace, ensure_ascii=False, indent=2), encoding="utf-8")


    pub_result = validate_premium_narrative(
        reviewer_bundle, provenance, birth, profile,
        prepared_handoff=handoff, include_timing=True,
    )
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

    # Assemble publication report with deterministic technical appendix
    appendix_path = output_dir / "canonical_technical_appendix.md"
    appendix_text = appendix_path.read_text(encoding="utf-8") if appendix_path.exists() else ""
    full_publication_report = f"{final_report.strip()}\n\n---\n\n{appendix_text.strip()}\n"
    (output_dir / "relatorio_publicacao_valencia_v22.md").write_text(full_publication_report, encoding="utf-8")

    return qa_report



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Preparation, prospective planning, and guard validation harness for Premium Complete pipeline"
    )
    # Root arguments
    parser.add_argument("--date", default="1989-11-01T12:08:00")
    parser.add_argument("--tz", default="America/Caracas")
    parser.add_argument("--lat", type=float, default=10.1620)
    parser.add_argument("--lon", type=float, default=-68.0077)
    parser.add_argument("--lang", default="pt-BR")
    parser.add_argument("--out", default="/tmp/run_valencia_1989_v22")
    parser.add_argument("--author-selection-plan", type=Path, default=None, help="Path to Author Selection Plan JSON")
    parser.add_argument("--allow-conservative-fallback", action="store_true", help="Allow conservative fallback selection plan (for test/headless)")

    subparsers = parser.add_subparsers(dest="subcommand", help="Optional pipeline subcommands")

    # Subcommand: prepare-selection
    p_prep_sel = subparsers.add_parser("prepare-selection", help="Generate handoff, candidate catalog, and author selection prompt")
    p_prep_sel.add_argument("--date", default="1989-11-01T12:08:00")
    p_prep_sel.add_argument("--tz", default="America/Caracas")
    p_prep_sel.add_argument("--lat", type=float, default=10.1620)
    p_prep_sel.add_argument("--lon", type=float, default=-68.0077)
    p_prep_sel.add_argument("--lang", default="pt-BR")
    p_prep_sel.add_argument("--out", default="/tmp/run_valencia_1989_v22")

    # Subcommand: validate-selection
    p_val_sel = subparsers.add_parser("validate-selection", help="Validate an author selection plan against handoff")
    p_val_sel.add_argument("--handoff", type=Path, required=True, help="Path to 01-handoff.json")
    p_val_sel.add_argument("--selection-plan", type=Path, required=True, help="Path to Author Selection Plan JSON")

    # Subcommand: prepare-author
    p_prep_auth = subparsers.add_parser("prepare-author", help="Compile prospective block plan and generate author/reviewer prompts")
    p_prep_auth.add_argument("--handoff", type=Path, required=True, help="Path to 01-handoff.json")
    p_prep_auth.add_argument("--selection-plan", type=Path, default=None, help="Path to Author Selection Plan JSON")
    p_prep_auth.add_argument("--allow-conservative-fallback", action="store_true", help="Allow conservative fallback selection plan")
    p_prep_auth.add_argument("--out", type=Path, required=True, help="Output directory")
    p_prep_auth.add_argument("--lang", default="pt-BR")

    args = parser.parse_args()

    if args.subcommand == "prepare-selection":
        b = BirthData(args.date, args.tz, args.lat, args.lon, birth_time_known=True)
        p = LocalizationProfile(preferred_language=args.lang)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        effective_as_of = datetime.now(timezone.utc)
        handoff = prepare_premium_handoff(b, profile=p, report_depth="deep", include_timing=True, as_of=effective_as_of)
        (out_dir / "01-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
        if handoff.get("candidate_catalog"):
            (out_dir / "01-candidate-catalog.json").write_text(
                json.dumps(handoff["candidate_catalog"], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        prompt = build_author_selection_prompt(handoff, args.lang)
        (out_dir / "author_selection_prompt.txt").write_text(prompt, encoding="utf-8")
        appendix = render_canonical_technical_appendix(b, profile=p, timing=handoff.get("timing"))
        (out_dir / "canonical_technical_appendix.md").write_text(appendix, encoding="utf-8")
        print(f"[Stage 1] Deterministic handoff and author selection prompt ready in {out_dir}.")
        print(f"Packet ID: {handoff['packet_id']}")
        sys.exit(0)

    elif args.subcommand == "validate-selection":
        handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        sel_plan = json.loads(args.selection_plan.read_text(encoding="utf-8"))
        if sel_plan.get("packet_id") and sel_plan["packet_id"] != handoff.get("packet_id"):
            print(
                f"ERROR: Lineage mismatch: selection packet_id ({sel_plan.get('packet_id')}) != handoff packet_id ({handoff.get('packet_id')})",
                file=sys.stderr,
            )
            sys.exit(1)
        valid, errors = validate_author_selection_plan(
            sel_plan, handoff["reader_domain_manifest"], handoff=handoff
        )
        if not valid:
            print(f"ERROR: Author selection plan validation failed:\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
            sys.exit(1)
        print("SUCCESS: Author selection plan is valid and matches handoff lineage.")
        sys.exit(0)

    elif args.subcommand == "prepare-author":
        handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        sel_plan = None
        if args.selection_plan:
            sel_plan = json.loads(args.selection_plan.read_text(encoding="utf-8"))
            if sel_plan.get("packet_id") and sel_plan["packet_id"] != handoff.get("packet_id"):
                print(
                    f"ERROR: Lineage mismatch: selection packet_id ({sel_plan.get('packet_id')}) != handoff packet_id ({handoff.get('packet_id')})",
                    file=sys.stderr,
                )
                sys.exit(1)
            valid, errors = validate_author_selection_plan(
                sel_plan, handoff["reader_domain_manifest"], handoff=handoff
            )
            if not valid:
                print(f"ERROR: Author selection plan validation failed:\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
                sys.exit(1)
            (out_dir / "01-author-selection-plan.json").write_text(
                json.dumps(sel_plan, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            block_plan = plan_prospective_narrative_blocks(handoff, author_selection_plan=sel_plan)
        elif args.allow_conservative_fallback:
            block_plan = plan_prospective_narrative_blocks(handoff, allow_conservative_fallback=True)
        else:
            print("ERROR: Must provide either --selection-plan <path> or --allow-conservative-fallback", file=sys.stderr)
            sys.exit(1)

        (out_dir / "01-prospective-block-plan.json").write_text(
            json.dumps(block_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        author_prompt = (
            f"=== AUTHOR INSTRUCTIONS ===\n{humanization_instructions(args.lang)}\n\n"
            f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
            f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(handoff['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
            f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
            f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
        )
        (out_dir / "author_prompt.txt").write_text(author_prompt, encoding="utf-8")

        reviewer_prompt = (
            f"=== REVIEWER INSTRUCTIONS ===\n{humanization_verifier_instructions(args.lang)}\n\n"
            f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(block_plan, ensure_ascii=False, indent=2)}\n\n"
            f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(handoff['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
            f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
            f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
        )
        (out_dir / "reviewer_prompt.txt").write_text(reviewer_prompt, encoding="utf-8")
        print(f"Prospective block plan and author/reviewer prompts ready in {out_dir}.")
        print(f"Packet ID: {block_plan['packet_id']}")
        sys.exit(0)

    else:
        # Default root execution
        b = BirthData(args.date, args.tz, args.lat, args.lon, birth_time_known=True)
        p = LocalizationProfile(preferred_language=args.lang)
        out_dir = Path(args.out)

        sel_plan = None
        if args.author_selection_plan:
            sel_plan = json.loads(args.author_selection_plan.read_text(encoding="utf-8"))

        if sel_plan is not None or args.allow_conservative_fallback:
            res = prepare_audit_run(
                b, p, out_dir,
                author_selection_plan=sel_plan,
                allow_conservative_fallback=args.allow_conservative_fallback,
            )
            print(f"Handoff and prospective block plan ready. Packet ID: {res['packet_id']}")
        else:
            # Prepare Stage 1 handoff and selection prompt, fail closed before Stage 2
            out_dir.mkdir(parents=True, exist_ok=True)
            effective_as_of = datetime.now(timezone.utc)
            handoff = prepare_premium_handoff(b, profile=p, report_depth="deep", include_timing=True, as_of=effective_as_of)
            (out_dir / "01-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
            if handoff.get("candidate_catalog"):
                (out_dir / "01-candidate-catalog.json").write_text(
                    json.dumps(handoff["candidate_catalog"], ensure_ascii=False, indent=2), encoding="utf-8"
                )
            prompt = build_author_selection_prompt(handoff, args.lang)
            (out_dir / "author_selection_prompt.txt").write_text(prompt, encoding="utf-8")
            appendix = render_canonical_technical_appendix(b, profile=p, timing=handoff.get("timing"))
            (out_dir / "canonical_technical_appendix.md").write_text(appendix, encoding="utf-8")
            print(f"[Stage 1] Deterministic handoff and author_selection_prompt.txt generated in {out_dir}.")
            print(f"Packet ID: {handoff['packet_id']}")
            print("Under V2.3.1 Invariant 1 (Author-Owned Selection), block planning fails closed without an Author selection plan.")
            print("To proceed to Stage 2:")
            print(f"  1. Prompt the Author using {out_dir / 'author_selection_prompt.txt'}")
            print(f"  2. Re-run with: python3 scripts/run_canonical_premium_pipeline.py --out {out_dir} --author-selection-plan <path_to_plan.json>")
            print("  (Or specify --allow-conservative-fallback for automated test/headless runs)")
