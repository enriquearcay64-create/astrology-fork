"""Paradox and compensation hypotheses derived after evidence synthesis."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .config import THEME_POLES


def build_paradoxes(themes: Iterable[Dict[str, object]], language: str = "pt-BR", limit: int = 5) -> List[Dict[str, object]]:
    output = []
    lang = "pt" if language.startswith("pt") else "en"
    for theme in themes:
        poles = THEME_POLES[lang].get(str(theme["id"]))
        if not poles or theme["support_level"] == "light":
            continue
        output.append({
            "theme": theme["id"], "poles": list(poles), "support_level": theme["support_level"],
            "evidence": list(theme["evidence"]), "counterweights": list(theme["counterweights"]),
            "interpretation_limit": "A polarity can coexist or alternate; it is not a diagnosis or fixed personality split.",
        })
    return output[:limit]


def build_compensation_hypotheses(structure: Dict[str, object], language: str = "pt-BR") -> List[Dict[str, object]]:
    """Generate hypotheses from sparse elements without asserting compensation."""
    lang = "pt" if language.startswith("pt") else "en"
    possibilities = {
        "pt": {
            "fire": ["cultivar iniciativa deliberadamente", "usar estruturas externas para iniciar movimento"],
            "earth": ["construir rotinas práticas conscientemente", "buscar ancoragem em compromissos concretos"],
            "air": ["desenvolver linguagem para mudar de perspectiva", "usar diálogo para organizar a experiência"],
            "water": ["desenvolver vocabulário emocional deliberadamente", "buscar contextos que permitam processamento receptivo"],
        },
        "en": {
            "fire": ["deliberately cultivate initiative", "borrow momentum from external structures"],
            "earth": ["build practical routines consciously", "seek grounding through concrete commitments"],
            "air": ["develop language for perspective-taking", "seek dialogue to organize experience"],
            "water": ["develop emotional vocabulary deliberately", "seek contexts that permit receptive processing"],
        },
    }
    counts = dict(structure.get("core_elements", structure.get("elements", {})))
    output = []
    for element in ("fire", "earth", "air", "water"):
        if counts.get(element, 0) <= 1:
            output.append({
                "element": element,
                "astrological_support": {"type": "relative_element_scarcity", "count": counts.get(element, 0), "family": f"element_balance_{element}"},
                "manifestation_feedback": "unknown",
                "possible_expressions": possibilities[lang][element],
                "interpretation_limit": "Escassez não prova ausência nem compensação; são alternativas a testar, inclusive a possibilidade de não ressoar." if lang == "pt" else "Scarcity does not prove absence or compensation; these are alternatives to test, including non-resonance.",
            })
    return output
