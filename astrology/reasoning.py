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


READER_DOMAIN_DEFINITIONS = (
    {"id": "identity_presence", "en": "Central identity and presence", "pt": "Identidade central e presença", "question_en": "How do identity, direction and presence organise themselves?", "question_pt": "Como identidade, direção e presença se organizam?", "houses": (1,), "angles": ("asc",), "intrinsic": {"sun": "identity, vitality and direction"}},
    {"id": "emotional_security", "en": "Emotional world and inner security", "pt": "Mundo emocional e segurança interna", "question_en": "What supports emotional regulation and inner security?", "question_pt": "O que sustenta regulação emocional e segurança interna?", "houses": (4,), "angles": ("ic",), "intrinsic": {"moon": "needs and emotional regulation"}},
    {"id": "mind_learning_communication", "en": "Mind, learning, decisions and communication", "pt": "Mente, aprendizagem, decisões e comunicação", "question_en": "How do thought, learning and communication operate?", "question_pt": "Como pensamento, aprendizagem e comunicação operam?", "houses": (3, 9), "angles": (), "intrinsic": {"mercury": "thinking and communication"}},
    {"id": "desire_action_limits", "en": "Desire, action, assertiveness and limits", "pt": "Desejo, ação, assertividade e limites", "question_en": "How do desire, action and boundaries work together?", "question_pt": "Como desejo, ação e limites trabalham juntos?", "houses": (1, 6, 8), "angles": (), "intrinsic": {"mars": "action, desire and boundaries"}},
    {"id": "love_intimacy_relationship", "en": "Love, attraction, intimacy and relationship", "pt": "Amor, atração, intimidade e relacionamentos", "question_en": "What supports connection, reciprocity and intimacy?", "question_pt": "O que sustenta vínculo, reciprocidade e intimidade?", "houses": (5, 7, 8), "angles": ("dsc",), "intrinsic": {"venus": "connection, pleasure and values"}},
    {"id": "creativity_pleasure_aliveness", "en": "Creativity, pleasure, play and aliveness", "pt": "Criatividade, prazer, brincadeira e vitalidade", "question_en": "Where do pleasure, expression and aliveness become available?", "question_pt": "Onde prazer, expressão e vitalidade se tornam disponíveis?", "houses": (5,), "angles": (), "intrinsic": {"sun": "vitality and aliveness", "venus": "pleasure and values"}},
    {"id": "work_vocation_visibility", "en": "Work, vocation, contribution and visibility", "pt": "Trabalho, vocação, contribuição e visibilidade", "question_en": "How do contribution, work and visibility take form?", "question_pt": "Como contribuição, trabalho e visibilidade ganham forma?", "houses": (6, 10), "angles": ("mc",), "intrinsic": {}},
    {"id": "money_resources_value", "en": "Money, resources, value and material security", "pt": "Dinheiro, recursos, valor e segurança material", "question_en": "How are resources, value and material security approached?", "question_pt": "Como recursos, valor e segurança material são abordados?", "houses": (2, 8), "angles": (), "intrinsic": {}},
    {"id": "body_energy_routine", "en": "Body, energy, routine and sustainability", "pt": "Corpo, energia, rotina e sustentabilidade", "question_en": "What supports energy, effort and sustainable routine?", "question_pt": "O que sustenta energia, esforço e rotina sustentável?", "houses": (1, 6), "angles": (), "intrinsic": {"sun": "vitality and energy", "mars": "action and effort"}},
    {"id": "home_roots_private_life", "en": "Home, roots, family and private life", "pt": "Lar, raízes, família e vida privada", "question_en": "What supports roots, privacy and a psychological base?", "question_pt": "O que sustenta raízes, privacidade e uma base psicológica?", "houses": (4,), "angles": ("ic",), "intrinsic": {}},
    {"id": "friendship_community_belonging", "en": "Friendship, community and belonging", "pt": "Amizade, comunidade e pertencimento", "question_en": "How do community, networks and belonging operate?", "question_pt": "Como comunidade, redes e pertencimento operam?", "houses": (11,), "angles": (), "intrinsic": {}},
    {"id": "meaning_beliefs_horizon", "en": "Meaning, beliefs, study and horizon", "pt": "Sentido, crenças, estudo e horizonte", "question_en": "How are meaning, study and wider perspective developed?", "question_pt": "Como sentido, estudo e perspectiva mais ampla se desenvolvem?", "houses": (3, 9), "angles": (), "intrinsic": {"jupiter": "growth, meaning and exploration", "mercury": "learning and communication"}},
    {"id": "shadow_defenses_patterns", "en": "Shadow, defenses, power and repeating patterns", "pt": "Sombra, defesas, poder e padrões repetitivos", "question_en": "Which authorised tensions or background patterns deserve awareness?", "question_pt": "Quais tensões ou padrões de fundo autorizados merecem consciência?", "houses": (8, 12), "angles": (), "intrinsic": {}, "hard_relational": True},
    {"id": "growth_through_contradiction", "en": "Growth through contradiction", "pt": "Crescimento através da contradição", "question_en": "Which legitimate needs repeatedly ask to coexist?", "question_pt": "Quais necessidades legítimas pedem repetidamente para coexistir?", "houses": (), "angles": (), "intrinsic": {}, "hard_relational": True},
    {"id": "developmental_direction", "en": "Developmental direction", "pt": "Direção de desenvolvimento", "question_en": "What is familiar, and what asks for less automatic engagement?", "question_pt": "O que é familiar e o que pede um engajamento menos automático?", "houses": (), "angles": (), "intrinsic": {}, "node_axis": True},
    {"id": "active_life_chapter", "en": "The chapter of life active now", "pt": "O capítulo de vida ativo agora", "question_en": "Which natal field is being activated now?", "question_pt": "Qual campo natal está sendo ativado agora?", "houses": (), "angles": (), "intrinsic": {}, "timing": True},
)

READER_OPENING_HEADINGS = {"en": "Whole-chart architecture", "pt": "Arquitetura do mapa"}
READER_INTEGRATION_HEADINGS = {"en": "Final integration", "pt": "Integração final"}
HARD_RELATIONAL_OPERATIONS = frozenset({"friction", "polarity", "adjustment"})
HARD_CONFIGURATION_KINDS = frozenset({"t_square", "yod", "grand_cross", "mystic_rectangle"})


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
    house_rulers = [to_primitive(item) for item in chart.factors if item.kind == "placidus_house_ruler"]
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
            "placidus_house_rulers": house_rulers,
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
            "house_ruler_routing_policy": "A reliable Placidus house-ruler Claim may state only its atomic cusp-to-ruler route directly. Any use of the ruler's natal context requires an approved house-ruler-context synthesis with same-ruler ancestry.",
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
    timing_ids = set(timing_evidence_ids or [])
    claim_map = {claim.id: claim for claim in (claims or []) if claim.status == "allowed"}
    output: List[ReasonedSynthesis] = []
    for item in items:
        errors = synthesis_ancestry_errors(item, chart, claim_map.values(), timing_ids)
        source_claims = [claim_map[claim_id] for claim_id in item.source_claim_ids if claim_id in claim_map]
        if item.confidence_within_astrological_model not in CONFIDENCE:
            errors.append("invalid_confidence")
        if claim_map:
            allowed_motifs = {motif for claim in source_claims for motif in claim.authorized_motifs}
            if any(motif not in allowed_motifs for motif in item.source_motif_ids):
                errors.append("source_motif_not_authorized_by_source_claim")
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
        folded = " ".join([item.observation, item.alternative_reading, *item.possible_expressions]).casefold()
        if any(token in folded for token in ("diagnóstico", "diagnosis", "trauma", "morte", "death", "doença", "disease", "vai acontecer", "will happen")):
            errors.append("prohibited_extension_in_reasoning")
        item.verification_errors = errors
        item.status = "blocked" if errors else "allowed"
        output.append(item)
    return output


def synthesis_ancestry_errors(
    item: ReasonedSynthesis,
    chart: SafeInterpretiveChart,
    claims: Iterable[Claim],
    timing_evidence_ids: Iterable[str] = (),
) -> List[str]:
    """Validate non-literary Claim/factor ancestry for synthesis and routing.

    Reader-domain availability uses this same path as the full synthesis guard;
    prose, confidence and literary specificity remain later validation layers.
    """
    known = _evidence_ids(chart)
    timing_ids = set(timing_evidence_ids)
    claim_map = {claim.id: claim for claim in claims if claim.status == "allowed"}
    factor_kinds = {factor.id: factor.kind for factor in chart.factors}
    cited = list(item.primary_factors) + list(item.modifiers) + list(item.counterweights)
    errors: List[str] = []
    source_claims: List[Claim] = []
    if not item.primary_factors:
        errors.append("missing_primary_factors")
    if any(factor not in known and factor not in timing_ids for factor in cited):
        errors.append("unknown_or_unsafe_factor")
    if item.reasoning_class not in REASONING_CLASSES:
        errors.append("invalid_reasoning_class")
    if claim_map:
        if not item.source_claim_ids:
            errors.append("missing_source_claim_ids")
        if any(claim_id not in claim_map for claim_id in item.source_claim_ids):
            errors.append("unknown_source_claim_id")
        source_claims = [claim_map[claim_id] for claim_id in item.source_claim_ids if claim_id in claim_map]
        allowed_primary = {factor for claim in source_claims for factor in claim.evidence}
        natal_primary = {factor for factor in item.primary_factors if factor not in timing_ids}
        if not natal_primary.issubset(allowed_primary):
            errors.append("primary_factor_not_authorized_by_source_claim")
        if not item.composition_operations:
            errors.append("missing_composition_operation")
        if _incompatible_operations(item, chart, timing_ids):
            errors.append("composition_operation_not_supported_by_factor")
        errors.extend(_house_ruler_context_errors(item, chart, source_claims, factor_kinds))
    # A raw route cannot evade its specialised contract by omitting a Claim.
    errors.extend(_house_ruler_factor_contract_errors(item, chart, source_claims, factor_kinds))
    if item.reasoning_class == "natal_timing_interaction" and (
        not any(factor in timing_ids for factor in item.primary_factors)
        or not any(factor not in timing_ids for factor in item.primary_factors)
    ):
        errors.append("natal_timing_interaction_requires_natal_and_timing_evidence")
    if item.reasoning_class != "single_structural_factor" and len(set(item.primary_factors)) < 2 and not any(factor.startswith("aspect.") for factor in item.primary_factors):
        errors.append("insufficient_composition_support")
    configuration_factors = {factor.id: factor for factor in chart.factors if factor.kind == "configuration"}
    if any(factor in configuration_factors for factor in item.primary_factors):
        from .structure import detect_configurations
        detected = {str(record["id"]): record for record in detect_configurations(chart.semantic_chart())}
        for factor_id in set(item.primary_factors).intersection(configuration_factors):
            if detected.get(factor_id) != configuration_factors[factor_id].data:
                errors.append("invalid_configuration_provenance")
    return list(dict.fromkeys(errors))


def _house_ruler_factor_contract_errors(
    item: ReasonedSynthesis,
    chart: SafeInterpretiveChart,
    source_claims: Sequence[Claim],
    factor_kinds: Dict[str, str],
) -> List[str]:
    """Require every raw cusp-ruler factor to use the sole routing contract.

    House-ruler factors are factual routes, not free-standing synthesis
    material.  A valid occurrence is exactly one route in primary factors of
    its canonical contextualisation synthesis; the specialised validator then
    checks the required same-ruler context Claim and all modifiers.
    """
    factor_by_id = {factor.id: factor for factor in chart.factors}
    cited = list(item.primary_factors) + list(item.modifiers) + list(item.counterweights)
    routing_ids = [
        factor_id
        for factor_id in cited
        if factor_kinds.get(factor_id) == "placidus_house_ruler"
    ]
    if not routing_ids:
        return []

    errors: List[str] = []
    routing_primary = [
        factor_id
        for factor_id in item.primary_factors
        if factor_kinds.get(factor_id) == "placidus_house_ruler"
    ]
    if any(factor_id in item.modifiers or factor_id in item.counterweights for factor_id in routing_ids):
        errors.append("house_ruler_factor_must_be_routing_primary")
    unique_routing_ids = list(dict.fromkeys(routing_ids))
    if len(unique_routing_ids) != 1:
        errors.append("house_ruler_factor_requires_single_routing_primary")
        return errors
    if len(routing_ids) != 1 or routing_primary != unique_routing_ids:
        errors.append("house_ruler_factor_requires_single_routing_primary")

    routing_factor = factor_by_id.get(unique_routing_ids[0])
    if not routing_factor:
        return [*errors, "invalid_house_ruler_context_ancestry"]
    house = routing_factor.data.get("house")
    ruler = routing_factor.data.get("ruler")
    if not isinstance(house, int) or house not in range(1, 13) or not isinstance(ruler, str):
        return [*errors, "invalid_house_ruler_context_ancestry"]
    expected_claim_id = f"claim.house_ruler.placidus.{house}"
    matching_claims = [
        claim
        for claim in source_claims
        if claim.id == expected_claim_id
        and claim.type == "placidus_house_ruler"
        and claim.evidence == [routing_factor.id]
    ]
    if len(matching_claims) != 1:
        errors.append("house_ruler_factor_requires_matching_routing_claim")
    expected_id = f"reasoned.house_ruler_context.placidus.{house}.{ruler}"
    if (
        item.id != expected_id
        or item.reasoning_class != "integrated_pattern"
        or "contextualization" not in item.composition_operations
    ):
        errors.append("house_ruler_factor_requires_contextualization_contract")
    return list(dict.fromkeys(errors))


def _house_ruler_context_errors(
    item: ReasonedSynthesis,
    chart: SafeInterpretiveChart,
    source_claims: Sequence[Claim],
    factor_kinds: Dict[str, str],
) -> List[str]:
    """Keep cusp-ruler routing compositional without inventing topical themes."""
    routing_claims = [claim for claim in source_claims if claim.type == "placidus_house_ruler"]
    if not routing_claims:
        return []
    errors: List[str] = []
    if len(routing_claims) != 1:
        return ["house_ruler_context_requires_one_routing_claim"]
    routing = routing_claims[0]
    factor_by_id = {factor.id: factor for factor in chart.factors}
    routing_factor = factor_by_id.get(routing.evidence[0]) if routing.evidence else None
    if not routing_factor or routing_factor.kind != "placidus_house_ruler":
        return ["invalid_house_ruler_context_ancestry"]
    house = int(routing_factor.data["house"])
    ruler = str(routing_factor.data["ruler"])
    expected_id = f"reasoned.house_ruler_context.placidus.{house}.{ruler}"
    if item.id != expected_id:
        errors.append("noncanonical_house_ruler_context_id")
    if item.reasoning_class != "integrated_pattern" or "contextualization" not in item.composition_operations:
        errors.append("house_ruler_context_requires_contextualization")
    if routing_factor.id not in item.primary_factors:
        errors.append("house_ruler_factor_missing_from_primary")
    context_claims = [claim for claim in source_claims if claim.id != routing.id]
    if not context_claims:
        errors.append("house_ruler_context_requires_authorized_ruler_claim")
    allowed_context_kinds = {"position", "placidus_house", "angle_contact", "configuration", "aspect"}
    for claim in context_claims:
        if not claim.evidence:
            errors.append("invalid_house_ruler_context_ancestry")
            continue
        for evidence_id in claim.evidence:
            bodies, kind = _evidence_bodies_and_kind(evidence_id, chart, factor_by_id, factor_kinds)
            if kind not in allowed_context_kinds or ruler not in bodies:
                errors.append("house_ruler_context_not_owned_by_ruler")
            if evidence_id not in item.primary_factors:
                errors.append("house_ruler_context_factor_missing_from_primary")

    # A routing synthesis may qualify an already-authorised ruler context, but
    # it may not smuggle in another body's factors as modifiers or
    # counterweights.  Conditions and hierarchy are the existing modifier
    # roles; counterweights retain the existing Claim-level aspect contract.
    for modifier in item.modifiers:
        bodies, kind = _evidence_bodies_and_kind(modifier, chart, factor_by_id, factor_kinds)
        if kind == "hierarchy":
            if bodies != {ruler}:
                errors.append("house_ruler_modifier_not_owned_by_ruler")
        elif kind == "planetary_condition":
            if bodies != {ruler}:
                errors.append("house_ruler_condition_not_owned_by_ruler")
        else:
            errors.append("house_ruler_modifier_not_authorized")

    allowed_counterweights = {
        counterweight
        for claim in context_claims
        for counterweight in claim.counterweights
    }
    for counterweight in item.counterweights:
        bodies, kind = _evidence_bodies_and_kind(counterweight, chart, factor_by_id, factor_kinds)
        if kind != "aspect" or ruler not in bodies:
            errors.append("house_ruler_counterweight_not_owned_by_ruler")
        if counterweight not in allowed_counterweights:
            errors.append("house_ruler_counterweight_not_authorized")
    return list(dict.fromkeys(errors))


def _evidence_bodies_and_kind(
    evidence_id: str,
    chart: SafeInterpretiveChart,
    factor_by_id: Dict[str, object],
    factor_kinds: Dict[str, str],
) -> tuple[set[str], Optional[str]]:
    """Resolve one existing evidence id through its canonical ownership path."""
    if evidence_id.startswith("hierarchy."):
        return {evidence_id.removeprefix("hierarchy.")}, "hierarchy"
    aspect = next((entry for entry in chart.aspects if entry.id == evidence_id), None)
    if aspect:
        return {aspect.left, aspect.right}, "aspect"
    factor = factor_by_id.get(evidence_id)
    if factor:
        return set(factor.bodies), factor_kinds.get(evidence_id)
    return set(), None


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


def build_reader_domain_manifest(
    chart: SafeInterpretiveChart,
    claims: Iterable[Claim],
    prepared_syntheses: List[Dict[str, object]],
    chart_signature: Dict[str, object],
    timing_evidence: Iterable[Dict[str, object]] = (),
    language: str = "pt-BR",
) -> Dict[str, object]:
    """Route existing semantic authority to reader questions without scoring it."""
    lang = "pt" if language.startswith("pt") else "en"
    allowed_claims = [claim for claim in claims if claim.status == "allowed"]
    claim_map = {claim.id: claim for claim in allowed_claims}
    factors = {factor.id: factor for factor in chart.factors}
    aspects = {aspect.id: aspect for aspect in chart.aspects}
    evidence_bodies = _evidence_bodies(chart)
    timing_records = {str(item["id"]): dict(item) for item in timing_evidence if item.get("id")}
    activation_targets = {
        str(item.get("activation_instance")): str(item.get("target"))
        for item in timing_records.values()
        if item.get("kind") == "activation_instance" and item.get("activation_instance") and item.get("target")
    }
    position_claims = {
        claim.evidence[0].removeprefix("position."): claim
        for claim in allowed_claims
        if claim.id.startswith("claim.position.") and len(claim.evidence) == 1 and claim.evidence[0].startswith("position.")
    }
    core_factors = set(map(str, chart_signature.get("core_factors", [])))
    central_bodies = set(map(str, chart_signature.get("central_dynamic", {}).get("bodies", [])))
    strongest_houses = {int(item["house"]) for item in chart_signature.get("strongest_domains", []) if isinstance(item, dict) and str(item.get("house", "")).isdigit()}

    def legal(item: ReasonedSynthesis) -> bool:
        return not synthesis_ancestry_errors(item, chart, allowed_claims, timing_records)

    def record(kind: str, item: ReasonedSynthesis, scope: str, house: int | None = None) -> Dict[str, object] | None:
        if not legal(item):
            return None
        return {
            "kind": kind,
            "source_claim_ids": list(item.source_claim_ids),
            "primary_factor_ids": list(item.primary_factors),
            "reasoning_class": item.reasoning_class,
            "composition_operations": list(item.composition_operations),
            "authorized_scope": scope,
            **({"placidus_house": house} if house is not None else {}),
        }

    def single_claim_path(claim: Claim, scope: str) -> Dict[str, object] | None:
        if claim.direct_paragraph_renderable or not claim.evidence:
            return None
        factor_id = claim.evidence[0]
        operation = ASPECT_OPERATIONS[aspects[factor_id].kind] if factor_id in aspects else "contextualization"
        reasoning_class = "integrated_pattern" if operation in HARD_RELATIONAL_OPERATIONS else "single_structural_factor"
        item = ReasonedSynthesis(
            id=f"reader.route.{claim.id}", observation="", primary_factors=[factor_id], modifiers=[], counterweights=[],
            reasoning_class=reasoning_class, confidence_within_astrological_model="light", possible_expressions=[], alternative_reading="",
            prohibited_extensions=[], source_claim_ids=[claim.id], source_motif_ids=[], composition_operations=[operation], derived_propositions=[],
        )
        return record("claim_anchored", item, scope)

    def house_path(claim: Claim, house: int, scope: str) -> Dict[str, object] | None:
        if claim.direct_paragraph_renderable or not claim.evidence:
            return None
        item = ReasonedSynthesis(
            id=f"reader.route.{claim.id}", observation="", primary_factors=[claim.evidence[0]], modifiers=[], counterweights=[],
            reasoning_class="single_structural_factor", confidence_within_astrological_model="light", possible_expressions=[], alternative_reading="",
            prohibited_extensions=[], source_claim_ids=[claim.id], source_motif_ids=[], composition_operations=["contextualization"], derived_propositions=[],
        )
        return record("topical_placidus", item, scope, house)

    def house_ruler_path(house: int, scope: str) -> Dict[str, object] | None:
        routing = claim_map.get(f"claim.house_ruler.placidus.{house}")
        if not routing or not routing.evidence:
            return None
        factor = factors.get(routing.evidence[0])
        if not factor or factor.kind != "placidus_house_ruler":
            return None
        ruler = str(factor.data.get("ruler", ""))
        context = position_claims.get(ruler)
        if not context:
            return None
        item = ReasonedSynthesis(
            id=f"reasoned.house_ruler_context.placidus.{house}.{ruler}", observation="",
            primary_factors=[factor.id, context.evidence[0]], modifiers=[], counterweights=[], reasoning_class="integrated_pattern",
            confidence_within_astrological_model="light", possible_expressions=[], alternative_reading="", prohibited_extensions=[],
            source_claim_ids=[routing.id, context.id], source_motif_ids=[], composition_operations=["contextualization"], derived_propositions=[],
        )
        return record("house_ruler_context", item, scope, house)

    def timing_paths(scope: str) -> List[Dict[str, object]]:
        paths: List[Dict[str, object]] = []
        for timing_id, timing_item in sorted(timing_records.items()):
            kind = str(timing_item.get("kind", ""))
            targets: List[str] = []
            if kind in {"activation_instance", "secondary_progression", "solar_arc"} and timing_item.get("target"):
                targets.append(str(timing_item["target"]))
            elif kind == "annual_profection" and timing_item.get("time_lord"):
                targets.append(str(timing_item["time_lord"]))
            elif kind in {"timeline_phase", "developmental_interval"}:
                targets.extend(
                    activation_targets[activation]
                    for activation in timing_item.get("activation_instances", [])
                    if activation in activation_targets
                )
            for target in dict.fromkeys(targets):
                claim = position_claims.get(target)
                if not claim:
                    continue
                item = ReasonedSynthesis(
                    id=f"reader.route.timing.{kind}.{target}", observation="", primary_factors=[claim.evidence[0], timing_id], modifiers=[], counterweights=[],
                    reasoning_class="natal_timing_interaction", confidence_within_astrological_model="light", possible_expressions=[], alternative_reading="",
                    prohibited_extensions=[], source_claim_ids=[claim.id], source_motif_ids=[], composition_operations=["contextualization", "timing_activation"], derived_propositions=[],
                )
                candidate = record("timing_natal", item, scope)
                if candidate:
                    candidate["timing_ids"] = [timing_id]
                    paths.append(candidate)
        return paths

    domains = []
    house_claims: Dict[int, List[Claim]] = defaultdict(list)
    for claim in allowed_claims:
        if claim.type != "topical_tendency" or not claim.evidence or not claim.evidence[0].startswith("house.placidus."):
            continue
        body = claim.evidence[0].removeprefix("house.placidus.")
        placement = chart.house_placements.get(body)
        if placement and placement.placidus_house is not None:
            house_claims[int(placement.placidus_house)].append(claim)

    for definition in READER_DOMAIN_DEFINITIONS:
        paths: List[Dict[str, object]] = []
        for body, scope in definition.get("intrinsic", {}).items():
            claim = position_claims.get(body)
            candidate = single_claim_path(claim, scope) if claim else None
            if candidate:
                paths.append(candidate)
        for angle in definition.get("angles", ()):
            prefix = "claim.ascendant." if angle == "asc" else f"claim.angle."
            for claim in allowed_claims:
                is_match = claim.id.startswith(prefix) and (angle == "asc" or f".{angle}." in claim.id)
                if is_match:
                    candidate = single_claim_path(claim, f"the authorised {angle.upper()} function")
                    if candidate:
                        paths.append(candidate)
            if angle == "asc":
                for claim in allowed_claims:
                    if claim.id.startswith("claim.chart_ruler."):
                        candidate = single_claim_path(claim, "orientation and ways of beginning")
                        if candidate:
                            paths.append(candidate)
        for house in definition.get("houses", ()):
            scope = f"the existing Placidus house {house} topic"
            for claim in house_claims.get(house, []):
                candidate = house_path(claim, house, scope)
                if candidate:
                    paths.append(candidate)
            candidate = house_ruler_path(house, scope)
            if candidate:
                paths.append(candidate)
        if definition.get("hard_relational"):
            for claim in allowed_claims:
                factor_id = claim.evidence[0] if claim.evidence else ""
                if factor_id in aspects and ASPECT_OPERATIONS[aspects[factor_id].kind] in HARD_RELATIONAL_OPERATIONS:
                    candidate = single_claim_path(claim, "the authorised friction, polarity or adjustment between the cited functions")
                    if candidate:
                        paths.append(candidate)
                factor = factors.get(factor_id)
                if factor and factor.kind == "configuration" and factor.data.get("kind") in HARD_CONFIGURATION_KINDS:
                    candidate = single_claim_path(claim, "the authorised integrated tension in the detected configuration")
                    if candidate:
                        paths.append(candidate)
        if definition.get("node_axis"):
            for claim in allowed_claims:
                if claim.id.startswith("claim.node_axis."):
                    candidate = single_claim_path(claim, "developmental direction and familiar available patterning")
                    if candidate:
                        paths.append(candidate)
        if definition.get("timing"):
            paths.extend(timing_paths("the human field activated by the selected timing record and its natal target"))

        unique: List[Dict[str, object]] = []
        seen = set()
        for candidate in paths:
            key = (
                candidate["kind"], tuple(candidate["source_claim_ids"]), tuple(candidate["primary_factor_ids"]),
                tuple(candidate.get("timing_ids", [])), candidate.get("placidus_house"), candidate["authorized_scope"],
            )
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        unique.sort(key=lambda item: (str(item["kind"]), tuple(item["source_claim_ids"]), tuple(item["primary_factor_ids"])))
        for index, candidate in enumerate(unique, 1):
            candidate["id"] = f"reader_path.{definition['id']}.{candidate['kind']}.{index}"
        path_factors = {factor for candidate in unique for factor in candidate["primary_factor_ids"]}
        path_bodies = set().union(*(evidence_bodies.get(factor, set()) for factor in path_factors)) if path_factors else set()
        supporting_claim_ids = sorted({
            claim.id for claim in allowed_claims
            if not claim.direct_paragraph_renderable
            and any(path_bodies.intersection(evidence_bodies.get(evidence, set())) for evidence in claim.evidence)
        } - {claim_id for candidate in unique for claim_id in candidate["source_claim_ids"]})
        supporting_synthesis_ids = sorted({
            str(item["id"]) for item in prepared_syntheses if item.get("status") == "allowed"
            and path_factors.intersection(map(str, item.get("primary_factors", [])))
        })
        high = any(
            core_factors.intersection(candidate["primary_factor_ids"])
            or central_bodies.intersection(set().union(*(evidence_bodies.get(factor, set()) for factor in candidate["primary_factor_ids"])))
            or candidate.get("placidus_house") in strongest_houses
            for candidate in unique
        )
        heading = str(definition[lang])
        unavailable = not unique
        notice = None
        if unavailable:
            if definition["id"] == "active_life_chapter":
                text = (f"Em “{heading}”, a evidência de timing selecionada não sustenta uma ativação atual suficientemente específica; por isso, o relatório não infere uma."
                        if lang == "pt" else f"For “{heading},” the selected timing evidence does not support a sufficiently specific current activation, so this report does not infer one.")
            else:
                text = (f"Em “{heading}”, o mapa não oferece evidência suficientemente confiável e específica; por isso, o relatório deixa a questão em aberto em vez de inventar uma interpretação."
                        if lang == "pt" else f"For “{heading},” the chart does not provide sufficiently reliable, specific evidence, so this report leaves the question open rather than inventing an interpretation.")
            import hashlib
            notice = {"id": f"reader_notice.unavailable.{definition['id']}", "text": text, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        domains.append({
            "id": definition["id"], "position": len(domains) + 1, "heading": heading,
            "human_question": definition[f"question_{lang}"], "legal_coverage_paths": unique,
            "supporting_claim_ids": supporting_claim_ids, "supporting_synthesis_ids": supporting_synthesis_ids,
            "availability": "unavailable" if unavailable else "available", "emphasis": "low" if unavailable or not high else "high",
            "unavailable_notice": notice,
        })
    return {
        "contract_version": "1.0", "locale": language,
        "opening": {"heading": READER_OPENING_HEADINGS[lang]},
        "domains": domains,
        "integration": {"heading": READER_INTEGRATION_HEADINGS[lang]},
        "rules": {
            "coverage": "fixed", "depth": "adaptive", "path_kinds": ["claim_anchored", "topical_placidus", "house_ruler_context", "timing_natal"],
            "direct_claim_satisfies_domain": False, "reused_evidence_changes_structural_weight": False,
        },
    }


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
    # Reliable cusp-to-ruler routes remain available to the Author and source
    # map, but they are contextual routing rather than independent structural
    # evidence.  The marker is reconstructed from an already-allowed synthesis
    # plus its canonical routing Claim/factor ancestry, never from a model
    # supplied label alone.
    structural_syntheses = [
        item for item in usable
        if not _is_verified_house_ruler_context_synthesis(item, chart)
    ]
    routing_factor_ids = {
        factor.id for factor in chart.factors
        if factor.kind == "placidus_house_ruler"
    }
    evidence_bodies = _evidence_bodies(chart)
    body_to_syntheses: Dict[str, set[str]] = defaultdict(set)
    for synthesis in structural_syntheses:
        for factor_id in synthesis["primary_factors"]:
            if factor_id in routing_factor_ids:
                continue
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
    counterweights = sorted({
        item
        for synthesis in structural_syntheses
        for item in synthesis.get("counterweights", [])
        if item not in routing_factor_ids
    })
    contradictions = [item["id"] for item in structural_syntheses if "polarity" in item.get("composition_operations", []) or "friction" in item.get("composition_operations", [])]
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
    for synthesis in structural_syntheses:
        theme = str(synthesis["id"]).removeprefix("reasoned.")
        scoring_factors = []
        for factor in synthesis["primary_factors"]:
            if factor in routing_factor_ids:
                continue
            family = configuration_families.get(factor)
            if family and family in seen_configuration_families:
                continue
            if family:
                seen_configuration_families.add(family)
            scoring_factors.append(factor)
        # Preserve the existing zero-score record for a deduplicated
        # configuration family, but do not manufacture a theme from a raw
        # routing factor after its structural contribution was removed.
        if not scoring_factors and any(factor in routing_factor_ids for factor in synthesis["primary_factors"]):
            continue
        bodies = sorted(set().union(*(evidence_bodies.get(factor, set()) for factor in scoring_factors)))
        score = sum(sorted((body_scores.get(body, 0) for body in bodies), reverse=True)[:2]) + min(2, len(scoring_factors))
        theme_priorities.append({"theme": theme, "score": score, "bodies": bodies, "source_syntheses": [synthesis["id"]]})
    theme_priorities.sort(key=lambda item: (-int(item["score"]), str(item["theme"])))
    core_factor_ids = []
    for synthesis_id in selected_syntheses:
        synthesis = next((item for item in structural_syntheses if item["id"] == synthesis_id), None)
        if synthesis:
            core_factor_ids.extend(
                factor for factor in synthesis["primary_factors"]
                if factor not in routing_factor_ids
            )
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


def _is_verified_house_ruler_context_synthesis(
    synthesis: Dict[str, object],
    chart: SafeInterpretiveChart,
) -> bool:
    """Recognise the approved non-scoring routing composition canonically."""
    if synthesis.get("status") != "allowed":
        return False
    factors = {
        factor.id: factor
        for factor in chart.factors
        if factor.kind == "placidus_house_ruler"
    }
    routing_ids = [factor_id for factor_id in synthesis.get("primary_factors", []) if factor_id in factors]
    if len(routing_ids) != 1:
        return False
    routing = factors[routing_ids[0]]
    house = routing.data.get("house")
    ruler = routing.data.get("ruler")
    if not isinstance(house, int) or not isinstance(ruler, str):
        return False
    return (
        synthesis.get("id") == f"reasoned.house_ruler_context.placidus.{house}.{ruler}"
        and synthesis.get("reasoning_class") == "integrated_pattern"
        and "contextualization" in synthesis.get("composition_operations", [])
        and f"claim.house_ruler.placidus.{house}" in synthesis.get("source_claim_ids", [])
    )


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
            "Escreva como alguém que entra no mapa ao lado da pessoa: caloroso, receptivo, elegante e psicologicamente claro, sem intimidade inventada ou bajulação. "
            "Dirija-se predominantemente à pessoa em segunda pessoa natural, variando a construção quando a repetição ficar mecânica. Comece, quando ajudar, "
            "pela experiência humana — uma tensão, necessidade ou modo de estar reconhecível — e revele em seguida a astrologia que a ilumina. Preserve nuance "
            "ou contradição e deixe uma reflexão respirar; não force essa ordem quando a estrutura astrológica for mais clara ou natural. Evite aberturas mecânicas "
            "como 'você pode notar' e o ritmo repetitivo de recurso, risco e pergunta. Para as dinâmicas centrais, desenvolva, quando realmente acrescentar sentido: mecanismo interno, "
            "expressão reconhecível, distinção entre expressão integrada e reação defensiva/sob pressão, excesso ou falsa solução, contrapeso material e via de integração com outro fator importante — sem transformar isso "
            "numa fórmula repetitiva. Entenda que expressão integrada, reação defensiva/sob pressão e excesso são exclusivamente lentes internas de raciocínio psicodinâmico para o autor calibrar os mecanismos humanos na prosa, e NUNCA devem ser reproduzidas como títulos, subtítulos, triplets obrigatórios de bullets (ex.: listas formulaicas de três itens rotuladas como integrada, defensiva ou excesso) ou andaimes estruturais rígidos entre capítulos. "
            "Esse foco organiza a abertura, não limita a profundidade do restante: em cada domínio, desenvolva todo mecanismo distinto e relevante que a evidência autorizada sustentar, incluindo tensão, contrapeso, consequência própria e integração com a arquitetura inteira quando eles realmente acrescentarem sentido. A profundidade pode ser visivelmente irregular quando a carta a ganha; comprimentos parecidos pedem revisão editorial, não uma meta mecânica. Humanizar muda a expressão, não reduz o que o mapa compreende. Prefira verbos, movimentos, decisões e experiência vivida a repetir registro nominal como função, coordenação disponível, estrutura, direção, integração, critério ou possibilidade. "
            "Não leve vocabulário de roteamento ao leitor: diga, por exemplo, 'como Vênus rege sua quarta casa', não 'a casa quatro encaminhada a Vênus'. "
            "Arquitetura e respiração de cada capítulo de domínio: cada domínio deve ser desenvolvido com densidade, nuance e acolhimento, desdobrando-se organicamente em 2 a 4 parágrafos distintos (evite rigorosamente parágrafos únicos comprimidos ou monólitos maciços de texto): "
            "(1) O cerne da experiência humana e a astrologia que a ilumina: parta da experiência concreta, tensão, anseio ou desafio característico daquela área, revelando o fator astrológico condutor; "
            "(2) Psicodinâmica, defesas e cenas do cotidiano: aprofunde as reações sob pressão, os mecanismos compensatórios, contrastes relacionais e microcenas cotidianas realistas de tomada de decisão ou limites; "
            "(3) Auto-observação ativa e integração: inclua perguntas reflexivas lúcidas ou hipóteses práticas de auto-observação que transformem a leitura em um instrumento vivo de percepção pessoal, conectando o domínio aos eixos estruturantes do mapa. "
            "Variedade sintática e rejeição de moldes repetitivos: varie deliberadamente as aberturas e transições entre capítulos. É expressamente proibido repetir fórmulas sintáticas padronizadas (como iniciar sucessivos capítulos com construções passivas idênticas do tipo '[Substantivo A] e [Substantivo B] são estruturados/governados/orientados por [planeta/casa]'). Inicie capítulos ora por um dilema psicológico, ora por um contraste prático, ora por uma pergunta interna, ora pela fenomenologia de um comportamento real. "
            "Ritmo editorial e recursos destacados: a vasta maioria do relatório deve ser prosa natural contínua rica e fluida. Use recursos editoriais (uma microcena contextual dentro do parágrafo, um exemplo ilustrativo, bullets para manifestações paralelas, uma pergunta discriminativa ou uma síntese orgânica) apenas quando melhorarem materialmente a compreensão, retenção ou ritmo, sem quotas fixas ou contagens prescritas; microcenas hipotéticas são bem-vindas onde dinâmicas abstratas ganharem clareza imediata no cotidiano (como tomada de decisão, limites, conflito, trabalho ou dinheiro), nunca por quota, nunca rotuladas com tags em caixa alta e nunca como biografia inventada. Use bullets preferencialmente e com moderação para manifestações paralelas, polos de tensão, comportamentos sob pressão ou escolhas práticas, e não para meramente repetir placements já citados no texto nem como triplets estruturais padronizados. "
            "Proteção 1 — Calibração Epistêmica: não transforme interpretação simbólica em certeza biográfica ou psicológica estabelecida. Evite afirmações categóricas ou generalizações comportamentais como 'você desenvolveu precocemente', 'você possui um dom natural', 'seus limites são absolutamente', 'você certamente', 'esta é a sua verdadeira essência', 'você foi desenhado para', 'dificilmente você...', 'é comum você...' ou 'você costuma...'. Prefira formulações testáveis como 'isso pode favorecer...', 'sob certas condições, uma manifestação possível é...', 'uma hipótese útil para auto-observação é...', 'a configuração aponta para...' ou 'o risco desta dinâmica é...'. Diferencie com rigor estrutura astrológica forte de biografia inferida, mantendo a confiança estritamente proporcional à evidência. "
            "Proteção 2 — Anti-Grandiosidade e Anti-Bajulação: evite qualquer linguagem que torne a pessoa artificialmente excepcional, heroica ou superior (ex.: 'intensidade vulcânica', 'autoridade penetrante', 'dom extraordinário', 'uma das configurações mais nobres', 'integridade que é sua marca natural', 'vocação talhada para', 'liderança excepcional', 'destino grandioso', 'força monumental', 'capacidade sobre-humana', 'brilho incomparável'). O relatório deve ser cativante porque revela mecanismos humanos reais, não porque elogia o leitor. "
            "Proteção 3 — Corpo e Saúde (Não-Medicalização): astrologia não gera diagnósticos nem explicações fisiológicas. Não faça inferências causais sobre problemas digestivos, sono, regeneração celular, necessidade fisiológica de isolamento, resistência física excepcional, sensações corporais específicas ('peso ou lentidão') ou sinais físicos. O capítulo de corpo/rotina (Capítulo 9) deve focar estritamente em hipóteses simbólicas de auto-observação sobre ritmo, carga de trabalho, rotina diária, pausas, sustentabilidade, relação subjetiva com o esforço e a necessidade de alternar atividade e recolhimento. "
            "Proteção 4 — Precisão Técnica Imutável e Fidelidade de Relações: o LLM não pode recalcular, arredondar criativamente, reconstruir ou inventar graus, minutos, orbes, cúspides, datas exatas, janelas, dignidades ou regências. Na narrativa principal, mencione os fatores preferencialmente por signo, casa e relações angulares (ex.: 'Sol em Escorpião culminando no Meio do Céu, em sextil com Saturno e Netuno em Capricórnio'), deixando valores matemáticos exatos de graus e orbes para o apêndice técnico canônico ou fatos verificados do handoff. Termos técnicos devem ser estritamente fiéis (conjunção somente dentro de orbe, não chame planetas de luminares, não diga 'junto ao ASC' sem suporte de orbe). Nunca combine aspectos diferentes sob o mesmo verbo ou conectivo (ex.: se Saturno faz sextil ao Sol e conjunção a Netuno, nunca escreva que 'Saturno faz sextil ao Sol e a Netuno'). "
            "Arquitetura da Abertura: a seção de abertura ('## Arquitetura do mapa') deve conter entre 2 e 4 parágrafos densos e conectados de síntese relacional entre os eixos estruturantes do mapa. É expressamente proibido fazer um inventário isolado de colocações (ex.: dedicar um parágrafo ou bullet separado para cada planeta ou fator mandatório). Fatores mandatórios devem ser tecidos conjuntamente nas dinâmicas relacionais que organizam o mapa. "
            "Plano Prospectivo de Blocos: utilize o plano prospectivo de blocos (SourceAwareBlockPlan) onde as fontes e o mecanismo pretendido são estabelecidos previamente. A redação deve materializar o mecanismo planejado a partir das fontes selecionadas, calculando os hashes dos blocos após a escrita. "
            "No eixo nodal, trate o Nodo Sul como repertório familiar e zona de conforto simbólica, e o Nodo Norte como direção de experimentação autônoma e desenvolvimento, evitando tratar o Sul como passado biográfico comprovado ou o Norte como destino obrigatório. "
            "No timing (Capítulo 18), comece pelo campo humano ativado e então apresente a técnica, aspecto/configuração, janela temporal, datas de exatidão/perfeição versus aproximação máxima, fator natal ativado e interpretação humana sem previsões deterministas ou acontecimentos garantidos (evite 'portal decisivo', 'alinhamento de destino', 'abrirá portas', 'determinará as próximas décadas'). Desenvolva detalhadamente a profecção anual ativa, o Senhor do Ano, os trânsitos maiores prioritários com datas de pico, as progressões secundárias e os ciclos planetários, sem comprimir o timing em um resumo apressado. "
            "A integração final organiza a pessoa como um todo através de uma síntese concreta e superior do mapa, evitando clichês abstratos ('síntese mais elevada', 'habitar o próprio centro', 'integridade consciente', 'soberania interior') quando formulações diretas comunicarem melhor, e encerra com uma única pergunta reflexiva profunda para testar a integração na vida real. "
            "Não use voz acadêmica, legalista ou de QA interno. Não acrescente fator, biografia, evento, diagnóstico ou certeza. Preserve citações internas de fatores para verificação, mas não as exponha no corpo principal. "
            "Quando um parágrafo usar modo direto de Claim, use-o apenas para a rota atômica da regência Placidus; nunca use esse modo para contexto natal do regente, personalidade, conclusão de domínio, timing ou outra composição, que exigem uma ReasonedSynthesis aprovada. "
            "Estruture o Premium com a introdução fixa do produto antes da abertura, depois abertura do mapa inteiro, exatamente os 16 headings canônicos do manifest e integração final. A introdução não é interpretação, não recebe proveniência nem conta como seção. Cada domínio disponível recebe tratamento próprio; low emphasis reduz prioridade, nunca vira um padrão de um parágrafo nem apaga mecanismos distintos. Não use quotas de palavras ou de parágrafos. Use somente as legal coverage paths e seu authorized_scope: um apoio não fabrica âncora e uma âncora estreita não autoriza todos os conceitos do heading. Em criatividade, Sol só sustenta vitalidade e Vênus prazer/valores: criatividade e expressão exigem rota legal da casa 5. Em corpo, Marte só sustenta ação/esforço; rotina, serviço e cuidado prático exigem rota legal da casa 6, e Marte não autoriza por si recuperação, regulação corporal ou saúde. Na direção de desenvolvimento, trate o eixo nodal completo — ambos os signos, ambas as casas e a tensão relacional — sem transformar Nodo Norte em Aquário na casa 1 em dependência de grupo. Explique um mecanismo central por inteiro uma vez e, em domínio posterior, acrescente a consequência específica daquele campo. Para domínio indisponível, reproduza apenas o aviso determinístico exato, sem editar nem acrescentar prosa. As sínteses de cobertura não alteram a ChartSignature preparada. Antes de escrever qualquer prosa, inspecione todo o manifest, construa prospectivamente o ReaderSelectionPlan com cada legal path como represented, merged_with_represented ou omitted_no_distinct_reader_value e só então escreva os blocos a partir desse plano; o plano não pode ser uma justificativa retrospectiva. A ordem das legal paths é serialização, não prioridade. No Premium Complete, não omita um mecanismo humano distinto apenas porque seu fator é secundário à ChartSignature. Em 1.4, use apenas o parser line-aware de narrative blocks: paragraphs e list items são coverage-eligible, H3 é subheading sourced e synthesis-only, mas nunca prova coverage ou selection; cada bloco source-required precisa de sua própria row e hash canônico. Não use nested lists, tabelas, blockquotes, HTML, code fences, separators, metadata ou H4+. Não inclua no leitor números de parágrafos, mecanismos, bullets, subseções, exemplos, palavras, minutos ou páginas. Contract 1.3 é somente replay/validation legado; novos handoffs são 1.4."
        )
    return (
        "Write as someone entering the chart beside the reader: warm, receptive, elegant, psychologically clear, and intimate without invented familiarity or flattery. "
        "Address the reader predominantly in natural second person, varying construction whenever repeated direct address would become mechanical. When useful, lead "
        "with human experience — a recognizable tension, need, or way of being — then reveal the astrology that illuminates it. Preserve nuance or contradiction and leave room "
        "for reflection; do not force that order when the astrological structure is clearer or more natural. Translate astrology immediately into plain language. Avoid mechanical openings such as 'you may notice' and a repeated resource/risk/question rhythm. "
        "For central dynamics, develop an inner mechanism, recognizable expression, distinction between integrated expression and defensive/under-pressure response, excess or false solution, material counterweight, and pathway of integration with another important factor when each genuinely adds meaning, never as a repeated formula. Note that integrated expression, defensive/under-pressure response, and excess are strictly internal psychodynamic reasoning lenses for the writer to calibrate human mechanisms in prose, and must NEVER be rendered as headings, subheadings, mandatory bullet triplets (e.g. formulaic three-bullet lists labeled as integrated, defensive, or excess), or rigid chapter-level structural scaffolds. "
        "Prefer verbs, movement, decisions, and lived experience over repeated nominalizations such as function, available coordination, structure, direction, integration, criterion, or possibility. Depth may be visibly irregular when the chart earns it; similar section lengths call for editorial inspection, never a mechanical target. That focus organizes the opening; it does not cap the rest of the reading. In each domain, develop every distinct reader-relevant mechanism supported by authorised evidence, including a tension, counterweight, distinct consequence, or whole-chart integration when each adds meaning. Humanisation changes expression; it does not reduce what the chart understands. Do not expose routing vocabulary: write 'because Venus rules your fourth house', not 'house four routed to Venus'. "
        "Chapter architecture and breathing room: each domain chapter must be developed with depth, nuance, and warmth across 2 to 4 distinct paragraphs (strictly avoid single-paragraph compressed monoliths of text): "
        "(1) The lived human core and the astrology that illuminates it: lead with the recognizable tension, core desire, or dilemma characteristic of that area, revealing the guiding astrological factor; "
        "(2) Psychodynamics, defenses, and everyday scenes: unfold how this behaves under pressure, automatic defense mechanisms, relational contrasts, and concrete everyday micro-scenes of decisions, work, or boundaries; "
        "(3) Active self-observation and integration: provide a lucid self-observation question or practical reflective inquiry that gives the reader an active mirror for self-understanding, connecting this domain to the wider chart architecture. "
        "Syntactic variety and rejection of repetitive templates: deliberately vary chapter openings and transitions. It is strictly forbidden to open consecutive chapters with repetitive passive templates (such as '[Noun A] and [Noun B] are structured/governed/guided by [planet/house]'). Open chapters with psychological paradoxes, practical contrasts, inner dilemmas, or tangible descriptions of behavior. "
        "Editorial rhythm and featured elements: the vast majority of the report must remain continuous natural prose. Use editorial elements (an embedded micro-scene, a separate example, bullets for parallel manifestations, a discriminative question, or an organic synthesis) only when they materially improve comprehension, retention, or rhythm, without fixed quotas or prescribed counts; hypothetical micro-scenes are welcome where abstract dynamics gain immediate clarity in everyday life (such as decision-making, boundaries, conflict, work, or money), never by quota, never labeled with uppercase tags, and never as invented biography. Use bullets preferably and sparingly for parallel manifestations, tension poles, pressure behaviors, or practical choices, not merely repeating placements already in prose nor as standardized structural triplets. "
        "Protection 1 — Epistemic Calibration: do not turn symbolic interpretation into established biographical or psychological certainty. Avoid categorical assertions or broad behavioral generalizations such as 'you developed precociously', 'you possess a natural gift', 'your boundaries are absolutely', 'you certainly', 'this is your true essence', 'you were designed to', 'hardly do you...', 'it is common for you to...', or 'you usually...'. Prefer testable hypotheses such as 'this can favor...', 'under certain conditions, a possible response is...', 'a useful hypothesis for self-observation is...', 'the configuration points to...', or 'the risk of this dynamic is...'. Rigorously distinguish strong astrological structure from inferred biography, keeping confidence strictly proportional to evidence. "
        "Protection 2 — Anti-Grandiosity and Anti-Flattery: avoid language that makes the person artificially exceptional, heroic, or superior (e.g. 'volcanic intensity', 'penetrating authority', 'extraordinary gift', 'innate gift', 'most noble configurations', 'naturally marked integrity', 'tailored vocation', 'exceptional leadership', 'grand destiny', 'monumental strength', 'superhuman capacity', 'incomparable brilliance'). The reading should be compelling because it reveals real human mechanisms, not because it flatters the reader. "
        "Protection 3 — Body and Health (Non-Medicalization): astrology does not produce diagnoses or physiological explanations. Do not make causal inferences about digestive issues, sleep, cellular regeneration, physiological necessity of isolation, exceptional physical stamina, specific bodily sensations ('heaviness or sluggishness'), or physical symptoms. The body/routine chapter (Chapter 9) must strictly focus on symbolic hypotheses for self-observation on rhythm, workload, daily routine, pauses, sustainability, subjective relationship with effort, and the need to alternate activity and quiet reflection. "
        "Protection 4 — Immutable Technical Precision and Relationship Fidelity: the LLM must never recalculate, round creatively, reconstruct, or invent degrees, minutes, orbs, cusps, exact dates, windows, dignities, or house rulers. In the narrative prose, refer to placements preferably by sign, house, and angular relationships (e.g. 'Sun in Scorpio culminating at the Midheaven, in sextile with Saturn and Neptune in Capricorn'), reserving exact mathematical degrees and orbs for the canonical technical appendix or verified handoff facts. Technical terms must be strictly faithful (conjunction only within orb criteria, do not call planets luminaries, do not say 'near the ASC' without orb backing). Never combine different aspects under a single connective (e.g. if Saturn sextiles Sun and conjuncts Neptune, never write that 'Saturn sextiles Sun and Neptune'). "
        "Whole-Chart Opening Architecture: the opening section ('## Arquitetura do mapa') must contain between 2 and 4 dense, connected paragraphs of relational synthesis between the chart's structural axes. It is strictly forbidden to present an isolated inventory of placements (e.g. dedicating a separate paragraph or bullet to each planet or mandatory factor). Mandatory factors must be woven together within the relational dynamics organizing the chart. "
        "Prospective Block Plan: work from the prospective block plan (SourceAwareBlockPlan) where sources and intended mechanisms are established prior to drafting. The writing must materialize the planned mechanism from selected sources, calculating block hashes after drafting. "
        "On the nodal axis, treat the South Node as a familiar repertoire and symbolic comfort zone, and the North Node as an experimental direction of autonomous individuation, avoiding treating the South Node as proven biography or the North Node as mandatory destiny. "
        "For timing (Chapter 18), lead with the human field being activated and then name the transit, profection, progression, arc, or cycle; use selected typed candidates only when they support a specific field. When several legal natal-timing interactions add distinct human consequences, develop their convergence, natal linkage, and useful dates/windows without technical dumping; group timing by human field and convergence, not a technique list, and do not reduce the active chapter to one activation merely for brevity. Show technique, aspect/configuration, window, exactness/perfection dates versus closest approach, activated natal factor, and human interpretation without deterministic prophecies or guaranteed events (avoid 'decisive portal', 'destiny alignment', 'will open doors', 'will determine decades'). Develop the annual profection, Lord of the Year, major transits with exact peak dates, secondary progressions, and planetary cycles in depth without compressing timing into a rushed summary. "
        "Final integration organizes the whole person through a concrete higher-order synthesis of the map, avoiding abstract clichés ('highest synthesis', 'inhabiting one's center', 'conscious integrity', 'inner sovereignty') when direct formulations communicate better, and closes with a single reflective question to test integration in real life. "
        "Use no academic, legalistic, or internal-QA voice. Do not add a factor, biography, event, diagnosis or certainty. "
        "Preserve internal factor citations for verification, but do not expose them in the main reading. When a paragraph uses direct Claim mode, use it only "
        "for the atomic Placidus house-ruler route; never use it for ruler natal context, personality, a domain conclusion, timing, or another composition, "
        "which require an approved ReasonedSynthesis. Structure Premium with the fixed product introduction before the whole-chart opening, exactly the manifest's 16 canonical headings, and final "
        "integration. The introduction is not interpretation, has no provenance, and does not count as a section. Every available domain receives its own treatment; low emphasis reduces priority but is never a one-paragraph default and never erases distinct mechanisms. Do not use word or paragraph quotas. Use only legal coverage paths and their "
        "authorized_scope: support cannot manufacture an anchor, and a narrow anchor does not authorise every concept in a heading. In creativity, the Sun supports vitality only and Venus pleasure/values only; creativity and expression require a legal house-5 route. In body, Mars supports action/effort only; routine, service, and practical care require a legal house-6 route, and Mars alone cannot authorise recovery, bodily regulation, or health. In developmental direction, treat the complete nodal axis — both signs, both houses, and their relational contrast — without turning an Aquarius North Node in house 1 into group dependence. Explain a central mechanism "
        "fully once, then add the distinct consequence in each later domain. For an unavailable domain, reproduce only the exact deterministic notice with no "
        "editing or added prose. Coverage syntheses do not alter the prepared ChartSignature. Before writing prose, inspect the entire manifest, build the prospective ReaderSelectionPlan with every legal path marked represented, merged_with_represented, or omitted_no_distinct_reader_value, and only then write blocks from that plan; the plan cannot be a retrospective justification. Legal-path order is serialization, not priority. In Premium Complete, do not omit a distinct human mechanism merely because its factor is secondary to the ChartSignature. In 1.4 use only the closed line-aware narrative-block parser: paragraphs and list items are coverage-eligible, while H3 subheadings are sourced and synthesis-only but never prove coverage or selection; each source-required block needs its own canonical hash and source row. Do not use nested lists, tables, blockquotes, HTML, code fences, separators, metadata, or H4+. Do not include reader-facing counts of paragraphs, mechanisms, bullets, subsections, examples, words, minutes, or pages. Contract 1.3 is replay/validation-only; new handoffs are always 1.4."
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
            "íntima sem presunção ou bajulação, de baixo jargão, com tradução imediata de termos astrológicos e interpretação antes de coaching; mantenha todo o relatório voltado ao leitor consistentemente no idioma solicitado, sem termos residuais de outro idioma; "
            "rejeite texto tecnicamente correto mas abstrato, psicologicamente genérico, emocionalmente plano, excessivamente cauteloso, "
            "fácil de trocar por outro mapa ou guiado por coaching; "
            "rejeite e reescreva ativamente quando encontrar: (1) grandiosidade ou tom heroico inflado; (2) bajulação ou elogios desprovidos de lastro técnico; (3) certeza biográfica ou psicológica injustificada; (4) medicalização ou alegações fisiológicas específicas; (5) termos técnicos incorretos ou números/graus recalculados pelo LLM; (6) timing determinista com garantia de acontecimentos; (7) fórmulas genéricas tipo Barnum ou autoajuda rasa; (8) abstração vazia sem ancoragem concreta; (9) repetição vocabular e loops retóricos; (10) template smell e andaimes mecânicos previsíveis entre capítulos (incluindo triplets obrigatórios de bullets, rotulação das lentes internas 'integrado / defensivo / excesso' ou repetição monótona de fórmulas sintáticas de abertura como '[A] e [B] são estruturados por [C]'); (11) capítulos comprimidos em monólitos de parágrafo único sem respiração tipográfica (exija que cada domínio desdobre 2 a 4 parágrafos bem modulados); (12) seções longas sem nenhum elemento concreto; (13) exemplos hipotéticos que não derivam da evidência do mapa; (14) aberturas que inventariem colocações planetárias isoladas (ex.: um parágrafo por planeta/fato mandatório); (15) combinações sintáticas falsas de aspectos (ex.: 'Saturno faz sextil ao Sol e a Netuno'). "
            "Tarefa editorial obrigatória: examine onde dinâmicas abstratas necessitam de situações concretas e certifique-se de que microcenas hipotéticas surjam organicamente onde agregam clareza, sem impor quotas de contagem ou fórmulas obrigatórias por capítulo. Exija que cada domínio respire organicamente em 2 a 4 parágrafos estruturados (o cerne vivido e a astrologia que ilumina; psicodinâmica, defesas e cenas do cotidiano; hipótese ou pergunta lúcida de auto-observação integrando ao todo), eliminando rigorosamente qualquer parágrafo único monolítico ou vácuo interrogativo. Revise bullets: certifique-se de que bullets sejam usados com moderação para manifestações paralelas, polos de tensão ou escolhas práticas, eliminando completamente qualquer triplet mecânico recorrente (especialmente listas formulaicas replicando 'integrado / defensivo / excesso' como andaime estrutural) e garantindo que a prosa contínua prevaleça. "
            "Nas dinâmicas centrais, exija desenvolvimento reconhecível do mecanismo sem impor uma fórmula de abertura ou parágrafo. Exija que a abertura ('## Arquitetura do mapa') seja estritamente síntese relacional em 2 a 4 blocos conectando os centros de gravidade; rejeite aberturas de inventário isolado mesmo se a cobertura técnica estiver satisfeita. Não aprove uma leitura só porque cada heading existe: verifique se mecanismos autorizados distintos foram desenvolvidos antes de o texto ser comprimido e revise ativamente o ReaderSelectionPlan: rejeite justificativas padronizadas de omissão, exija que fusões sejam substantivas e ateste que nenhuma consequência humana distinta foi perdida em omissões em massa. Dê preferência a uma cadência humana: experiência, astrologia que ilumina, nuance e reflexão, preservando variação. "
            "Remova linguagem de QA, avisos legais e a repetição de recurso/risco quando a cautela puder ser dita naturalmente sem perder o limite, mas nunca troque raciocínio astrológico por autoajuda genérica. Retenha timing ou desenvolvimento somente quando a evidência tipada selecionada "
            "sustentar um campo humano útil e específico ligado ao natal; se não acrescentar consequência própria, corte-o em vez de preencher espaço; se mais de uma interação legal acrescentar consequência distinta, preserve a convergência, a ligação natal e datas úteis em linguagem humana. Corte apenas padding, não profundidade. Faça o swap test "
            "conceitual em cada parágrafo principal e corrija genericidade por seleção ou mecanismo, nunca inventando detalhes de vida. Para cada "
            "parágrafo em modo direto de Claim, compare-o com o Claim canônico indicado, não com uma síntese: um Claim de regência Placidus autoriza "
            "somente a rota atômica casa–cúspide–regente. Reescreva ou remova qualquer contexto natal do regente, significado de personalidade, "
            "conclusão de domínio, timing ou dedução multifatorial sem ReasonedSynthesis aprovada. Proteja as três camadas: bloqueie heading ausente, domínio "
            "superficial, abertura que inventarie placements e conclusão que apenas resuma. Exija que a integração comece pelo que organiza a pessoa como um todo através de síntese concreta, não por timeline ou metadados. Compare cada tratamento com authorized_scope de sua legal path; um "
            "fator de apoio não cria âncora e um escopo estreito não cobre automaticamente todo o heading. Garanta localidade de atribuição semântica: cada proposição gramatical deve ser autorizada pelo fator ao qual ela é atribuída; uma âncora válida mais adiante no parágrafo não salva uma alegação anterior ampla. Em criatividade, exija que expressão/criatividade tenha rota legal da casa 5, sem transformar Sol em criatividade genérica; em corpo, exija casa 6 para rotina/cuidado prático e não deixe Marte fabricar recuperação, regulação corporal ou saúde. Na direção de desenvolvimento, confira o eixo nodal inteiro, com ambos os signos e casas, e rejeite suposição de gênero ou formulação marcada quando ela não foi fornecida. Low emphasis reduz prioridade, não autoriza uma seção curta por padrão. Exija que reutilização "
            "acrescente consequência própria do domínio, que a integração final desenvolva síntese memorável em vez de resumo, e preserve exatamente qualquer aviso determinístico indisponível. Antes de aprovar, julgue semanticamente se o mecanismo humano distinto de cada path `represented` está materialmente expresso nos blocos elegíveis; para `merged_with_represented`, a convergência precisa ser material e não pode ser justificada apenas por planeta, regente, classe de raciocínio, operação ou tópico amplo compartilhado. Para `omitted_no_distinct_reader_value`, ateste que nenhuma consequência humana distinta permanece. Python prova somente shape, ordem, IDs, hashes, syntheses aprovadas, provenance física de paragraphs/list items, legalidade individual de syntheses, ownership, timing e coverage determinística; não prova equivalência semântica. H3 deve ser revisado para orientação e significado, mas nunca conta para mandatory/domain/selection coverage. Revalide no relatório final o plano usando somente paragraphs/list items; se o Author paragraph/list for removido e restar apenas H3 sourced, rejeite. Exija hashes, ownership e source rows atualizados após qualquer edição de layout."
        )
    return (
        "Compare each final paragraph with its authorised ReasonedSynthesis. Approve only if core meaning, certainty and "
        "limits are equivalent; also confirm that valid contradictions were not flattened and every counterweight materially "
        "qualifies the proposition. Prose may be more human but cannot add a factor, treat a conditional house as fact, add "
        "biography, diagnosis, event or forecast. Require direct, psychologically legible, intimate-but-non-presumptive, low-jargon "
        "voice with immediate plain-language translation of astrology and interpretation before coaching; keep the entire reader-facing report consistently in the requested language, without residual terms from another language; "
        "reject prose that is technically correct but abstract, psychologically generic, emotionally flat, overly cautious, easily swapped to another chart, or coaching-led; "
        "actively reject and rewrite when encountering: (1) grandiosity or inflated heroic tone; (2) flattery or ungrounded praise; (3) unjustified biographical or psychological certainty; (4) medicalization or specific physiological claims; (5) incorrect technical terms or LLM-recalculated mathematical degrees; (6) deterministic timing with guaranteed events; (7) generic Barnum phrasing or shallow self-help; (8) empty abstraction lacking concrete grounding; (9) repetitive vocabulary and rhetorical loops; (10) template smell and predictable mechanical scaffolding across chapters (including mandatory bullet triplets, labeling of internal lenses 'integrated / defensive / excess', or repetitive passive opening templates like '[A] and [B] are structured by [C]'); (11) chapters collapsed into single-paragraph monoliths lacking typographic breathing room (require 2 to 4 well-modulated paragraphs per domain); (12) long sections without any concrete element; (13) hypothetical examples that do not derive from chart evidence; (14) openings that inventory isolated placements (e.g. one paragraph per planet/mandatory factor); (15) false aspect relationship combinations (e.g. 'Saturn sextiles Sun and Neptune'). "
        "Mandatory editorial task: examine where abstract dynamics require concrete situations and ensure hypothetical micro-scenes appear organically where they add clarity, without imposing count quotas or mandatory formulas per chapter. Require every domain chapter to breathe organically across 2 to 4 structured paragraphs (the lived human core and illuminating astrology; psychodynamics, defenses, and everyday scenes; lucid self-observation question/hypothesis integrating into the whole), strictly eliminating single-paragraph monoliths or interrogative vacuums. Inspect bullets: ensure bullets are used sparingly for parallel manifestations, tension poles, or practical choices, completely eliminating any recurring mechanical triplets (especially formulaic lists replicating 'integrated / defensive / excess' as structural scaffolding) and ensuring that continuous prose prevails. "
        "For central dynamics, require recognizable development of the mechanism without imposing a fixed opening or paragraph formula. Require the opening ('## Arquitetura do mapa') to be strictly relational synthesis in 2 to 4 blocks connecting structural centers of gravity; reject placement inventories even if deterministic coverage passes. Do not approve merely because each heading exists: check that distinct authorised mechanisms were developed before prose was compressed, and actively inspect the reader_selection_plan: reject boilerplate omission rationales, require merges to be substantive, and verify no distinct human consequence was lost in mass omissions. Prefer a human cadence of experience, illuminating astrology, nuance, and reflection, while preserving variation. Remove internal-QA wording, legalistic cautions, and repeated resource/risk scaffolding whenever natural language keeps the same boundary, but never replace astrological reasoning with generic self-help. Retain timing or developmental material only "
        "when selected typed evidence supports a useful, specific human field linked to natal evidence; when more than one legal interaction adds a distinct consequence, preserve convergence, natal linkage, and useful dates in human language. Cut padding, not depth. Apply a conceptual "
        "swap test to each major paragraph and correct genericity through selection or mechanism, never invented life detail. For every direct-Claim paragraph, "
        "compare the prose with its cited canonical Claim rather than a synthesis: a Placidus house-ruler Claim authorises only the atomic house–cusp–ruler "
        "route. Rewrite or remove ruler natal context, personality meaning, a domain conclusion, timing, or any multi-factor deduction unless an approved "
        "ReasonedSynthesis authorises it. Protect all three layers: block a missing heading, superficial domain, placement-inventory opening, or merely summarising "
        "ending. Require final integration to begin with the whole person's higher-order concrete organization, not timeline or metadata. Compare each treatment with the authorized_scope of its legal path; a supporting factor cannot create an anchor and a narrow scope cannot cover "
        "every concept in the heading. Enforce semantic attribution locality: every grammatical proposition must be authorised by the factor to which it is attributed; a valid anchor later in the paragraph cannot rescue an earlier broad assertion. In creativity, require a legal house-5 route for creativity/expression rather than making the Sun generic creativity; in body, require house 6 for routine/practical care and do not let Mars manufacture recovery, bodily regulation, or health. In developmental direction, verify the entire nodal axis, both signs and houses, and reject gendered wording when none was supplied. Low emphasis reduces priority; it never licenses a default short section. Require reused mechanisms to add a domain-specific consequence and final integration to develop memorable synthesis rather than a summary, "
        "and preserve any deterministic unavailable notice exactly. Before approval, judge semantically whether each `represented` path's distinct human mechanism is materially expressed in coverage-eligible blocks; for `merged_with_represented` paths, convergence must be material and cannot be justified merely by a shared planet, house ruler, reasoning class, operation, or broad topic. For `omitted_no_distinct_reader_value` paths, attest that no distinct human consequence remains. Python proves only shape, order, IDs, hashes, approved syntheses, physical paragraph/list-item provenance, individual synthesis legality, ownership, timing, and deterministic coverage; it does not prove semantic equivalence. Review H3 for orientation and meaning, but never count it for mandatory, domain, or selection coverage. Revalidate the plan against the final report using paragraphs and list items only; if the Author paragraph/list item is removed and only a sourced H3 remains, reject. Require hashes, ownership, and source rows to be updated after layout edits."
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
