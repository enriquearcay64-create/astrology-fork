"""Versioned conservative policy defaults.  Change only with a methodology version bump."""
from __future__ import annotations

METHODOLOGY_VERSION = "4.1.2"
SCHEMA_VERSION = "4.1.1"
PREMIUM_HANDOFF_CONTRACT_VERSION = "1.1"
EPHEMERIS_START_YEAR = 1800
EPHEMERIS_END_YEAR = 2399

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_RULERS = {
    "Aries": "mars", "Taurus": "venus", "Gemini": "mercury", "Cancer": "moon",
    "Leo": "sun", "Virgo": "mercury", "Libra": "venus", "Scorpio": "mars",
    "Sagittarius": "jupiter", "Capricorn": "saturn", "Aquarius": "saturn", "Pisces": "jupiter",
}
EXALTATIONS = {"Aries": "sun", "Taurus": "moon", "Cancer": "jupiter", "Virgo": "mercury", "Libra": "saturn", "Capricorn": "mars", "Pisces": "venus"}
DETRIMENTS = {"Aries": "venus", "Taurus": "mars", "Gemini": "jupiter", "Cancer": "saturn", "Leo": "saturn", "Virgo": "jupiter", "Libra": "mars", "Scorpio": "venus", "Sagittarius": "mercury", "Capricorn": "moon", "Aquarius": "sun", "Pisces": "mercury"}
FALLS = {"Aries": "saturn", "Cancer": "mars", "Virgo": "venus", "Libra": "sun", "Scorpio": "moon", "Capricorn": "jupiter", "Pisces": "mercury"}

# The default includes only factors that have a documented deterministic definition.
BODY_CODES = {
    "sun": ("Sun", "SUN"), "moon": ("Moon", "MOON"), "mercury": ("Mercury", "MERCURY"),
    "venus": ("Venus", "VENUS"), "mars": ("Mars", "MARS"), "jupiter": ("Jupiter", "JUPITER"),
    "saturn": ("Saturn", "SATURN"), "uranus": ("Uranus", "URANUS"), "neptune": ("Neptune", "NEPTUNE"),
    "pluto": ("Pluto", "PLUTO"), "true_node": ("True North Node", "TRUE_NODE"),
    "chiron": ("Chiron", "CHIRON"), "lilith_mean": ("Mean Lunar Apogee (Lilith)", "MEAN_APOG"),
}
PRIMARY_BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto")
CORE_STRUCTURE_BODIES = ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn")
SECONDARY_BODIES = ("true_node", "chiron", "lilith_mean")
SUPPORT_VALUE = {"none": 0, "light": 1, "moderate": 2, "strong": 3}

BODY_LABELS = {
    "pt": {"sun": "Sol", "moon": "Lua", "mercury": "Mercúrio", "venus": "Vênus", "mars": "Marte", "jupiter": "Júpiter", "saturn": "Saturno", "uranus": "Urano", "neptune": "Netuno", "pluto": "Plutão", "true_node": "Nodo Norte", "chiron": "Quíron", "lilith_mean": "Lilith média"},
    "en": {},
}

THEME_POLES = {
    "pt": {
        "autonomy_closeness": ("autonomia", "proximidade"), "stability_change": ("estabilidade", "mudança"),
        "visibility_privacy": ("visibilidade", "privacidade"), "control_spontaneity": ("controle", "espontaneidade"),
        "security_exploration": ("segurança", "exploração"), "reason_feeling": ("razão", "sentimento"),
        "receptivity_initiative": ("receptividade", "iniciativa"), "individuality_belonging": ("individualidade", "pertencimento"),
    },
    "en": {
        "autonomy_closeness": ("autonomy", "closeness"), "stability_change": ("stability", "change"),
        "visibility_privacy": ("visibility", "privacy"), "control_spontaneity": ("control", "spontaneity"),
        "security_exploration": ("security", "exploration"), "reason_feeling": ("reason", "feeling"),
        "receptivity_initiative": ("receptivity", "initiative"), "individuality_belonging": ("individuality", "belonging"),
    },
}

ASPECTS = {"conjunction": 0.0, "sextile": 60.0, "square": 90.0, "trine": 120.0, "quincunx": 150.0, "opposition": 180.0}
DEFAULT_ORBS = {"conjunction": 8.0, "sextile": 5.0, "square": 6.0, "trine": 6.0, "quincunx": 3.0, "opposition": 8.0}
LUMINARY_ORB_BONUS = 1.0
ANGLE_ORB = 5.0
STATIONARY_SPEED_BY_BODY = {
    "sun": 0.01, "moon": 0.05, "mercury": 0.10, "venus": 0.05, "mars": 0.02,
    "jupiter": 0.01, "saturn": 0.005, "uranus": 0.002, "neptune": 0.001,
    "pluto": 0.001, "true_node": 0.001, "chiron": 0.002, "lilith_mean": 0.01,
}
CAZIMI_ORB = 0.28
COMBUST_ORB = 8.0
UNDER_BEAMS_ORB = 15.0
APPLYING_SAMPLE_MINUTES = 1.0
UNKNOWN_TIME_STABLE_BODY_SPAN = 1.0
HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES = 180.0
ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES = 30.0
SENSITIVITY_STRESS_TEST_MINUTES = (5.0, 15.0, 30.0)
SEMANTIC_SUPPORT_THRESHOLDS = {"light": 1, "moderate": 3, "strong": 6}

ELEMENT_BY_SIGN = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}
MODALITY_BY_SIGN = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}
POLARITY_BY_SIGN = {sign: ("active" if element in ("fire", "air") else "receptive") for sign, element in ELEMENT_BY_SIGN.items()}
CORE_ANGLES = ("asc", "dsc", "mc", "ic")

THEME_LABELS_PT = {
    "autonomy_closeness": "autonomia e proximidade", "stability_change": "estabilidade e mudança",
    "visibility_privacy": "visibilidade e privacidade", "control_spontaneity": "controle e espontaneidade",
    "security_exploration": "segurança e exploração", "reason_feeling": "razão e sentimento",
    "receptivity_initiative": "receptividade e iniciativa", "individuality_belonging": "individualidade e pertencimento",
    "purpose": "propósito", "creativity": "expressão criativa", "competence": "competência e estrutura",
    "care": "cuidado", "ambition": "ambição", "pleasure": "prazer", "transformation": "transformação",
    "power": "poder e agência", "service": "serviço", "spirituality": "significado e transcendência",
    "curiosity": "curiosidade", "order": "ordem",
}
