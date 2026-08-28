"""Dynamic hierarchy with separate prominence, condition, friction and relevance."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List

from .config import CORE_ANGLES, PRIMARY_BODIES, SIGN_RULERS
from .engine import sign_for
from .models import Chart
from .structure import detect_configurations


def ordinal(value: int) -> str:
    return "none" if value <= 0 else "light" if value == 1 else "moderate" if value == 2 else "strong"


def calculate_hierarchy(chart: Chart, question_topics: Iterable[int] = (), active_bodies: Iterable[str] = ()) -> Dict[str, Dict[str, object]]:
    """Keep natal prominence invariant while allowing separate contextual relevance."""
    selected = set(question_topics)
    active = set(active_bodies)
    output: Dict[str, Dict[str, object]] = {}
    aspect_count = defaultdict(int)
    configurations = detect_configurations(chart)
    configuration_members = {body for item in configurations for body in item["bodies"]}
    configuration_focals = {str(item["apex"]) for item in configurations if item.get("apex")}
    for aspect in chart.aspects:
        # Technical-only secondary points cannot inflate the natal hierarchy.
        if aspect.left in PRIMARY_BODIES and aspect.right in PRIMARY_BODIES:
            aspect_count[aspect.left] += 1
            aspect_count[aspect.right] += 1
    conditions = {factor.bodies[0]: factor.data.get("conditions", []) for factor in chart.factors if factor.kind == "planetary_condition"}
    # An exact Ascendant is still a valid angle when a *stress test* crosses a
    # sign boundary.  Its Whole Sign topology is not.  Do not quietly recreate
    # unsafe houses/rulers from the angle inside the hierarchy layer.
    topology_is_safe = (
        bool(chart.angles)
        and chart.stability.get("whole_sign_topology_status", "stable") != "conditional"
        and chart.stability.get("allow_house_claims", True)
    )
    if topology_is_safe:
        asc_start = int(chart.angles["asc"] // 30) * 30
        whole_signs = {house: sign_for(asc_start + (house - 1) * 30)[0] for house in range(1, 13)}
        house_rulers = {house: SIGN_RULERS[sign] for house, sign in whole_signs.items()}
        asc_ruler = house_rulers[1]
    else:
        house_rulers, asc_ruler = {}, None
    # The MC sign itself is an independently calculated angle, not a Whole
    # Sign-house claim.  It remains available when the MC stability gate allows
    # it; its ruler must not restore an unsafe Ascendant topology.
    mc_ruler = SIGN_RULERS[sign_for(chart.angles["mc"])[0]] if chart.angles and chart.stability.get("allow_angle_claims", True) else None
    core_angular_bodies = {contact.body for contact in chart.angle_contacts if contact.angle in CORE_ANGLES}
    uncertain_time = bool(chart.birth.time_uncertainty_minutes and chart.birth.time_uncertainty_minutes >= 10)
    for body in chart.positions:
        roles: List[str] = []
        prominence = 0
        resources = 0
        frictions = 0
        topical = 0
        reliability = 3
        if body in ("sun", "moon"):
            roles.append("luminary")
            prominence += 1
        governed = [house for house, ruler in house_rulers.items() if ruler == body]
        if body == asc_ruler:
            roles.append("asc_ruler")
            prominence += 2
        if body == mc_ruler:
            roles.append("mc_ruler")
            prominence += 1
        if body in core_angular_bodies:
            roles.append("core_angle_contact")
            prominence += 2
        if body in configuration_members:
            roles.append("named_configuration_member")
        if body in configuration_focals:
            roles.append("configuration_focal")
            prominence += 1
        if aspect_count[body] >= 2:
            prominence += 1
        exact_aspects = [aspect for aspect in chart.aspects if body in (aspect.left, aspect.right) and aspect.left in PRIMARY_BODIES and aspect.right in PRIMARY_BODIES and aspect.orb <= 1.5]
        if exact_aspects:
            roles.append("exact_aspect")
            prominence += 1
        if len(governed) >= 2:
            roles.append("multiple_house_rulership")
        if any(factor.kind == "final_dispositor" and body in factor.bodies for factor in chart.factors):
            roles.append("final_dispositor")
            prominence += 1
        if any(factor.kind == "mutual_reception" and body in factor.bodies for factor in chart.factors):
            roles.append("mutual_reception")
            resources += 1
        if body in active:
            roles.append("timing_activated")
            topical += 1
        if selected and any(house in selected for house in governed):
            roles.append("query_topic_ruler")
            topical += 2
        elif governed:
            topical += 1
        planet_conditions = conditions.get(body, [])
        resources += int("domicile" in planet_conditions) + int("exaltation" in planet_conditions) + int("cazimi" in planet_conditions)
        frictions += int("detriment" in planet_conditions) + int("fall" in planet_conditions)
        # Outer-planet retrogradation is common and remains a technical condition,
        # but it does not inflate the interpretive friction score.
        frictions += int(body in ("mercury", "venus", "mars", "jupiter", "saturn") and "retrograde" in planet_conditions)
        frictions += int("combust" in planet_conditions) + int("under_beams" in planet_conditions)
        if "stationary" in planet_conditions:
            roles.append("stationary")
            prominence += 1
        if uncertain_time and (body in core_angular_bodies or body in (asc_ruler, mc_ruler)):
            reliability = 1
        elif not chart.placidus_available and body in core_angular_bodies:
            reliability = 2
        output[body] = {
            "roles": roles,
            "governs_whole_sign_houses": governed,
            "prominence": ordinal(prominence),
            "condition_resources": ordinal(resources),
            "condition_frictions": ordinal(frictions),
            "topical_relevance": ordinal(topical),
            "evidence_reliability": ordinal(reliability),
            "aspect_centrality": ordinal(aspect_count[body] // 2),
            "conditions": planet_conditions,
        }
    return output
