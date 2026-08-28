"""Bilingual consultation constrained to verified claims and declared topics."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .config import BODY_LABELS, SUPPORT_VALUE
from .models import Claim
from .semantics import theme_label

INTENTS = {
    "career": {"keywords": ("trabalho", "carreira", "profiss", "career", "work", "job", "vocation"), "themes": ("purpose", "competence", "visibility_privacy", "ambition", "service", "security_exploration"), "houses": (2, 6, 10)},
    "relationships": {"keywords": ("relacion", "amor", "parceria", "relationship", "love", "partner", "intimacy"), "themes": ("autonomy_closeness", "individuality_belonging", "care", "pleasure", "transformation"), "houses": (5, 7, 8)},
    "money": {"keywords": ("dinheiro", "finan", "money", "finance", "income"), "themes": ("security_exploration", "competence"), "houses": (2, 8, 10)},
    "family": {"keywords": ("família", "familia", "casa", "family", "home", "roots"), "themes": ("care", "individuality_belonging", "visibility_privacy"), "houses": (4, 10)},
    "emotions": {"keywords": ("emoç", "sentimento", "emotion", "feeling", "mood"), "themes": ("autonomy_closeness", "reason_feeling", "care"), "houses": (4, 8, 12)},
    "purpose": {"keywords": ("propósito", "proposito", "espiritual", "sentido", "purpose", "spiritual", "meaning"), "themes": ("purpose", "spirituality", "security_exploration"), "houses": (9, 10, 12)},
    "boundaries": {"keywords": ("limite", "raiva", "coragem", "boundary", "boundaries", "anger", "courage"), "themes": ("control_spontaneity", "receptivity_initiative", "competence"), "houses": (1, 6, 7)},
    "houses": {"keywords": ("placidus", "whole sign", "signo inteiro", "casas", "houses"), "themes": ("individuality_belonging", "security_exploration", "curiosity", "care", "creativity", "service", "autonomy_closeness", "transformation", "purpose", "ambition", "spirituality"), "houses": tuple(range(1, 13))},
}
SENSITIVE = ("saúde", "saude", "doença", "doenca", "health", "disease", "diagnosis", "gravidez", "pregnancy", "morte", "death")
ASPECT_LABELS = {"conjunction": "conjunção", "sextile": "sextil", "square": "quadratura", "trine": "trígono", "quincunx": "quincúncio", "opposition": "oposição"}
NEXT_STEPS = {
    "pt": {
        "career": "Escolha duas opções reais de carreira e registre qual permite praticar essa integração de forma observável nas próximas semanas.",
        "relationships": "Escolha uma interação recente e formule um pedido ou limite observável que teste essa integração.",
        "money": "Aplique essa integração a uma decisão financeira pequena, com critério e prazo definidos antes de agir.",
        "family": "Escolha uma interação familiar recente e observe o que mudaria se essa integração orientasse sua resposta.",
        "emotions": "Aplique essa integração a uma situação emocional recente e registre necessidade, intensidade e ação possível separadamente.",
        "purpose": "Escolha uma ação de baixo risco que teste essa integração sem exigir certeza sobre a direção inteira.",
        "boundaries": "Formule um limite observável que pratique essa integração, contendo fato, necessidade e consequência prática.",
        "houses": "Compare as duas casas como lentes complementares e registre qual descreve tópico e qual descreve forma de expressão.",
    },
    "en": {
        "career": "Choose two real career options and note which one lets you practice this integration observably over the next few weeks.",
        "relationships": "Choose one recent interaction and formulate an observable request or boundary that tests this integration.",
        "money": "Apply this integration to one small financial decision, defining the criterion and timeframe before acting.",
        "family": "Choose one recent family interaction and notice what would change if this integration guided your response.",
        "emotions": "Apply this integration to one recent emotional situation and record need, intensity and possible action separately.",
        "purpose": "Choose one low-risk action that tests this integration without demanding certainty about the whole direction.",
        "boundaries": "Formulate an observable boundary that practices this integration and contains fact, need and practical consequence.",
        "houses": "Compare the two houses as complementary lenses and note which describes topic and which describes form of expression.",
    },
}


def classify_question(question: str) -> Dict[str, object]:
    lowered = question.casefold()
    matched = [name for name, item in INTENTS.items() if any(keyword in lowered for keyword in item["keywords"])]
    themes = sorted({theme for name in matched for theme in INTENTS[name]["themes"]})
    houses = sorted({house for name in matched for house in INTENTS[name]["houses"]})
    return {"intents": matched, "themes": themes, "houses": houses, "sensitive": any(token in lowered for token in SENSITIVE)}


def _claim_bodies(claim: Claim, chart: Optional[object]) -> set:
    if not chart:
        return {part for evidence in claim.evidence for part in evidence.replace(".", "_").split("_")}
    if isinstance(chart, dict):
        factor_by_id = {factor["id"]: factor for factor in chart["factors"]}
        aspect_by_id = {aspect["id"]: aspect for aspect in chart["aspects"]}
    else:
        factor_by_id = {factor.id: factor for factor in chart.factors}
        aspect_by_id = {aspect.id: aspect for aspect in chart.aspects}
    bodies = set()
    for evidence in claim.evidence:
        if evidence in aspect_by_id:
            aspect = aspect_by_id[evidence]
            bodies.update((aspect["left"], aspect["right"]) if isinstance(aspect, dict) else (aspect.left, aspect.right))
        elif evidence in factor_by_id:
            factor = factor_by_id[evidence]
            bodies.update(factor["bodies"] if isinstance(factor, dict) else factor.bodies)
    return bodies


def _group_timing(events: Iterable[Dict[str, object]], limit: int = 4) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = {}
    for event in events:
        grouped.setdefault(str(event["evidence_family"]), []).append(event)
    windows = []
    for family, passes in grouped.items():
        passes.sort(key=lambda item: str(item["exact_at"]))
        first = dict(passes[0])
        first.update({"evidence_family": family, "pass_dates": [str(item["exact_at"]) for item in passes], "pass_count": len(passes), "priority": max(int(item.get("priority", 0)) for item in passes)})
        windows.append(first)
    return sorted(windows, key=lambda item: (-int(item["priority"]), str(item["exact_at"])))[:limit]


def answer_question(question: str, claims: Iterable[Claim], language: str = "pt-BR", timing: Optional[Dict[str, object]] = None, hierarchy: Optional[Dict[str, Dict[str, object]]] = None, chart: Optional[object] = None, themes: Optional[List[Dict[str, object]]] = None) -> Dict[str, object]:
    intent = classify_question(question)
    pt = language.startswith("pt")
    if intent["sensitive"]:
        return {
            "answer": "Não uso astrologia para avaliar saúde, diagnóstico, gravidez ou risco. Posso reformular a pergunta em termos não médicos de rotina, energia percebida ou apoio profissional." if pt else "I do not use astrology to assess health, diagnosis, pregnancy or risk. I can reframe the question around non-medical routines, perceived energy or professional support.",
            "claims": [], "intent": intent, "limits": ["Sensitive-domain boundary."],
        }
    if not intent["themes"]:
        return {
            "answer": "A pergunta é ampla ou não corresponde a um domínio configurado. Especifique carreira, vínculos, recursos, família, emoções, propósito, limites ou comparação de casas." if pt else "The question is broad or does not match a configured domain. Specify career, relationships, resources, family, emotions, purpose, boundaries or house-system comparison.",
            "claims": [], "intent": intent, "limits": ["No arbitrary fallback claims were selected."],
        }
    candidates = [claim for claim in claims if claim.status == "allowed" and claim.theme in intent["themes"]]
    ordinal = {"none": 0, "light": 1, "moderate": 2, "strong": 3}
    def query_score(claim: Claim) -> tuple:
        bodies = _claim_bodies(claim, chart)
        relevance = max((ordinal.get(str((hierarchy or {}).get(body, {}).get("topical_relevance", "none")), 0) for body in bodies), default=0)
        house_priority = int("houses" in intent["intents"] and claim.type == "topical_tendency")
        return (-house_priority, -relevance, -SUPPORT_VALUE[claim.astrological_support], -len(claim.evidence_families), claim.id)
    candidates.sort(key=query_score)
    candidates = candidates[:5]
    if not candidates:
        return {"answer": "Não há suporte rastreável suficiente para responder sem improvisar." if pt else "There is not enough traceable support to answer without improvising.", "claims": [], "intent": intent, "limits": ["Insufficient traceable evidence."]}
    relevant_timing = []
    if timing:
        claim_bodies = {body for claim in candidates for body in _claim_bodies(claim, chart)}
        relevant_timing = _group_timing(event for event in timing["modern_stream"]["major_transits"] if event["target"] in claim_bodies or event["transit_body"] in claim_bodies)
    house_comparison = []
    if chart and "houses" in intent["intents"]:
        placements = chart["house_placements"] if isinstance(chart, dict) else chart.house_placements
        house_comparison = []
        for body, placement in placements.items():
            house_comparison.append({
                "body": body,
                "whole_sign_house": placement["whole_sign_house"] if isinstance(placement, dict) else placement.whole_sign_house,
                "placidus_house": placement["placidus_house"] if isinstance(placement, dict) else placement.placidus_house,
                "integration_state": placement["integration_state"] if isinstance(placement, dict) else placement.integration_state,
                "rationale": placement["integration_rationale"] if isinstance(placement, dict) else placement.integration_rationale,
            })
    selected_themes = [theme_label(theme, language) for theme in dict.fromkeys(claim.theme for claim in candidates)]
    focus = [theme for theme in (themes or []) if theme["id"] in {claim.theme for claim in candidates}][:3]
    if "houses" in intent["intents"]:
        answer = "Signo Inteiro define os tópicos; Placidus qualifica posição espacial e proximidade de cúspide. As convergências e divergências concretas estão listadas abaixo." if pt else "Whole Sign defines topics; Placidus qualifies spatial position and cusp proximity. The concrete convergences and divergences are listed below."
    else:
        joined = ", ".join(selected_themes)
        if focus:
            movement = focus[0]["expressions"]["integrated"]
            answer = f"A leitura prioriza {joined}. O movimento mais útil para esta pergunta é {movement}. As hipóteses abaixo mostram a base e os limites dessa síntese." if pt else f"The reading prioritizes {joined}. The most useful move for this question is to {movement}. The hypotheses below show the basis and limits of that synthesis."
        else:
            answer = f"Para esta pergunta, a hierarquia tópica prioriza os temas: {joined}. As hipóteses abaixo são as mais sustentadas e contextualmente relevantes." if pt else f"For this question, topical hierarchy prioritizes: {joined}. The hypotheses below are the most supported and contextually relevant."
    return {
        "answer": answer,
        "claims": [{"statement": claim.statement, "evidence": claim.evidence, "counterweights": claim.counterweights, "specificity": claim.allowed_specificity} for claim in candidates],
        "intent": intent, "focus": focus, "relevant_timing": relevant_timing, "house_comparison": house_comparison,
        "limits": ["Não diagnostica nem promete acontecimentos." if pt else "It does not diagnose or promise events.", "Discordância é um resultado válido; feedback não aumenta o suporte astrológico." if pt else "Non-resonance is a valid result; feedback does not increase astrological support."],
    }


def render_consultation(question: str, answer: Dict[str, object], language: str = "pt-BR") -> str:
    """Render a concise consultation while preserving the structured payload."""
    pt = language.startswith("pt")
    lines = ["# Consulta Astrológica" if pt else "# Astrological Consultation", "", f"> **Pergunta:** {question}" if pt else f"> **Question:** {question}", "", "## Resposta direta" if pt else "## Direct answer", "", str(answer["answer"])]
    claims = answer.get("claims", [])
    if claims:
        focus = answer.get("focus", [])
        if focus:
            lines.extend(["", "## Luz, tensão e integração" if pt else "## Constructive, tension and integration", ""])
            for theme in focus:
                expressions = theme["expressions"]
                if pt:
                    lines.extend([f"### {theme['label']}", "", f"- ✦ **Luz:** {expressions['constructive']}.", f"- ◐ **Sob pressão:** {expressions['defensive']}.", f"- → **Integração:** {expressions['integrated']}.", ""])
                else:
                    lines.extend([f"### {theme['label']}", "", f"- ✦ **Constructive:** {expressions['constructive']}.", f"- ◐ **Under pressure:** {expressions['defensive']}.", f"- → **Integration:** {expressions['integrated']}.", ""])
        lines.extend(["", "## O que sustenta a resposta" if pt else "## What supports the answer", ""])
        for index, claim in enumerate(claims, 1):
            lines.append(f"{index}. {claim['statement']}")
        lines.extend(["", "<details>", "<summary><strong>Evidência e contrapesos</strong></summary>" if pt else "<summary><strong>Evidence and counterweights</strong></summary>", ""])
        for index, claim in enumerate(claims, 1):
            evidence = ", ".join(claim.get("evidence", [])) or ("nenhuma" if pt else "none")
            counterweights = ", ".join(claim.get("counterweights", [])) or ("nenhum registrado" if pt else "none recorded")
            lines.append(f"- **{index}:** evidência `{evidence}`; contrapesos: {counterweights}." if pt else f"- **{index}:** evidence `{evidence}`; counterweights: {counterweights}.")
        lines.extend(["", "</details>"])
    timing = answer.get("relevant_timing", [])
    if timing:
        lines.extend(["", "## Timing relevante" if pt else "## Relevant timing", ""])
        for event in timing:
            body = BODY_LABELS["pt"].get(str(event["transit_body"]), str(event["transit_body"])) if pt else str(event["transit_body"]).title()
            target = BODY_LABELS["pt"].get(str(event["target"]), str(event["target"]).upper() if str(event["target"]) in {"asc", "mc", "dsc", "ic"} else str(event["target"])) if pt else str(event["target"]).upper() if str(event["target"]) in {"asc", "mc", "dsc", "ic"} else str(event["target"]).title()
            aspect = ASPECT_LABELS.get(str(event["aspect"]), str(event["aspect"])) if pt else str(event["aspect"]).replace("_", " ")
            dates = ", ".join(date[:10] for date in event.get("pass_dates", [str(event["exact_at"])]) )
            suffix = f"{event.get('pass_count', 1)} passagens: {dates}" if pt and event.get("pass_count", 1) > 1 else f"{event.get('pass_count', 1)} passes: {dates}" if event.get("pass_count", 1) > 1 else dates
            lines.append(f"- {body} {aspect} {target} — {suffix}.")
    primary_intent = next(iter(answer.get("intent", {}).get("intents", [])), None)
    next_step = NEXT_STEPS["pt" if pt else "en"].get(primary_intent, "Use a resposta como hipótese: escolha um sinal observável a favor e um contra antes de decidir." if pt else "Use the answer as a hypothesis: choose one observable sign for it and one against it before deciding.")
    focus = answer.get("focus", [])
    if focus:
        integration = focus[0]["expressions"]["integrated"]
        next_step = (f"**Experimento:** {integration}. " if pt else f"**Experiment:** {integration}. ") + next_step
    lines.extend(["", "## Síntese e próximo passo" if pt else "## Synthesis and next step", "", next_step, "", "## Limites" if pt else "## Limits", ""])
    lines.extend(f"- {item}" for item in answer.get("limits", []))
    return "\n".join(lines)
