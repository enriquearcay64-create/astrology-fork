"""Bilingual human rendering from verified claims and structured synthesis."""
from __future__ import annotations

import json
import re
from typing import Dict, Iterable, List, Optional

from .localization import localized_examples, localization_audit
from .config import BODY_LABELS, PRIMARY_BODIES
from .models import Claim, LocalizationProfile
from .safe_view import SafeInterpretiveChart
from .semantics import HOUSE_TOPICS, PLANET_FUNCTIONS

TOKENS = {
    "pt": {
        **BODY_LABELS["pt"],
        "asc": "ASC", "dsc": "DSC", "mc": "MC", "ic": "IC", "conjunction": "conjunção", "sextile": "sextil", "square": "quadratura", "trine": "trígono", "quincunx": "quincúncio", "opposition": "oposição",
    },
    "en": {},
}
SIGNS = {
    "pt": ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes"],
    "en": ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"],
}
SUPPORT = {"pt": {"strong": "forte", "moderate": "moderado", "light": "leve"}, "en": {"strong": "strong", "moderate": "moderate", "light": "light"}}
RESOURCE_LEVELS = {"pt": {"strong": "fortes", "moderate": "moderados", "light": "leves", "none": "nenhum"}, "en": {"strong": "strong", "moderate": "moderate", "light": "light", "none": "none"}}
FRICTION_LEVELS = {"pt": {"strong": "fortes", "moderate": "moderadas", "light": "leves", "none": "nenhuma"}, "en": {"strong": "strong", "moderate": "moderate", "light": "light", "none": "none"}}
ELEMENTS = {"pt": {"fire": "fogo", "earth": "terra", "air": "ar", "water": "água"}, "en": {}}
MODALITIES = {"pt": {"cardinal": "cardinal", "fixed": "fixo", "mutable": "mutável"}, "en": {}}
CONFIGURATIONS = {
    "pt": {"grand_trine": "grande trígono", "t_square": "quadratura em T", "yod": "Yod", "grand_cross": "grande cruz", "mystic_rectangle": "retângulo místico", "kite": "pipa", "stellium_sign": "stellium por signo", "stellium_whole_sign_house": "stellium por casa de Signo Inteiro"},
    "en": {},
}
TIMING_FOCUS = {
    "pt": {"jupiter": "expansão, estudo e sentido", "saturn": "estrutura, responsabilidade e maturação", "uranus": "autonomia e atualização de padrões", "neptune": "imaginação, idealização e discernimento", "pluto": "poder, intensidade e transformação", "true_node": "reorientação e direção de desenvolvimento", "chiron": "sensibilidade, aprendizagem e reparação"},
    "en": {"jupiter": "growth, study and meaning", "saturn": "structure, responsibility and maturation", "uranus": "autonomy and pattern renewal", "neptune": "imagination, idealization and discernment", "pluto": "power, intensity and transformation", "true_node": "reorientation and developmental direction", "chiron": "sensitivity, learning and repair"},
}
HOUSE_EXAMPLES = {
    "pt": {
        1: "como você inicia, ocupa espaço e ajusta sua presença", 2: "como organiza dinheiro, tempo, habilidades e segurança", 3: "como aprende, pergunta, escreve e troca informação", 4: "como constrói privacidade, base emocional e pertencimento familiar", 5: "como brinca, cria, deseja e assume autoria", 6: "como transforma intenção em rotina, prática e cuidado sustentável", 7: "como negocia reciprocidade, compromisso e diferenças", 8: "como lida com confiança, intimidade, partilha e mudanças profundas", 9: "como amplia visão por estudo, viagem, filosofia ou espiritualidade", 10: "como assume responsabilidade, contribuição e visibilidade pública", 11: "como participa de redes, amizades, projetos e futuros coletivos", 12: "como processa silêncio, descanso, imaginação e conteúdos de fundo",
    },
    "en": {
        1: "how you begin, take up space and adjust your presence", 2: "how you organize money, time, skills and security", 3: "how you learn, ask, write and exchange information", 4: "how you build privacy, emotional foundations and family belonging", 5: "how you play, create, desire and claim authorship", 6: "how intention becomes routine, practice and sustainable care", 7: "how you negotiate reciprocity, commitment and difference", 8: "how you handle trust, intimacy, sharing and deep change", 9: "how you broaden perspective through study, travel, philosophy or spirituality", 10: "how you assume responsibility, contribution and public visibility", 11: "how you participate in networks, friendships, projects and collective futures", 12: "how you process silence, rest, imagination and background material",
    },
}
CONDITIONS = {
    "pt": {"domicile": "domicílio", "exaltation": "exaltação", "detriment": "detrimento", "fall": "queda", "retrograde": "retrógrado", "stationary": "estacionário", "cazimi": "cazimi", "combust": "combusto", "under_beams": "sob os raios"},
    "en": {},
}


def _lang(profile: Optional[LocalizationProfile]) -> str:
    return "pt" if not profile or profile.preferred_language.startswith("pt") else "en"


def _token(value: str, lang: str) -> str:
    return TOKENS[lang].get(value, value.replace("_", " ").title() if lang == "en" else value.replace("_", " "))


def _degree(value: float, lang: str) -> str:
    return f"{value % 30:05.2f}° {SIGNS[lang][int(value // 30) % 12]}"


def _translated_counts(values: Dict[str, int], labels: Dict[str, Dict[str, str]], lang: str) -> Dict[str, int]:
    return {labels[lang].get(key, key): value for key, value in values.items()}


def _transit_windows(events: List[Dict[str, object]], limit: int) -> List[Dict[str, object]]:
    # Timing v3 already groups exact/retrógrade passes into activation instances.
    # Never regroup those windows by semantic family: the same Saturn aspect may
    # return years later as a separate activation.
    if events and all("activation_instance" in event for event in events):
        return sorted(events, key=lambda item: (-int(item.get("window_priority", item.get("priority", 0))), str(item["window_start"])))[:limit]
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for event in events:
        grouped.setdefault(str(event["evidence_family"]), []).append(event)
    windows = []
    for passes in grouped.values():
        passes.sort(key=lambda item: str(item.get("exact_at") or item.get("closest_approach_at")))
        first = dict(passes[0])
        first["passes"] = passes
        first["window_priority"] = max(item.get("priority", 0) for item in passes)
        windows.append(first)
    return sorted(windows, key=lambda item: (-item["window_priority"], str(item.get("exact_at") or item.get("closest_approach_at"))))[:limit]


def _format_transit_window(event: Dict[str, object], lang: str) -> str:
    dates = [str(item.get("exact_at") or item.get("closest_approach_at"))[:10] for item in event["passes"]]
    passes = f"; {len(dates)} passagens ({', '.join(dates)})" if lang == "pt" and len(dates) > 1 else f"; {len(dates)} passes ({', '.join(dates)})" if len(dates) > 1 else f" ({dates[0]})"
    connector = " com " if lang == "pt" else " to "
    body = str(event["transit_body"])
    focus = TIMING_FOCUS[lang].get(body)
    suffix = f" — foco simbólico em {focus}" if focus and lang == "pt" else f" — symbolic focus on {focus}" if focus else ""
    precision = "" if event.get("perfected", True) else ("; aproximação mais próxima" if lang == "pt" else "; closest approach")
    return f"{_token(body, lang)} {_token(str(event['aspect']), lang)}{connector}{_token(str(event['target']), lang)}{passes}{precision}{suffix}"


def _narrative_thread(themes: List[Dict[str, object]], paradoxes: List[Dict[str, object]], lang: str, narrative_plan: Optional[Dict[str, object]] = None) -> str:
    if narrative_plan and narrative_plan.get("opening", {}).get("observation"):
        return str(narrative_plan["opening"]["observation"])
    labels = [str(item["label"]) for item in themes[:3]]
    if not labels:
        return "Não há suporte suficiente para definir um fio condutor." if lang == "pt" else "There is not enough support to define a narrative thread."
    joined = ", ".join(f"**{label}**" for label in labels)
    leading = themes[0]["expressions"]
    if lang == "pt":
        return f"A hipótese central combina {joined}. O recurso mais visível é {leading['constructive']}. Em situações de pressão, o mesmo eixo pode levar a {leading['defensive']}. A diferença importante está no modo como essas tendências se relacionam: elas descrevem uma negociação possível, não uma identidade fechada."
    return f"The central hypothesis combines {joined}. The clearest resource is the capacity to {leading['constructive']}. Under pressure, the same axis may lead you to {leading['defensive']}. What matters is how these tendencies interact: they describe a possible negotiation, not a fixed identity."


def _final_synthesis(themes: List[Dict[str, object]], paradoxes: List[Dict[str, object]], lang: str, narrative_plan: Optional[Dict[str, object]] = None) -> str:
    if not themes:
        return "A síntese permanece aberta por falta de suporte suficiente." if lang == "pt" else "The synthesis remains open because support is insufficient."
    first = themes[0]
    second = themes[1] if len(themes) > 1 else None
    planned_move = str((narrative_plan or {}).get("integration_move", ""))
    if lang == "pt":
        move = planned_move or first['expressions']['integrated']
        qualifier = second['expressions']['constructive'] if second else first['expressions']['constructive']
        return f"A integração mais promissora passa por {move}. Na prática, observe se isso preserva a capacidade de {qualifier} quando surge a pressão de {first['expressions']['defensive']}."
    move = planned_move or first['expressions']['integrated']
    qualifier = second['expressions']['constructive'] if second else first['expressions']['constructive']
    return f"The most promising integration move is to {move}. In practice, notice whether it preserves the capacity to {qualifier} when the pressure to {first['expressions']['defensive']} appears."


def _executive_orientation(themes: List[Dict[str, object]], lang: str) -> str:
    """A human bridge between the overview table and the current phase."""
    if len(themes) < 2:
        return ""
    first, second = themes[:2]
    count_label = f"{len(themes)} temas" if lang == "pt" else f"{len(themes)} themes"
    if lang == "pt":
        return (
            f"Leia a tabela como um mapa de decisões, não como {count_label}. **{first['label']}** mostra o mecanismo "
            f"que merece atenção primeiro; **{second['label']}** mostra a condição que o qualifica. "
            f"Como teste, compare quando você tende a {first['expressions']['defensive']} com uma resposta que procura "
            f"{second['expressions']['integrated']} em uma situação concreta desta semana."
        )
    return (
        f"Read the table as a map of decisions, not {count_label}. **{first['label']}** names the mechanism worth noticing "
        f"first; **{second['label']}** names the condition that qualifies it. As a test, compare when "
        f"you tend to {first['expressions']['defensive']} with a response that tries to {second['expressions']['integrated']}. "
        "Use one concrete situation from this week."
    )


def _configuration_basis(item: Dict[str, object], lang: str) -> str:
    if not item.get("basis"):
        return ""
    basis = str(item["basis"])
    if item.get("kind") == "stellium_sign" and lang == "pt" and basis in SIGNS["en"]:
        basis = SIGNS["pt"][SIGNS["en"].index(basis)]
    return f" ({basis})"


def _theme_block(theme: Dict[str, object], lang: str, rank: int, profile: Optional[LocalizationProfile] = None, include_support: bool = False, composition: Optional[Dict[str, object]] = None) -> List[str]:
    expression = theme["expressions"]
    support = f" · {SUPPORT[lang][theme['support_level']]}" if include_support else ""
    lines = [f"### {rank}. {theme['label']}{support}", ""]
    observation = str((composition or {}).get("observation", ""))
    possible = list((composition or {}).get("possible_expressions", []))
    moves = dict((composition or {}).get("narrative_moves", {}))
    if lang == "pt":
        if observation:
            # The composition makes this theme chart-specific.  The editorial
            # movement deliberately varies by rank, so the deep reading does
            # not become five copies of a light/shadow/integration template.
            if rank == 1:
                paragraph = f"{observation} A capacidade a desenvolver aqui é {expression['constructive']}; neste mapa, isso pede {moves.get('constructive', expression['integrated'])}. O cuidado está em não usar o padrão para {expression['defensive']}; a integração pede {moves.get('integration', expression['integrated'])}."
            elif rank == 2:
                paragraph = f"{observation} Ele tende a ficar mais útil quando você consegue {expression['constructive']}. Uma distorção possível é {expression['excessive']}. Como contrapeso, experimente {moves.get('constructive', expression['integrated'])}."
            elif rank == 3:
                paragraph = f"{observation} Em momentos de maior carga, pode haver a tentação de {expression['defensive']}. O recurso contido no mesmo padrão é {moves.get('constructive', expression['constructive'])}; vale observar como isso muda com o contexto."
            else:
                paragraph = f"{observation} Não é necessário transformar isso numa regra sobre você. A pergunta prática é como {expression['integrated']} sem perder de vista os limites e as escolhas reais."
            lines.append(paragraph)
            # Localization is an optional contextual accent, never the whole
            # example. A chart-derived example carries the mechanism; the
            # locale may make a single example more familiar.
            example = theme.get("examples", [None])[0] or theme.get("lived_examples", [None])[0]
            local_examples = localized_examples(profile, str(theme["id"])) if rank == 1 else []
            if example and local_examples:
                example = f"{example}; em uma decisão prática, pode ajudar {local_examples[0]}"
            elif not example and local_examples:
                example = local_examples[0]
            if example and ("função do mapa" in str(example).casefold() or "chart function" in str(example).casefold()):
                example = None
            if rank <= 3 and example:
                lines.extend(["", f"> **Na prática:** Isso poderia aparecer, por exemplo, em {example}."])
            return lines + [""]
        if rank == 1:
            paragraph = f"Em sua forma construtiva, este tema favorece {expression['constructive']}. Sob pressão, pode surgir a estratégia de {expression['defensive']}; quando ela endurece, o risco é {expression['excessive']}. A integração passa por {expression['integrated']}."
        elif rank == 2:
            paragraph = f"A força aqui está em {expression['constructive']}. O ponto cego não é uma falha de caráter: é a possibilidade de {expression['defensive']}, ou de {expression['underdeveloped']}. O movimento mais útil é {expression['integrated']}."
        elif rank == 3:
            paragraph = f"Este tema amadurece quando se consegue {expression['constructive']}. A defesa tende a aparecer como {expression['defensive']}; levada ao limite, pode {expression['excessive']}. Integrar significa {expression['integrated']}."
        elif rank == 4:
            paragraph = f"Aqui, o recurso é {expression['constructive']}. A proteção automática pode assumir a forma de {expression['defensive']}, enquanto o outro extremo é {expression['underdeveloped']}. O contraponto é {expression['integrated']}."
        else:
            paragraph = f"Na melhor expressão, o tema ajuda a {expression['constructive']}. Se houver pressão, a resposta pode ser {expression['defensive']}; em excesso, pode {expression['excessive']}. O trabalho de integração é {expression['integrated']}."
        lines.append(paragraph)
        example = theme.get("lived_examples", [None])[0]
        local_examples = localized_examples(profile, str(theme["id"])) if rank == 1 else []
        if example and local_examples:
            example = f"{example}; em uma decisão prática, pode ajudar {local_examples[0]}"
        elif not example and local_examples:
            example = local_examples[0]
        if example and ("função do mapa" in str(example).casefold() or "chart function" in str(example).casefold()):
            example = None
        if rank <= 3 and example:
            lines.extend(["", f"> **Na prática:** {example}."])
    else:
        if observation:
            if rank == 1:
                paragraph = f"{observation} The capacity to develop here is to {expression['constructive']}; in this chart, that asks you to {moves.get('constructive', expression['integrated'])}. The caution is not to use the pattern to {expression['defensive']}; integration asks you to {moves.get('integration', expression['integrated'])}."
            elif rank == 2:
                paragraph = f"{observation} It becomes more useful when you can {expression['constructive']}. One possible distortion is to {expression['excessive']}. As a counterweight, try to {moves.get('constructive', expression['integrated'])}."
            elif rank == 3:
                paragraph = f"{observation} Under greater load, there may be a temptation to {expression['defensive']}. The resource in the same pattern is to {moves.get('constructive', expression['constructive'])}; notice how it changes with context."
            else:
                paragraph = f"{observation} This does not need to become a rule about you. The practical question is how to {expression['integrated']} while keeping real limits and choices in view."
            lines.append(paragraph)
            example = theme.get("examples", [None])[0] or theme.get("lived_examples", [None])[0]
            if rank <= 3 and example:
                lines.extend(["", f"> **In practice:** This could show up, for example, in {example}."])
            return lines + [""]
        if rank == 1:
            paragraph = f"In its constructive form, this theme supports the capacity to {expression['constructive']}. Under pressure, the strategy may become to {expression['defensive']}; when it hardens, the risk is to {expression['excessive']}. Integration means learning to {expression['integrated']}."
        elif rank == 2:
            paragraph = f"The strength here is the capacity to {expression['constructive']}. The blind spot is not a character flaw: it is the possibility of trying to {expression['defensive']}, or of starting to {expression['underdeveloped']}. The useful movement is to {expression['integrated']}."
        elif rank == 3:
            paragraph = f"This theme matures through the capacity to {expression['constructive']}. Its defensive strategy is to {expression['defensive']}; taken to an extreme, it may lead you to {expression['excessive']}. Integration means learning to {expression['integrated']}."
        elif rank == 4:
            paragraph = f"Here, the resource is the capacity to {expression['constructive']}. Automatic protection may take the form of trying to {expression['defensive']}, while the other extreme is to {expression['underdeveloped']}. The counter-movement is to {expression['integrated']}."
        else:
            paragraph = f"At its best, this theme helps you {expression['constructive']}. Under pressure, the response may be to {expression['defensive']}; in excess, it may become a way to {expression['excessive']}. The integration work is to {expression['integrated']}."
        lines.append(paragraph)
        example = theme.get("lived_examples", [None])[0]
        if rank <= 3 and example:
            lines.extend(["", f"> **In practice:** {example}."])
    return lines + [""]


ANGLE_FUNCTIONS = {
    "pt": {"asc": "presença e modo de começar", "dsc": "reciprocidade e parceria", "mc": "contribuição e visibilidade", "ic": "raízes e vida privada"},
    "en": {"asc": "presence and ways of beginning", "dsc": "reciprocity and partnership", "mc": "contribution and visibility", "ic": "roots and private life"},
}


def _focus_for_body(body: str, lang: str) -> str:
    return PLANET_FUNCTIONS[lang].get(body, ANGLE_FUNCTIONS[lang].get(body, _token(body, lang)))


def _window_dates(event: Dict[str, object]) -> str:
    dates = [str(item.get("exact_at") or item.get("closest_approach_at"))[:10] for item in event["passes"]]
    return dates[0] if len(dates) == 1 else f"{dates[0]}–{dates[-1]}"


def _human_window(event: Dict[str, object], lang: str) -> str:
    body_focus = TIMING_FOCUS[lang].get(str(event["transit_body"]), _focus_for_body(str(event["transit_body"]), lang))
    target_focus = _focus_for_body(str(event["target"]), lang)
    aspect = str(event["aspect"])
    if lang == "pt":
        dynamics = {"conjunction": "concentração em", "trine": "fluidez com", "sextile": "oportunidade em", "square": "tensão produtiva com", "opposition": "negociação com", "quincunx": "ajuste em relação a"}
        return f"**{_window_dates(event)}:** {body_focus} — {dynamics[aspect]} {target_focus}."
    dynamics = {"conjunction": "concentration around", "trine": "flow with", "sextile": "opportunity around", "square": "productive tension with", "opposition": "negotiation with", "quincunx": "adjustment in relation to"}
    return f"**{_window_dates(event)}:** {body_focus} — {dynamics[aspect]} {target_focus}."


def _current_phase_human(timing: Optional[Dict[str, object]], lang: str, window_limit: int = 3) -> List[str]:
    if not timing:
        return []
    phase = timing["current_phase"]
    focus = phase["traditional_focus"]
    lord = focus["time_lord"]
    house = focus["house"]
    if lang == "pt":
        if lord:
            lines = [f"A ênfase anual recai sobre **{HOUSE_TOPICS[lang][house]}**, com **{_focus_for_body(lord, lang)}** funcionando como fio condutor. Isso define um campo de observação, não um resultado."]
        elif timing["traditional_stream"].get("status") == "conditional":
            lines = ["A ênfase anual por profecção foi omitida: o teste de sensibilidade altera a topologia de Signo Inteiro."]
        else:
            lines = ["A ênfase anual tradicional não está disponível porque a hora natal é desconhecida."]
    else:
        if lord:
            lines = [f"The annual emphasis falls on **{HOUSE_TOPICS[lang][house]}**, with **{_focus_for_body(lord, lang)}** acting as the thread. This defines a field of observation, not an outcome."]
        elif timing["traditional_stream"].get("status") == "conditional":
            lines = ["The annual profection emphasis was omitted: the sensitivity test changes the Whole Sign topology."]
        else:
            lines = ["The traditional annual emphasis is unavailable because birth time is unknown."]
    windows = _transit_windows(timing["modern_stream"]["major_transits"], window_limit)
    lines.extend(f"- {_human_window(event, lang)}" for event in windows)
    if windows:
        lines.append("*Use estas janelas para observar escolhas e efeitos, não para esperar acontecimentos.*" if lang == "pt" else "*Use these windows to observe choices and effects, not to expect events.*")
    return lines


def _current_phase_lines(timing: Optional[Dict[str, object]], lang: str) -> List[str]:
    if not timing:
        return []
    phase = timing["current_phase"]
    focus = phase["traditional_focus"]
    lord = focus["time_lord"]
    if lang == "pt":
        lines = [f"- **Profecção:** casa {focus['house']}; senhor do ano: {_token(lord, lang)}." if lord else ("- Profecção anual omitida: o teste de sensibilidade altera a topologia de Signo Inteiro." if timing["traditional_stream"].get("status") == "conditional" else "- Profecção indisponível porque a hora natal é desconhecida.")]
        prefix = "- **Janelas principais:** "
    else:
        lines = [f"- **Profection:** house {focus['house']}; time lord: {_token(lord, lang)}." if lord else ("- Annual profection omitted: the sensitivity test changes the Whole Sign topology." if timing["traditional_stream"].get("status") == "conditional" else "- Profection unavailable because birth time is unknown.")]
        prefix = "- **Main windows:** "
    windows = _transit_windows(timing["modern_stream"]["major_transits"], 4)
    if windows:
        lines.append(prefix + "; ".join(_format_transit_window(event, lang) for event in windows) + ".")
    convergent = [item for item in phase["convergence"] if item["technique_overlap"] != "single"]
    if convergent:
        label = "- **Convergência entre técnicas:** " if lang == "pt" else "- **Cross-technique convergence:** "
        lines.append(label + "; ".join(f"{_token(item['body'], lang)} ({item['intensity']})" for item in convergent[:3]) + ".")
    return lines


def _executive_theme_table(themes: List[Dict[str, object]], lang: str, limit: int = 5) -> List[str]:
    if lang == "pt":
        lines = ["| Tema | Recurso | Atenção |", "|---|---|---|"]
    else:
        lines = ["| Theme | Resource | Watch for |", "|---|---|---|"]
    for theme in themes[:limit]:
        expression = theme["expressions"]
        lines.append(f"| **{theme['label']}** | {expression['constructive']} | {expression['defensive']} |")
    return lines


def _paradox_callout(themes: List[Dict[str, object]], paradoxes: List[Dict[str, object]], lang: str) -> List[str]:
    if not paradoxes:
        return []
    paradox = paradoxes[0]
    theme = next((item for item in themes if item["id"] == paradox["theme"]), None)
    if not theme:
        return []
    expression = theme["expressions"]
    left, right = paradox["poles"]
    if lang == "pt":
        return [f"> ↔ **Paradoxo central — {left} e {right}:** os dois lados podem coexistir ou alternar conforme o contexto. Sob pressão, o padrão pode levar a {expression['defensive']}. A saída não é escolher um lado definitivo, mas {expression['integrated']}."]
    return [f"> ↔ **Central paradox — {left} and {right}:** both sides may coexist or alternate with context. Under pressure, the pattern may lead you to {expression['defensive']}. The way through is not choosing one permanent side, but learning to {expression['integrated']}."]


def _life_area_lines(chart: SafeInterpretiveChart, lang: str, hierarchy: Optional[Dict[str, Dict[str, object]]] = None, visible_limit: int = 4) -> List[str]:
    if not chart.house_placements:
        if chart.conditional_house_scenarios:
            return [
                "House themes are conditional because a sensitivity test crosses the Ascendant sign boundary; they are not used as central evidence." if lang == "en" else
                "Os temas de casa são condicionais porque um teste de sensibilidade atravessa a fronteira de signo do Ascendente; eles não são usados como evidência central."
            ]
        return ["Houses are unavailable because birth time is unknown." if lang == "en" else "As casas estão indisponíveis porque a hora natal é desconhecida."]

    by_house = {house: [] for house in range(1, 13)}
    for body in PRIMARY_BODIES:
        if body in chart.house_placements:
            by_house[chart.house_placements[body].whole_sign_house].append(body)
    hierarchy = hierarchy or {}
    scores: Dict[int, int] = {house: len(bodies) for house, bodies in by_house.items()}
    for _body, details in hierarchy.items():
        prominence = {"strong": 3, "moderate": 2, "light": 1}.get(str(details.get("prominence")), 0)
        for house in details.get("governs_whole_sign_houses", []):
            scores[int(house)] = scores.get(int(house), 0) + prominence
    occupied = sorted((house for house, score in scores.items() if score > 0), key=lambda house: (-scores[house], house))
    visible = occupied[:visible_limit]
    topics = HOUSE_TOPICS[lang]
    if lang == "pt":
        lines = ["As áreas abaixo não são previsões. Elas mostram onde os temas do mapa encontram contextos mais concretos.", "", "| Área | Fatores centrais | Pergunta prática |", "|---|---|---|"]
    else:
        lines = ["The areas below are not predictions. They show where chart themes meet more concrete contexts.", "", "| Area | Central factors | Practical question |", "|---|---|---|"]
    for house in visible:
        bodies = ", ".join(_token(body, lang) for body in by_house[house])
        lines.append(f"| **{topics[house]}** | {bodies} | {HOUSE_EXAMPLES[lang][house]}? |")

    divergence_groups: Dict[tuple, List[str]] = {}
    for house in visible:
        for body in by_house[house]:
            placement = chart.house_placements[body]
            if placement.placidus_house is None:
                continue
            if placement.placidus_house != placement.whole_sign_house:
                divergence_groups.setdefault((house, placement.placidus_house), []).append(body)
    if divergence_groups:
        lines.extend(["", "Apenas as divergências que mudam a leitura são nomeadas:" if lang == "pt" else "Only differences that change the reading are named:", ""])
        for (house, placidus_house), bodies in divergence_groups.items():
            labels = [_token(body, lang) for body in bodies]
            if len(labels) == 1:
                body_text = labels[0]
            else:
                connector = " e " if lang == "pt" else " and "
                body_text = ", ".join(labels[:-1]) + connector + labels[-1]
            states = {chart.house_placements[body].integration_state for body in bodies}
            if "material_divergence" in states:
                if lang == "pt":
                    lines.append(f"- **{body_text}:** Signo Inteiro aponta para {topics[house]}, enquanto Placidus aponta para {topics[placidus_house]}. São domínios diferentes; o relatório não os funde numa única conclusão.")
                else:
                    lines.append(f"- **{body_text}:** Whole Sign points to {topics[house]}, while Placidus points to {topics[placidus_house]}. These are different domains; the report does not merge them into one conclusion.")
            elif lang == "pt":
                lines.append(f"- **{body_text}:** o tópico principal é {topics[house]}; Placidus qualifica a expressão pela lente de {topics[placidus_house]}.")
            else:
                lines.append(f"- **{body_text}:** the main topic is {topics[house]}; Placidus qualifies expression through {topics[placidus_house]}.")

    lines.extend(["", "<details>", "<summary><strong>Ver as doze áreas</strong></summary>" if lang == "pt" else "<summary><strong>View all twelve areas</strong></summary>", ""])
    if lang == "pt":
        lines.extend(["| Casa | Área | Fatores centrais |", "|---:|---|---|"])
    else:
        lines.extend(["| House | Area | Central factors |", "|---:|---|---|"])
    for house in range(1, 13):
        bodies = ", ".join(_token(body, lang) for body in by_house[house])
        if not bodies:
            bodies = "sem planeta central" if lang == "pt" else "no central planet"
        lines.append(f"| {house} | {topics[house]} | {bodies} |")
    closing = (
        "Quando não há observação sobre Placidus, os sistemas configurados permaneceram na mesma casa. Uma casa vazia também pode ganhar relevância por regência e timing."
        if lang == "pt" and chart.placidus_available else
        "When no Placidus note appears, the configured systems remained in the same house. An empty house may also gain relevance through rulership and timing."
        if chart.placidus_available else
        "Placidus não estava disponível neste cálculo; a tabela mostra somente a topologia de Signo Inteiro."
        if lang == "pt" else
        "Placidus was unavailable for this calculation; the table shows Whole Sign topology only."
    )
    lines.extend(["", closing, "", "</details>"])
    return lines


def _cycle_lines(timeline: Optional[List[Dict[str, object]]], timing: Optional[Dict[str, object]], lang: str, developmental_intervals: Optional[List[Dict[str, object]]] = None) -> List[str]:
    if not timeline or not timing:
        return []
    age = int(timing["modern_stream"]["progressions"]["age_years"])
    if developmental_intervals:
        active = next((item for item in developmental_intervals if float(item["age_range"].split("–")[0]) <= age <= float(item["age_range"].split("–")[1])), None)
        interval_status = "active"
        if active is None:
            future = [item for item in developmental_intervals if float(item["age_range"].split("–")[0]) > age]
            if future:
                active = min(future, key=lambda item: float(item["age_range"].split("–")[0]))
                interval_status = "upcoming"
            else:
                active = max(developmental_intervals, key=lambda item: float(item["age_range"].split("–")[1]))
                interval_status = "recent"
        start_age, end_age = active["age_range"].split("–")
        age_label = f"na idade {start_age}" if lang == "pt" and start_age == end_age else f"idades {active['age_range']}" if lang == "pt" else f"at age {start_age}" if start_age == end_age else f"ages {active['age_range']}"
        if lang == "pt":
            status_label = {"active": "A ativação emergente em curso", "upcoming": "A próxima ativação emergente", "recent": "A ativação emergente mais recente"}[interval_status]
            lines = [
                f"{status_label} é **{active['developmental_label']}** ({age_label}). Ela é formada pelas janelas calculadas abaixo, não por uma década genérica.",
                "",
                f"- **Pressão possível:** {active['possible_pressures']}.",
                f"- **Potencial:** {active['potential']}.",
                f"- **O que este período pode pedir:** {active['what_this_period_may_ask']}.",
            ]
        else:
            status_label = {"active": "The active emergent activation", "upcoming": "The next emergent activation", "recent": "The most recent emergent activation"}[interval_status]
            lines = [f"{status_label} is **{active['developmental_label']}** ({age_label}). It is formed from the calculated windows below, not a generic decade."]
        lines.extend(["", "<details>", "<summary><strong>Calculated activations in this interval</strong></summary>" if lang == "en" else "<summary><strong>Ativações calculadas neste intervalo</strong></summary>", ""])
        for item in active["activations"]:
            lines.append(f"- {_token(str(item['body']), lang)}: {str(item['window_start'])[:10]}–{str(item['window_end'])[:10]}.")
        lines.extend(["", "</details>"])
        return lines
    current = None
    for phase in timeline:
        bounds = [int(value) for value in re.findall(r"\d+", str(phase["range"]))]
        if len(bounds) == 2 and bounds[0] <= age <= bounds[1]:
            current = phase
            break
    if not current:
        return []
    if lang == "pt":
        lines = [f"Aos {age} anos, o mapa de ciclos coloca a década **{current['range']} anos** em primeiro plano. As datas abaixo marcam períodos simbólicos de revisão; não descrevem o que aconteceu nem prometem eventos.", ""]
    else:
        lines = [f"At age {age}, the cycle map brings the **ages {current['range']}** decade into focus. The dates below mark symbolic review periods; they do not describe what happened or promise events.", ""]
    as_of_date = str(timing["modern_stream"]["progressions"]["as_of"])[:10]
    ordered = sorted(current["activations"], key=lambda item: str(item["window_start"]))
    upcoming = [item for item in ordered if str(item["window_end"])[:10] >= as_of_date]
    visible = upcoming[:4]
    if len(visible) < 2:
        recent = [item for item in ordered if item not in visible][-1:]
        visible = recent + visible
    for item in visible:
        focus = TIMING_FOCUS[lang].get(str(item["body"]), _focus_for_body(str(item["body"]), lang))
        start_date = str(item["window_start"])[:10]
        end_date = str(item["window_end"])[:10]
        date_range = f"{start_date}–{end_date}"
        is_active = start_date <= as_of_date <= end_date
        status = ("em curso" if is_active else "próxima") if lang == "pt" else ("active" if is_active else "upcoming")
        lines.append(f"- **{date_range} ({status}):** {focus}.")
    lines.extend(["", "<details>", "<summary><strong>Mapa completo por década</strong></summary>" if lang == "pt" else "<summary><strong>Complete decade map</strong></summary>", ""])
    if lang == "pt":
        lines.extend(["| Idades | Ciclos calculados | Janelas |", "|---|---|---|"])
    else:
        lines.extend(["| Ages | Calculated cycles | Windows |", "|---|---|---|"])
    for phase in timeline:
        if not phase["activations"]:
            continue
        bodies = ", ".join(_token(str(item), lang) for item in phase["dominant_themes"])
        sorted_activations = sorted(phase["activations"], key=lambda item: str(item["window_start"]))
        windows = "; ".join(f"{_token(str(item['body']), lang)} {str(item['window_start'])[:10]}–{str(item['window_end'])[:10]}" for item in sorted_activations)
        lines.append(f"| {phase['range']} | {bodies} | {windows} |")
    lines.extend(["", "</details>"])
    return lines


def _optional_depth_lines(chart: Chart, themes: List[Dict[str, object]], compensations: List[Dict[str, object]], structure: Dict[str, object], lang: str) -> List[str]:
    lines = ["## Optional depth" if lang == "en" else "## Profundidade opcional", ""]
    if len(themes) > 5:
        lines.extend(["<details>", "<summary><strong>Secondary themes</strong></summary>" if lang == "en" else "<summary><strong>Temas secundários</strong></summary>", ""])
        if lang == "pt":
            lines.extend(["| Tema | Recurso | Atenção |", "|---|---|---|"])
        else:
            lines.extend(["| Theme | Resource | Watch for |", "|---|---|---|"])
        for theme in themes[5:]:
            expression = theme["expressions"]
            lines.append(f"| **{theme['label']}** | {expression['constructive']} | {expression['defensive']} |")
        lines.extend(["", "</details>", ""])
    if compensations:
        lines.extend(["<details>", "<summary><strong>Balance hypotheses</strong></summary>" if lang == "en" else "<summary><strong>Hipóteses de equilíbrio</strong></summary>", ""])
        for item in compensations:
            element = ELEMENTS[lang].get(str(item["element"]), str(item["element"]))
            lines.append(f"- **{element}:** " + "; ".join(item["possible_expressions"]) + f". {item['interpretation_limit']}")
        lines.extend(["", "</details>", ""])
    lines.extend(["<details>", "<summary><strong>Data quality and compact calculation basis</strong></summary>" if lang == "en" else "<summary><strong>Qualidade dos dados e base compacta de cálculo</strong></summary>", ""])
    if lang == "pt":
        angle_line = f"- ASC: {_degree(chart.angles['asc'], lang)}; MC: {_degree(chart.angles['mc'], lang)}." if chart.angles else "- Ângulos e casas indisponíveis porque a hora natal é desconhecida."
        lines.extend([f"- Resolução do fuso: {chart.data_quality.timezone_resolution}.", f"- UTC utilizado: {chart.utc_datetime}.", angle_line, f"- Elementos centrais: {_translated_counts(structure['core_elements'], ELEMENTS, lang)}; modalidades: {_translated_counts(structure['core_modalities'], MODALITIES, lang)}."])
    else:
        angle_line = f"- ASC: {_degree(chart.angles['asc'], lang)}; MC: {_degree(chart.angles['mc'], lang)}." if chart.angles else "- Angles and houses unavailable because birth time is unknown."
        lines.extend([f"- Timezone resolution: {chart.data_quality.timezone_resolution}.", f"- UTC used: {chart.utc_datetime}.", angle_line, f"- Core elements: {structure['core_elements']}; modalities: {structure['core_modalities']}."])
    warning_label = "Warning" if lang == "en" else "Aviso"
    sensitivity_label = "Sensitivity" if lang == "en" else "Sensibilidade"
    lines.extend(f"- {warning_label}: {item}" for item in chart.data_quality.warnings + chart.warnings)
    for item in chart.data_quality.input_sensitivity:
        if lang == "pt" and item.startswith("Sensitivity stress test:"):
            item = "O teste contrafactual de sensibilidade atravessa a fronteira de signo do Ascendente; isso pede cautela adicional, mas não substitui a qualidade declarada da hora."
        lines.append(f"- {sensitivity_label}: {item}")
    lines.extend(["", "</details>"])
    return lines


def executive_reading(chart: SafeInterpretiveChart, claims: Iterable[Claim], themes: List[Dict[str, object]], timing: Optional[Dict[str, object]], paradoxes: List[Dict[str, object]], profile: Optional[LocalizationProfile], narrative_plan: Optional[Dict[str, object]] = None, chart_signature: Optional[Dict[str, object]] = None) -> str:
    lang = _lang(profile)
    heading = "# Executive Reading" if lang == "en" else "# Leitura Executiva"
    opening = "## The architecture in one page" if lang == "en" else "## A arquitetura em uma página"
    visible_theme_ids = set((narrative_plan or {}).get("themes", []))
    visible_themes = [theme for theme in themes if not visible_theme_ids or str(theme["id"]) in visible_theme_ids]
    theme_count = len(visible_themes)
    themes_heading = (f"## {theme_count} themes worth keeping" if lang == "en" else f"## {theme_count} temas para guardar")
    tension_heading = "## The central negotiation" if lang == "en" else "## A negociação central"
    phase_heading = "## The current chapter" if lang == "en" else "## O capítulo atual"
    synthesis_heading = "## What to do with this" if lang == "en" else "## O que fazer com esta leitura"
    lines = [heading, "", opening, "", _narrative_thread(visible_themes, paradoxes, lang, narrative_plan)]
    if chart_signature and chart_signature.get("mode") == "distributed":
        lines.extend(["", "*Esta carta não pede uma única explicação totalizante: os temas principais operam como um conjunto distribuído.*" if lang == "pt" else "*This chart does not ask for one totalising explanation: its main themes operate as a distributed set.*"])
    lines.extend(["", themes_heading, "", *_executive_theme_table(visible_themes, lang, max(theme_count, 1))])
    orientation = _executive_orientation(visible_themes, lang)
    if orientation:
        lines.extend(["", orientation])
    if paradoxes and not narrative_plan:
        lines.extend(["", tension_heading, "", *_paradox_callout(themes, paradoxes, lang)])
    if timing:
        lines.extend(["", phase_heading, "", *_current_phase_human(timing, lang, 2)])
    lines.extend(["", synthesis_heading, "", _final_synthesis(visible_themes, paradoxes, lang, narrative_plan), ""])
    if visible_themes:
        action_theme = next((item for item in visible_themes if paradoxes and item["id"] == paradoxes[0]["theme"]), visible_themes[0])
        local = localized_examples(profile, str(action_theme["id"]))
        example = action_theme.get("lived_examples", [""])[0]
        if example and local:
            example = f"{example}; se isso ajudar a tornar a escolha concreta, {local[0]}"
        elif not example and local:
            example = local[0]
        if lang == "pt":
            lines.extend([f"**Experimento concreto:** {example}.", "", f"**Pergunta útil:** em qual situação atual o tema **{action_theme['label']}** pede uma resposta diferente da habitual?"])
        else:
            lines.extend([f"**Concrete experiment:** {example}.", "", f"**Useful question:** in which current situation does **{action_theme['label']}** call for a response different from the usual one?"])
    if lang == "pt":
        lines.extend(["", "---", "", "*Leitura simbólica: descreve hipóteses para reflexão; não diagnostica, não estabelece biografia e não prevê acontecimentos concretos.*"])
    else:
        lines.extend(["", "---", "", "*Symbolic reading: it offers hypotheses for reflection; it does not diagnose, establish biography or predict concrete events.*"])
    return "\n".join(lines)


def deep_reading(chart: SafeInterpretiveChart, claims: Iterable[Claim], themes: List[Dict[str, object]], hierarchy: Dict[str, Dict[str, object]], timing: Optional[Dict[str, object]], timeline: Optional[List[Dict[str, object]]], paradoxes: List[Dict[str, object]], compensations: List[Dict[str, object]], structure: Dict[str, object], profile: Optional[LocalizationProfile], reasoned_syntheses: Optional[List[Dict[str, object]]] = None, narrative_plan: Optional[Dict[str, object]] = None, developmental_intervals: Optional[List[Dict[str, object]]] = None, chart_signature: Optional[Dict[str, object]] = None) -> str:
    lang = _lang(profile)
    if lang == "pt":
        lines = ["# Leitura Natal Profunda", "", "> **Percurso:** arquitetura → dinâmica central → temas diferenciados → áreas da vida → fase atual → ciclos → integração. Recurso, tensão e possibilidade de escolha aparecem em prosa; cálculo e jargão ficam no apêndice técnico.", "", "## A arquitetura da pessoa", "", _narrative_thread(themes, paradoxes, lang, narrative_plan)]
    else:
        lines = ["# Deep Natal Reading", "", "> **Path:** architecture → central dynamic → differentiated themes → life areas → current phase → cycles → integration. Resource, tension and choice appear in prose; calculation and jargon stay in the technical appendix.", "", "## The person's architecture", "", _narrative_thread(themes, paradoxes, lang, narrative_plan)]
    visible_theme_ids = set((narrative_plan or {}).get("themes", []))
    visible_themes = [theme for theme in themes if not visible_theme_ids or str(theme["id"]) in visible_theme_ids]
    if paradoxes and not narrative_plan:
        lines.extend(["", *_paradox_callout(themes, paradoxes, lang)])
    lines.extend(["", "## Core themes: resource, shadow and integration" if lang == "en" else "## Temas centrais: recurso, sombra e integração", ""])
    composition_by_theme = {str(item["id"]).removeprefix("reasoned."): item for item in (reasoned_syntheses or []) if item.get("status") == "allowed"}
    for rank, theme in enumerate(visible_themes, 1):
        lines.extend(_theme_block(theme, lang, rank, profile, composition=composition_by_theme.get(str(theme["id"]))))
    lines.extend(["", "## Where this may become concrete" if lang == "en" else "## Onde isso pode ganhar forma concreta", "", *_life_area_lines(chart, lang)])
    if timing:
        lines.extend(["", "## Current phase" if lang == "en" else "## Fase atual", "", *_current_phase_human(timing, lang, 3), "", "<details>", "<summary><strong>Technical timing basis</strong></summary>" if lang == "en" else "<summary><strong>Base técnica do timing</strong></summary>", "", *_current_phase_lines(timing, lang), "", "</details>"])
    cycle_section = _cycle_lines(timeline, timing, lang, developmental_intervals)
    if cycle_section:
        lines.extend(["", "## Life cycles" if lang == "en" else "## Ciclos da vida", "", *cycle_section])
    lines.extend(["", "## Integration" if lang == "en" else "## Integração", "", _final_synthesis(visible_themes, paradoxes, lang, narrative_plan)])
    if visible_themes:
        if lang == "pt":
            lines.extend(["", "**Experimento de sete dias:** anote contexto → reação automática → alternativa escolhida → efeito. O objetivo é observar o padrão, não provar a interpretação.", "", f"- Em que contexto **{visible_themes[0]['label']}** já funciona como recurso?", f"- Qual sinal mostraria que a estratégia defensiva começou a assumir o controle?"])
        else:
            lines.extend(["", "**Seven-day experiment:** record context → automatic response → chosen alternative → effect. The aim is to observe the pattern, not prove the interpretation.", "", f"- In what context does **{visible_themes[0]['label']}** already work as a resource?", f"- What sign would show that the defensive strategy has begun to take over?"])
    lines.extend(["", *_optional_depth_lines(chart, themes, compensations, structure, lang), "", "---", ""])
    if lang == "pt":
        lines.append("*Predisposição simbólica, capacidade e manifestação informada são categorias diferentes. Discordar de uma hipótese é um resultado válido. Esta leitura não diagnostica nem prevê acontecimentos concretos.*")
    else:
        lines.append("*Symbolic predisposition, capacity and reported manifestation are different categories. Disagreeing with a hypothesis is a valid result. This reading does not diagnose or predict concrete events.*")
    return "\n".join(lines)

def technical_appendix(chart: SafeInterpretiveChart, hierarchy: Dict[str, Dict[str, object]], claims: Iterable[Claim], timing: Optional[Dict[str, object]], structure: Dict[str, object], profile: Optional[LocalizationProfile], reasoned_syntheses: Optional[List[Dict[str, object]]] = None, narrative_plan: Optional[Dict[str, object]] = None, chart_signature: Optional[Dict[str, object]] = None) -> str:
    lang = _lang(profile)
    lines = [
        "# Technical Appendix" if lang == "en" else "# Apêndice Técnico", "",
        "> This appendix is for audit and advanced study. The main reading remains complete without it." if lang == "en" else "> Este apêndice serve para auditoria e estudo avançado. A leitura principal permanece completa sem ele.", "",
        "## Audit identity" if lang == "en" else "## Identidade de auditoria", "",
        f"- Schema: {chart.schema_version}", f"- Methodology: {chart.methodology_version}",
        f"- Backend: {chart.backend['name']} {chart.backend['version']}.",
        f"- Timezone data: {chart.backend['tzdata']}.",
        "", "<details>",
        "<summary><strong>Complete versioned policy</strong></summary>" if lang == "en" else "<summary><strong>Política versionada completa</strong></summary>",
        "", "```json", json.dumps(chart.policy, ensure_ascii=False, indent=2, sort_keys=True), "```", "", "</details>",
        "", "## Positions" if lang == "en" else "## Posições", "",
    ]
    for item in chart.positions.values():
        placement = chart.house_placements.get(item.key)
        conditional = chart.conditional_house_scenarios.get(item.key)
        house_text = f"Whole Sign {placement.whole_sign_house}; Placidus {placement.placidus_house}; integration {placement.integration_state}" if placement else (f"conditional primary Whole Sign {conditional.primary_whole_sign_house}; Placidus {conditional.primary_placidus_house}; not used as interpretive evidence" if conditional else "houses unavailable")
        label = _token(item.key, lang)
        if lang == "pt":
            house_text = f"Signo Inteiro {placement.whole_sign_house}; Placidus {placement.placidus_house}; integração {placement.integration_state}" if placement else (f"Signo Inteiro primário condicional {conditional.primary_whole_sign_house}; Placidus {conditional.primary_placidus_house}; não usado como evidência interpretativa" if conditional else "casas indisponíveis")
            lines.append(f"- {label}: {_degree(item.longitude, lang)}; velocidade {item.speed_longitude:.6f}°/dia; {house_text}.")
        else:
            lines.append(f"- {label}: {_degree(item.longitude, lang)}; speed {item.speed_longitude:.6f}°/day; {house_text}.")
    lines.extend(["", "## Angles" if lang == "en" else "## Ângulos", ""])
    lines.extend(f"- {name.upper()}: {_degree(value, lang)}" for name, value in chart.angles.items())
    lines.extend(["", "## Lots" if lang == "en" else "## Lotes", "", json.dumps(chart.lots, ensure_ascii=False, sort_keys=True), "", "## Aspects" if lang == "en" else "## Aspectos", ""])
    lines.extend(f"- {_token(item.left, lang)} {_token(item.kind, lang)} {_token(item.right, lang)}; orbe {item.orb:.4f}°; aplicando: {'indeterminado' if item.applying is None else 'sim' if item.applying else 'não'}." if lang == "pt" else f"- {_token(item.left, lang)} {_token(item.kind, lang)} {_token(item.right, lang)}; orb {item.orb:.4f}°; applying: {item.applying}." for item in chart.aspects)
    lines.extend(["", "## Structure and configurations" if lang == "en" else "## Estrutura e configurações", ""])
    for item in structure.get("configurations", []):
        name = CONFIGURATIONS[lang].get(str(item["kind"]), str(item["kind"]).replace("_", " "))
        bodies = ", ".join(_token(str(body), lang) for body in item["bodies"])
        lines.append(f"- **{name}{_configuration_basis(item, lang)}:** {bodies}.")
    lines.extend(["", "<details>", "<summary><strong>Structured calculation data</strong></summary>" if lang == "en" else "<summary><strong>Dados estruturados do cálculo</strong></summary>", "", "```json", json.dumps(structure, ensure_ascii=False, indent=2, sort_keys=True), "```", "", "</details>", "", "## Dynamic hierarchy" if lang == "en" else "## Hierarquia dinâmica", ""])
    for body, item in hierarchy.items():
        if lang == "pt":
            lines.append(f"- {_token(body, lang)}: proeminência {item['prominence']}; recursos {item['condition_resources']}; fricções {item['condition_frictions']}; relevância {item['topical_relevance']}; confiabilidade {item['evidence_reliability']}; funções {', '.join(item['roles']) or 'nenhuma'}.")
        else:
            lines.append(f"- {body}: prominence {item['prominence']}; resources {item['condition_resources']}; frictions {item['condition_frictions']}; relevance {item['topical_relevance']}; reliability {item['evidence_reliability']}; roles {', '.join(item['roles']) or 'none'}.")
    lines.extend(["", "## Claims", ""])
    for claim in claims:
        lines.append(f"- {claim.id}: {claim.status}; evidence {claim.evidence}; motifs {claim.authorized_motifs}; counterweights {claim.counterweight_types}; verifier {claim.verification_errors}.")
    if reasoned_syntheses:
        lines.extend(["", "## Reasoned synthesis", ""])
        for item in reasoned_syntheses:
            lines.append(f"- {item['id']}: {item['status']}; claims={item.get('source_claim_ids', [])}; motifs={item.get('source_motif_ids', [])}; primary={item['primary_factors']}; modifiers={item['modifiers']}; operations={item.get('composition_operations', [])}; propositions={item.get('derived_propositions', [])}; counterweights={item['counterweights']}; verifier={item['verification_errors']}.")
    if chart_signature:
        lines.extend(["", "## Chart signature", "", "```json", json.dumps(chart_signature, ensure_ascii=False, indent=2, sort_keys=True), "```"])
    if narrative_plan:
        lines.extend(["", "## Narrative plan", "", "```json", json.dumps(narrative_plan, ensure_ascii=False, indent=2, sort_keys=True), "```"])
    if timing:
        lines.extend(["", "## Timing", "", f"- {timing['deduplication_policy']}"])
        focus = timing["current_phase"]["traditional_focus"]
        if lang == "pt":
            lines.append(f"- Foco anual: casa {focus['house']}; senhor do ano: {_token(focus['time_lord'], lang)}." if focus["time_lord"] else ("- Foco anual por profecção: omitido porque a topologia de Signo Inteiro é condicional." if timing["traditional_stream"].get("status") == "conditional" else "- Foco anual por profecção: indisponível."))
        else:
            lines.append(f"- Annual focus: house {focus['house']}; time lord: {_token(focus['time_lord'], lang)}." if focus["time_lord"] else ("- Annual profection focus: omitted because the Whole Sign topology is conditional." if timing["traditional_stream"].get("status") == "conditional" else "- Annual profection focus: unavailable."))
        lines.extend(["", "<details>", "<summary><strong>Major transit windows</strong></summary>" if lang == "en" else "<summary><strong>Janelas de trânsitos maiores</strong></summary>", ""])
        for event in _transit_windows(timing["modern_stream"]["major_transits"], 1000):
            raw = _format_transit_window(event, lang)
            lines.append(f"- {raw}; family `{event['evidence_family']}`; priority {event['window_priority']}.")
        lines.extend(["", "</details>", "", "<details>", "<summary><strong>Secondary progressions</strong></summary>" if lang == "en" else "<summary><strong>Progressões secundárias</strong></summary>", ""])
        for contact in timing["modern_stream"]["progressions"]["contacts"]:
            lines.append(f"- {_token(contact['body'], lang)} {_token(contact['aspect'], lang)} {_token(contact['target'], lang)}; orb {contact['orb']:.4f}°; family `{contact['evidence_family']}`.")
        lines.extend(["", "</details>", "", "<details>", "<summary><strong>Solar arcs</strong></summary>" if lang == "en" else "<summary><strong>Arcos solares</strong></summary>", ""])
        for contact in timing["modern_stream"]["solar_arcs"]["contacts"]:
            lines.append(f"- {_token(contact['body'], lang)} {_token(contact['aspect'], lang)} {_token(contact['target'], lang)}; orb {contact['orb']:.4f}°; family `{contact['evidence_family']}`.")
        lines.extend(["", "</details>"])
    lines.extend(["", "## Localization", "", "```json", json.dumps(localization_audit(profile), ensure_ascii=False, indent=2, sort_keys=True), "```"])
    return "\n".join(lines)


def render_report(depth: str, chart: SafeInterpretiveChart, claims: Iterable[Claim], themes: List[Dict[str, object]], hierarchy: Dict[str, Dict[str, object]], timing: Optional[Dict[str, object]], timeline: Optional[List[Dict[str, object]]], paradoxes: List[Dict[str, object]], compensations: List[Dict[str, object]], structure: Dict[str, object], profile: Optional[LocalizationProfile], reasoned_syntheses: Optional[List[Dict[str, object]]] = None, narrative_plan: Optional[Dict[str, object]] = None, developmental_intervals: Optional[List[Dict[str, object]]] = None, chart_signature: Optional[Dict[str, object]] = None) -> str:
    if depth == "executive":
        return executive_reading(chart, claims, themes, timing, paradoxes, profile, narrative_plan, chart_signature)
    if depth == "technical":
        return technical_appendix(chart, hierarchy, claims, timing, structure, profile, reasoned_syntheses, narrative_plan, chart_signature)
    if depth != "deep":
        raise ValueError("report_depth must be executive, deep or technical")
    return deep_reading(chart, claims, themes, hierarchy, timing, timeline, paradoxes, compensations, structure, profile, reasoned_syntheses, narrative_plan, developmental_intervals, chart_signature)
