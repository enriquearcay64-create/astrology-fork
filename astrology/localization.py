"""Post-synthesis localization.  It may change wording, never chart evidence."""
from __future__ import annotations

from typing import Dict, List, Optional

from .models import LocalizationProfile


def localized_examples(profile: Optional[LocalizationProfile], theme: str) -> List[str]:
    if not profile or profile.localization_level == "off":
        return []
    # Country never selects a scenario.  Examples must originate from chart
    # evidence; localization is limited to language and formatting elsewhere.
    return []


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
