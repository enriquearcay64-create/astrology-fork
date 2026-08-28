"""Single orchestration entrypoint with strict fact-to-language boundaries."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Dict, Iterable, Optional

from .consultation import answer_question, classify_question, render_consultation
from .engine import calculate_chart
from .hierarchy import calculate_hierarchy
from .interpretation import build_compensation_hypotheses, build_paradoxes
from .localization import localization_audit
from .models import BirthData, Claim, LocalizationProfile, ReasonedSynthesis, to_primitive
from .privacy import record_boundaries
from .report import render_report
from .reasoning import build_chart_signature, build_narrative_plan, build_natal_timing_interactions, build_reasoning_packet, compose_reasoned_syntheses, humanization_instructions, humanization_verifier_instructions, llm_reasoning_instructions, validate_reasoned_syntheses
from .safe_view import build_safe_interpretive_view
from .semantics import build_claims, verify_claims
from .structure import chart_structure
from .synthesis import synthesize_themes
from .timing import cross_technique_timing, developmental_intervals, life_timeline, upcoming_eclipses


def analyse_birth_chart(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "executive", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366, question_topics: Iterable[int] = ()) -> Dict[str, object]:
    language = profile.preferred_language if profile else "pt-BR"
    raw_chart = calculate_chart(birth)
    chart = build_safe_interpretive_view(raw_chart)
    semantic_chart = chart.semantic_chart()
    structure = chart_structure(semantic_chart)
    natal_hierarchy = calculate_hierarchy(semantic_chart)
    claims = verify_claims(build_claims(semantic_chart, language=language), semantic_chart)
    themes = synthesize_themes(claims, language)
    paradoxes = build_paradoxes(themes, language)
    compensations = build_compensation_hypotheses(structure, language)
    timing = cross_technique_timing(semantic_chart, as_of, horizon_days) if include_timing else None
    active_bodies = timing["current_phase"]["active_bodies"] if timing else []
    current_hierarchy = calculate_hierarchy(semantic_chart, question_topics=question_topics, active_bodies=active_bodies) if timing or question_topics else natal_hierarchy
    timeline = life_timeline(semantic_chart) if include_timing and report_depth in ("deep", "technical") else None
    intervals = developmental_intervals(semantic_chart, timeline) if timeline else None
    reasoned_syntheses = compose_reasoned_syntheses(chart, themes, claims, natal_hierarchy, language)
    chart_signature = build_chart_signature(chart, natal_hierarchy, structure, reasoned_syntheses, language)
    narrative_plan = build_narrative_plan(themes, reasoned_syntheses, language, chart, chart_signature)
    natal_timing_interactions = build_natal_timing_interactions(chart, natal_hierarchy, claims, themes, timing)
    if timing:
        timing["current_phase"]["natal_timing_interactions"] = natal_timing_interactions[:6]
    reasoning_packet = build_reasoning_packet(chart, natal_hierarchy, claims, timing, language, profile)
    report = render_report(report_depth, chart, claims, themes, natal_hierarchy, timing, timeline, paradoxes, compensations, structure, profile, reasoned_syntheses, narrative_plan, intervals, chart_signature)
    return {
        "chart": raw_chart.as_dict(), "safe_interpretive_view": to_primitive(chart), "hierarchy": natal_hierarchy, "current_hierarchy": current_hierarchy,
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


def consult(birth: BirthData, question: str, profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None) -> Dict[str, object]:
    intent = classify_question(question)
    core = analyse_birth_chart(birth, profile, "executive", True, as_of, question_topics=intent["houses"])
    language = profile.preferred_language if profile else "pt-BR"
    answer = answer_question(question, [Claim(**claim) for claim in core["claims"]], language, core["timing"], core["current_hierarchy"], core["safe_interpretive_view"], core["themes"], core["reasoned_synthesis"], core["chart_signature"])
    return {"question": question, "consultation": answer, "report": render_consultation(question, answer, language), "methodology_version": core["chart"]["methodology_version"], "query_hierarchy": core["current_hierarchy"], "timing": core["timing"]}


def prepare_premium_handoff(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "executive", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366) -> Dict[str, object]:
    """Prepare the closed packet for a manual Sol High pass in Codex."""
    core = analyse_birth_chart(birth, profile, report_depth, include_timing, as_of, horizon_days)
    return {
        "stage": "reasoning_packet_ready",
        "premium_required_for_publication": True,
        "deterministic_fallback_notice": "The local fallback is useful for tests and debugging. Do not label it as the premium report without the two High review passes.",
        "workflow": [
            "1. deterministic calculation", "2. SafeInterpretiveChart", "3. claims", "4. ReasoningPacket",
            "5. Sol High returns structured ReasonedSynthesis JSON", "6. deterministic Synthesis Judge",
            "7. Sol High composes holistic narrative", "8. Sol High Narrative Judge pass",
            "9. final rendering", "10. publish only if both gates pass",
        ],
        "reasoning_packet": core["reasoning_packet"],
        "chart_signature": core["chart_signature"],
        "narrative_plan": core["narrative_plan"],
        "reasoned_synthesis_schema": list(ReasonedSynthesis.__dataclass_fields__),
        "narrative_submission_contract": {"report": "string", "paragraph_sources": [{"section": "string", "synthesis_ids": ["reasoned.id"]}], "narrative_judge": {"model": "gpt-5.6-sol", "verdict": "approved", "notes": "semantic equivalence reviewed"}},
        "sol_high_instruction": llm_reasoning_instructions(),
        "narrative_judge_instruction": humanization_verifier_instructions(profile.preferred_language if profile else "pt-BR"),
    }


def validate_premium_syntheses(birth: BirthData, synthesis_payload: Iterable[Dict[str, object]], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None) -> Dict[str, object]:
    """Deterministically gate manually authored High syntheses; no API call."""
    core = analyse_birth_chart(birth, profile, "executive", True, as_of)
    allowed_fields = set(ReasonedSynthesis.__dataclass_fields__)
    items = [ReasonedSynthesis(**{key: value for key, value in item.items() if key in allowed_fields}) for item in synthesis_payload]
    chart = build_safe_interpretive_view(calculate_chart(birth))
    checked = validate_reasoned_syntheses(items, chart, [Claim(**claim) for claim in core["claims"]])
    approved = [to_primitive(item) for item in checked if item.status == "allowed"]
    signature = build_chart_signature(chart, core["hierarchy"], core["chart_structure"], approved, profile.preferred_language if profile else "pt-BR")
    plan = build_narrative_plan(core["themes"], approved, profile.preferred_language if profile else "pt-BR", chart, signature)
    return {"stage": "synthesis_judged", "approved": len(approved) == len(checked), "reasoned_synthesis": [to_primitive(item) for item in checked], "chart_signature": signature, "narrative_plan": plan, "next_step": "Use Sol High to write prose from only the approved syntheses and attach a paragraph-to-synthesis source map for the separate Narrative Judge."}


def validate_premium_narrative(narrative_payload: Dict[str, object], synthesis_payload: Iterable[Dict[str, object]]) -> Dict[str, object]:
    """Check publication provenance after the separate human/High narrative judge.

    This is intentionally a structural and safety gate.  An attestation by a
    High Narrative Judge is required for semantic equivalence; token checks do
    not claim to prove it.
    """
    approved_ids = {str(item.get("id")) for item in synthesis_payload if item.get("status") == "allowed"}
    report = narrative_payload.get("report")
    judge = narrative_payload.get("narrative_judge", {})
    paragraphs = narrative_payload.get("paragraph_sources", [])
    errors = []
    if not isinstance(report, str) or not report.strip():
        errors.append("missing_final_report")
    if not isinstance(judge, dict) or judge.get("verdict") != "approved":
        errors.append("missing_high_narrative_judge_approval")
    if not isinstance(paragraphs, list) or not paragraphs:
        errors.append("missing_paragraph_source_map")
    for item in paragraphs if isinstance(paragraphs, list) else []:
        source_ids = set(item.get("synthesis_ids", [])) if isinstance(item, dict) else set()
        if not source_ids or not source_ids.issubset(approved_ids):
            errors.append("untraceable_paragraph_source")
            break
    if isinstance(report, str) and re.search(r"\b(trauma|diagn[oó]stico|diagnosis|morte|death|doen[cç]a|disease|gravidez|pregnancy|div[oó]rcio|divorce|fal[eê]ncia|bankruptcy|vai acontecer|will happen)\b", report, re.I):
        errors.append("prohibited_extension_in_final_narrative")
    return {
        "stage": "narrative_judged",
        "approved": not errors,
        "verification_errors": errors,
        "semantic_status": "high_judge_attested_not_deterministically_proven" if not errors else "not_publishable",
        "report": report if not errors else None,
    }
