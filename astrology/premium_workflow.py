"""Shared manual Premium 1.4 stages; no external model calls or implicit resume calculation."""
from __future__ import annotations
import json
from datetime import datetime
from typing import Dict, Optional
from .pipeline import plan_prospective_narrative_blocks
from .reasoning import humanization_instructions

def prepared_timing_parameters(handoff: Dict[str, object]) -> tuple[Optional[datetime], int, bool]:
    parameters = handoff.get("preparation_parameters")
    if not isinstance(parameters, dict):
        raise ValueError("premium handoff is missing preparation_parameters")
    effective = parameters.get("effective_as_of")
    effective_as_of = datetime.fromisoformat(str(effective).replace("Z", "+00:00")) if effective is not None else None
    if effective_as_of is not None and effective_as_of.tzinfo is None:
        raise ValueError("premium handoff effective_as_of must include a UTC offset")
    horizon_days = parameters.get("horizon_days")
    include_timing = parameters.get("include_timing")
    if not isinstance(horizon_days, int) or isinstance(horizon_days, bool) or horizon_days <= 0:
        raise ValueError("premium handoff horizon_days must be a positive integer")
    if not isinstance(include_timing, bool):
        raise ValueError("premium handoff include_timing must be boolean")
    if include_timing and effective_as_of is None:
        raise ValueError("timed premium handoff effective_as_of is required")
    return effective_as_of, horizon_days, include_timing


def build_author_selection_prompt(handoff: Dict[str, object], lang: str = "pt-BR") -> str:
    """Generate prompt instructing the Author to build the ReaderSelectionPlan."""
    manifest = handoff["reader_domain_manifest"]
    catalog = handoff["candidate_catalog"]
    approved_synths = handoff["approved_reasoned_syntheses"]
    packet_id = handoff.get("packet_id", "")
    return (
        f"=== AUTHOR SELECTION INSTRUCTIONS ===\n"
        f"You are the Premium Astrological Author. Before drafting prose, you must evaluate all candidate legal coverage paths\n"
        f"in the Selection Candidate Catalog and Reader Domain Manifest, and produce the Author Selection Plan (ReaderSelectionPlan v1.1).\n\n"
        f"For each available domain in the manifest:\n"
        f"- Classify each legal path as: 'represented', 'merged_with_represented', or 'omitted_no_distinct_reader_value'.\n"
        f"- Coverage contract: Every available domain MUST have at least one 'represented' path.\n"
        f"- For 'represented': assign the approved synthesis ID(s) from the candidate catalog that materialize this path's distinct human mechanism.\n"
        f"- For 'merged_with_represented': specify the 'merged_with_path_id' (must be a represented path in the same domain) and a non-empty rationale explaining how the mechanisms converge.\n"
        f"- For 'omitted_no_distinct_reader_value': specify a non-empty rationale explaining why this path provides no distinct reader value.\n"
        f"- Lineage invariant: Include 'packet_id': '{packet_id}' in the selection plan.\n"
        f"- Output exactly version ('1.1'), packet_id, domains, editorial_sections. Domain rows have domain_id and paths.\n"
        f"- Each path has exactly path_id, decision, synthesis_ids (list), merged_with_path_id (null unless merged), rationale (null when represented).\n"
        f"- editorial_sections has opening and integration, each a nonempty list of blocks with synthesis_ids and intended_mechanism. You choose these sources and mechanisms; Python will not rank or allocate them.\n"
        f"- Weave mandatory evidence into selected mechanisms; do not omit required coverage. No paragraph quota applies.\n\n"
        f"=== REQUIRED COVERAGE ===\n{json.dumps(handoff['reasoning_packet']['facts'].get('coverage', {}), ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== SELECTION CANDIDATE CATALOG ===\n{json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)}\n\n"
        f"=== APPROVED SYNTHESES ===\n{json.dumps(approved_synths, ensure_ascii=False, sort_keys=True, indent=2)}\n"
    )


def prepare_author_from_selection(handoff, selection, lang="pt-BR"):
    prepared_timing_parameters(handoff)
    blocks = plan_prospective_narrative_blocks(handoff, author_selection_plan=selection)
    prompt = (
        f"=== AUTHOR INSTRUCTIONS ===\n{humanization_instructions(lang)}\n\n"
        f"=== FROZEN SELECTION ===\n{json.dumps(selection, ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== PROSPECTIVE BLOCK PLAN ===\n{json.dumps(blocks, ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(handoff['reasoning_packet'], ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, sort_keys=True)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    prompt += "\n" + EXPLICIT_PROSE_INSTRUCTIONS
    return {"stage": "awaiting_author", "packet_id": handoff["packet_id"], "block_plan": blocks, "author_prompt": prompt}


def validate_frozen_inputs(handoff, birth, profile):
    """Authenticate the requested birth/configuration without another chart calculation."""
    from .pipeline import _packet_id
    from .policy import policy_manifest
    from .exceptions import LineageMismatchError
    instant, horizon, timing = prepared_timing_parameters(handoff)
    expected = _packet_id(birth, profile, policy_manifest(), instant, horizon, timing)
    if handoff.get('packet_id') != expected:
        raise LineageMismatchError('Birth/profile/configuration does not match frozen packet_id')


def require_deliverable(qa):
    """A failed or incomplete QA result must never produce a publication artifact."""
    from .exceptions import BenchmarkIntegrityError
    if qa.get('publication_approved') is not True or qa.get('relationship_fidelity_errors') != []:
        raise BenchmarkIntegrityError('Publication or technical fidelity gate failed')
    for name in ('barnum_risk', 'grandiosity_risk', 'medicalization_risk'):
        risk = qa.get(name)
        if not isinstance(risk, dict) or risk.get('share') != 0.0:
            raise BenchmarkIntegrityError(f'Editorial gate failed: {name}')


EXPLICIT_PROSE_INSTRUCTIONS = '''Return ONLY JSON with exactly packet_id and blocks.
blocks is an ordered list of objects with exactly section_id, kind, content, synthesis_ids, claim_ids, timing_ids.
kind is paragraph, list_item or subheading. content contains that single block without a Markdown prefix or blank-line-separated extra blocks.
Select sources explicitly for every block from the corresponding frozen section. claim_ids must be [].
Do not calculate hashes or source bindings; deterministic rendering handles those.
Use as many blocks as distinct reader value requires. Never borrow a source merely to pass validation.
'''


def build_reviewer_prompt(handoff, block_plan, author_payload, provenance, scope, lang='pt-BR'):
    from .reasoning import humanization_verifier_instructions
    return (humanization_verifier_instructions(lang) + '\n' + EXPLICIT_PROSE_INSTRUCTIONS +
            '\nThe Selection plan is immutable. Your source authority is limited to Author-materialized sources in each section.\n' +
            json.dumps({'reasoning_packet': handoff['reasoning_packet'], 'manifest': handoff['reader_domain_manifest'],
                        'block_plan': block_plan, 'author_blocks': author_payload, 'provenance': provenance,
                        'author_scope': scope}, ensure_ascii=False, sort_keys=True))


def validate_saved_block_plan(handoff, saved):
    from .benchmark_integrity import require_equal
    compiled = plan_prospective_narrative_blocks(handoff, author_selection_plan=saved['selection_plan'])
    require_equal(saved, compiled, 'saved prospective block plan')
    return compiled


def build_reviewer_preflight(handoff, block_plan, lang='pt-BR'):
    """Diagnostic instructions only; the executable prompt requires Author output."""
    from .reasoning import humanization_verifier_instructions
    return ('Not an executable Reviewer request: wait for validated Author output and materialized scope.\n' +
            humanization_verifier_instructions(lang) + '\n' + json.dumps(
                {'block_plan': block_plan, 'reasoning_packet': handoff['reasoning_packet'],
                 'manifest': handoff['reader_domain_manifest']}, ensure_ascii=False, sort_keys=True))
