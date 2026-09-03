"""Versioned semantic registry and evidence-aware claim verification.

The renderer never improvises directly from positions. Facts are converted into
authorised motifs here, then verified against the chart evidence ledger.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .config import BODY_LABELS, CORE_ANGLES, ELEMENT_BY_SIGN, MODALITY_BY_SIGN, POLARITY_BY_SIGN, SIGN_RULERS, THEME_LABELS_PT
from .models import Chart, Claim

SEMANTIC_REGISTRY_VERSION = "2.6.0"

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
        "sun": "direção pessoal", "moon": "necessidades emocionais", "mercury": "pensamento e comunicação",
        "venus": "vínculo e valores", "mars": "ação e limites", "jupiter": "crescimento e sentido",
        "saturn": "estrutura e responsabilidade", "uranus": "autonomia e mudança", "neptune": "imaginação e sensibilidade",
        "pluto": "intensidade e transformação", "true_node": "direção de desenvolvimento", "chiron": "sensibilidade e reparação",
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

# Small compositional atoms for the generic fallback.  This is intentionally
# not a second catalogue of pair rules: a routed theme remains only an
# organisational label, while the synthesis receives the functions actually
# interacting in this chart.
PLANET_FUNCTION_PRIMITIVES = {
    "pt": {
        "sun": ("direção", "expressão", "vitalidade"), "moon": ("necessidade", "regulação", "memória emocional"),
        "mercury": ("cognição", "linguagem", "categorização", "aprendizado"), "venus": ("vínculo", "valor", "prazer"),
        "mars": ("ação", "impulso", "limite"), "jupiter": ("ampliação", "sentido", "exploração"),
        "saturn": ("estrutura", "critério", "responsabilidade"), "uranus": ("autonomia", "novidade", "descontinuidade", "reorganização rápida"),
        "neptune": ("imaginação", "permeabilidade", "idealização"), "pluto": ("intensidade", "poder", "transformação"),
        "true_node": ("direção", "aprendizado"), "chiron": ("sensibilidade", "reparação"), "lilith_mean": ("limite", "recusa"),
    },
    "en": {
        "sun": ("direction", "expression", "vitality"), "moon": ("need", "regulation", "emotional memory"),
        "mercury": ("cognition", "language", "categorisation", "learning"), "venus": ("connection", "value", "pleasure"),
        "mars": ("action", "impulse", "boundary"), "jupiter": ("expansion", "meaning", "exploration"),
        "saturn": ("structure", "criterion", "responsibility"), "uranus": ("autonomy", "novelty", "discontinuity", "rapid reorganisation"),
        "neptune": ("imagination", "permeability", "idealisation"), "pluto": ("intensity", "power", "transformation"),
        "true_node": ("direction", "learning"), "chiron": ("sensitivity", "repair"), "lilith_mean": ("boundary", "refusal"),
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


def planet_function_primitives(body: str, language: str = "pt-BR") -> Tuple[str, ...]:
    """Compact function atoms used by constrained semantic composition."""
    lang = _language(language)
    return tuple(PLANET_FUNCTION_PRIMITIVES[lang].get(body, (PLANET_SHORT_FUNCTIONS[lang].get(body, body),)))


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
        left, right = ordered
        left_atoms = ", ".join(planet_function_primitives(left, language)[:2])
        right_atoms = ", ".join(planet_function_primitives(right, language)[:2])
        if lang == "pt":
            core = f"coordenação entre {left_atoms} de {BODY_LABELS[lang].get(left, left)} e {right_atoms} de {BODY_LABELS[lang].get(right, right)}"
        else:
            core = f"coordination between {left_atoms} of {left.title()} and {right_atoms} of {right.title()}"
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
    if placement.placidus_house is None:
        raise ValueError("Canonical natal house claim requires an available Placidus placement.")
    topic = HOUSE_TOPICS[lang][placement.placidus_house]
    if lang == "pt":
        statement = f"{BODY_LABELS[lang].get(body, chart.positions[body].label)} encontra contexto psicológico em {topic} pela casa Placidus {placement.placidus_house}."
        examples = [f"decisões ligadas a {topic}"]
        prohibited = ["evento material específico", "causalidade"]
    else:
        statement = f"{chart.positions[body].label} finds psychological context in {topic} through Placidus house {placement.placidus_house}."
        examples = [f"choices involving {topic}"]
        prohibited = ["specific material event", "causality"]
    theme = HOUSE_THEME[placement.placidus_house]
    evidence = [f"house.placidus.{body}"]
    return Claim(
        id=f"claim.house.{body}.{index}", theme=theme, type="topical_tendency", statement=statement,
        evidence=evidence, evidence_families=[f"placidus_house_topic_{placement.placidus_house}"],
        counterweights=[], allowed_specificity="domain_possibility", allowed_examples=examples,
        prohibited_inferences=prohibited, astrological_support="light", authorized_motifs=[f"placidus_house_{placement.placidus_house}_topic"],
    )


def _claim_from_house_ruler(chart: Chart, factor, language: str) -> Claim:
    """Authorize only a reliable Placidus cusp-to-ruler routing relation."""
    lang = _language(language)
    house = int(factor.data["house"])
    sign = str(factor.data["cusp_sign"])
    ruler = str(factor.data["ruler"])
    label = BODY_LABELS[lang].get(ruler, ruler.title())
    topic = HOUSE_TOPICS[lang].get(house, "invalid Placidus house")
    if lang == "pt":
        statement = f"A casa Placidus {house}, ligada a {topic}, tem cúspide em {sign} e é regida por {label}; isso apenas encaminha esse campo ao contexto natal já autorizado de {label}."
        examples = [f"observar a rota factual da casa Placidus {house} até {label}"]
    else:
        statement = f"Placidus house {house}, linked to {topic}, has its cusp in {sign} and is ruled by {label}; this only routes that area to {label}'s separately authorised natal context."
        examples = [f"observe the factual route from Placidus house {house} to {label}"]
    return Claim(
        id=f"claim.house_ruler.placidus.{house}", theme=HOUSE_THEME.get(house, "invalid_house_ruler_routing"), type="placidus_house_ruler",
        statement=statement, evidence=[factor.id], evidence_families=[f"placidus_house_ruler_context.{ruler}"],
        counterweights=[], allowed_specificity="structural_tendency", allowed_examples=examples,
        prohibited_inferences=["interpretação do signo do regente", "interpretação da casa do regente", "resultado de vida", "causalidade"],
        astrological_support="light", authorized_motifs=["placidus_house_ruler_routing"],
        direct_paragraph_renderable=True,
    )


def _sign_mode(position, language: str) -> str:
    lang = _language(language)
    descriptors = {
        "pt": {
            "fire": "iniciativa e vitalidade", "earth": "concretização e continuidade", "air": "troca e elaboração", "water": "sensibilidade e ligação emocional",
            "cardinal": "inicia e movimenta", "fixed": "sustenta e aprofunda", "mutable": "adapta e ajusta",
            "active": "de forma mais exteriorizada", "receptive": "de forma mais receptiva",
        },
        "en": {
            "fire": "initiative and vitality", "earth": "practical continuity", "air": "exchange and reflection", "water": "sensitivity and emotional connection",
            "cardinal": "initiates and moves", "fixed": "sustains and deepens", "mutable": "adapts and adjusts",
            "active": "in a more outward way", "receptive": "in a more receptive way",
        },
    }[lang]
    return f"{descriptors[ELEMENT_BY_SIGN[position.sign]]}; {descriptors[MODALITY_BY_SIGN[position.sign]]}; {descriptors[POLARITY_BY_SIGN[position.sign]]}"


def _claim_from_position(chart: Chart, body: str, index: int, language: str) -> Claim:
    lang = _language(language)
    position = chart.positions[body]
    function = PLANET_FUNCTIONS[lang].get(body, body)
    sign_expression = _sign_mode(position, language)
    if lang == "pt":
        statement = f"{BODY_LABELS[lang].get(body, position.label)} em {position.sign} colore {function} com {sign_expression}."
        examples = [f"observar como {function} ganha esse ritmo"]
    else:
        statement = f"{position.label} in {position.sign} colours {function} with {sign_expression}."
        examples = [f"notice how {function} takes on this rhythm"]
    return Claim(
        id=f"claim.position.{body}.{index}", theme=PLANET_DEFAULT_THEME[body], type="symbolic_tendency", statement=statement,
        evidence=[f"position.{body}"], evidence_families=[f"position_{body}"], counterweights=[],
        allowed_specificity="behavioral_possibility", allowed_examples=examples,
        prohibited_inferences=["biografia específica", "diagnóstico", "evento previsto"], astrological_support="light",
        authorized_motifs=[f"{body}_function_in_sign"],
    )


def _claim_from_node_axis(chart: Chart, index: int, language: str) -> Claim:
    lang = _language(language)
    factor = next(item for item in chart.factors if item.id == "node_axis.natal")
    north, south = factor.data["north"], factor.data["south"]
    houses = ""
    if factor.data.get("placidus_house_reliable"):
        houses = (f"; casas Placidus {north['placidus_house']} e {south['placidus_house']}" if lang == "pt"
                  else f"; Placidus houses {north['placidus_house']} and {south['placidus_house']}")
    if lang == "pt":
        statement = f"O eixo nodal liga Nodo Norte em {north['sign']} e Nodo Sul em {south['sign']}{houses}: direção de desenvolvimento e padrões familiares já disponíveis, sem transformar nenhum polo em destino ou descarte."
        examples = ["considerar a tensão entre o que já é disponível e um engajamento menos automático"]
    else:
        statement = f"The nodal axis links the North Node in {north['sign']} and South Node in {south['sign']}{houses}: developmental direction and familiar available patterns, without turning either pole into destiny or something to discard."
        examples = ["consider the tension between what is already available and less automatic engagement"]
    contacts = [aspect for aspect in chart.aspects if aspect.id in set(factor.data.get("contact_ids", []))]
    contact_evidence = [aspect.id for aspect in contacts]
    contact_motifs = [
        motif
        for aspect in contacts
        for motif in (f"nodal_axis_{aspect.kind}_contact", *_claim_from_aspect(aspect, 0, language).authorized_motifs)
    ]
    return Claim(
        id=f"claim.node_axis.{index}", theme="purpose", type="symbolic_tendency", statement=statement,
        evidence=["node_axis.natal", *contact_evidence], evidence_families=["natal_node_axis"], counterweights=[],
        allowed_specificity="behavioral_possibility", allowed_examples=examples,
        prohibited_inferences=["destino inevitável", "missão predestinada", "abandono do Nodo Sul"], astrological_support="light",
        authorized_motifs=["natal_node_axis_developmental_direction", *contact_motifs],
    )


def _claim_from_configuration(chart: Chart, factor, index: int, language: str) -> Claim:
    lang = _language(language)
    kind, members = str(factor.data["kind"]), ", ".join(factor.data["bodies"])
    basis = factor.data.get("basis")
    qualifier = f" em {basis}" if basis and lang == "pt" else (f" in {basis}" if basis else "")
    if lang == "pt":
        statement = f"A estrutura {kind}{qualifier} reúne {members} como um padrão integrado, a ser explicado uma vez antes de observar o papel de cada corpo."
    else:
        statement = f"The {kind} structure{qualifier} joins {members} as one integrated pattern, to be explained once before considering each body's role."
    group = str(factor.data.get("group_id") or factor.id)
    return Claim(
        id=f"claim.configuration.{index}", theme="order", type="structural_prominence", statement=statement,
        evidence=[factor.id], evidence_families=[group], counterweights=[], allowed_specificity="structural_tendency",
        allowed_examples=["a structural pattern to read as one family" if lang == "en" else "um padrão estrutural a ler como uma família"],
        prohibited_inferences=["evento específico", "causalidade"], astrological_support="moderate",
        authorized_motifs=[f"{kind}_integrated_structure"],
    )


def _claim_from_ascendant(chart: Chart, factor, index: int, language: str) -> Claim:
    lang = _language(language)
    sign = factor.data["sign"]
    statement = (f"O Ascendente em {sign} descreve uma porta de entrada simbólica para presença e início de experiências."
                 if lang == "pt" else f"The Ascendant in {sign} describes a symbolic entry point for presence and beginning experiences.")
    return Claim(f"claim.ascendant.{index}", "individuality_belonging", "structural_prominence", statement, [factor.id], ["ascendant"], [], "structural_tendency", ["uma forma de iniciar e se apresentar" if lang == "pt" else "a way of beginning and presenting oneself"], ["biografia específica"], "moderate", authorized_motifs=["ascendant_presence"])


def _claim_from_chart_ruler(chart: Chart, factor, index: int, language: str) -> Claim:
    lang = _language(language)
    ruler = str(factor.data["ruler"])
    label = BODY_LABELS[lang].get(ruler, ruler.title())
    statement = (f"{label}, regente do Ascendente em {factor.data['ascendant_sign']}, organiza uma função recorrente na forma de iniciar e orientar-se."
                 if lang == "pt" else f"{label}, ruler of the Ascendant in {factor.data['ascendant_sign']}, organizes a recurring function in how you begin and orient yourself.")
    return Claim(f"claim.chart_ruler.{index}", PLANET_DEFAULT_THEME[ruler], "structural_prominence", statement, [factor.id], ["chart_ruler"], [], "structural_tendency", ["uma função a observar em escolhas de direção" if lang == "pt" else "a function to observe in directional choices"], ["destino inevitável"], "moderate", authorized_motifs=["chart_ruler_orientation"])


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
    # Every primary planet receives a small compositional position/sign claim.
    # This is coverage, not a prewritten planet×sign×house catalogue: houses,
    # aspects, conditions and structures remain separately composable evidence.
    primary_positions = [body for body in PLANET_DEFAULT_THEME if body in chart.positions and body not in secondary]
    for index, body in enumerate(primary_positions, 1):
        claims.append(_claim_from_position(chart, body, index, language))
    if any(factor.id == "node_axis.natal" for factor in chart.factors):
        claims.append(_claim_from_node_axis(chart, 1, language))
    ascendant = next((factor for factor in chart.factors if factor.kind == "ascendant"), None)
    if ascendant:
        claims.append(_claim_from_ascendant(chart, ascendant, 1, language))
    chart_ruler = next((factor for factor in chart.factors if factor.kind == "chart_ruler"), None)
    if chart_ruler:
        claims.append(_claim_from_chart_ruler(chart, chart_ruler, 1, language))
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
    unstable_houses = set(chart.stability.get("unstable_placidus_house_bodies", chart.stability.get("unstable_house_bodies", [])))
    allow_houses = chart.stability.get("allow_house_claims", True)
    eligible = [body for body in chart.house_placements if allow_houses and body not in unstable_houses and (include_secondary_semantics or body not in secondary)]
    for index, body in enumerate(sorted(eligible, key=lambda item: _body_priority(chart, item))[:max_house_claims], 1):
        if chart.house_placements[body].placidus_house is not None:
            claims.append(_claim_from_house(chart, body, index, language))
    for factor in sorted((item for item in chart.factors if item.kind == "placidus_house_ruler"), key=lambda item: int(item.data["house"])):
        claims.append(_claim_from_house_ruler(chart, factor, language))
    for index, factor in enumerate((item for item in chart.factors if item.kind == "configuration"), 1):
        claims.append(_claim_from_configuration(chart, factor, index, language))
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
        # Geometry describes the kind of relation, not its final value.
        claim.counterweight_types = {item: ("low_resistance_dynamic" if item in qualifications else "friction_or_polarity_dynamic") for item in claim.counterweights}
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
            expected_direct_renderable = False
            semantic_source_count = 0
            node_axis_factor = factor_by_id.get("node_axis.natal") if "node_axis.natal" in claim.evidence else None
            node_contact_ids = set(node_axis_factor.data.get("contact_ids", [])) if node_axis_factor else set()
            if node_axis_factor and set(claim.evidence[1:]) != node_contact_ids:
                errors.append("invalid_nodal_axis_contact_ancestry")
            for evidence_id in claim.evidence:
                # Nodal contacts qualify the one axis claim.  They are not
                # independent aspect claims or a second semantic family.
                if node_axis_factor and evidence_id in node_contact_ids:
                    continue
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
                if factor.kind == "placidus_house":
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
                elif factor.kind == "placidus_house_ruler":
                    from .engine import sign_for
                    house = int(factor.data.get("house", 0))
                    cusp_valid = bool(chart.house_cusps_placidus) and 1 <= house <= len(chart.house_cusps_placidus)
                    expected_sign = sign_for(chart.house_cusps_placidus[house - 1])[0] if cusp_valid else None
                    expected_ruler = SIGN_RULERS.get(expected_sign) if expected_sign else None
                    if (
                        not factor.data.get("cusp_sign_reliable")
                        or not factor.data.get("available_for_house_ruler_claim")
                        or factor.data.get("house_system") != "placidus"
                        or factor.data.get("cusp_sign") != expected_sign
                        or factor.data.get("ruler") != expected_ruler
                        or factor.data.get("ruler_position_id") != f"position.{expected_ruler}"
                        or factor.data.get("rulership_system") != "traditional_configured"
                        or factor.bodies != [expected_ruler]
                        or factor.id != f"house_ruler.placidus.{house}"
                    ):
                        errors.append("invalid_placidus_house_ruler_provenance")
                    semantic_source_count += 1
                    expected_direct_renderable = True
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_house_ruler(chart, factor, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "position":
                    semantic_source_count += 1
                    body = factor.bodies[0]
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_position(chart, body, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "natal_node_axis":
                    semantic_source_count += 1
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_node_axis(chart, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "configuration":
                    from .structure import detect_configurations
                    expected_configurations = {str(item["id"]): item for item in detect_configurations(chart)}
                    expected_configuration = expected_configurations.get(factor.id)
                    if expected_configuration != factor.data:
                        errors.append("invalid_configuration_provenance")
                    semantic_source_count += 1
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_configuration(chart, factor, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "ascendant":
                    semantic_source_count += 1
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_ascendant(chart, factor, 0, language)
                        expected_motifs.update(canonical.authorized_motifs)
                        expected_families.update(canonical.evidence_families)
                        expected_themes.add(canonical.theme)
                        expected_types.add(canonical.type)
                        expected_support.add(canonical.astrological_support)
                        expected_statements.add(canonical.statement)
                        expected_specificity.add(canonical.allowed_specificity)
                        expected_example_variants.add(tuple(canonical.allowed_examples))
                        expected_prohibited_variants.add(tuple(canonical.prohibited_inferences))
                elif factor.kind == "chart_ruler":
                    semantic_source_count += 1
                    for language in ("pt-BR", "en-US"):
                        canonical = _claim_from_chart_ruler(chart, factor, 0, language)
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
            if claim.direct_paragraph_renderable != expected_direct_renderable:
                errors.append("direct_paragraph_capability_not_authorized")
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
                expected_type = "low_resistance_dynamic" if aspect and aspect.kind in ("trine", "sextile") else "friction_or_polarity_dynamic" if aspect and aspect.kind in ("square", "opposition", "quincunx") else None
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
