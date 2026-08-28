"""Constrained astrological reasoning between facts and human prose.

This module does not calculate astrology and it does not call a remote model.
It builds the closed factual packet, validates model-authored deductions, and
offers a deterministic fallback plan for the local CLI.  A high-reasoning LLM
uses the same packet to make the actual holistic choices at freedom levels 2–3.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Dict, Iterable, List, Sequence

from .config import BODY_LABELS, PRIMARY_BODIES
from .models import Claim, ReasonedSynthesis, to_primitive
from .safe_view import SafeInterpretiveChart
from .semantics import PLANET_FUNCTIONS, PLANET_SHORT_FUNCTIONS, theme_label
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


def build_reasoning_packet(
    chart: SafeInterpretiveChart,
    hierarchy: Dict[str, Dict[str, object]],
    claims: Iterable[Claim],
    timing: Dict[str, object] | None = None,
    language: str = "pt-BR",
    localization_profile: object | None = None,
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
            "whole_sign_house": placement.whole_sign_house,
            "placidus_house": placement.placidus_house,
            "integration_state": placement.integration_state,
        }
        for body, placement in chart.house_placements.items()
        if body in PRIMARY_BODIES
    ]
    return {
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
        },
        "hard_boundaries": {
            "may_use_only_factor_ids": sorted(_evidence_ids(chart)),
            "may_not_infer": PROHIBITED_EXTENSIONS,
            "conditional_house_policy": "Do not use conditional house context as central evidence. It may be disclosed as a conditional alternative only.",
            "localization_policy": "Localization may change language and examples, never factor weights, personality or prediction.",
        },
        "localized_rendering_context": localization_audit(localization_profile).get("rendering_context"),
    }


def validate_reasoned_syntheses(items: Sequence[ReasonedSynthesis], chart: SafeInterpretiveChart) -> List[ReasonedSynthesis]:
    """Strictly validate an emergent synthesis without forcing registry prose."""
    known = _evidence_ids(chart)
    output: List[ReasonedSynthesis] = []
    for item in items:
        errors: List[str] = []
        cited = list(item.primary_factors) + list(item.modifiers) + list(item.counterweights)
        if not item.primary_factors:
            errors.append("missing_primary_factors")
        if any(factor not in known for factor in cited):
            errors.append("unknown_or_unsafe_factor")
        if item.reasoning_class not in REASONING_CLASSES:
            errors.append("invalid_reasoning_class")
        if item.confidence_within_astrological_model not in CONFIDENCE:
            errors.append("invalid_confidence")
        # One aspect already composes two planetary functions; a lone house or
        # condition does not.
        if item.reasoning_class != "single_structural_factor" and len(set(item.primary_factors)) < 2 and not any(factor.startswith("aspect.") for factor in item.primary_factors):
            errors.append("insufficient_composition_support")
        folded = " ".join([item.observation, item.alternative_reading, *item.possible_expressions]).casefold()
        if any(token in folded for token in ("diagnóstico", "diagnosis", "trauma", "morte", "death", "doença", "disease", "vai acontecer", "will happen")):
            errors.append("prohibited_extension_in_reasoning")
        item.verification_errors = errors
        item.status = "blocked" if errors else "allowed"
        output.append(item)
    return output


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
        if len(primary) == 1 and structural:
            reasoning_class = "single_structural_factor"
        elif counterweights:
            reasoning_class = "integrated_pattern"
        else:
            reasoning_class = "theme_interaction" if len(bodies) >= 2 else "integrated_pattern"
        observation = _fallback_observation(theme_id, bodies, structural, chart, primary, language)
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
            narrative_moves=_narrative_moves(chart, primary, bodies, language),
        ))
    # hierarchy.* is a valid packet id, although it is not a raw Chart factor.
    checked = validate_reasoned_syntheses(candidates, chart)
    for item in checked:
        virtual = [factor for factor in item.modifiers if factor.startswith("hierarchy.")]
        if virtual and item.status == "blocked" and "unknown_or_unsafe_factor" in item.verification_errors:
            item.verification_errors.remove("unknown_or_unsafe_factor")
            item.status = "allowed" if not item.verification_errors else "blocked"
    return [to_primitive(item) for item in checked]


def build_narrative_plan(themes: List[Dict[str, object]], syntheses: List[Dict[str, object]], language: str = "pt-BR") -> Dict[str, object]:
    """Choose hierarchy and cross references before prose is drafted."""
    usable = [item for item in syntheses if item["status"] == "allowed"]
    by_id = {item["id"].removeprefix("reasoned."): item for item in usable}
    ordered = [theme for theme in themes if str(theme["id"]) in by_id]
    leading = ordered[:5]
    central = _central_dynamic(leading, by_id, language)
    references = []
    seen_bodies: Dict[str, str] = {}
    for theme in leading:
        synthesis = by_id[str(theme["id"])]
        for factor in synthesis["primary_factors"]:
            for body in factor.split(".")[-1].replace("_", " ").split():
                if body in seen_bodies and seen_bodies[body] != theme["id"]:
                    references.append({"from": theme["id"], "to": seen_bodies[body], "reason": "shared structural factor"})
                else:
                    seen_bodies[body] = str(theme["id"])
    return {
        "opening": central,
        "themes": [str(theme["id"]) for theme in leading],
        "sequence": "structure → central dynamic → differentiated themes → concrete areas → timing → integration",
        "cross_references": references[:6],
        "avoid_repetition": ["Explain each structural factor once; later sections reference it briefly.", "Do not force a light/shadow formula where a nuance or counterweight is more useful."],
        "technical_details_to_hide": ["aspect names", "house-system labels when convergent", "orb values", "registry identifiers"],
        "integration_move": by_id[str(leading[0]["id"])]["narrative_moves"]["integration"] if leading else "",
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
            "Reescreva a partir do plano e das sínteses autorizadas. Varie ritmo e estrutura; use exemplos hipotéticos e "
            "contextuais; explique mecanismos antes de nomes técnicos. Não acrescente fator, biografia, evento, diagnóstico ou "
            "certeza. Preserve as citações internas de fatores para verificação, mas não as exponha no corpo principal."
        )
    return (
        "Rewrite from the plan and authorised syntheses. Vary rhythm and structure; use contextual hypothetical examples; "
        "explain mechanisms before technical labels. Do not add a factor, biography, event, diagnosis or certainty. Preserve "
        "internal factor citations for verification, but do not expose them in the main reading."
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
            "o nível de certeza e os limites forem equivalentes; a prosa pode ser mais humana, mas não pode incluir novo "
            "fator, casa condicional como fato, biografia, diagnóstico, evento ou previsão. Para cada falha, devolva a "
            "frase, o factor_id ausente ou limite violado e uma instrução curta de regeneração."
        )
    return (
        "Compare each final paragraph with its authorised ReasonedSynthesis. Approve only if core meaning, certainty and "
        "limits are equivalent; prose may be more human but cannot add a factor, treat a conditional house as fact, add "
        "biography, diagnosis, event or forecast. For every failure return the sentence, missing factor_id or violated "
        "limit, and a short regeneration instruction."
    )


def llm_reasoning_instructions() -> str:
    return (
        "Use only the closed factual packet. You may create a derived_claim when it cites 1–5 existing factor ids, names an "
        "alternative reading and stays at symbolic/behavioral possibility level. Treat registry motifs as boundaries, not report "
        "sentences. Give priority to structural bodies, exact configurations, condition, safe topical context and counterweights. "
        "Do not turn conditional house context into central evidence. Return ReasonedSynthesis objects before writing prose."
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
        left = labels.get(chosen.left, chosen.left)
        right = labels.get(chosen.right, chosen.right)
        left_function = functions.get(chosen.left, chosen.left)
        right_function = functions.get(chosen.right, chosen.right)
        dynamic = (ASPECT_FUNCTIONS_PT if lang == "pt" else ASPECT_FUNCTIONS)[chosen.kind]
        if lang == "pt":
            return (
                f"Neste mapa, o tema **{label}** ganha uma coloração própria: {left} liga {left_function} a {right_function} "
                f"por uma dinâmica de {dynamic}."
            )
        return (
            f"In this chart, **{label}** takes on a particular colour: {left} links {left_function} with {right_function} "
            f"through a dynamic of {dynamic}. The theme is not a loose label; it describes how those two functions need to work together."
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


def _central_dynamic(themes: List[Dict[str, object]], syntheses: Dict[str, Dict[str, object]], language: str) -> Dict[str, object]:
    if not themes:
        return {"status": "distributed", "observation": "No sufficient central dynamic."}
    if len(themes) == 1:
        return {"status": "single", "themes": [themes[0]["id"]], "observation": syntheses[str(themes[0]["id"])]["observation"]}
    first, second = themes[:2]
    first_synthesis = syntheses[str(first["id"])]
    second_synthesis = syntheses[str(second["id"])]
    shared = set(first_synthesis["primary_factors"]) & set(second_synthesis["primary_factors"])
    if language.startswith("pt"):
        observation = (
            f"A leitura se organiza em torno de **{first['label']}** e **{second['label']}**. "
            "Em vez de tratá-los como traços isolados, vale observar onde um modifica a forma de viver o outro: "
            "a resposta mais fértil costuma depender do contexto, não de escolher um polo definitivo."
        )
    else:
        observation = (
            f"The reading is organised around **{first['label']}** and **{second['label']}**. "
            "Rather than treating them as isolated traits, notice where one changes how the other is lived: "
            "the more useful response usually depends on context, not on choosing one permanent pole."
        )
    return {"status": "candidate", "themes": [first["id"], second["id"]], "shared_factors": sorted(shared), "observation": observation}
