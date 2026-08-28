"""Post-synthesis localization.  It may change wording, never chart evidence."""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import LocalizationProfile


def localized_examples(profile: Optional[LocalizationProfile], theme: str) -> List[str]:
    if not profile or profile.localization_level == "off":
        return []
    country = (profile.current_country or "").casefold().replace(" ", "_")
    # These are presentation seeds, not cultural psychology. The LLM may use
    # them only when they improve a hypothetical example and may omit them.
    examples_by_context = {
        "brazil": {
            "security_exploration": ["definir uma reserva em reais e qual margem pode financiar uma mudança ou experiência"],
            "competence": ["comparar uma posição estável com um projeto independente, considerando renda, direitos e margem de risco"],
        },
        "portugal": {
            "competence": ["comparar uma proposta de contrato com um projeto independente, considerando ritmo, rendimentos e continuidade"],
            "security_exploration": ["separar uma decisão de crescimento de uma escolha feita apenas para reduzir incerteza financeira"],
        },
        "venezuela": {
            "security_exploration": ["rever um plano de despesas e mudança sem transformar toda adaptação prática numa decisão de identidade"],
            "competence": ["decidir quais compromissos manter enquanto se testa uma alternativa com margem realista"],
        },
        "united_states": {
            "competence": ["comparar escopo, autonomia e sustentabilidade antes de assumir uma nova responsabilidade"],
        },
        "united_kingdom": {
            "purpose": ["avaliar se uma oportunidade amplia contribuição real ou apenas acrescenta visibilidade"],
        },
        "netherlands": {
            "service": ["negociar responsabilidades num projeto coletivo sem assumir sozinho o trabalho de coordenação"],
        },
        "japan": {
            "individuality_belonging": ["dar uma contribuição clara a um grupo sem abandonar um critério pessoal importante"],
        },
    }
    return examples_by_context.get(country, {}).get(theme, [])[:1]


def localization_audit(profile: Optional[LocalizationProfile]) -> Dict[str, object]:
    return {
        "enabled": bool(profile and profile.localization_level != "off"),
        "source": profile.source if profile else None,
        "allowed_changes": ["language", "wording", "examples", "institutions", "units", "date_format"],
        "prohibited_changes": ["personality", "astrological_weights", "themes", "prediction"],
        "rendering_context": {
            "language": profile.preferred_language if profile else None,
            "current_context": profile.current_country if profile else None,
            "background_context": profile.cultural_context if profile else None,
            "strength": profile.localization_level if profile else "off",
            "rule": "Use context only for wording and hypothetical examples; never infer psychology from country, language or culture.",
        },
    }
