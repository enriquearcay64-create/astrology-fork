"""Safe projection between astronomical facts and interpretation/rendering.

The raw :class:`Chart` is the reproducible record.  It is deliberately not the
object handed to synthesis or report code: a house or angle that is conditional
under the declared time quality or a configured stress test cannot quietly
re-enter through a presentation helper.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List

from .models import AngleContact, Chart, Factor, HousePlacement


@dataclass(frozen=True)
class ConditionalHouseScenario:
    """A disclosed, non-central house reading at a timing boundary."""

    body: str
    primary_whole_sign_house: int
    primary_placidus_house: int | None
    reason: str
    stress_test_minutes: List[float]


@dataclass
class SafeInterpretiveChart:
    """Only facts licensed for interpretation plus explicit conditionals.

    ``house_placements`` contains stable placements only.  Conditional
    placements live in a separate disclosure-only field, which prevents the
    ordinary report and theme code from treating them as established topical
    evidence.
    """

    schema_version: str
    methodology_version: str
    backend: Dict[str, str]
    birth: object
    data_quality: object
    utc_datetime: str
    julian_day_ut: float
    positions: Dict[str, object]
    angles: Dict[str, float]
    house_cusps_placidus: List[float] | None
    placidus_available: bool
    aspects: List[object]
    house_placements: Dict[str, HousePlacement]
    conditional_house_scenarios: Dict[str, ConditionalHouseScenario]
    angle_contacts: List[AngleContact]
    factors: List[Factor]
    lots: Dict[str, float]
    policy: Dict[str, object]
    stability: Dict[str, object]
    warnings: List[str]

    def semantic_chart(self) -> Chart:
        """Return a filtered chart for existing deterministic claim tooling.

        This adapter is intentionally created here rather than in the report
        layer.  Its house factors and angle contacts are already gated.
        """
        return Chart(
            schema_version=self.schema_version,
            methodology_version=self.methodology_version,
            backend=self.backend,
            birth=self.birth,
            data_quality=self.data_quality,
            utc_datetime=self.utc_datetime,
            julian_day_ut=self.julian_day_ut,
            positions=self.positions,
            angles=self.angles,
            house_cusps_placidus=self.house_cusps_placidus,
            placidus_available=self.placidus_available,
            aspects=self.aspects,
            house_placements=self.house_placements,
            angle_contacts=self.angle_contacts,
            factors=self.factors,
            lots=self.lots,
            policy=self.policy,
            stability=self.stability,
            warnings=self.warnings,
        )


def build_safe_interpretive_view(chart: Chart) -> SafeInterpretiveChart:
    """Project raw facts through declared-quality and stress-test gates."""
    stability = dict(chart.stability)
    declared_unstable = set(stability.get("unstable_house_bodies", []))
    stress_conditional = set(stability.get("stress_conditional_house_bodies", []))
    allow_houses = bool(stability.get("allow_house_claims", True))
    conditional = declared_unstable | stress_conditional

    stable_houses = {
        body: placement
        for body, placement in chart.house_placements.items()
        if allow_houses and body not in conditional
    }
    stress_minutes = [
        float(item["minutes"])
        for item in stability.get("sensitivity_tests", [])
        if item.get("whole_sign_topology_changed") or body_in_test(item, conditional)
    ]
    scenarios = {
        body: ConditionalHouseScenario(
            body=body,
            primary_whole_sign_house=placement.whole_sign_house,
            primary_placidus_house=placement.placidus_house,
            reason=(
                "declared_birth_time_uncertainty"
                if body in declared_unstable
                else "sensitivity_stress_test_changes_whole_sign_topology"
            ),
            stress_test_minutes=stress_minutes,
        )
        for body, placement in chart.house_placements.items()
        if body in conditional or not allow_houses
    }

    allowed_house_ids = {f"house.whole_sign.{body}" for body in stable_houses}
    allowed_house_ids.update(f"house.placidus.{body}" for body, item in stable_houses.items() if item.placidus_house is not None)
    allowed_house_ids.update(f"house.robustness.{body}" for body in stable_houses)
    allow_angles = bool(stability.get("allow_angle_claims", True))
    unstable_contacts = set(stability.get("unstable_angle_contact_ids", []))
    safe_contacts = [
        contact for contact in chart.angle_contacts
        if allow_angles and f"angle.{contact.body}_{contact.angle}" not in unstable_contacts
    ]
    allowed_angle_ids = {f"angle.{contact.body}_{contact.angle}" for contact in safe_contacts}
    factors = [
        factor for factor in chart.factors
        if (
            factor.kind not in {"whole_sign_house", "placidus_house", "house_system_robustness", "angle_contact"}
            or factor.id in allowed_house_ids | allowed_angle_ids
        )
    ]
    # Lots depend on ASC and must not be available when the declared angle gate
    # excludes angular inference.
    lots = dict(chart.lots) if allow_angles else {}
    return SafeInterpretiveChart(
        schema_version=chart.schema_version,
        methodology_version=chart.methodology_version,
        backend=dict(chart.backend),
        birth=chart.birth,
        data_quality=chart.data_quality,
        utc_datetime=chart.utc_datetime,
        julian_day_ut=chart.julian_day_ut,
        positions=dict(chart.positions),
        angles=dict(chart.angles) if allow_angles else {},
        house_cusps_placidus=list(chart.house_cusps_placidus) if chart.house_cusps_placidus and allow_houses else None,
        placidus_available=chart.placidus_available and allow_houses,
        aspects=list(chart.aspects),
        house_placements=stable_houses,
        conditional_house_scenarios=scenarios,
        angle_contacts=safe_contacts,
        factors=factors,
        lots=lots,
        policy=dict(chart.policy),
        stability=stability,
        warnings=list(chart.warnings),
    )


def body_in_test(test: Dict[str, object], bodies: set[str]) -> bool:
    """Keep the conditional scenario calculation readable and total."""
    return bool(bodies.intersection(set(test.get("changed_whole_sign_bodies", []))))
