"""Whole-chart structure and named configuration detection."""
from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Dict, List, Optional

from .config import CORE_STRUCTURE_BODIES, ELEMENT_BY_SIGN, MODALITY_BY_SIGN, POLARITY_BY_SIGN, PRIMARY_BODIES
from .models import Aspect, Chart


def _aspect_lookup(chart: Chart) -> Dict[frozenset, Aspect]:
    return {frozenset((aspect.left, aspect.right)): aspect for aspect in chart.aspects}


def _kind(lookup: Dict[frozenset, Aspect], left: str, right: str) -> Optional[str]:
    aspect = lookup.get(frozenset((left, right)))
    return aspect.kind if aspect else None


def detect_configurations(chart: Chart) -> List[Dict[str, object]]:
    bodies = [body for body in PRIMARY_BODIES if body in chart.positions]
    lookup = _aspect_lookup(chart)
    found: List[Dict[str, object]] = []
    seen = set()
    for trio in combinations(bodies, 3):
        kinds = [_kind(lookup, *pair) for pair in combinations(trio, 2)]
        if kinds.count("trine") == 3:
            found.append({"kind": "grand_trine", "bodies": list(trio), "evidence": [lookup[frozenset(pair)].id for pair in combinations(trio, 2)]})
        if kinds.count("opposition") == 1 and kinds.count("square") == 2:
            found.append({"kind": "t_square", "bodies": list(trio), "evidence": [lookup[frozenset(pair)].id for pair in combinations(trio, 2)]})
        for apex in trio:
            base = [body for body in trio if body != apex]
            if _kind(lookup, apex, base[0]) == _kind(lookup, apex, base[1]) == "quincunx" and _kind(lookup, base[0], base[1]) == "sextile":
                found.append({"kind": "yod", "bodies": [*base, apex], "apex": apex, "evidence": [lookup[frozenset((apex, base[0]))].id, lookup[frozenset((apex, base[1]))].id, lookup[frozenset(base)].id]})
    for quartet in combinations(bodies, 4):
        pairs = list(combinations(quartet, 2))
        kinds = [_kind(lookup, *pair) for pair in pairs]
        if kinds.count("opposition") == 2 and kinds.count("square") == 4:
            key = ("grand_cross", tuple(quartet))
            if key not in seen:
                seen.add(key)
                found.append({"kind": "grand_cross", "bodies": list(quartet), "evidence": [lookup[frozenset(pair)].id for pair in pairs]})
        if kinds.count("opposition") == 2 and kinds.count("trine") == 2 and kinds.count("sextile") == 2:
            found.append({"kind": "mystic_rectangle", "bodies": list(quartet), "evidence": [lookup[frozenset(pair)].id for pair in pairs]})
        for grand_trine in combinations(quartet, 3):
            fourth = next(body for body in quartet if body not in grand_trine)
            if all(_kind(lookup, *pair) == "trine" for pair in combinations(grand_trine, 2)):
                opposed = [body for body in grand_trine if _kind(lookup, fourth, body) == "opposition"]
                if len(opposed) == 1 and all(_kind(lookup, fourth, body) == "sextile" for body in grand_trine if body not in opposed):
                    found.append({"kind": "kite", "bodies": list(grand_trine) + [fourth], "apex": fourth, "evidence": [lookup[frozenset(pair)].id for pair in pairs]})
    # Stellia are declared separately from aspect figures. Sign clusters describe
    # zodiacal concentration; Whole Sign clusters describe topical concentration.
    for sign, members in _clusters(chart, bodies, "sign").items():
        if len(members) >= 3:
            found.append({"kind": "stellium_sign", "basis": sign, "bodies": members, "evidence": [f"position.{body}" for body in members]})
    for house, members in _clusters(chart, bodies, "house").items():
        if len(members) >= 3:
            found.append({"kind": "stellium_whole_sign_house", "basis": str(house), "bodies": members, "evidence": [f"house.whole_sign.{body}" for body in members]})

    grand_crosses = [set(item["bodies"]) for item in found if item["kind"] == "grand_cross"]
    kites = [set(item["bodies"]) for item in found if item["kind"] == "kite"]
    absorbed = []
    unique = set()
    for item in found:
        bodies = set(item["bodies"])
        if item["kind"] == "t_square" and any(bodies < cross for cross in grand_crosses):
            continue
        if item["kind"] == "grand_trine" and any(bodies < kite for kite in kites):
            continue
        key = (item["kind"], tuple(sorted(item["bodies"])), item.get("apex"))
        if key not in unique:
            unique.add(key)
            absorbed.append(item)
    return absorbed


def _clusters(chart: Chart, bodies: List[str], basis: str) -> Dict[object, List[str]]:
    output: Dict[object, List[str]] = {}
    for body in bodies:
        if basis == "sign":
            key: object = chart.positions[body].sign
        elif body in chart.house_placements:
            key = chart.house_placements[body].whole_sign_house
        else:
            continue
        output.setdefault(key, []).append(body)
    return output


def chart_structure(chart: Chart) -> Dict[str, object]:
    bodies = [body for body in PRIMARY_BODIES if body in chart.positions]
    core_bodies = [body for body in CORE_STRUCTURE_BODIES if body in chart.positions]
    elements = Counter(ELEMENT_BY_SIGN[chart.positions[body].sign] for body in core_bodies)
    modalities = Counter(MODALITY_BY_SIGN[chart.positions[body].sign] for body in core_bodies)
    polarities = Counter(POLARITY_BY_SIGN[chart.positions[body].sign] for body in core_bodies)
    all_elements = Counter(ELEMENT_BY_SIGN[chart.positions[body].sign] for body in bodies)
    all_modalities = Counter(MODALITY_BY_SIGN[chart.positions[body].sign] for body in bodies)
    all_polarities = Counter(POLARITY_BY_SIGN[chart.positions[body].sign] for body in bodies)
    signs = Counter(chart.positions[body].sign for body in bodies)
    houses = Counter(chart.house_placements[body].whole_sign_house for body in bodies if body in chart.house_placements)
    placidus_houses = [chart.house_placements[body].placidus_house for body in bodies if body in chart.house_placements and chart.house_placements[body].placidus_house]
    quadrants = Counter(f"q{((house - 1) // 3) + 1}" for house in placidus_houses)
    spatial = {
        "above_horizon": sum(house >= 7 for house in placidus_houses), "below_horizon": sum(house <= 6 for house in placidus_houses),
        "eastern": sum(house in (10, 11, 12, 1, 2, 3) for house in placidus_houses),
        "western": sum(house in (4, 5, 6, 7, 8, 9) for house in placidus_houses),
        "quadrants": dict(quadrants), "basis": "Placidus house position; omitted when birth time or Placidus is unavailable",
    } if placidus_houses else None
    return {
        "elements": dict(elements), "modalities": dict(modalities), "polarities": dict(polarities),
        "core_elements": dict(elements), "core_modalities": dict(modalities), "core_polarities": dict(polarities),
        "all_primary_elements": dict(all_elements), "all_primary_modalities": dict(all_modalities), "all_primary_polarities": dict(all_polarities),
        "balance_basis": "Sun through Saturn; outer planets remain visible in all_primary_* without determining compensation",
        "sign_concentrations": {sign: count for sign, count in signs.items() if count >= 3},
        "whole_sign_house_concentrations": {str(house): count for house, count in houses.items() if count >= 3},
        "spatial_distribution": spatial,
        "configurations": detect_configurations(chart),
    }
