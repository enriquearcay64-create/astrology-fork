"""Single orchestration entrypoint with strict fact-to-language boundaries."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import re
from typing import Dict, Iterable, Optional

from .consultation import answer_question, classify_question, render_consultation
from .config import PREMIUM_HANDOFF_CONTRACT_VERSION
from .engine import calculate_chart
from .hierarchy import calculate_hierarchy
from .interpretation import build_compensation_hypotheses, build_paradoxes
from .localization import localization_audit
from .models import BirthData, Claim, LocalizationProfile, ReasonedSynthesis, to_primitive
from .privacy import record_boundaries
from .report import render_report, technical_appendix
from .reasoning import build_chart_signature, build_narrative_plan, build_natal_timing_interactions, build_reasoning_packet, compose_reasoned_syntheses, humanization_instructions, humanization_verifier_instructions, llm_reasoning_instructions, validate_reasoned_syntheses
from .safe_view import build_safe_interpretive_view
from .semantics import build_claims, verify_claims
from .structure import chart_structure
from .synthesis import synthesize_themes
from .timing import cross_technique_timing, developmental_intervals, life_timeline, upcoming_eclipses


def analyse_birth_chart(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "executive", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366, question_topics: Iterable[int] = ()) -> Dict[str, object]:
    language = profile.preferred_language if profile else "pt-BR"
    raw_chart = calculate_chart(birth)
    packet_id = _packet_id(birth, profile, raw_chart.policy, as_of, horizon_days, include_timing)
    chart = build_safe_interpretive_view(raw_chart)
    semantic_chart = chart.semantic_chart()
    structure = chart_structure(semantic_chart)
    natal_hierarchy = calculate_hierarchy(semantic_chart)
    claims = verify_claims(build_claims(semantic_chart, language=language), semantic_chart)
    # Coverage facts make every required component available to Premium
    # Complete, but they must not mechanically inflate thematic support or
    # flatten hierarchy.  Existing aspect/house/angle synthesis remains the
    # prominence selector; the Author can add a coverage synthesis where it is
    # needed and its paragraph provenance then verifies it.
    thematic_claims = [
        claim for claim in claims
        if claim.id.startswith(("claim.aspect.", "claim.house.", "claim.angle."))
    ]
    themes = synthesize_themes(thematic_claims, language)
    paradoxes = build_paradoxes(themes, language)
    compensations = build_compensation_hypotheses(structure, language)
    timing = cross_technique_timing(semantic_chart, as_of, horizon_days) if include_timing else None
    active_bodies = timing["current_phase"]["active_bodies"] if timing else []
    current_hierarchy = calculate_hierarchy(semantic_chart, question_topics=question_topics, active_bodies=active_bodies) if timing or question_topics else natal_hierarchy
    timeline = life_timeline(semantic_chart) if include_timing and report_depth in ("deep", "technical") else None
    intervals = developmental_intervals(semantic_chart, timeline) if timeline else None
    reasoned_syntheses = compose_reasoned_syntheses(chart, themes, thematic_claims, natal_hierarchy, language)
    chart_signature = build_chart_signature(chart, natal_hierarchy, structure, reasoned_syntheses, language)
    narrative_plan = build_narrative_plan(themes, reasoned_syntheses, language, chart, chart_signature)
    natal_timing_interactions = build_natal_timing_interactions(chart, natal_hierarchy, claims, themes, timing)
    if timing:
        timing["current_phase"]["natal_timing_interactions"] = natal_timing_interactions[:6]
    reasoning_packet = build_reasoning_packet(chart, natal_hierarchy, claims, timing, timeline, intervals, language, profile, packet_id)
    report = render_report(report_depth, chart, claims, themes, natal_hierarchy, timing, timeline, paradoxes, compensations, structure, profile, reasoned_syntheses, narrative_plan, intervals, chart_signature)
    return {
        "packet_id": packet_id, "chart": raw_chart.as_dict(), "safe_interpretive_view": to_primitive(chart), "hierarchy": natal_hierarchy, "current_hierarchy": current_hierarchy,
        "chart_structure": structure, "claims": to_primitive(claims), "themes": themes,
        "paradoxes": paradoxes, "compensation_hypotheses": compensations,
        "reasoned_synthesis": reasoned_syntheses, "chart_signature": chart_signature, "narrative_plan": narrative_plan,
        "reasoning_packet": reasoning_packet, "llm_reasoning_instructions": llm_reasoning_instructions(), "humanization_instructions": humanization_instructions(language),
        "humanization_verifier_instructions": humanization_verifier_instructions(language),
        "timing": timing, "timeline": timeline, "developmental_intervals": intervals,
        "progressions": timing["modern_stream"]["progressions"] if timing else None,
        "solar_arcs": timing["modern_stream"]["solar_arcs"] if timing else None,
        "upcoming_eclipses": upcoming_eclipses(as_of, 4) if include_timing else None,
        "report_mode": "deterministic_fallback", "localization_audit": localization_audit(profile), "privacy_boundaries": record_boundaries(), "report": report,
    }


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_PARAGRAPH_SOURCE_FIELDS = ("paragraph_sha256", "synthesis_ids", "claim_ids", "timing_ids")


def _premium_handoff_contract() -> Dict[str, object]:
    """One serialized source-map contract for both Premium guard stages."""
    return {
        "version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "author_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "reasoned_syntheses", "draft_report", "paragraph_sources", "synthesis_bundle_sha256", "draft_report_sha256",
        ],
        "reviewer_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "synthesis_bundle_sha256", "reviewed_draft_sha256", "verdict", "corrections_made", "remaining_warnings",
            "final_report", "final_report_sha256", "paragraph_sources",
        ],
        "paragraph_source_required_fields": list(_PARAGRAPH_SOURCE_FIELDS),
        "paragraph_source_rules": {
            "synthesis_mode": "one_or_more_approved_synthesis_ids_and_empty_claim_ids",
            "direct_claim_mode": "exactly_one_allowed_direct_paragraph_renderable_claim_id_and_empty_synthesis_ids_and_timing_ids",
            "direct_claim_semantic_boundary": "atomic_placidus_house_ruler_route_only; ruler_context_or_other_composition_requires_approved_reasoned_synthesis",
        },
        "reasoned_synthesis_fields": list(ReasonedSynthesis.__dataclass_fields__),
    }


def _packet_id(birth: BirthData, profile: Optional[LocalizationProfile], policy: Dict[str, object], as_of: Optional[datetime], horizon_days: int, include_timing: bool) -> str:
    """Identity for one methodologically meaningful premium calculation."""
    return _canonical_hash({
        "birth": to_primitive(birth), "localization_profile": to_primitive(profile) if profile else None,
        "versions": {
            **{key: policy.get(key) for key in ("methodology_version", "schema_version", "semantic_registry_version", "timing_version")},
            "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        },
        "as_of": as_of.isoformat() if as_of else None, "horizon_days": horizon_days, "include_timing": include_timing,
    })


def consult(birth: BirthData, question: str, profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None) -> Dict[str, object]:
    intent = classify_question(question)
    core = analyse_birth_chart(birth, profile, "executive", True, as_of, question_topics=intent["houses"])
    language = profile.preferred_language if profile else "pt-BR"
    answer = answer_question(question, [Claim(**claim) for claim in core["claims"]], language, core["timing"], core["current_hierarchy"], core["safe_interpretive_view"], core["themes"], core["reasoned_synthesis"], core["chart_signature"])
    return {"question": question, "consultation": answer, "report": render_consultation(question, answer, language), "methodology_version": core["chart"]["methodology_version"], "query_hierarchy": core["current_hierarchy"], "timing": core["timing"]}


def prepare_premium_handoff(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "deep", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366) -> Dict[str, object]:
    """Debug handoff; normal Codex use follows the same stages internally."""
    _require_premium_birth_time(birth)
    if report_depth != "deep":
        raise ValueError("Premium Complete preparation requires report_depth='deep'.")
    core = analyse_birth_chart(birth, profile, "deep", include_timing, as_of, horizon_days)
    handoff_chart = build_safe_interpretive_view(calculate_chart(birth))
    handoff_contract = _premium_handoff_contract()
    handoff_contract_hash = _canonical_hash(handoff_contract)
    return {
        "stage": "reasoning_packet_ready",
        "premium_report_depth": "deep",
        "packet_id": core["packet_id"],
        "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "premium_handoff_contract": handoff_contract,
        "premium_handoff_contract_sha256": handoff_contract_hash,
        "premium_required_for_publication": True,
        "deterministic_fallback_notice": "The local fallback is useful for tests and debugging. Do not label it as the premium report without the two High review passes.",
        "workflow": [
            "1. deterministic calculation and packet identity", "2. Premium Author creates one AuthorBundle", "3. Deterministic Provenance Guard",
            "4. independent Premium Reviewer edits to ReviewerBundle", "5. Publication Guard", "6. publish only if both guards pass",
        ],
        "reasoning_packet": core["reasoning_packet"],
        "chart_signature": core["chart_signature"],
        "narrative_plan": core["narrative_plan"],
        "timeline": core["timeline"],
        "developmental_intervals": core["developmental_intervals"],
        # The client appendix is concise deterministic reference data; the
        # established full technical renderer remains an internal audit sidecar.
        "technical_appendix": technical_appendix(handoff_chart, core["hierarchy"], [], core["timing"], core["chart_structure"], profile),
        "audit_sidecar": render_report("technical", handoff_chart, [], [], core["hierarchy"], core["timing"], core["timeline"], [], [], core["chart_structure"], profile, [], core["narrative_plan"], core["developmental_intervals"], core["chart_signature"]),
        "reasoned_synthesis_schema": list(ReasonedSynthesis.__dataclass_fields__),
        "author_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "reasoned_syntheses": "list[ReasonedSynthesis]", "draft_report": "string", "paragraph_sources": [{"paragraph_sha256": "sha256", "synthesis_ids": ["reasoned.id"], "claim_ids": ["claim.id"], "timing_ids": ["timing.activation.id"]}], "synthesis_bundle_sha256": "sha256", "draft_report_sha256": "sha256"},
        "reviewer_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "synthesis_bundle_sha256": "sha256", "reviewed_draft_sha256": "sha256", "verdict": "approved|blocked", "corrections_made": ["string"], "remaining_warnings": ["string"], "final_report": "string", "final_report_sha256": "sha256", "paragraph_sources": "same mapping contract"},
        "sol_high_instruction": llm_reasoning_instructions(),
        "author_voice_instruction": core["humanization_instructions"],
        "narrative_judge_instruction": humanization_verifier_instructions(profile.preferred_language if profile else "pt-BR"),
    }


def validate_premium_syntheses(birth: BirthData, synthesis_payload: Iterable[Dict[str, object]], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True) -> Dict[str, object]:
    """Deterministically gate manually authored High syntheses; no API call."""
    core = analyse_birth_chart(birth, profile, "deep", include_timing, as_of, horizon_days)
    allowed_fields = set(ReasonedSynthesis.__dataclass_fields__)
    items = [ReasonedSynthesis(**{key: value for key, value in item.items() if key in allowed_fields}) for item in synthesis_payload]
    chart = build_safe_interpretive_view(calculate_chart(birth))
    timing_ids = [item["id"] for item in core["reasoning_packet"]["facts"]["timing_evidence"]]
    checked = validate_reasoned_syntheses(items, chart, [Claim(**claim) for claim in core["claims"]], timing_ids)
    approved = [to_primitive(item) for item in checked if item.status == "allowed"]
    signature = build_chart_signature(chart, core["hierarchy"], core["chart_structure"], approved, profile.preferred_language if profile else "pt-BR")
    plan = build_narrative_plan(core["themes"], approved, profile.preferred_language if profile else "pt-BR", chart, signature)
    return {"stage": "provenance_syntheses_checked", "packet_id": core["packet_id"], "approved": len(approved) == len(checked), "reasoned_synthesis": [to_primitive(item) for item in checked], "synthesis_bundle_sha256": _canonical_hash(approved), "chart_signature": signature, "narrative_plan": plan, "timing_evidence_ids": timing_ids, "allowed_claims": [claim for claim in core["claims"] if claim.get("status") == "allowed"], "coverage": core["reasoning_packet"]["facts"]["coverage"], "next_step": "A Premium Reviewer may use only approved syntheses and typed timing IDs."}


def _substantive_paragraphs(report: str) -> List[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", report) if block.strip()]
    skipped = ("#", "---", "*leitura simbólica", "*symbolic reading", "> **percurso", "> **path")
    result = []
    for block in blocks:
        folded = block.casefold()
        if folded.startswith(skipped) or block.startswith("|") or all(line.lstrip().startswith("-") for line in block.splitlines()):
            continue
        if len(re.findall(r"\w+", block)) >= 12:
            result.append(block)
    return result


def _validated_paragraph_sources(report: object, paragraph_sources: object, approved_ids: set[str], allowed_claims: Dict[str, Claim], timing_ids: set[str]) -> tuple[List[str], List[Dict[str, object]]]:
    if not isinstance(report, str) or not report.strip():
        return ["missing_final_report"], []
    if not isinstance(paragraph_sources, list):
        return ["missing_paragraph_source_map"], []
    expected_hashes = list(dict.fromkeys(_canonical_hash(paragraph) for paragraph in _substantive_paragraphs(report)))
    expected_hash_set = set(expected_hashes)
    by_hash: Dict[str, Dict[str, object]] = {}
    errors = []
    for source in paragraph_sources:
        if not isinstance(source, dict):
            errors.append("invalid_paragraph_source_map")
            continue
        if any(field not in source for field in _PARAGRAPH_SOURCE_FIELDS):
            errors.append("premium_handoff_source_row_missing_field")
            continue
        paragraph_hash = str(source.get("paragraph_sha256"))
        if paragraph_hash in by_hash:
            errors.append("duplicate_paragraph_source_map")
            if by_hash[paragraph_hash] != source:
                errors.append("conflicting_duplicate_paragraph_source_map")
            continue
        by_hash[paragraph_hash] = source
    source_hashes = set(by_hash)
    if expected_hash_set - source_hashes:
        errors.append("interpretive_paragraph_without_source_map")
    if source_hashes - expected_hash_set:
        errors.append("orphan_paragraph_source_map")
    for paragraph_hash in expected_hash_set.intersection(source_hashes):
        source = by_hash[paragraph_hash]
        synthesis_values, claim_values, timing_values = source.get("synthesis_ids"), source.get("claim_ids"), source.get("timing_ids")
        if not all(isinstance(item, list) and all(isinstance(value, str) for value in item) for item in (synthesis_values, claim_values, timing_values)):
            errors.append("invalid_paragraph_source_references")
            continue
        synthesis_ids, claim_ids, timing_refs = set(synthesis_values), set(claim_values), set(timing_values)
        if len(synthesis_ids) != len(synthesis_values) or len(claim_ids) != len(claim_values) or len(timing_refs) != len(timing_values):
            errors.append("duplicated_paragraph_source_reference")
        if synthesis_ids:
            if claim_ids or not synthesis_ids.issubset(approved_ids):
                errors.append("untraceable_paragraph_source")
        elif claim_ids:
            if (
                len(claim_values) != 1
                or timing_refs
                or any(claim_id not in allowed_claims or not allowed_claims[claim_id].direct_paragraph_renderable for claim_id in claim_ids)
            ):
                errors.append("invalid_direct_claim_paragraph_source")
        else:
            errors.append("untraceable_paragraph_source")
        if not timing_refs.issubset(timing_ids):
            errors.append("invented_or_unapproved_timing_evidence")
    errors = list(dict.fromkeys(errors))
    return errors, ([] if errors else [by_hash[item] for item in expected_hashes])


def _validate_paragraph_sources(report: object, paragraph_sources: object, approved_ids: set[str], allowed_claims: Dict[str, Claim], timing_ids: set[str]) -> List[str]:
    return _validated_paragraph_sources(report, paragraph_sources, approved_ids, allowed_claims, timing_ids)[0]


def _validate_mandatory_coverage(report: object, paragraph_sources: object, approved_syntheses: Iterable[Dict[str, object]], coverage: object) -> List[str]:
    """Verify Premium Complete targets through existing paragraph provenance.

    This intentionally adds no parallel coverage framework: the existing
    source map is the contract, and a target is covered only when a substantive
    paragraph cites a synthesis that cites its deterministic evidence.
    """
    if not isinstance(paragraph_sources, list) or not isinstance(coverage, dict):
        return ["missing_mandatory_coverage_map"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict)}
    sourced_ids = {
        str(synthesis_id)
        for source in paragraph_sources if isinstance(source, dict)
        for synthesis_id in source.get("synthesis_ids", [])
    }
    sourced_factors = {
        str(factor)
        for synthesis_id in sourced_ids
        for factor in approved.get(synthesis_id, {}).get("primary_factors", [])
    }
    errors = []
    for target, factors in coverage.get("required_evidence", {}).items():
        if not set(map(str, factors)).intersection(sourced_factors):
            errors.append(f"missing_mandatory_coverage:{target}")
    return errors


def paragraph_source_template(report: str) -> List[Dict[str, object]]:
    """Return the exact substantial-paragraph hashes an Author must source."""
    return [
        {"paragraph_sha256": paragraph_hash, "synthesis_ids": [], "claim_ids": [], "timing_ids": []}
        for paragraph_hash in dict.fromkeys(_canonical_hash(paragraph) for paragraph in _substantive_paragraphs(report))
    ]


def _handoff_contract_errors(bundle: Dict[str, object], bundle_kind: str) -> List[str]:
    contract = _premium_handoff_contract()
    contract_hash = _canonical_hash(contract)
    errors = []
    required_key = f"{bundle_kind}_bundle_required_fields"
    for field in contract[required_key]:
        if field not in bundle:
            errors.append(f"premium_handoff_{bundle_kind}_bundle_missing_required_field:{field}")
    if bundle.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("premium_handoff_contract_version_mismatch")
    if bundle.get("premium_handoff_contract") != contract:
        errors.append("premium_handoff_contract_body_mismatch")
    if bundle.get("premium_handoff_contract_sha256") != contract_hash:
        errors.append("premium_handoff_contract_hash_mismatch")
    if "premium_handoff_contract" in bundle and _canonical_hash(bundle["premium_handoff_contract"]) != bundle.get("premium_handoff_contract_sha256"):
        errors.append("premium_handoff_contract_body_hash_mismatch")
    return errors


def validate_premium_author_bundle(birth: BirthData, author_bundle: Dict[str, object], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True) -> Dict[str, object]:
    """Deterministic Provenance Guard between the Author and Reviewer."""
    items = author_bundle.get("reasoned_syntheses", [])
    checked = validate_premium_syntheses(birth, items if isinstance(items, list) else [], profile, as_of, horizon_days, include_timing)
    errors = _handoff_contract_errors(author_bundle, "author")
    if author_bundle.get("packet_id") != checked["packet_id"]:
        errors.append("packet_id_mismatch")
    expected_synthesis_hash = _canonical_hash([item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"])
    if author_bundle.get("synthesis_bundle_sha256") != expected_synthesis_hash:
        errors.append("synthesis_bundle_hash_mismatch")
    draft = author_bundle.get("draft_report")
    if author_bundle.get("draft_report_sha256") != _canonical_hash(draft):
        errors.append("draft_report_hash_mismatch")
    approved_ids = {item["id"] for item in checked["reasoned_synthesis"] if item["status"] == "allowed"}
    allowed_claims = {item["id"]: Claim(**item) for item in checked["allowed_claims"]}
    source_errors, valid_sources = _validated_paragraph_sources(draft, author_bundle.get("paragraph_sources"), approved_ids, allowed_claims, set(checked["timing_evidence_ids"]))
    errors.extend(source_errors)
    errors.extend(_validate_mandatory_coverage(draft, valid_sources, checked["approved_reasoned_syntheses"] if "approved_reasoned_syntheses" in checked else [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"], checked.get("coverage")))
    if isinstance(draft, str) and _contains_prohibited_extension(draft):
        errors.append("prohibited_extension_in_author_draft")
    if not birth.birth_time_known:
        errors.append("premium_birth_time_required")
    return {"stage": "deterministic_provenance_guard", "approved": checked["approved"] and not errors, "verification_errors": list(dict.fromkeys(errors)), "packet_id": checked["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": _premium_handoff_contract(), "premium_handoff_contract_sha256": _canonical_hash(_premium_handoff_contract()), "approved_reasoned_syntheses": [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"], "allowed_claims": checked["allowed_claims"], "synthesis_bundle_sha256": expected_synthesis_hash, "draft_report_sha256": _canonical_hash(draft), "timing_evidence_ids": checked["timing_evidence_ids"], "coverage": checked.get("coverage"), "chart_signature": checked["chart_signature"], "narrative_plan": checked["narrative_plan"]}


def validate_premium_narrative(narrative_payload: Dict[str, object], provenance: Dict[str, object]) -> Dict[str, object]:
    """Check publication provenance after the separate human/High narrative judge.

    This is intentionally a structural and safety gate.  An attestation by a
    High Narrative Judge is required for semantic equivalence; token checks do
    not claim to prove it.
    """
    approved_ids = {str(item.get("id")) for item in provenance.get("approved_reasoned_syntheses", [])}
    report = narrative_payload.get("final_report")
    errors = [] if provenance.get("approved") else ["author_provenance_not_approved"]
    errors.extend(_handoff_contract_errors(narrative_payload, "reviewer"))
    if provenance.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("provenance_handoff_contract_version_mismatch")
    if provenance.get("premium_handoff_contract_sha256") != _canonical_hash(_premium_handoff_contract()):
        errors.append("provenance_handoff_contract_hash_mismatch")
    if provenance.get("premium_handoff_contract") != _premium_handoff_contract():
        errors.append("provenance_handoff_contract_body_mismatch")
    if narrative_payload.get("packet_id") != provenance.get("packet_id"):
        errors.append("packet_id_mismatch")
    if narrative_payload.get("synthesis_bundle_sha256") != provenance.get("synthesis_bundle_sha256"):
        errors.append("synthesis_bundle_hash_mismatch")
    if narrative_payload.get("reviewed_draft_sha256") != provenance.get("draft_report_sha256"):
        errors.append("reviewed_draft_hash_mismatch")
    if narrative_payload.get("verdict") != "approved":
        errors.append("reviewer_not_approved")
    if narrative_payload.get("final_report_sha256") != _canonical_hash(report):
        errors.append("final_report_hash_mismatch")
    allowed_claims = {str(item.get("id")): Claim(**item) for item in provenance.get("allowed_claims", []) if isinstance(item, dict) and item.get("status") == "allowed"}
    source_errors, valid_sources = _validated_paragraph_sources(report, narrative_payload.get("paragraph_sources"), approved_ids, allowed_claims, set(provenance.get("timing_evidence_ids", [])))
    errors.extend(source_errors)
    errors.extend(_validate_mandatory_coverage(report, valid_sources, provenance.get("approved_reasoned_syntheses", []), provenance.get("coverage")))
    if isinstance(report, str) and _contains_prohibited_extension(report):
        errors.append("prohibited_extension_in_final_narrative")
    return {
        "stage": "narrative_judged",
        "approved": not errors,
        "verification_errors": errors,
        "semantic_status": "reviewer_attested_not_deterministically_proven" if not errors else "not_publishable",
        "report": report if not errors else None,
    }


def _contains_prohibited_extension(text: str) -> bool:
    return bool(re.search(r"\b(trauma|diagn[oó]stico|diagnosis|morte|death|doen[cç]a|disease|gravidez|pregnancy|div[oó]rcio|divorce|fal[eê]ncia|bankruptcy|vai acontecer|will happen)\b", text, re.I))


def _require_premium_birth_time(birth: BirthData) -> None:
    if not birth.birth_time_known:
        raise ValueError("Premium beta requires a known local birth time. Use the limited safe deterministic reading when the time is unknown.")
