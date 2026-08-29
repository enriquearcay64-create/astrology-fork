"""Constrained astrological reasoning between facts and human prose.

This module does not calculate astrology and it does not call a remote model.
It builds the closed factual packet, validates model-authored deductions, and
offers a deterministic fallback plan for the local CLI.  A high-reasoning LLM
uses the same packet to make the actual holistic choices at freedom levels 2–3.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
import re
from typing import Dict, Iterable, List, Optional, Sequence

from .config import BODY_LABELS, PRIMARY_BODIES
from .models import Claim, ReasonedSynthesis, to_primitive
from .safe_view import SafeInterpretiveChart
from .semantics import PLANET_FUNCTIONS, PLANET_SHORT_FUNCTIONS, planet_function_primitives, theme_label
from .localization import localization_audit


ASPECT_FUNCTIONS = {
    "conjunction": "concentration and inseparability",
    "sextile": "available coordination and experiment",
    "square": "friction that asks for adjustment",
    "trine": "ease that can become habitual",
    "quincunx": "recalibration between unlike functions",
    "opposition": "polarity and negotiation across contexts",
}
ASPECT_FUNCTIONS_PT = {
    "conjunction": "concentração e inseparabilidade",
    "sextile": "coordenação disponível e experimentação",
    "square": "fricção que pede ajuste",
    "trine": "fluidez que pode tornar-se automática",
    "quincunx": "recalibração entre funções diferentes",
    "opposition": "polaridade e negociação entre contextos",
}
PROHIBITED_EXTENSIONS = [
    "trauma específico", "diagnóstico", "evento inevitável", "biografia inventada",
    "morte", "doença", "gravidez", "divórcio", "falência",
]
REASONING_CLASSES = {"single_structural_factor", "integrated_pattern", "theme_interaction", "natal_timing_interaction"}
CONFIDENCE = {"light", "moderate", "strong"}
ASPECT_OPERATIONS = {
    "conjunction": "concentration",
    "sextile": "available_coordination",
    "square": "friction",
    "trine": "low_resistance",
    "quincunx": "adjustment",
    "opposition": "polarity",
}
SIGN_LABELS_PT = {"Aries": "Áries", "Taurus": "Touro", "Gemini": "Gêmeos", "Cancer": "Câncer", "Leo": "Leão", "Virgo": "Virgem", "Libra": "Libra", "Scorpio": "Escorpião", "Sagittarius": "Sagitário", "Capricorn": "Capricórnio", "Aquarius": "Aquário", "Pisces": "Peixes"}
OUTER_PLANETS = frozenset({"uranus", "neptune", "pluto"})
PERSONALIZING_BODIES = frozenset({"sun", "moon", "mercury", "venus", "mars"})


def build_reasoning_packet(
    chart: SafeInterpretiveChart,
    hierarchy: Dict[str, Dict[str, object]],
    claims: Iterable[Claim],
    timing: Dict[str, object] | None = None,
    timeline: List[Dict[str, object]] | None = None,
    developmental_intervals: List[Dict[str, object]] | None = None,
    language: str = "pt-BR",
    localization_profile: object | None = None,
    packet_id: str | None = None,
) -> Dict[str, object]:
    """Create a closed-world factual packet for constrained LLM reasoning."""
    lang = "pt" if language.startswith("pt") else "en"
    functions = PLANET_FUNCTIONS[lang]
    allowed_claims = [claim for claim in claims if claim.status == "allowed"]
    aspects = []
    for aspect in chart.aspects:
        if aspect.left not in PRIMARY_BODIES or aspect.right not in PRIMARY_BODIES:
            continue
        aspects.append({
            "id": aspect.id,
            "bodies": [aspect.left, aspect.right],
            "planet_functions": [functions.get(aspect.left, aspect.left), functions.get(aspect.right, aspect.right)],
            "aspect": aspect.kind,
            "aspect_function": (ASPECT_FUNCTIONS_PT if lang == "pt" else ASPECT_FUNCTIONS)[aspect.kind],
            "orb": aspect.orb,
            "applying": aspect.applying,
        })
    structural_bodies = [
        {"body": body, **value}
        for body, value in hierarchy.items()
        if value["prominence"] in {"strong", "moderate"} or "asc_ruler" in value["roles"] or "configuration_focal" in value["roles"]
    ]
    structural_bodies.sort(key=lambda item: (item["prominence"] != "strong", item["body"]))
    house_context = [
        {
            "body": body,
            "placidus_house": placement.placidus_house,
        }
        for body, placement in chart.house_placements.items()
        if body in PRIMARY_BODIES
    ]
    timing_evidence = _timing_evidence(timing, timeline, developmental_intervals)
    # These are already selected, typed records. They are candidates for reader
    # prose, not an additional timing ranking or a coverage obligation.
    reader_timing_candidates = [
        {"id": item["id"], "kind": item["kind"]}
        for item in timing_evidence
    ]
    configurations = [dict(item.data) for item in chart.factors if item.kind == "configuration"]
    promoted_configurations = _promoted_configurations(configurations, hierarchy)
    node_axis = next((to_primitive(item) for item in chart.factors if item.kind == "natal_node_axis"), None)
    coverage = {
        "required_primary_planets": [body for body in PRIMARY_BODIES if body in chart.positions],
        "ascendant_required": any(item.kind == "ascendant" for item in chart.factors),
        "chart_ruler_required": any(item.kind == "chart_ruler" for item in chart.factors),
        "natal_node_axis_required": node_axis is not None,
        "detected_configuration_ids": [item["id"] for item in configurations],
        "promoted_configuration_ids": [item["id"] for item in promoted_configurations],
        "rule": "Coverage is mandatory but verbosity is adaptive. A structural group may be reused contextually, but its group_id is one evidence family and one full structural explanation.",
        "required_evidence": {
            **{f"planet.{body}": [f"position.{body}"] for body in PRIMARY_BODIES if body in chart.positions},
            **({"ascendant": ["ascendant.natal"]} if any(item.kind == "ascendant" for item in chart.factors) else {}),
            **({"chart_ruler": ["chart_ruler.natal"]} if any(item.kind == "chart_ruler" for item in chart.factors) else {}),
            **({"natal_node_axis": ["node_axis.natal"]} if node_axis else {}),
            **{f"configuration.{item['id']}": [item["id"]] for item in promoted_configurations},
        },
    }
    return {
        "packet_id": packet_id,
        "reasoning_freedom": {
            "level_0_calculation": "closed; no LLM choice",
            "level_1_technical_inference": "closed factual packet only",
            "level_2_astrological_synthesis": "free combination of listed facts; every deduction cites 1–5 factor ids",
            "level_3_narrative": "free voice, order, examples and transitions; no new astrological facts",
            "level_4_biography": "blocked without user-provided context",
        },
        "facts": {
            "data_reliability": chart.stability,
            "structural_bodies": structural_bodies,
            "aspects": aspects,
            "conditions": [to_primitive(item) for item in chart.factors if item.kind == "planetary_condition"],
            "safe_house_context": house_context,
            "conditional_house_context": [asdict(item) for item in chart.conditional_house_scenarios.values()],
            "angle_contacts": [to_primitive(item) for item in chart.angle_contacts],
            "allowed_claims": [to_primitive(item) for item in allowed_claims],
            "timing": timing or {},
            "timing_evidence": timing_evidence,
            "reader_timing_candidates": reader_timing_candidates,
            "positions": [to_primitive(item) for item in chart.factors if item.kind == "position" and item.bodies[0] in PRIMARY_BODIES],
            "natal_node_axis": node_axis,
            "configurations": configurations,
            "coverage": coverage,
        },
        "hard_boundaries": {
            "may_use_only_factor_ids": sorted(_evidence_ids(chart)),
            "may_use_only_timing_ids": sorted(item["id"] for item in timing_evidence),
            "may_not_infer": PROHIBITED_EXTENSIONS,
            "conditional_house_policy": "Do not use conditional house context as central evidence. It may be disclosed as a conditional alternative only.",
            "counterweight_policy": "Counterweights are candidates, not conclusions. Use one only when it materially qualifies the cited proposition or domain.",
            "timing_context_policy": "Selected typed timing records are optional reader candidates, not mandatory coverage. Retain one in prose only when it supports a useful, specific human field linked to natal evidence; every timing statement must cite an authorised timing evidence id.",
            "configuration_reuse_policy": "A configuration may be cited in more than one synthesis only for a genuinely distinct role. Its group_id remains one structural evidence family: reuse cannot raise confidence, prominence, support count or evidence-family count, and the full configuration explanation appears once.",
            "localization_policy": "Localization may change language and examples, never factor weights, personality or prediction.",
        },
        "localized_rendering_context": localization_audit(localization_profile).get("rendering_context"),
    }


def validate_reasoned_syntheses(
    items: Sequence[ReasonedSynthesis],
    chart: SafeInterpretiveChart,
    claims: Optional[Iterable[Claim]] = None,
    timing_evidence_ids: Optional[Iterable[str]] = None,
) -> List[ReasonedSynthesis]:
    """Synthesis Judge: validate provenance and conservative semantic fit.

    This is deliberately not a claim of scientific proof.  It catches a
    deduction that is disconnected from its cited semantic units before prose
    is considered by the separate Narrative Judge.
    """
    known = _evidence_ids(chart)
    timing_ids = set(timing_evidence_ids or [])
    claim_map = {claim.id: claim for claim in (claims or []) if claim.status == "allowed"}
    output: List[ReasonedSynthesis] = []
    for item in items:
        errors: List[str] = []
        cited = list(item.primary_factors) + list(item.modifiers) + list(item.counterweights)
        if not item.primary_factors:
            errors.append("missing_primary_factors")
        if any(factor not in known and factor not in timing_ids for factor in cited):
            errors.append("unknown_or_unsafe_factor")
        if item.reasoning_class not in REASONING_CLASSES:
            errors.append("invalid_reasoning_class")
        if item.confidence_within_astrological_model not in CONFIDENCE:
            errors.append("invalid_confidence")
        if claim_map:
            if not item.source_claim_ids:
                errors.append("missing_source_claim_ids")
            if any(claim_id not in claim_map for claim_id in item.source_claim_ids):
                errors.append("unknown_source_claim_id")
            source_claims = [claim_map[claim_id] for claim_id in item.source_claim_ids if claim_id in claim_map]
            allowed_motifs = {motif for claim in source_claims for motif in claim.authorized_motifs}
            if any(motif not in allowed_motifs for motif in item.source_motif_ids):
                errors.append("source_motif_not_authorized_by_source_claim")
            allowed_primary = {factor for claim in source_claims for factor in claim.evidence}
            natal_primary = {factor for factor in item.primary_factors if factor not in timing_ids}
            if not natal_primary.issubset(allowed_primary):
                errors.append("primary_factor_not_authorized_by_source_claim")
            if not item.composition_operations:
                errors.append("missing_composition_operation")
            incompatible = _incompatible_operations(item, chart, timing_ids)
            if incompatible:
                errors.append("composition_operation_not_supported_by_factor")
            if _confidence_exceeds_sources(item, source_claims, chart):
                errors.append("confidence_exceeds_source_ceiling")
            for proposition in item.derived_propositions:
                sources = set(proposition.get("sources", []))
                if not sources or not sources.issubset(set(item.source_claim_ids)):
                    errors.append("untraceable_derived_proposition")
                    break
            if _semantic_disconnect(item, claim_map):
                errors.append("semantic_disconnect_from_sources")
            if _specificity_escalation(item):
                errors.append("biographical_specificity_escalation")
        # One aspect already composes two planetary functions; a lone house or
        # condition does not.
        if item.reasoning_class == "natal_timing_interaction" and (not any(factor in timing_ids for factor in item.primary_factors) or not any(factor not in timing_ids for factor in item.primary_factors)):
            errors.append("natal_timing_interaction_requires_natal_and_timing_evidence")
        if item.reasoning_class != "single_structural_factor" and len(set(item.primary_factors)) < 2 and not any(factor.startswith("aspect.") for factor in item.primary_factors):
            errors.append("insufficient_composition_support")
        configuration_factors = {factor.id: factor for factor in chart.factors if factor.kind == "configuration"}
        if any(factor in configuration_factors for factor in item.primary_factors):
            from .structure import detect_configurations
            detected = {str(record["id"]): record for record in detect_configurations(chart.semantic_chart())}
            for factor_id in set(item.primary_factors).intersection(configuration_factors):
                factor = configuration_factors[factor_id]
                if detected.get(factor_id) != factor.data:
                    errors.append("invalid_configuration_provenance")
        folded = " ".join([item.observation, item.alternative_reading, *item.possible_expressions]).casefold()
        if any(token in folded for token in ("diagnóstico", "diagnosis", "trauma", "morte", "death", "doença", "disease", "vai acontecer", "will happen")):
            errors.append("prohibited_extension_in_reasoning")
        item.verification_errors = errors
        item.status = "blocked" if errors else "allowed"
        output.append(item)
    return output


def _timing_evidence(
    timing: Dict[str, object] | None,
    timeline: List[Dict[str, object]] | None = None,
    developmental_intervals: List[Dict[str, object]] | None = None,
) -> List[Dict[str, object]]:
    """Expose timing windows as closed, typed evidence for premium reasoning."""
    if not timing:
        return []
    evidence: List[Dict[str, object]] = []
    selected_transits = set(timing.get("current_phase", {}).get("selected_transit_ids", []))
    for event in timing.get("modern_stream", {}).get("major_transits", []):
        if event.get("id") not in selected_transits:
            continue
        activation = str(event.get("activation_instance", ""))
        if activation:
            evidence.append({
                "id": f"timing.activation.{activation}", "kind": "activation_instance",
                "transit_body": event.get("transit_body"), "target": event.get("target"),
                "aspect": event.get("aspect"), "window_start": event.get("window_start"),
                "window_end": event.get("window_end"), "exact_at": event.get("exact_at"),
                "closest_approach_at": event.get("closest_approach_at"), "perfected": event.get("perfected"),
            })
    profection = timing.get("traditional_stream", {})
    if profection.get("status") not in {"conditional", "unavailable"} and profection.get("time_lord"):
        evidence.append({
            "id": f"timing.profection.{profection['start']}", "kind": "annual_profection",
            "house": profection.get("house"), "sign": profection.get("sign"), "time_lord": profection.get("time_lord"),
            "window_start": profection.get("start"), "window_end": profection.get("end"),
        })
    for kind, records in (
        ("secondary_progression", timing.get("current_phase", {}).get("progression_contacts", [])),
        ("solar_arc", timing.get("current_phase", {}).get("solar_arc_contacts", [])),
    ):
        for index, record in enumerate(records, 1):
            evidence.append({
                "id": f"timing.{kind}.{record['body']}.{record['aspect']}.{record['target']}.{index}", "kind": kind,
                **dict(record),
            })
    phase = _selected_timeline_phase(timing, timeline or [])
    if phase:
        evidence.append({
            "id": f"timing.timeline.{phase['range'].replace('–', '_')}", "kind": "timeline_phase",
            "range": phase["range"], "activation_instances": [item.get("activation_instance") for item in phase.get("activations", [])],
        })
    interval = _selected_developmental_interval(timing, developmental_intervals or [])
    if interval:
        evidence.append({
            "id": f"timing.developmental.{interval['id']}", "kind": "developmental_interval",
            "interval_id": interval["id"], "age_range": interval["age_range"],
            "window_start": interval["window_start"], "window_end": interval["window_end"],
            "activation_instances": [item.get("activation_instance") for item in interval.get("activations", [])],
        })
    return evidence


def _selected_timeline_phase(timing: Dict[str, object], timeline: List[Dict[str, object]]) -> Dict[str, object] | None:
    age = int(float(timing.get("modern_stream", {}).get("progressions", {}).get("age_years", -1)))
    return next((item for item in timeline if len(bounds := re.findall(r"\d+", str(item.get("range", "")))) == 2 and int(bounds[0]) <= age <= int(bounds[1])), None)


def _selected_developmental_interval(timing: Dict[str, object], intervals: List[Dict[str, object]]) -> Dict[str, object] | None:
    if not intervals:
        return None
    age = float(timing.get("modern_stream", {}).get("progressions", {}).get("age_years", -1))
    def start(item: Dict[str, object]) -> float:
        return float(str(item["age_range"]).split("–")[0])
    def end(item: Dict[str, object]) -> float:
        return float(str(item["age_range"]).split("–")[1])
    active = next((item for item in intervals if start(item) <= age <= end(item)), None)
    if active:
        return active
    future = [item for item in intervals if start(item) > age]
    return min(future, key=start) if future else max(intervals, key=end)


def _promoted_configurations(configurations: List[Dict[str, object]], hierarchy: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    """Choose a material subset and one representative per structural family."""
    ranked = sorted(
        configurations,
        key=lambda item: (0 if item.get("kind") == "stellium_placidus_house" else 1, str(item["id"])),
    )
    promoted: List[Dict[str, object]] = []
    seen_families = set()
    for item in ranked:
        family = str(item.get("group_id") or item["id"])
        if family in seen_families:
            continue
        members = [hierarchy.get(str(body), {}) for body in item.get("bodies", [])]
        material_members = sum(member.get("prominence") in {"strong", "moderate"} for member in members)
        focal = str(item.get("apex", ""))
        focal_material = focal and hierarchy.get(focal, {}).get("prominence") in {"strong", "moderate"}
        if focal_material or material_members >= 2:
            promoted.append(item)
            seen_families.add(family)
    return promoted


def _incompatible_operations(item: ReasonedSynthesis, chart: SafeInterpretiveChart, timing_ids: set[str]) -> bool:
    aspects = {aspect.id: aspect for aspect in chart.aspects}
    factor_kinds = {factor.id: factor.kind for factor in chart.factors}
    supported = set()
    for factor_id in item.primary_factors:
        if factor_id in aspects:
            supported.add(ASPECT_OPERATIONS[aspects[factor_id].kind])
        elif factor_kinds.get(factor_id) in {"placidus_house", "house_system_robustness"}:
            supported.add("contextualization")
        elif factor_id in timing_ids:
            supported.add("timing_activation")
        else:
            supported.add("contextualization")
    if item.counterweights:
        supported.add("qualification")
    return any(operation not in supported for operation in item.composition_operations)


def _confidence_exceeds_sources(item: ReasonedSynthesis, source_claims: Sequence[Claim], chart: SafeInterpretiveChart) -> bool:
    """A conservative ceiling: strong needs strong source plus structural support."""
    ordinal = {"light": 1, "moderate": 2, "strong": 3}
    claimed = ordinal[item.confidence_within_astrological_model]
    source_ceiling = max((ordinal.get(claim.astrological_support, 0) for claim in source_claims), default=0)
    # The hard ceiling is intentionally narrow: this guard prevents a High
    # pass from calling weak evidence *strong*. Moderate synthesis may emerge
    # from several light sources and remains a reviewer judgement.
    if item.confidence_within_astrological_model != "strong":
        return False
    if source_ceiling < ordinal["strong"]:
        return True
    structural_modifier = any(modifier.startswith("hierarchy.") for modifier in item.modifiers)
    multiple_sources = len(set(item.source_claim_ids)) >= 2 or len(set(item.primary_factors)) >= 2
    return not (structural_modifier or multiple_sources)


def _semantic_disconnect(item: ReasonedSynthesis, claim_map: Dict[str, Claim]) -> bool:
    """Cheap adversarial gate, not a substitute for a model-based judge."""
    source_claims = [claim_map[claim_id] for claim_id in item.source_claim_ids if claim_id in claim_map]
    # A house-only topic is contextual by definition and may legitimately be
    # worded through its topical theme rather than aspect vocabulary.
    if source_claims and all(claim.type == "topical_tendency" for claim in source_claims):
        return False
    source = " ".join(
        [claim_map[claim_id].statement + " " + claim_map[claim_id].theme.replace("_", " ") for claim_id in item.source_claim_ids if claim_id in claim_map]
        + [motif.replace("_", " ") for claim_id in item.source_claim_ids if claim_id in claim_map for motif in claim_map[claim_id].authorized_motifs]
    )
    proposed = " ".join([item.observation, *[str(value.get("text", "")) for value in item.derived_propositions]])
    source_tokens = _semantic_tokens(source)
    proposed_tokens = _semantic_tokens(proposed)
    # A conservative derived proposition should retain at least one meaningful
    # semantic anchor from the claims it says it composes.
    return bool(source_tokens and proposed_tokens and not source_tokens.intersection(proposed_tokens))


def _specificity_escalation(item: ReasonedSynthesis) -> bool:
    text = " ".join([item.observation, *item.possible_expressions, *[str(value.get("text", "")) for value in item.derived_propositions]]).casefold()
    return bool(re.search(r"\b(você (?:é|trabalha|casará|vai)|you (?:are|work|will marry)|quando era criança|your childhood|seu pai|sua mãe)\b", text))


def _semantic_tokens(value: str) -> set[str]:
    stopwords = {"de", "da", "do", "e", "em", "a", "o", "the", "and", "of", "in", "is", "a", "an", "this", "that"}
    return {token for token in re.findall(r"[^\W\d_]+", value.casefold()) if len(token) > 3 and token not in stopwords}


def compose_reasoned_syntheses(
    chart: SafeInterpretiveChart,
    themes: List[Dict[str, object]],
    claims: Iterable[Claim],
    hierarchy: Dict[str, Dict[str, object]],
    language: str = "pt-BR",
) -> List[Dict[str, object]]:
    """Create evidence-rich starting points, not prewritten report paragraphs."""
    allowed = [claim for claim in claims if claim.status == "allowed"]
    by_theme: Dict[str, List[Claim]] = defaultdict(list)
    for claim in allowed:
        by_theme[claim.theme].append(claim)
    by_evidence_body = _evidence_bodies(chart)
    candidates: List[ReasonedSynthesis] = []
    for theme in themes:
        theme_id = str(theme["id"])
        source = by_theme.get(theme_id, [])
        primary = [evidence for claim in source for evidence in claim.evidence][:5]
        bodies = {body for evidence in primary for body in by_evidence_body.get(evidence, set())}
        modifiers = []
        for body in sorted(bodies):
            roles = hierarchy.get(body, {}).get("roles", [])
            if roles:
                modifiers.append(f"hierarchy.{body}")
        # Hierarchy ids are virtual but deterministic members of the packet.
        modifier_ids = [item for item in modifiers[:3]]
        counterweights = [item for claim in source for item in claim.counterweights][:3]
        confidence = str(theme["support_level"])
        structural = [body for body in bodies if hierarchy.get(body, {}).get("prominence") == "strong"]
        if len(primary) == 1:
            reasoning_class = "single_structural_factor"
        elif counterweights:
            reasoning_class = "integrated_pattern"
        else:
            reasoning_class = "theme_interaction" if len(bodies) >= 2 else "integrated_pattern"
        observation = _fallback_observation(theme_id, bodies, structural, chart, primary, language)
        source_claim_ids = [claim.id for claim in source]
        source_motif_ids = list(dict.fromkeys(motif for claim in source for motif in claim.authorized_motifs))
        operations = _composition_operations(chart, primary, counterweights)
        candidates.append(ReasonedSynthesis(
            id=f"reasoned.{theme_id}",
            observation=observation,
            primary_factors=primary,
            modifiers=modifier_ids,
            counterweights=counterweights,
            reasoning_class=reasoning_class,
            confidence_within_astrological_model=confidence,
            possible_expressions=_possible_expression_seeds(chart, bodies, language),
            alternative_reading=_alternative_reading(theme_id, language),
            prohibited_extensions=list(PROHIBITED_EXTENSIONS),
            source_claim_ids=source_claim_ids,
            source_motif_ids=source_motif_ids,
            composition_operations=operations,
            derived_propositions=[{"text": observation, "sources": source_claim_ids[:3]}],
            narrative_moves=_narrative_moves(chart, primary, bodies, language),
        ))
    # hierarchy.* is a valid packet id, although it is not a raw Chart factor.
    checked = validate_reasoned_syntheses(candidates, chart, allowed)
    for item in checked:
        virtual = [factor for factor in item.modifiers if factor.startswith("hierarchy.")]
        if virtual and item.status == "blocked" and "unknown_or_unsafe_factor" in item.verification_errors:
            item.verification_errors.remove("unknown_or_unsafe_factor")
            item.status = "allowed" if not item.verification_errors else "blocked"
    return [to_primitive(item) for item in checked]


def build_narrative_plan(
    themes: List[Dict[str, object]],
    syntheses: List[Dict[str, object]],
    language: str = "pt-BR",
    chart: Optional[SafeInterpretiveChart] = None,
    chart_signature: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Plan the reading from the signature; themes are editorial categories."""
    usable = [item for item in syntheses if item["status"] == "allowed"]
    by_id = {item["id"].removeprefix("reasoned."): item for item in usable}
    signature = chart_signature or {"mode": "distributed", "theme_priorities": []}
    priority = {str(item["theme"]): float(item["score"]) for item in signature.get("theme_priorities", [])}
    ordered = sorted(
        (theme for theme in themes if str(theme["id"]) in by_id),
        key=lambda theme: (-priority.get(str(theme["id"]), 0.0), -{"strong": 3, "moderate": 2, "light": 1}.get(str(theme.get("support_level")), 0), str(theme["id"])),
    )
    # A central signature privileges connected material; a distributed chart
    # deliberately keeps several independent centres visible.
    anchor_bodies = set(signature.get("central_dynamic", {}).get("bodies", []))
    evidence_bodies = _evidence_bodies(chart) if chart else {}
    if signature.get("mode") == "central" and anchor_bodies:
        connected = [theme for theme in ordered if any(anchor_bodies.intersection(evidence_bodies.get(factor, set())) for factor in by_id[str(theme["id"])]["primary_factors"])]
        leading = (connected + [theme for theme in ordered if theme not in connected])[:3]
    else:
        leading = []
        represented: set[str] = set()
        for theme in ordered:
            bodies = set().union(*(evidence_bodies.get(factor, set()) for factor in by_id[str(theme["id"])]["primary_factors"]))
            if len(leading) < 2 or not bodies.issubset(represented):
                leading.append(theme)
                represented.update(bodies)
            if len(leading) >= 4:
                break
    opening = _signature_opening(signature, by_id, language)
    references = []
    seen_bodies: Dict[str, str] = {}
    for theme in leading:
        synthesis = by_id[str(theme["id"])]
        for factor in synthesis["primary_factors"]:
            bodies = evidence_bodies.get(factor, set())
            if factor.startswith("hierarchy."):
                bodies = {factor.removeprefix("hierarchy.")}
            for body in bodies:
                if body in seen_bodies and seen_bodies[body] != theme["id"]:
                    references.append({"from": theme["id"], "to": seen_bodies[body], "reason": "shared structural factor"})
                else:
                    seen_bodies[body] = str(theme["id"])
    return {
        "opening": opening,
        "themes": [str(theme["id"]) for theme in leading],
        "secondary_themes": [str(theme["id"]) for theme in ordered if theme not in leading],
        "sequence": "chart signature → differentiated themes → relevant areas → timing → integration",
        "cross_references": references[:6],
        "avoid_repetition": ["Explain each structural factor once; later sections reference it briefly.", "Do not force a light/shadow formula where a nuance or counterweight is more useful."],
        "technical_details_to_hide": ["raw aspect labels unless they aid orientation and are immediately translated", "house-system labels when convergent", "orb values", "registry identifiers"],
        "integration_move": by_id[str(leading[0]["id"])]["narrative_moves"]["integration"] if leading else "",
        "life_area_priorities": signature.get("domain_priorities", []),
    }


def _composition_operations(chart: SafeInterpretiveChart, primary: Iterable[str], counterweights: Iterable[str]) -> List[str]:
    aspects = {item.id: item for item in chart.aspects}
    operations = []
    for factor_id in primary:
        aspect = aspects.get(factor_id)
        if aspect:
            operations.append(ASPECT_OPERATIONS[aspect.kind])
        elif factor_id.startswith("house."):
            operations.append("contextualization")
    if counterweights:
        operations.append("qualification")
    return list(dict.fromkeys(operations)) or ["contextualization"]


def build_chart_signature(
    chart: SafeInterpretiveChart,
    hierarchy: Dict[str, Dict[str, object]],
    structure: Dict[str, object],
    syntheses: List[Dict[str, object]],
    language: str = "pt-BR",
) -> Dict[str, object]:
    """Compact, traceable architecture used to plan rather than template prose."""
    usable = [item for item in syntheses if item.get("status") == "allowed"]
    evidence_bodies = _evidence_bodies(chart)
    body_to_syntheses: Dict[str, set[str]] = defaultdict(set)
    for synthesis in usable:
        for factor_id in synthesis["primary_factors"]:
            # A configuration's members may be contextually reused across
            # syntheses, but the structural family cannot become independent
            # connection/support votes for each member.
            if factor_id.startswith("configuration."):
                continue
            for body in evidence_bodies.get(factor_id, set()):
                body_to_syntheses[body].add(str(synthesis["id"]))
    role_weight = {"asc_ruler": 2, "configuration_focal": 2, "core_angle_contact": 2, "final_dispositor": 2}
    body_scores: Dict[str, int] = {}
    for body, details in hierarchy.items():
        prominence = {"strong": 3, "moderate": 1, "light": 0}.get(str(details.get("prominence")), 0)
        roles = set(details.get("roles", []))
        role_score = min(3, sum(role_weight.get(role, 0) for role in roles))
        connection_score = min(3, max(0, len(body_to_syntheses.get(body, set())) - 1))
        # Number of traditional rulerships is a property of the table, not a
        # chart-specific sign of centrality.  Keep rulership for topical work,
        # but do not reward Mercury/Venus/Mars/Jupiter/Saturn by construction.
        body_scores[body] = prominence + role_score + connection_score
    structural_bodies = sorted(
        (body for body in hierarchy if body_scores[body] > 0),
        key=lambda body: (-body_scores[body], -len(body_to_syntheses.get(body, set())), body),
    )
    anchors = [
        body for body in structural_bodies
        if len(body_to_syntheses.get(body, set())) >= 3
        and body_scores[body] >= 5
        and (hierarchy[body].get("prominence") == "strong" or set(hierarchy[body].get("roles", [])) & set(role_weight))
        and _has_personalizing_link(chart, body)
    ]
    mode = "central" if anchors else "distributed"
    selected_bodies = anchors[:3] if anchors else structural_bodies[:4]
    selected_syntheses = sorted(set().union(*(body_to_syntheses[body] for body in selected_bodies))) if selected_bodies else []
    central_dynamic = {
        "status": "supported" if anchors else "distributed",
        "bodies": selected_bodies,
        "syntheses": selected_syntheses[:5],
        "logic": "a structural body connects three or more authorised syntheses" if anchors else "no structural body connects three or more authorised syntheses; retain multiple centres",
        "connection_counts": {body: len(body_to_syntheses.get(body, set())) for body in selected_bodies},
    }
    counterweights = sorted({item for synthesis in usable for item in synthesis.get("counterweights", [])})
    contradictions = [item["id"] for item in usable if "polarity" in item.get("composition_operations", []) or "friction" in item.get("composition_operations", [])]
    domain_scores: Dict[int, Dict[str, object]] = {}
    if chart.house_placements:
        for body, placement in chart.house_placements.items():
            if body in body_scores:
                if placement.placidus_house is None:
                    continue
                item = domain_scores.setdefault(placement.placidus_house, {"house": placement.placidus_house, "score": 0, "bodies": []})
                item["score"] += body_scores[body]
                item["bodies"].append(body)
    strongest_domains = sorted(domain_scores.values(), key=lambda item: (-int(item["score"]), int(item["house"])))[:4]
    theme_priorities = []
    configuration_families = {
        factor.id: str(factor.data.get("group_id") or factor.id)
        for factor in chart.factors if factor.kind == "configuration"
    }
    seen_configuration_families = set()
    for synthesis in usable:
        theme = str(synthesis["id"]).removeprefix("reasoned.")
        scoring_factors = []
        for factor in synthesis["primary_factors"]:
            family = configuration_families.get(factor)
            if family and family in seen_configuration_families:
                continue
            if family:
                seen_configuration_families.add(family)
            scoring_factors.append(factor)
        bodies = sorted(set().union(*(evidence_bodies.get(factor, set()) for factor in scoring_factors)))
        score = sum(sorted((body_scores.get(body, 0) for body in bodies), reverse=True)[:2]) + min(2, len(scoring_factors))
        theme_priorities.append({"theme": theme, "score": score, "bodies": bodies, "source_syntheses": [synthesis["id"]]})
    theme_priorities.sort(key=lambda item: (-int(item["score"]), str(item["theme"])))
    core_factor_ids = []
    for synthesis_id in selected_syntheses:
        synthesis = next((item for item in usable if item["id"] == synthesis_id), None)
        if synthesis:
            core_factor_ids.extend(synthesis["primary_factors"])
    return {
        "mode": mode,
        "core_factors": list(dict.fromkeys(core_factor_ids))[:12],
        "structural_bodies": structural_bodies[:8],
        "structural_scores": {body: body_scores[body] for body in structural_bodies[:8]},
        "central_dynamic": central_dynamic,
        "modifying_factors": [factor.id for factor in chart.factors if factor.kind == "planetary_condition"][:12],
        "counterweights": counterweights,
        "major_contradictions": contradictions,
        "strongest_domains": strongest_domains,
        "domain_priorities": strongest_domains,
        "theme_priorities": theme_priorities,
        "configuration_summary": structure.get("configurations", []),
    }


def build_natal_timing_interactions(
    chart: SafeInterpretiveChart,
    hierarchy: Dict[str, Dict[str, object]],
    claims: Iterable[Claim],
    themes: List[Dict[str, object]],
    timing: Dict[str, object] | None,
) -> List[Dict[str, object]]:
    """Relate a timing activation to natal structure without forecasting."""
    if not timing:
        return []
    theme_by_body: Dict[str, set[str]] = defaultdict(set)
    bodies_by_evidence = _evidence_bodies(chart)
    for claim in claims:
        if claim.status == "allowed":
            for evidence in claim.evidence:
                for body in bodies_by_evidence.get(evidence, set()):
                    theme_by_body[body].add(claim.theme)
    result = []
    for activation in timing["modern_stream"]["major_transits"][:12]:
        transit_body = str(activation["transit_body"])
        target = str(activation["target"])
        target_roles = hierarchy.get(target, {}).get("roles", [])
        transit_roles = hierarchy.get(transit_body, {}).get("roles", [])
        structural = bool({"asc_ruler", "configuration_focal", "core_angle_contact", "final_dispositor"} & set(target_roles + transit_roles))
        natal_themes = sorted(theme_by_body.get(target, set()) | theme_by_body.get(transit_body, set()))
        result.append({
            "activation_instance": activation["activation_instance"],
            "transit_body": transit_body,
            "target": target,
            "natal_structural_relevance": "structural" if structural else "contextual",
            "natal_roles": {"transit_body": transit_roles, "target": target_roles},
            "natal_themes": natal_themes,
            "duration": {"start": activation["window_start"], "end": activation["window_end"]},
            "reliability": "conditional" if target in chart.conditional_house_scenarios else "stable",
            "interpretation_limit": "This describes symbolic amplification of an existing natal factor, not a predicted event.",
        })
    return result


def humanization_instructions(language: str = "pt-BR") -> str:
    """Instructions for the high-freedom editorial pass, not a prose template."""
    if language.startswith("pt"):
        return (
            "Escreva em nossa voz: dirija-se predominantemente à pessoa em segunda pessoa natural, variando a construção quando "
            "a repetição ficar mecânica. Seja direto, psicologicamente perceptivo, priorize significado humano quando isso ajudar a clareza, emocionalmente legível, "
            "íntimo sem presumir biografia e de baixo jargão. Ao nomear astrologia, traduza imediatamente o termo para linguagem comum. "
            "Nas seções centrais, comece normalmente por um padrão psicologicamente reconhecível quando isso ajudar o leitor e revele em seguida "
            "a astrologia que o sustenta; não force essa ordem quando a estrutura astrológica for mais clara ou natural. Evite aberturas mecânicas "
            "como 'você pode notar'. Para as três ou quatro dinâmicas principais, desenvolva, quando realmente acrescentar sentido, mecanismo interno, "
            "expressão reconhecível, recurso, tensão ou modo de falha, contrapeso material e interação com outro fator importante — sem transformar isso "
            "numa fórmula repetitiva. Prefira linguagem vivida a repetir registro semântico como função, coordenação disponível, estrutura, critério ou "
            "possibilidade. Interpretação vem antes de coaching. No timing, comece pelo campo humano ativado e então apresente trânsito, profecção, "
            "progressão, arco ou ciclo; use somente candidatos tipados selecionados quando puderem sustentar um campo específico. Não use voz acadêmica, "
            "legalista ou de QA interno. Não acrescente fator, biografia, evento, diagnóstico ou certeza. Preserve citações internas de fatores para "
            "verificação, mas não as exponha no corpo principal."
        )
    return (
        "Write in our house voice: address the reader predominantly in natural second person, varying construction whenever repeated "
        "direct address would become mechanical. Be direct, psychologically perceptive, prioritize human meaning when that improves clarity, emotionally legible, "
        "intimate but non-presumptive, and low-jargon. When astrology is named, translate the term immediately into plain language. "
        "In central sections, normally lead with a psychologically recognizable pattern when that helps the reader, then reveal the supporting "
        "astrology; do not force that order when the astrological structure is clearer or more natural. Avoid mechanical openings such as 'you may notice'. "
        "For the three or four leading dynamics, develop an inner mechanism, recognizable expression, resource, tension or failure mode, material "
        "counterweight, and interaction with another important factor when each genuinely adds meaning, never as a repeated formula. Prefer lived language "
        "over semantic-register repetition such as function, available coordination, structure, criterion, or possibility. Interpretation comes before coaching. "
        "For timing, lead with the human field being activated and then name the transit, profection, progression, arc, or cycle; use selected typed candidates "
        "only when they support a specific field. Use no academic, legalistic, or internal-QA voice. Do not add a factor, biography, event, diagnosis or certainty. "
        "Preserve internal factor citations for verification, but do not expose them in the main reading."
    )


def humanization_verifier_instructions(language: str = "pt-BR") -> str:
    """Contract for the semantic before/after verifier used with an LLM.

    Exact semantic equivalence is not a regex problem.  The deterministic
    layer supplies the factor-id and safety checks; a verifier model compares
    the structured synthesis with the final paragraph before publication.
    """
    if language.startswith("pt"):
        return (
            "Compare cada parágrafo final com sua ReasonedSynthesis autorizada. Aprove somente se o sentido central, "
            "o nível de certeza e os limites forem equivalentes; confirme também que contradições válidas não foram achatadas "
            "e que cada contrapeso realmente qualifica a proposição. A prosa pode ser mais humana, mas não pode incluir novo "
            "fator, casa condicional como fato, biografia, diagnóstico, evento ou previsão. Exija voz direta, psicologicamente legível, "
            "íntima sem presunção, de baixo jargão, com tradução imediata de termos astrológicos e interpretação antes de coaching; "
            "rejeite texto tecnicamente correto mas abstrato, psicologicamente genérico, emocionalmente plano, excessivamente cauteloso, "
            "fácil de trocar por outro mapa ou guiado por coaching. Nas dinâmicas centrais, exija desenvolvimento reconhecível do mecanismo "
            "sem impor uma fórmula de abertura ou parágrafo. Retenha timing ou desenvolvimento somente quando a evidência tipada selecionada "
            "sustentar um campo humano útil e específico ligado ao natal; caso contrário, corte-o em vez de preencher espaço. Faça o swap test "
            "conceitual em cada parágrafo principal e corrija genericidade por seleção ou mecanismo, nunca inventando detalhes de vida."
        )
    return (
        "Compare each final paragraph with its authorised ReasonedSynthesis. Approve only if core meaning, certainty and "
        "limits are equivalent; also confirm that valid contradictions were not flattened and every counterweight materially "
        "qualifies the proposition. Prose may be more human but cannot add a factor, treat a conditional house as fact, add "
        "biography, diagnosis, event or forecast. Require direct, psychologically legible, intimate-but-non-presumptive, low-jargon "
        "voice with immediate plain-language translation of astrology and interpretation before coaching; reject prose that is technically correct "
        "but abstract, psychologically generic, emotionally flat, overly cautious, easily swapped to another chart, or coaching-led. For central dynamics, "
        "require recognizable development of the mechanism without imposing a fixed opening or paragraph formula. Retain timing or developmental material only "
        "when selected typed evidence supports a useful, specific human field linked to natal evidence; otherwise cut it rather than pad. Apply a conceptual "
        "swap test to each major paragraph and correct genericity through selection or mechanism, never invented life detail."
    )


def llm_reasoning_instructions() -> str:
    return (
        "Use only the closed factual packet. Select a few connected mechanisms rather than enumerating factors. You may create a "
        "derived_claim when it cites 1–5 existing factor ids, preserves their semantic ancestry, names an alternative reading and "
        "stays at symbolic/behavioral possibility level. Treat registry motifs as boundaries, not report sentences. Preserve valid "
        "contradictions. Treat counterweights as candidates and retain one only when it materially qualifies the proposition or its "
        "domain. Do not centralize an outer planet without a personalizing link, turn conditional house context into central evidence, "
        "or invent timing outside typed timing evidence. Return ReasonedSynthesis objects before writing prose."
    )


def _has_personalizing_link(chart: SafeInterpretiveChart, body: str) -> bool:
    """Outer planets need a personal-planet or core-angle link to anchor a signature."""
    if body not in OUTER_PLANETS:
        return True
    if any(contact.body == body and contact.angle in {"asc", "dsc", "mc", "ic"} for contact in chart.angle_contacts):
        return True
    return any(
        body in (aspect.left, aspect.right)
        and bool(({aspect.left, aspect.right} - {body}) & PERSONALIZING_BODIES)
        for aspect in chart.aspects
    )


def _evidence_ids(chart: SafeInterpretiveChart) -> set[str]:
    return {factor.id for factor in chart.factors} | {aspect.id for aspect in chart.aspects} | {f"hierarchy.{body}" for body in chart.positions}


def _evidence_bodies(chart: SafeInterpretiveChart) -> Dict[str, set[str]]:
    result: Dict[str, set[str]] = {}
    for aspect in chart.aspects:
        result[aspect.id] = {aspect.left, aspect.right}
    for factor in chart.factors:
        result[factor.id] = set(factor.bodies) & set(chart.positions)
    return result


def _fallback_observation(theme: str, bodies: set[str], structural: List[str], chart: SafeInterpretiveChart, primary: List[str], language: str) -> str:
    """Readable deterministic fallback; a reasoning model may replace it.

    It identifies the particular mechanism instead of concatenating every
    planetary function that happens to support a theme.
    """
    label = theme_label(theme, language)
    lang = "pt" if language.startswith("pt") else "en"
    functions = PLANET_SHORT_FUNCTIONS[lang]
    aspect_by_id = {item.id: item for item in chart.aspects}
    chosen = next((aspect_by_id[item] for item in primary if item in aspect_by_id), None)
    labels = BODY_LABELS[lang]
    if chosen:
        left = labels.get(chosen.left, chosen.left if lang == "pt" else chosen.left.title())
        right = labels.get(chosen.right, chosen.right if lang == "pt" else chosen.right.title())
        left_sign = chart.positions[chosen.left].sign
        right_sign = chart.positions[chosen.right].sign
        if lang == "pt":
            left_sign, right_sign = SIGN_LABELS_PT.get(left_sign, left_sign), SIGN_LABELS_PT.get(right_sign, right_sign)
        connector = " e " if lang == "pt" else " and "
        left_function = connector.join(planet_function_primitives(chosen.left, language)[:2])
        right_function = connector.join(planet_function_primitives(chosen.right, language)[:2])
        dynamic = (ASPECT_FUNCTIONS_PT if lang == "pt" else ASPECT_FUNCTIONS)[chosen.kind]
        if lang == "pt":
            return (
                f"Neste mapa, o tema **{label}** ganha uma coloração própria: {left} em {left_sign} liga {left_function} a {right} em {right_sign}, {right_function}, "
                f"por uma dinâmica de {dynamic}."
            )
        return (
            f"In this chart, **{label}** takes on a particular colour: {left} in {left_sign} links {left_function} with {right} in {right_sign}, {right_function}, "
            f"through a dynamic of {dynamic}."
        )
    relevant = [functions.get(body, body) for body in sorted(bodies)]
    relationships = []
    for factor in primary:
        aspect = aspect_by_id.get(factor)
        if aspect:
            relationships.append((ASPECT_FUNCTIONS_PT if lang == "pt" else ASPECT_FUNCTIONS)[aspect.kind])
    relationship = relationships[0] if relationships else ("condição estrutural" if lang == "pt" else "structural condition")
    joined = ", ".join(relevant[:2]) or ("fatores disponíveis" if lang == "pt" else "available factors")
    if language.startswith("pt"):
        return f"Neste mapa, **{label}** é sustentado por {joined}, numa dinâmica de {relationship}."
    return f"In this chart, **{label}** is supported by {joined}, through a dynamic of {relationship}."


def _possible_expression_seeds(chart: SafeInterpretiveChart, bodies: set[str], language: str) -> List[str]:
    lang = "pt" if language.startswith("pt") else "en"
    functions = PLANET_FUNCTIONS[lang]
    values = [functions.get(body, body) for body in sorted(bodies)]
    if lang == "pt":
        return [f"uma escolha que põe em relação {', '.join(values[:2])}", "uma resposta diferente em contexto de pressão", "um padrão a observar antes de generalizar"]
    return [f"a choice that brings together {', '.join(values[:2])}", "a different response under pressure", "a pattern to observe before generalising"]


def _alternative_reading(theme: str, language: str) -> str:
    if language.startswith("pt"):
        return f"O mesmo conjunto pode ser mais situacional do que central; observe se {theme_label(theme, language)} aparece apenas em contextos específicos."
    return f"The same set may be situational rather than central; observe whether {theme_label(theme, language)} appears only in specific contexts."


def _narrative_moves(chart: SafeInterpretiveChart, primary: List[str], bodies: set[str], language: str) -> Dict[str, str]:
    lang = "pt" if language.startswith("pt") else "en"
    aspect_by_id = {item.id: item for item in chart.aspects}
    chosen = next((aspect_by_id[item] for item in primary if item in aspect_by_id), None)
    selected_bodies = [chosen.left, chosen.right] if chosen else sorted(bodies)
    functions = [PLANET_SHORT_FUNCTIONS[lang].get(body, body) for body in selected_bodies]
    left = functions[0] if functions else ("o padrão" if lang == "pt" else "the pattern")
    right = functions[1] if len(functions) > 1 else left
    kinds = [aspect_by_id[item].kind for item in primary if item in aspect_by_id]
    dynamic = (ASPECT_FUNCTIONS_PT if lang == "pt" else ASPECT_FUNCTIONS).get(kinds[0], "coordenação" if lang == "pt" else "coordination") if kinds else ("contexto tópico" if lang == "pt" else "topical context")
    kind = kinds[0] if kinds else "context"
    if lang == "pt":
        moves = {
            "conjunction": (f"dar uma função concreta à combinação entre {left} e {right}", f"misturar {left} e {right} até que uma necessidade fale no lugar da outra", f"nomear onde {left} termina e onde {right} começa antes de decidir"),
            "sextile": (f"criar pequenas experiências em que {left} apoia {right}", f"esperar que uma oportunidade entre {left} e {right} se resolva sem iniciativa", f"escolher uma experiência curta e rever o que {left} ensinou a {right}"),
            "square": (f"usar o atrito entre {left} e {right} para aperfeiçoar uma escolha", f"agir como se {left} e {right} precisassem vencer um ao outro", f"adiar a resposta final até formular um critério que faça justiça a {left} e {right}"),
            "trine": (f"aproveitar a fluidez entre {left} e {right} em algo que exija consistência", f"confiar tanto na facilidade entre {left} e {right} que o padrão deixa de ser examinado", f"usar um contexto mais exigente para descobrir como {left} e {right} funcionam quando não há conforto"),
            "quincunx": (f"fazer ajustes pequenos e frequentes entre {left} e {right}", f"forçar {left} e {right} a operar no mesmo ritmo", f"recalibrar uma decisão depois de observar qual função ficou sem espaço"),
            "opposition": (f"dar tempos e contextos distintos a {left} e {right}", f"transformar uma alternância entre {left} e {right} em uma escolha de tudo ou nada", f"negociar uma proporção concreta entre {left} e {right} em vez de escolher um lado permanente"),
            "context": (f"observar como {left} se expressa quando o contexto pede {right}", f"tratar um contexto tópico como destino", f"usar a área indicada como pergunta, não como conclusão"),
        }
    else:
        moves = {
            "conjunction": (f"give the combination of {left} and {right} a concrete job", f"blend {left} and {right} until one need speaks for the other", f"name where {left} ends and {right} begins before deciding"),
            "sextile": (f"create small experiments in which {left} supports {right}", f"wait for an opportunity between {left} and {right} to resolve itself without initiative", f"choose one short experiment and review what {left} taught {right}"),
            "square": (f"use the friction between {left} and {right} to refine a choice", f"act as though {left} and {right} must defeat each other", f"delay the final response until a criterion respects both {left} and {right}"),
            "trine": (f"use the ease between {left} and {right} in something that requires consistency", f"trust the ease between {left} and {right} so much that the pattern goes unexamined", f"use a more demanding context to learn how {left} and {right} work without comfort"),
            "quincunx": (f"make small, frequent adjustments between {left} and {right}", f"force {left} and {right} to operate at the same rhythm", f"recalibrate a decision after noticing which function lost room"),
            "opposition": (f"give {left} and {right} different times and contexts", f"turn alternation between {left} and {right} into an all-or-nothing choice", f"negotiate a concrete proportion between {left} and {right} rather than choosing one permanent side"),
            "context": (f"observe how {left} appears when the context calls for {right}", f"treat a topical context as destiny", f"use the indicated area as a question rather than a conclusion"),
        }
    constructive, pressure, integration = moves[kind]
    return {"constructive": constructive, "pressure": pressure, "integration": integration}


def _signature_opening(signature: Dict[str, object], syntheses: Dict[str, Dict[str, object]], language: str) -> Dict[str, object]:
    """Make the opening answer to the signature, not a theme rank."""
    bodies = [str(body) for body in signature.get("central_dynamic", {}).get("bodies", [])]
    source_ids = [str(item) for item in signature.get("central_dynamic", {}).get("syntheses", [])]
    priority_sources = [str(source_id) for item in signature.get("theme_priorities", [])[:1] for source_id in item.get("source_syntheses", [])]
    if priority_sources:
        # Align the opening with the first signature-led theme selected by the
        # planner; alphabetical evidence ids must never choose the story.
        source_ids = priority_sources + [item for item in source_ids if item not in priority_sources]
    lang = "pt" if language.startswith("pt") else "en"
    labels = BODY_LABELS[lang]
    label_for = lambda body: labels.get(body, body if lang == "pt" else body.title())
    source = next((syntheses.get(item.removeprefix("reasoned.")) for item in source_ids if syntheses.get(item.removeprefix("reasoned."))), None)
    opening_theme = theme_label(source_ids[0].removeprefix("reasoned."), language) if source_ids else ("a primeira dinâmica" if language.startswith("pt") else "the first dynamic")
    if signature.get("mode") == "central" and bodies:
        body_text = ", ".join(label_for(body) for body in bodies[:2])
        observation = str(source.get("observation", "")) if source else ""
        functions = PLANET_SHORT_FUNCTIONS[lang]
        function_text = " e ".join(functions.get(body, label_for(body).casefold()) for body in bodies[:2]) if lang == "pt" else " and ".join(functions.get(body, label_for(body).casefold()) for body in bodies[:2])
        if language.startswith("pt"):
            text = f"A arquitetura central do mapa volta sobretudo a **{body_text}**: a relação entre {function_text} organiza a entrada em **{opening_theme}**. {observation}".strip()
        else:
            text = f"The map's central architecture returns chiefly to **{body_text}**: the relationship between {function_text} opens first through **{opening_theme}**. {observation}".strip()
        return {"status": "supported", "mode": "central", "structural_bodies": bodies, "source_syntheses": source_ids, "observation": text}
    body_text = ", ".join(label_for(body) for body in bodies[:3])
    if language.startswith("pt"):
        text = f"Este mapa não pede uma explicação única: **{body_text or 'vários fatores estruturais'}** formam centros diferentes, que precisam ser lidos em relação sem serem reduzidos a uma só história."
    else:
        text = f"This chart does not ask for one total explanation: **{body_text or 'several structural factors'}** form different centres that need to be read in relation without being reduced to one story."
    return {"status": "distributed", "mode": "distributed", "structural_bodies": bodies, "source_syntheses": source_ids, "observation": text}
