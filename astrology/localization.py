"""Post-synthesis localization.  It may change wording, never chart evidence."""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import LocalizationProfile


def localized_examples(profile: Optional[LocalizationProfile], theme: str) -> List[str]:
    if not profile or profile.localization_level == "off":
        return []
    country = (profile.current_country or "").casefold().replace(" ", "_")
    # Country supplies only neutral rendering context.  It never selects a
    # psychological theme or maps a culture to a trait.
    neutral_context = {
        "brazil": "considerar valores e margem em reais antes de escolher entre alternativas",
        "portugal": "comparar condições, continuidade e margem prática entre alternativas",
        "venezuela": "rever uma decisão prática sem transformar adaptação em identidade",
        "united_states": "comparar escopo, autonomia e sustentabilidade antes de assumir uma responsabilidade",
        "united_kingdom": "distinguir contribuição concreta de visibilidade adicional numa oportunidade",
        "netherlands": "clarificar responsabilidades num projeto coletivo antes de assumir coordenação extra",
        "japan": "definir uma contribuição concreta e um limite claro numa decisão coletiva",
    }
    return [neutral_context[country]] if country in neutral_context else []


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
