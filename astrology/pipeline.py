"""Single orchestration entrypoint with strict fact-to-language boundaries."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, Optional

from .consultation import answer_question, classify_question, render_consultation
from .engine import calculate_chart
from .hierarchy import calculate_hierarchy
from .interpretation import build_compensation_hypotheses, build_paradoxes
from .localization import localization_audit
from .models import BirthData, Claim, LocalizationProfile, to_primitive
from .privacy import record_boundaries
from .report import render_report
from .reasoning import build_narrative_plan, build_natal_timing_interactions, build_reasoning_packet, compose_reasoned_syntheses, humanization_instructions, humanization_verifier_instructions, llm_reasoning_instructions
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
    narrative_plan = build_narrative_plan(themes, reasoned_syntheses, language)
    natal_timing_interactions = build_natal_timing_interactions(chart, natal_hierarchy, claims, themes, timing)
    if timing:
        timing["current_phase"]["natal_timing_interactions"] = natal_timing_interactions[:6]
    reasoning_packet = build_reasoning_packet(chart, natal_hierarchy, claims, timing, language, profile)
    report = render_report(report_depth, chart, claims, themes, natal_hierarchy, timing, timeline, paradoxes, compensations, structure, profile, reasoned_syntheses, narrative_plan, intervals)
    return {
        "chart": raw_chart.as_dict(), "safe_interpretive_view": to_primitive(chart), "hierarchy": natal_hierarchy, "current_hierarchy": current_hierarchy,
        "chart_structure": structure, "claims": to_primitive(claims), "themes": themes,
        "paradoxes": paradoxes, "compensation_hypotheses": compensations,
        "reasoned_synthesis": reasoned_syntheses, "narrative_plan": narrative_plan,
        "reasoning_packet": reasoning_packet, "llm_reasoning_instructions": llm_reasoning_instructions(), "humanization_instructions": humanization_instructions(language),
        "humanization_verifier_instructions": humanization_verifier_instructions(language),
        "timing": timing, "timeline": timeline, "developmental_intervals": intervals,
        "progressions": timing["modern_stream"]["progressions"] if timing else None,
        "solar_arcs": timing["modern_stream"]["solar_arcs"] if timing else None,
        "upcoming_eclipses": upcoming_eclipses(as_of, 4) if include_timing else None,
        "localization_audit": localization_audit(profile), "privacy_boundaries": record_boundaries(), "report": report,
    }


def consult(birth: BirthData, question: str, profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None) -> Dict[str, object]:
    intent = classify_question(question)
    core = analyse_birth_chart(birth, profile, "executive", True, as_of, question_topics=intent["houses"])
    language = profile.preferred_language if profile else "pt-BR"
    answer = answer_question(question, [Claim(**claim) for claim in core["claims"]], language, core["timing"], core["current_hierarchy"], core["safe_interpretive_view"], core["themes"])
    return {"question": question, "consultation": answer, "report": render_consultation(question, answer, language), "methodology_version": core["chart"]["methodology_version"], "query_hierarchy": core["current_hierarchy"], "timing": core["timing"]}
