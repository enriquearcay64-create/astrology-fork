"""Versioned semantic registry and evidence-aware claim verification.

The renderer never improvises directly from positions. Facts are converted into
authorised motifs here, then verified against the chart evidence ledger.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .config import BODY_LABELS, CORE_ANGLES, SIGN_RULERS, THEME_LABELS_PT
from .models import Chart, Claim

SEMANTIC_REGISTRY_VERSION = "2.4.0"

THEME_LABELS_EN = {
    "autonomy_closeness": "autonomy and closeness", "stability_change": "stability and change",
    "visibility_privacy": "visibility and privacy", "control_spontaneity": "control and spontaneity",
    "security_exploration": "security and exploration", "reason_feeling": "reason and feeling",
    "receptivity_initiative": "receptivity and initiative", "individuality_belonging": "individuality and belonging",
    "purpose": "purpose", "creativity": "creative expression", "competence": "competence and structure",
    "care": "care", "ambition": "ambition", "pleasure": "pleasure", "transformation": "transformation",
    "power": "power and agency", "service": "service", "spirituality": "meaning and transcendence",
    "curiosity": "curiosity", "order": "order",
}

PLANET_FUNCTIONS = {
    "pt": {
        "sun": "identidade, vitalidade e direção", "moon": "necessidades e regulação emocional", "mercury": "pensamento e comunicação",
        "venus": "vínculo, prazer e valores", "mars": "ação, desejo e limites", "jupiter": "crescimento, sentido e exploração",
        "saturn": "estrutura, responsabilidade e limites", "uranus": "autonomia, mudança e ruptura de padrões",
        "neptune": "imaginação, sensibilidade e transcendência", "pluto": "intensidade, poder e transformação",
        "true_node": "direção de desenvolvimento", "chiron": "sensibilidade e reparação", "lilith_mean": "tensões de limite",
    },
    "en": {
        "sun": "identity, vitality and direction", "moon": "needs and emotional regulation", "mercury": "thinking and communication",
        "venus": "connection, pleasure and values", "mars": "action, desire and boundaries", "jupiter": "growth, meaning and exploration",
        "saturn": "structure, responsibility and limits", "uranus": "autonomy, change and pattern disruption",
        "neptune": "imagination, sensitivity and transcendence", "pluto": "intensity, power and transformation",
        "true_node": "developmental direction", "chiron": "sensitivity and repair", "lilith_mean": "boundary tension",
    },
}

PLANET_SHORT_FUNCTIONS = {
    "pt": {
        "sun": "direção pessoal", "moon": "necessidades emocionais", "mercury": "pensamento/comunicação",
        "venus": "vínculo/valores", "mars": "ação/limites", "jupiter": "crescimento/sentido",
        "saturn": "estrutura/responsabilidade", "uranus": "autonomia/mudança", "neptune": "imaginação/sensibilidade",
        "pluto": "intensidade/transformação", "true_node": "direção de desenvolvimento", "chiron": "sensibilidade/reparação",
        "lilith_mean": "tensões de limite",
    },
    "en": {
        "sun": "personal direction", "moon": "emotional needs", "mercury": "thought and communication",
        "venus": "connection and values", "mars": "action and boundaries", "jupiter": "growth and meaning",
        "saturn": "structure and responsibility", "uranus": "autonomy and change", "neptune": "imagination and sensitivity",
        "pluto": "intensity and transformation", "true_node": "developmental direction", "chiron": "sensitivity and repair",
        "lilith_mean": "boundary tensions",
    },
}

PLANET_DEFAULT_THEME = {
    "sun": "purpose", "moon": "care", "mercury": "curiosity", "venus": "pleasure", "mars": "receptivity_initiative",
    "jupiter": "security_exploration", "saturn": "competence", "uranus": "stability_change", "neptune": "spirituality",
    "pluto": "transformation", "true_node": "purpose", "chiron": "care", "lilith_mean": "control_spontaneity",
}

HOUSE_TOPICS = {
    "pt": {
        1: "identidade e presença", 2: "recursos e segurança", 3: "aprendizado e comunicação", 4: "raízes e vida privada",
        5: "expressão, prazer e criação", 6: "rotina, serviço e cuidado prático", 7: "parcerias e reciprocidade",
        8: "intimidade, recursos compartilhados e transformação", 9: "sentido, estudo e horizontes",
        10: "vocação, contribuição e visibilidade", 11: "redes, futuro e pertencimento", 12: "retirada, imaginação e processos de fundo",
    },
    "en": {
        1: "identity and presence", 2: "resources and security", 3: "learning and communication", 4: "roots and private life",
        5: "expression, pleasure and creation", 6: "routine, service and practical care", 7: "partnership and reciprocity",
        8: "intimacy, shared resources and transformation", 9: "meaning, study and wider horizons",
        10: "vocation, contribution and visibility", 11: "networks, future and belonging", 12: "retreat, imagination and background processes",
    },
}

HOUSE_THEME = {
    1: "individuality_belonging", 2: "security_exploration", 3: "curiosity", 4: "care",
    5: "creativity", 6: "service", 7: "autonomy_closeness", 8: "transformation",
    9: "purpose", 10: "ambition", 11: "individuality_belonging", 12: "spirituality",
}

# theme, pt core, en core, authorised motifs, safe examples, prohibited inferences
PAIR_RULES: Dict[frozenset, Tuple[str, str, str, List[str], List[str], List[str]]] = {
    frozenset(("moon", "uranus")): ("autonomy_closeness", "tensão entre continuidade emocional e autonomia/mudança", "tension between emotional continuity and autonomy/change", ["emotional_variability", "autonomy_vs_closeness"], ["necessidade variável de espaço emocional", "formas pouco convencionais de regular proximidade"], ["abandono", "trauma", "bipolaridade", "divórcio"]),
    frozenset(("moon", "saturn")): ("care", "tensão entre necessidade emocional e contenção/estrutura", "tension between emotional needs and containment/structure", ["care_with_structure", "emotional_reserve"], ["cuidado expresso com responsabilidade", "processar emoções com reserva"], ["mãe fria", "abandono", "depressão"]),
    frozenset(("venus", "uranus")): ("autonomy_closeness", "tensão entre vínculo, escolha e liberdade", "tension between connection, choice and freedom", ["relational_autonomy", "unconventional_connection"], ["relações que preservem individualidade", "formas menos convencionais de conexão"], ["divórcio", "incapacidade de compromisso"]),
    frozenset(("mars", "saturn")): ("control_spontaneity", "tensão entre impulso de agir e necessidade de estrutura", "tension between the impulse to act and the need for structure", ["disciplined_action", "frustration_and_pacing"], ["ação disciplinada com objetivo claro", "ritmo e estratégia diante da frustração"], ["raiva reprimida", "fracasso inevitável"]),
    frozenset(("sun", "saturn")): ("competence", "tensão entre expressão pessoal e exigência/estrutura", "tension between self-expression and demands/structure", ["earned_competence", "self_defined_standards"], ["seriedade ao construir competência", "definir padrões próprios de realização"], ["pai ausente", "baixa autoestima clínica"]),
    frozenset(("sun", "uranus")): ("individuality_belonging", "pressão entre expressão pessoal e independência", "pressure between self-expression and independence", ["originality", "directional_renewal"], ["espaço para originalidade", "renovar uma direção rígida"], ["ruptura inevitável"]),
    frozenset(("mercury", "neptune")): ("reason_feeling", "interação entre pensamento, imaginação e sensibilidade", "interaction between thought, imagination and sensitivity", ["associative_thinking", "intuition_with_verification"], ["linguagem imaginativa", "alternar intuição e checagem prática"], ["mentiroso", "confusão mental clínica"]),
    frozenset(("venus", "pluto")): ("transformation", "intensidade entre vínculo, valor e transformação", "intensity between connection, values and transformation", ["relational_intensity", "values_transformation"], ["vínculos mobilizando valores profundos", "clareza sobre desejo e reciprocidade"], ["obsessão", "abuso"]),
}

PROHIBITED_PATTERNS = [
    r"\b(abandono|abuso|trauma|bipolar|diagn[oó]stico|div[oó]rcio|morte|doen[cç]a|gravidez|fal[eê]ncia)\b",
    r"\b(abandonment|abuse|trauma|bipolar|diagnosis|divorce|death|disease|pregnancy|bankruptcy)\b",
    r"\b(inevitavelmente|garantidamente|sempre ser[aá]|vai acontecer|prova que|causou)\b",
    r"\b(inevitably|guaranteed|will always|will happen|proves that|caused by)\b",
    r"\b(pai ausente|m[aã]e ausente|m[aã]e fria|mentiroso|obsess[aã]o|raiva reprimida)\b",
    r"\b(absent father|absent mother|cold mother|liar|obsession|repressed anger|clinical)\b",
]


def _language(language: str) -> str:
    return "pt" if language.casefold().startswith("pt") else "en"


def _aspect_weight(kind: str, orb: float) -> str:
    exact = 1.0 if kind == "quincunx" else 1.5
    return "strong" if orb <= exact else "moderate" if orb <= 4.0 else "light"


def _safe_text(statement: str) -> bool:
    lowered = statement.casefold()
    return not any(re.search(pattern, lowered) for pattern in PROHIBITED_PATTERNS)


def _generic_theme(pair: frozenset) -> str:
    """Order-invariant conservative composition for pairs outside the registry."""
    if {"moon", "mars"} <= pair:
        return "receptivity_initiative"
    if "mercury" in pair and pair.intersection({"moon", "neptune", "venus"}):
        return "reason_feeling"
    if {"saturn", "uranus"} <= pair:
        return "stability_change"
    if "uranus" in pair:
        return "stability_change"
    if "pluto" in pair:
        return "transformation"
    if "neptune" in pair:
        return "spirituality"
    if "saturn" in pair:
        return "competence"
    if "jupiter" in pair:
        return "security_exploration"
    return sorted(PLANET_DEFAULT_THEME.get(body, "order") for body in pair)[0]


def _generic_example(left: str, right: str, kind: str, lang: str) -> str:
    functions = PLANET_SHORT_FUNCTIONS[lang]
    left_function, right_function = functions.get(left, left), functions.get(right, right)
    if lang == "pt":
        templates = {
            "square": "uma situação concreta com conflito de prioridade entre {left} e {right}",
            "opposition": "uma escolha que peça equilibrar {left} com {right}",
            "conjunction": "uma decisão que concentre {left} e {right}",
            "trine": "um contexto com apoio mútuo entre {left} e {right}, sem assumir que isso ocorra sempre",
            "sextile": "uma oportunidade de articular {left} com {right}",
            "quincunx": "um ajuste recorrente que articule {left} com {right}",
        }
    else:
        templates = {
            "square": "a concrete situation in which {left} and {right} compete for priority",
            "opposition": "a choice requiring balance between {left} and {right}",
            "conjunction": "a decision in which {left} and {right} act together",
            "trine": "a context in which {left} supports {right}, without assuming this always happens",
            "sextile": "an opportunity to combine {left} with {right}",
            "quincunx": "a recurring adjustment between {left} and {right}",
        }
    return templates[kind].format(left=left_function, right=right_function)


def _claim_from_aspect(aspect, index: int, language: str) -> Claim:
    lang = _language(language)
    pair = frozenset((aspect.left, aspect.right))
    if pair in PAIR_RULES:
        theme, core_pt, core_en, motifs, examples, prohibited = PAIR_RULES[pair]
        core = core_pt if lang == "pt" else core_en
    else:
        theme = _generic_theme(pair)
        ordered = sorted(pair)
        functions = PLANET_FUNCTIONS[lang]
        left, right = ordered
        if lang == "pt":
            core = f"coordenação entre a função de {BODY_LABELS[lang].get(left, left)} ({functions.get(left, left)}) e a de {BODY_LABELS[lang].get(right, right)} ({functions.get(right, right)})"
        else:
            core = f"coordination between {left.title()} ({functions.get(left, left)}) and {right.title()} ({functions.get(right, right)})"
        motifs = [f"{theme}_{aspect.kind}_coordination"]
        examples = [_generic_example(left, right, aspect.kind, lang)]
        prohibited = ["biografia específica", "diagnóstico", "evento previsto"]
    if lang == "en" and pair in PAIR_RULES:
        examples = [f"observe how {theme_label(theme, 'en-US')} may show up in a concrete choice"]
    dynamics = {
        "pt": {"square": "sob pressão", "opposition": "em polaridade", "conjunction": "de forma concentrada", "trine": "com maior fluidez", "sextile": "como oportunidade de coordenação", "quincunx": "como ajuste contínuo"},
        "en": {"square": "under pressure", "opposition": "as a polarity", "conjunction": "in concentrated form", "trine": "with greater ease", "sextile": "as an opportunity for coordination", "quincunx": "as an ongoing adjustment"},
    }
    sentence_core = core[:1].upper() + core[1:]
    if lang == "pt":
        statement = f"{sentence_core} pode aparecer {dynamics[lang][aspect.kind]}; é uma possibilidade simbólica, não um fato biográfico."
    else:
        statement = f"{sentence_core} may appear {dynamics[lang][aspect.kind]}; this is a symbolic possibility, not a biographical fact."
    return Claim(
        id=f"claim.aspect.{index}", theme=theme, type="symbolic_tendency", statement=statement,
        evidence=[aspect.id], evidence_families=["_".join(sorted(pair)) + f"_{aspect.kind}_dynamic"], counterweights=[],
        allowed_specificity="behavioral_possibility", allowed_examples=examples,
        prohibited_inferences=prohibited, astrological_support=_aspect_weight(aspect.kind, aspect.orb),
        authorized_motifs=motifs,
    )


def _claim_from_house(chart: Chart, body: str, index: int, language: str) -> Claim:
    lang = _language(language)
    placement = chart.house_placements[body]
    topic = HOUSE_TOPICS[lang][placement.whole_sign_house]
    placidus_topic = HOUSE_TOPICS[lang].get(placement.placidus_house) if placement.placidus_house else None
    integration = {
        "pt": {
            "convergence_strong": "Os dois sistemas configurados convergem na mesma casa.",
            "whole_topic_placidus_qualifier": f"Signo Inteiro fornece o tópico; Placidus qualifica a expressão espacial{f' pela casa {placement.placidus_house}, ligada a {placidus_topic}' if placidus_topic and placement.placidus_house != placement.whole_sign_house else ' pela proximidade de cúspide'}.",
            "complementary_emphases": f"Placidus acrescenta a casa {placement.placidus_house}, ligada a {placidus_topic}; as ênfases permanecem complementares sem somar evidência.",
            "material_divergence": f"Placidus localiza a expressão na casa {placement.placidus_house}, ligada a {placidus_topic}; as duas localizações permanecem distintas.",
            "placidus_unavailable": "A leitura tópica usa Whole Sign porque Placidus não estava disponível.",
        },
        "en": {
            "convergence_strong": "Both configured systems converge in the same house.",
            "whole_topic_placidus_qualifier": f"Whole Sign supplies the topic; Placidus qualifies spatial expression{f' through house {placement.placidus_house}, associated with {placidus_topic}' if placidus_topic and placement.placidus_house != placement.whole_sign_house else ' through cusp proximity'}.",
            "complementary_emphases": f"Placidus adds house {placement.placidus_house}, associated with {placidus_topic}; the emphases remain complementary without adding an evidence vote.",
            "material_divergence": f"Placidus locates expression in house {placement.placidus_house}, associated with {placidus_topic}; both placements remain distinct.",
            "placidus_unavailable": "The topical reading uses Whole Sign because Placidus was unavailable.",
        },
    }[lang].get(placement.integration_state, placement.integration_rationale)
    if lang == "pt":
        statement = f"{BODY_LABELS[lang].get(body, chart.positions[body].label)} organiza parte da linguagem simbólica em torno de {topic}. {integration}"
        examples = [f"decisões ligadas a {topic}"]
        prohibited = ["evento material específico", "causalidade"]
    else:
        statement = f"{chart.positions[body].label} organizes part of the symbolic language around {topic}. {integration}"
        examples = [f"choices involving {topic}"]
        prohibited = ["specific material event", "causality"]
    theme = HOUSE_THEME[placement.whole_sign_house]
    evidence = [f"house.whole_sign.{body}", f"house.robustness.{body}"]
    if placement.placidus_house is not None:
        evidence.append(f"house.placidus.{body}")
    return Claim(
        id=f"claim.house.{body}.{index}", theme=theme, type="topical_tendency", statement=statement,
        evidence=evidence, evidence_families=[f"house_topic_{placement.whole_sign_house}"],
        counterweights=[], allowed_specificity="domain_possibility", allowed_examples=examples,
        prohibited_inferences=prohibited, astrological_support="light", authorized_motifs=[f"house_{placement.whole_sign_house}_topic"],
    )


def _claim_from_angle(chart: Chart, contact, index: int, language: str) -> Claim:
    lang = _language(language)
    angle_names = {
        "pt": {"asc": "presença e modo de iniciar", "dsc": "encontros e reciprocidade", "mc": "visibilidade e contribuição", "ic": "raízes e espaço privado"},
        "en": {"asc": "presence and ways of beginning", "dsc": "encounters and reciprocity", "mc": "visibility and contribution", "ic": "roots and private space"},
    }
    if lang == "pt":
        statement = f"{BODY_LABELS[lang].get(contact.body, chart.positions[contact.body].label)} está próximo de {contact.angle.upper()}, ficando estruturalmente mais visível em {angle_names[lang][contact.angle]}. Proeminência não equivale a facilidade."
    else:
        statement = f"{chart.positions[contact.body].label} is close to {contact.angle.upper()}, making it structurally more visible in {angle_names[lang][contact.angle]}. Prominence does not mean ease."
    return Claim(
        id=f"claim.angle.{contact.body}.{contact.angle}.{index}", theme="visibility_privacy" if contact.angle in ("mc", "ic") else "individuality_belonging",
        type="structural_prominence", statement=statement, evidence=[f"angle.{contact.body}_{contact.angle}"],
        evidence_families=[f"angle_{contact.body}_{contact.angle}"], counterweights=[], allowed_specificity="structural_tendency",
        allowed_examples=["uma função do mapa que tende a ficar mais saliente" if lang == "pt" else "a chart function that tends to become more salient"], prohibited_inferences=["destino inevitável", "evento público específico"],
        astrological_support="strong" if contact.distance <= 2 else "moderate", authorized_motifs=[f"{contact.angle}_prominence"],
    )


def _body_priority(chart: Chart, body: str) -> Tuple[int, int, str]:
    core_contacts = sum(contact.body == body and contact.angle in CORE_ANGLES for contact in chart.angle_contacts)
    exact = sum(body in (aspect.left, aspect.right) and aspect.orb <= 1.5 for aspect in chart.aspects)
    luminary = int(body in ("sun", "moon"))
    from .engine import sign_for
    asc_ruler = int(bool(chart.angles) and SIGN_RULERS.get(sign_for(chart.angles["asc"])[0]) == body)
    return (-(core_contacts * 4 + asc_ruler * 3 + luminary * 2 + exact), -exact, body)


def build_claims(chart: Chart, max_house_claims: int = 10, include_secondary_semantics: bool = False, language: str = "pt-BR") -> List[Claim]:
    claims: List[Claim] = []
    secondary = {"true_node", "chiron", "lilith_mean"}
    unstable_aspects = set(chart.stability.get("unstable_aspect_ids", []))
    for index, aspect in enumerate(chart.aspects, 1):
        if aspect.id in unstable_aspects or (not include_secondary_semantics and ({aspect.left, aspect.right} & secondary)):
            continue
        claims.append(_claim_from_aspect(aspect, index, language))
    unstable_contacts = set(chart.stability.get("unstable_angle_contact_ids", []))
    allow_angles = chart.stability.get("allow_angle_claims", True)
    for index, contact in enumerate(chart.angle_contacts, 1):
        contact_id = f"angle.{contact.body}_{contact.angle}"
        if allow_angles and contact_id not in unstable_contacts and contact.angle in CORE_ANGLES and (include_secondary_semantics or contact.body not in secondary):
            claims.append(_claim_from_angle(chart, contact, index, language))
    unstable_houses = set(chart.stability.get("unstable_house_bodies", []))
    allow_houses = chart.stability.get("allow_house_claims", True)
    eligible = [body for body in chart.house_placements if allow_houses and body not in unstable_houses and (include_secondary_semantics or body not in secondary)]
    for index, body in enumerate(sorted(eligible, key=lambda item: _body_priority(chart, item))[:max_house_claims], 1):
        claims.append(_claim_from_house(chart, body, index, language))
    return apply_counterweights(chart, claims, include_secondary_semantics)


def apply_counterweights(chart: Chart, claims: Sequence[Claim], include_secondary_semantics: bool = False) -> List[Claim]:
    aspect_by_id = {aspect.id: aspect for aspect in chart.aspects}
    output: List[Claim] = []
    secondary = {"true_node", "chiron", "lilith_mean"}
    eligible_aspects = [aspect for aspect in chart.aspects if include_secondary_semantics or not ({aspect.left, aspect.right} & secondary)]
    for claim in claims:
        bodies = set()
        for evidence_id in claim.evidence:
            aspect = aspect_by_id.get(evidence_id)
            if aspect:
                bodies.update((aspect.left, aspect.right))
        qualifications = [
            aspect.id for aspect in eligible_aspects
            if aspect.id not in claim.evidence and aspect.orb <= 4.0 and aspect.kind in ("trine", "sextile") and bodies.intersection((aspect.left, aspect.right))
        ]
        alternatives = [
            aspect.id for aspect in eligible_aspects
            if aspect.id not in claim.evidence and aspect.orb <= 4.0 and aspect.kind in ("square", "opposition", "quincunx") and bodies.intersection((aspect.left, aspect.right))
        ]
        claim.counterweights = qualifications[:1] + alternatives[:1]
        claim.counterweight_types = {item: ("resource_or_qualification" if item in qualifications else "competing_pressure") for item in claim.counterweights}
        output.append(claim)
    return output


def verify_claims(claims: Iterable[Claim], chart: Optional[Chart] = None) -> List[Claim]:
    """Verify traceability and the authorised semantic ceiling, not only facts."""
    evidence_ids = set()
    if chart:
        evidence_ids.update(factor.id for factor in chart.factors)
        evidence_ids.update(aspect.id for aspect in chart.aspects)
    aspect_by_id = {aspect.id: aspect for aspect in chart.aspects} if chart else {}
    factor_by_id = {factor.id: factor for factor in chart.factors} if chart else {}
    verified: List[Claim] = []
    seen_claim_ids = set()
    for claim in claims:
        errors: List[str] = []
        if chart is None:
            errors.append("missing_chart_context")
        if claim.id in seen_claim_ids:
            errors.append("duplicated_claim_id")
        seen_claim_ids.add(claim.id)
        if not claim.evidence or not claim.evidence_families:
            errors.append("missing_traceability")
        if chart and any(item not in evidence_ids for item in claim.evidence):
            errors.append("unknown_evidence")
        if chart and any(item not in evidence_ids for item in claim.counterweights):
            errors.append("unknown_counterweight")
        if not claim.authorized_motifs:
            errors.append("missing_authorized_motif")
        if claim.astrological_support not in {"light", "moderate", "strong"}:
            errors.append("invalid_astrological_support")
        if chart:
            expected_motifs = set()
            expected_families = set()
            expected_themes = set()
            expected_types = set()
            expected_support = set()
            expected_statements = set()
            expected_specificity = set()
            expected_example_variants = set()
            expected_prohibited_variants = set()
            semantic_source_count = 0
            for evidence_id in claim.evidence:
                aspect = aspect_by_id.get(evidence_id)
                if aspect:
                    semantic_source_count += 1
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_aspect(aspect, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                    continue
                factor = factor_by_id.get(evidence_id)
                if not factor:
                    continue
                if factor.kind == "whole_sign_house":
                    semantic_source_count += 1
                    body = factor.bodies[0]
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_house(chart, body, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "angle_contact":
                    contact = next((item for item in chart.angle_contacts if f"angle.{item.body}_{item.angle}" == evidence_id), None)
                    if contact:
                        semantic_source_count += 1
                        for language in ("pt-BR", "en-US"):
                            canonical = _claim_from_angle(chart, contact, 0, language)
                            expected_motifs.update(canonical.authorized_motifs)
                            expected_families.update(canonical.evidence_families)
                            expected_themes.add(canonical.theme)
                            expected_types.add(canonical.type)
                            expected_support.add(canonical.astrological_support)
                            expected_statements.add(canonical.statement)
                            expected_specificity.add(canonical.allowed_specificity)
                            expected_example_variants.add(tuple(canonical.allowed_examples))
                            expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
            if semantic_source_count != 1:
                errors.append("mixed_or_missing_semantic_source")
            if set(claim.authorized_motifs) != expected_motifs:
                errors.append("unauthorized_motif_for_evidence")
            if set(claim.evidence_families) != expected_families:
                errors.append("noncanonical_evidence_family")
            if claim.theme not in expected_themes:
                errors.append("theme_not_authorized_by_evidence")
            if claim.type not in expected_types:
                errors.append("claim_type_not_authorized_by_evidence")
            if claim.astrological_support not in expected_support:
                errors.append("support_not_authorized_by_evidence")
            if claim.statement not in expected_statements:
                errors.append("statement_not_registry_rendered")
            if claim.allowed_specificity not in expected_specificity:
                errors.append("specificity_not_authorized_by_evidence")
            if tuple(claim.allowed_examples) not in expected_example_variants or any(not _safe_text(item) for item in claim.allowed_examples):
                errors.append("examples_not_registry_rendered")
            if tuple(claim.prohibited_inferences) not in expected_prohibited_variants:
                errors.append("prohibited_inferences_not_registry_rendered")
            if set(claim.counterweight_types) != set(claim.counterweights):
                errors.append("counterweight_type_mismatch")
            source_bodies = set()
            for evidence_id in claim.evidence:
                source_aspect = aspect_by_id.get(evidence_id)
                if source_aspect:
                    source_bodies.update((source_aspect.left, source_aspect.right))
            for counterweight in claim.counterweights:
                aspect = aspect_by_id.get(counterweight)
                declared_type = claim.counterweight_types.get(counterweight)
                expected_type = "resource_or_qualification" if aspect and aspect.kind in ("trine", "sextile") else "competing_pressure" if aspect and aspect.kind in ("square", "opposition", "quincunx") else None
                if counterweight in claim.evidence or not aspect or aspect.orb > 4.0 or not source_bodies.intersection((aspect.left, aspect.right)) or declared_type != expected_type:
                    errors.append("invalid_counterweight_contract")
        if not _safe_text(claim.statement):
            errors.append("prohibited_semantic_inference")
        statement_folded = claim.statement.casefold()
        if any(item.casefold() in statement_folded for item in claim.prohibited_inferences if len(item) >= 5):
            errors.append("claim_specific_prohibited_inference")
        if claim.allowed_specificity not in {"structural_tendency", "behavioral_possibility", "domain_possibility"}:
            errors.append("invalid_specificity_ceiling")
        if len(set(claim.evidence_families)) != len(claim.evidence_families):
            errors.append("duplicated_evidence_family")
        claim.verification_errors = errors
        claim.status = "blocked" if errors else "allowed"
        verified.append(claim)
    return verified


def theme_label(theme: str, language: str = "pt-BR") -> str:
    return THEME_LABELS_PT.get(theme, theme.replace("_", " ")) if _language(language) == "pt" else THEME_LABELS_EN.get(theme, theme.replace("_", " "))
