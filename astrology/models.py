"""Typed, serialisable objects for the deterministic astrology core.

The objects deliberately keep astronomical facts, astrological inferences, and
user-reported manifestations in different fields.  Do not merge those layers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def to_primitive(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_primitive(item) for item in value]
    return value


@dataclass(frozen=True)
class BirthData:
    local_datetime: str
    timezone_name: str
    latitude: float
    longitude: float
    place_label: Optional[str] = None
    utc_offset_override_minutes: Optional[int] = None
    time_uncertainty_minutes: Optional[float] = None
    calendar: str = "gregorian"
    source: str = "user_provided"
    dst_fold: Optional[int] = None
    birth_time_known: bool = True
    sensitivity_test_minutes: Tuple[float, ...] = (5.0, 15.0, 30.0)

    def __post_init__(self) -> None:
        if not isinstance(self.birth_time_known, bool):
            raise ValueError("birth_time_known must be boolean")
        if self.time_uncertainty_minutes is not None and self.time_uncertainty_minutes < 0:
            raise ValueError("time_uncertainty_minutes cannot be negative")
        if not self.sensitivity_test_minutes or any(minutes <= 0 for minutes in self.sensitivity_test_minutes):
            raise ValueError("sensitivity_test_minutes must contain positive minute values")


@dataclass(frozen=True)
class LocalizationProfile:
    preferred_language: str = "pt-BR"
    current_country: Optional[str] = None
    cultural_context: Optional[str] = None
    region: Optional[str] = None
    source: str = "user_provided"
    localization_level: str = "light"

    def __post_init__(self) -> None:
        if not (self.preferred_language.startswith("pt") or self.preferred_language.startswith("en")):
            raise ValueError("preferred_language must be Portuguese or English")
        if self.localization_level not in {"off", "light"}:
            raise ValueError("localization_level must be off or light")


@dataclass
class DataQuality:
    timezone_resolution: str
    offset_minutes: int
    warnings: List[str] = field(default_factory=list)
    input_sensitivity: List[str] = field(default_factory=list)


@dataclass
class PlanetPosition:
    key: str
    label: str
    longitude: float
    latitude: float
    distance_au: float
    speed_longitude: float
    sign: str
    degree_in_sign: float
    retrograde: bool
    stationary: bool


@dataclass
class Aspect:
    id: str
    left: str
    right: str
    kind: str
    angle: float
    separation: float
    orb: float
    applying: Optional[bool]


@dataclass
class HousePlacement:
    body: str
    whole_sign_house: int
    placidus_house: Optional[int]
    placidus_position: Optional[float]
    house_system_robustness: str
    cusp_proximity: Optional[Dict[str, float]] = None
    integration_state: str = "unavailable"
    integration_rationale: str = ""


@dataclass
class AngleContact:
    body: str
    angle: str
    distance: float
    contact: str
    orb: float


@dataclass
class Factor:
    id: str
    family: str
    kind: str
    bodies: List[str]
    data: Dict[str, Any]
    methodology_stream: str = "shared"


@dataclass
class Claim:
    id: str
    theme: str
    type: str
    statement: str
    evidence: List[str]
    evidence_families: List[str]
    counterweights: List[str]
    allowed_specificity: str
    allowed_examples: List[str]
    prohibited_inferences: List[str]
    astrological_support: str
    manifestation_feedback: str = "unknown"
    status: str = "allowed"
    authorized_motifs: List[str] = field(default_factory=list)
    verification_errors: List[str] = field(default_factory=list)
    counterweight_types: Dict[str, str] = field(default_factory=dict)


@dataclass
class ReasonedSynthesis:
    """LLM-authored, evidence-bounded interpretation unit.

    Unlike a registry claim, this may express an emergent combination of
    factors.  Its evidence chain remains machine-verifiable.
    """

    id: str
    observation: str
    primary_factors: List[str]
    modifiers: List[str]
    counterweights: List[str]
    reasoning_class: str
    confidence_within_astrological_model: str
    possible_expressions: List[str]
    alternative_reading: str
    prohibited_extensions: List[str]
    narrative_moves: Dict[str, str] = field(default_factory=dict)
    derived_claim: bool = True
    verification_errors: List[str] = field(default_factory=list)
    status: str = "pending"


@dataclass
class Chart:
    schema_version: str
    methodology_version: str
    backend: Dict[str, str]
    birth: BirthData
    data_quality: DataQuality
    utc_datetime: str
    julian_day_ut: float
    positions: Dict[str, PlanetPosition]
    angles: Dict[str, float]
    house_cusps_placidus: Optional[List[float]]
    placidus_available: bool
    aspects: List[Aspect]
    house_placements: Dict[str, HousePlacement]
    angle_contacts: List[AngleContact]
    factors: List[Factor]
    lots: Dict[str, float]
    policy: Dict[str, Any] = field(default_factory=dict)
    stability: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return to_primitive(self)
