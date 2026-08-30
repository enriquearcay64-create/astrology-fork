"""Astronomical, house, angle and shared-zodiacal calculation.

No interpretation is generated here.  Every output is a reproducible fact or a
declared conventional classification.  Placidus house position uses
``swe.house_pos``; it is never derived by longitude interpolation.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from importlib import metadata
from pathlib import Path
import sysconfig
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Dict, Iterable, List, Optional, Tuple

import swisseph as swe

from .config import (
    ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES, ANGLE_ORB, APPLYING_SAMPLE_MINUTES, ASPECTS, BODY_CODES, CAZIMI_ORB, COMBUST_ORB, DEFAULT_ORBS,
    DETRIMENTS, EXALTATIONS, FALLS, LUMINARY_ORB_BONUS, METHODOLOGY_VERSION,
    EPHEMERIS_END_YEAR, EPHEMERIS_START_YEAR, HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES, PRIMARY_BODIES, SCHEMA_VERSION,
    SECONDARY_BODIES, SIGN_RULERS, SIGNS, STATIONARY_SPEED_BY_BODY,
    UNDER_BEAMS_ORB, UNKNOWN_TIME_STABLE_BODY_SPAN, SENSITIVITY_STRESS_TEST_MINUTES,
)
from .models import (
    AngleContact, Aspect, BirthData, Chart, DataQuality, Factor, HousePlacement,
    PlanetPosition,
)
from .policy import policy_manifest


# Keep ephemerides local to the skill.  Do not rely on a machine-global path or
# a remote service for birth data calculations.
def _resolve_ephemeris_path() -> Path:
    source_tree = Path(__file__).resolve().parents[1] / "assets" / "ephe"
    installed = Path(sysconfig.get_path("data")) / "share" / "codex-interpretar-mapa-astrologico" / "ephe"
    for candidate in (source_tree, installed):
        if all((candidate / name).exists() for name in ("sepl_18.se1", "semo_18.se1", "seas_18.se1")):
            return candidate
    raise RuntimeError("Bundled Swiss Ephemeris files are missing; reinstall the package or restore assets/ephe")


EPHEMERIS_PATH = _resolve_ephemeris_path()
swe.set_ephe_path(str(EPHEMERIS_PATH))


def normalize(value: float) -> float:
    return value % 360.0


def signed_delta(left: float, right: float) -> float:
    """Shortest signed difference left-right in [-180, 180)."""
    return (left - right + 180.0) % 360.0 - 180.0


def angular_distance(left: float, right: float) -> float:
    return abs(signed_delta(left, right))


def sign_for(longitude: float) -> Tuple[str, float]:
    index = int(normalize(longitude) // 30.0)
    return SIGNS[index], normalize(longitude) % 30.0


def _resolve_datetime(birth: BirthData) -> Tuple[datetime, DataQuality]:
    try:
        naive = datetime.fromisoformat(birth.local_datetime)
    except ValueError as error:
        raise ValueError("local_datetime must be ISO-8601, e.g. 1990-07-12T14:30:00") from error
    if naive.tzinfo is not None:
        raise ValueError("local_datetime must be a local wall time without an offset; provide timezone_name separately")
    warnings: List[str] = []
    sensitivity: List[str] = []
    if not birth.birth_time_known:
        naive = naive.replace(hour=12, minute=0, second=0, microsecond=0)
        warnings.append("Birth time is unknown; 12:00 local is only a date-level proxy for planetary positions. Houses, angles, sect and Lots are disabled.")
        sensitivity.append("The Moon and fast planets can vary across the unknown-time date; no angle or house inference is allowed.")
    if not -90.0 <= birth.latitude <= 90.0 or not -180.0 <= birth.longitude <= 180.0:
        raise ValueError("latitude must be [-90, 90] and longitude [-180, 180]")
    if birth.calendar != "gregorian":
        raise ValueError("Only the proleptic Gregorian input calendar is supported")
    if birth.utc_offset_override_minutes is not None:
        offset = birth.utc_offset_override_minutes
        if not -14 * 60 <= offset <= 14 * 60:
            raise ValueError("utc_offset_override_minutes must be between -840 and 840")
        aware = naive.replace(tzinfo=timezone.utc).astimezone(timezone.utc) - timedelta(minutes=offset)
        warnings.append("UTC offset override used; IANA historical timezone resolution was bypassed.")
        return aware, DataQuality("utc_offset_override", offset, warnings, sensitivity)
    try:
        zone = ZoneInfo(birth.timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError("timezone_name must be a valid IANA name, e.g. America/Sao_Paulo") from error
    if birth.dst_fold not in (None, 0, 1):
        raise ValueError("dst_fold must be 0, 1 or null")
    fold0 = naive.replace(tzinfo=zone, fold=0)
    fold1 = naive.replace(tzinfo=zone, fold=1)
    roundtrip0 = fold0.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    roundtrip1 = fold1.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
    if roundtrip0 != naive and roundtrip1 != naive:
        raise ValueError("local_datetime falls in a non-existent local time during a DST transition; provide the corrected local time or an explicit UTC offset.")
    if fold0.utcoffset() != fold1.utcoffset():
        if birth.dst_fold is None:
            raise ValueError("local_datetime is ambiguous during a daylight-saving transition; provide dst_fold=0 or dst_fold=1 explicitly")
        warnings.append(f"Ambiguous local time resolved with the user-declared dst_fold={birth.dst_fold}.")
        sensitivity.append("The alternate DST fold can materially change houses, angles and timing.")
    aware = fold1 if birth.dst_fold == 1 else fold0
    utc = aware.astimezone(timezone.utc)
    offset_minutes = int(aware.utcoffset().total_seconds() // 60)
    if naive.year < 1970:
        warnings.append("Pre-1970 IANA historical timezone data may be less complete than modern data.")
    if birth.time_uncertainty_minutes is not None:
        sensitivity.append("The declared birth-time uncertainty can materially affect angles and Placidus houses.")
    return utc, DataQuality("iana_zoneinfo", offset_minutes, warnings, sensitivity)


def _julian_day(utc: datetime) -> float:
    seconds = utc.second + utc.microsecond / 1_000_000.0
    _jdet, jdut = swe.utc_to_jd(utc.year, utc.month, utc.day, utc.hour, utc.minute, seconds, swe.GREG_CAL)
    return jdut


def _body_positions(jd_ut: float, include_secondary: bool = True) -> Dict[str, PlanetPosition]:
    body_keys: Iterable[str] = PRIMARY_BODIES + (SECONDARY_BODIES if include_secondary else ())
    output: Dict[str, PlanetPosition] = {}
    flags = swe.FLG_SWIEPH | swe.FLG_SPEED
    for key in body_keys:
        label, code_name = BODY_CODES[key]
        xx, returned_flags = swe.calc_ut(jd_ut, getattr(swe, code_name), flags)
        if not returned_flags & swe.FLG_SWIEPH:
            raise RuntimeError(f"Swiss Ephemeris file backend was not used for {key}; refusing a silent fallback")
        sign, degree = sign_for(xx[0])
        output[key] = PlanetPosition(
            key=key, label=label, longitude=normalize(xx[0]), latitude=xx[1], distance_au=xx[2],
            speed_longitude=xx[3], sign=sign, degree_in_sign=degree,
            retrograde=xx[3] < 0.0, stationary=abs(xx[3]) <= STATIONARY_SPEED_BY_BODY[key],
        )
    return output


def _placidus_houses(jd_ut: float, latitude: float, longitude: float) -> Tuple[Optional[List[float]], Optional[Tuple[float, ...]], List[str]]:
    try:
        cusps, ascmc = swe.houses_ex(jd_ut, latitude, longitude, b"P", swe.FLG_SWIEPH)
        return list(cusps), tuple(ascmc), []
    except swe.Error as error:
        return None, None, [f"Placidus unavailable for this latitude/time: {error}. Whole Sign remains available; no silent fallback was applied."]


def _whole_sign_house(longitude: float, ascendant: float) -> int:
    asc_sign_start = int(normalize(ascendant) // 30.0) * 30.0
    return int(normalize(longitude - asc_sign_start) // 30.0) + 1


def _placidus_position(jd_ut: float, position: PlanetPosition, latitude: float, armc: float) -> Optional[float]:
    try:
        ecl_nut, _flags = swe.calc_ut(jd_ut, swe.ECL_NUT, swe.FLG_SWIEPH)
        obliquity = ecl_nut[0]
        return swe.house_pos(armc, latitude, obliquity, (position.longitude, position.latitude), b"P")
    except swe.Error:
        return None


def _cusp_proximity(longitude: float, house_position: Optional[float], cusps: List[float]) -> Dict[str, float]:
    ranked = sorted(((index + 1, angular_distance(longitude, cusp)) for index, cusp in enumerate(cusps)), key=lambda item: item[1])
    house, distance = ranked[0]
    result = {"nearest_zodiacal_cusp_house": float(house), "zodiacal_longitude_distance_degrees": round(distance, 4)}
    if house_position is not None:
        base_house = int(house_position)
        fraction = house_position - base_house
        nearest = base_house if fraction <= 0.5 else base_house % 12 + 1
        result.update({
            "nearest_spatial_cusp_house": float(nearest),
            "house_position_distance_degrees_equivalent": round(min(fraction, 1.0 - fraction) * 30.0, 4),
            "distance_degrees": round(min(fraction, 1.0 - fraction) * 30.0, 4),
        })
    else:
        result["distance_degrees"] = round(distance, 4)
    return result


def _aspects(positions: Dict[str, PlanetPosition]) -> List[Aspect]:
    keys = list(positions)
    result: List[Aspect] = []
    for left_index, left in enumerate(keys):
        for right in keys[left_index + 1:]:
            separation = angular_distance(positions[left].longitude, positions[right].longitude)
            for kind, angle in ASPECTS.items():
                orb_limit = DEFAULT_ORBS[kind] + (LUMINARY_ORB_BONUS if left in ("sun", "moon") or right in ("sun", "moon") else 0.0)
                orb = abs(separation - angle)
                if orb <= orb_limit:
                    sample_days = APPLYING_SAMPLE_MINUTES / 1440.0
                    now_delta = signed_delta(positions[left].longitude, positions[right].longitude)
                    next_delta = signed_delta(
                        positions[left].longitude + positions[left].speed_longitude * sample_days,
                        positions[right].longitude + positions[right].speed_longitude * sample_days,
                    )
                    applying = None if orb <= 1e-7 else abs(abs(next_delta) - angle) < abs(abs(now_delta) - angle)
                    result.append(Aspect(
                        id=f"aspect.{left}_{kind}_{right}", left=left, right=right, kind=kind,
                        angle=angle, separation=round(separation, 6), orb=round(orb, 6), applying=applying,
                    ))
                    break
    return sorted(result, key=lambda item: (item.orb, item.id))


def _conditions(positions: Dict[str, PlanetPosition], jd_ut: float, latitude: float, longitude: float, include_sect: bool = True) -> List[Factor]:
    factors: List[Factor] = []
    sun = positions["sun"]
    if include_sect:
        # Day/night uses local true solar altitude, not zodiacal house order.
        _azimuth, true_altitude, _apparent_altitude = swe.azalt(jd_ut, swe.ECL2HOR, (longitude, latitude, 0.0), 0.0, 0.0, (sun.longitude, sun.latitude, sun.distance_au))
        factors.append(Factor("condition.sect", "condition", "sect", ["sun"], {"sect": "day" if true_altitude >= 0 else "night", "sun_true_altitude": round(true_altitude, 6)}))
    for key, position in positions.items():
        condition: List[str] = []
        if SIGN_RULERS[position.sign] == key:
            condition.append("domicile")
        if EXALTATIONS.get(position.sign) == key:
            condition.append("exaltation")
        if DETRIMENTS.get(position.sign) == key:
            condition.append("detriment")
        if FALLS.get(position.sign) == key:
            condition.append("fall")
        if position.retrograde:
            condition.append("retrograde")
        if position.stationary:
            condition.append("stationary")
        # Solar conditions belong to the traditional seven-planet stream. Applying
        # them to trans-Saturnian bodies silently mixes incompatible conventions.
        if key in ("mercury", "venus", "mars", "jupiter", "saturn"):
            solar_distance = angular_distance(position.longitude, sun.longitude)
            if solar_distance <= CAZIMI_ORB:
                condition.append("cazimi")
            elif solar_distance <= COMBUST_ORB:
                condition.append("combust")
            elif solar_distance <= UNDER_BEAMS_ORB:
                condition.append("under_beams")
        if condition:
            factors.append(Factor(f"condition.{key}", "condition", "planetary_condition", [key], {"conditions": condition}))
    return factors


def _dispositors(positions: Dict[str, PlanetPosition]) -> List[Factor]:
    factors: List[Factor] = []
    graph = {key: SIGN_RULERS[position.sign] for key, position in positions.items() if position.sign in SIGN_RULERS}
    for key, ruler in graph.items():
        factors.append(Factor(f"dispositor.{key}", "shared_zodiacal", "dispositor", [key, ruler], {"ruler": ruler}))
    discovered: Dict[Tuple[str, ...], Dict[str, object]] = {}
    for start in graph:
        chain: List[str] = []
        current = start
        while current in graph and current not in chain and len(chain) < 14:
            chain.append(current)
            current = graph[current]
        if current in chain:
            cycle = chain[chain.index(current):]
            rotations = [tuple(cycle[index:] + cycle[:index]) for index in range(len(cycle))]
            canonical = min(rotations)
            kind = "final_dispositor" if len(cycle) == 1 else "dispositor_cycle"
            record = discovered.setdefault(canonical, {"kind": kind, "reachable_from": [], "example_chain": chain})
            record["reachable_from"].append(start)
    for cycle, record in sorted(discovered.items()):
        kind = str(record["kind"])
        factors.append(Factor(
            f"{kind}.{'_'.join(cycle)}", "shared_zodiacal", kind, list(cycle),
            {"cycle": list(cycle), "reachable_from": sorted(record["reachable_from"]), "example_chain": record["example_chain"]},
        ))
    seen = set()
    for left, right in graph.items():
        if left != right and graph.get(right) == left:
            key = tuple(sorted((left, right)))
            if key not in seen:
                seen.add(key)
                factors.append(Factor(f"reception.mutual_{left}_{right}", "shared_zodiacal", "mutual_reception", list(key), {}))
    return factors


def _lots(ascendant: float, positions: Dict[str, PlanetPosition], sect: str) -> Dict[str, float]:
    sun = positions["sun"].longitude
    moon = positions["moon"].longitude
    if sect == "day":
        fortune = normalize(ascendant + moon - sun)
        spirit = normalize(ascendant + sun - moon)
    else:
        fortune = normalize(ascendant + sun - moon)
        spirit = normalize(ascendant + moon - sun)
    return {"fortune": fortune, "spirit": spirit}


def _angle_contacts(positions: Dict[str, PlanetPosition], angles: Dict[str, float]) -> List[AngleContact]:
    output: List[AngleContact] = []
    for body, position in positions.items():
        for angle_name, angle_longitude in angles.items():
            distance = angular_distance(position.longitude, angle_longitude)
            if distance <= ANGLE_ORB:
                output.append(AngleContact(body, angle_name, round(distance, 6), "conjunction", ANGLE_ORB))
    return sorted(output, key=lambda item: item.distance)


def _house_integration_state(whole: int, placidus: Optional[int], cusp_proximity: Optional[Dict[str, float]]) -> Tuple[str, str]:
    """Keep a legacy technical comparison record without natal semantics."""
    if placidus is None:
        return "placidus_unavailable", "Canonical Placidus natal placement is unavailable; Whole Sign is retained only for techniques that require it."
    cusp_distance = float((cusp_proximity or {}).get("distance_degrees", 99.0))
    if placidus == whole:
        if cusp_distance <= 3.0:
            return "whole_topic_placidus_qualifier", "Technical comparison only: the systems share a number and the Placidus placement is near a cusp."
        return "robust_same_house", "Technical comparison only: the systems share a number; this is not a second natal evidence vote."
    circular_gap = min((placidus - whole) % 12, (whole - placidus) % 12)
    if circular_gap == 1 or cusp_distance <= 3.0:
        return "whole_topic_placidus_qualifier", "Technical comparison only: Whole Sign and Placidus differ by one house or a Placidus cusp is near."
    complementary_axes = {frozenset(pair) for pair in ((1, 7), (2, 8), (3, 9), (4, 10), (5, 11), (6, 12))}
    if frozenset((whole, placidus)) in complementary_axes:
        return "complementary_emphases", "Technical comparison only: the systems fall on an opposite-house pair; do not merge them as natal evidence."
    return "material_divergence", "Technical comparison only: the systems differ materially; canonical natal interpretation remains Placidus."


def _tzdata_version() -> str:
    try:
        return metadata.version("tzdata")
    except metadata.PackageNotFoundError:
        return "system-zoneinfo-unpinned"


def _placidus_house_ruler_factors(cusps: Optional[List[float]]) -> List[Factor]:
    """Record Placidus cusp-sign rulership as factual routing only."""
    if not cusps:
        return []
    factors: List[Factor] = []
    for house, cusp in enumerate(cusps, 1):
        sign, degree = sign_for(cusp)
        ruler = SIGN_RULERS[sign]
        factors.append(Factor(
            f"house_ruler.placidus.{house}", "placidus_house_ruler", "placidus_house_ruler", [ruler],
            {
                "house": house,
                "house_system": "placidus",
                "cusp_longitude": round(normalize(cusp), 6),
                "cusp_sign": sign,
                "cusp_degree_in_sign": round(degree, 6),
                "ruler": ruler,
                "ruler_position_id": f"position.{ruler}",
                "rulership_system": "traditional_configured",
                "cusp_sign_reliable": False,
                "available_for_house_ruler_claim": False,
            },
        ))
    return factors


def _cusp_sign_unstable_houses(chart: Chart, variants: Iterable[Chart]) -> List[int]:
    """Compare only declared-time endpoint cusp signs, never body placements."""
    if not chart.house_cusps_placidus:
        return list(range(1, 13))
    endpoint_cusps = [item.house_cusps_placidus for item in variants]
    unstable = []
    for house, cusp in enumerate(chart.house_cusps_placidus, 1):
        base_sign = sign_for(cusp)[0]
        if any(not endpoint or len(endpoint) < house or sign_for(endpoint[house - 1])[0] != base_sign for endpoint in endpoint_cusps):
            unstable.append(house)
    return unstable


def _set_house_ruler_reliability(chart: Chart) -> None:
    """Annotate raw routing facts; SafeInterpretiveChart enforces usability."""
    unstable = set(chart.stability.get("unstable_placidus_house_ruler_houses", []))
    cusp_signs_available = bool(chart.house_cusps_placidus)
    allowed = cusp_signs_available and bool(chart.stability.get("allow_house_claims", True))
    for factor in chart.factors:
        if factor.kind == "placidus_house_ruler":
            house = int(factor.data["house"])
            factor.data["cusp_sign_reliable"] = cusp_signs_available and house not in unstable
            factor.data["available_for_house_ruler_claim"] = allowed and house not in unstable


def calculate_chart(birth: BirthData, include_secondary: bool = True, _run_sensitivity_tests: bool = True) -> Chart:
    """Calculate the canonical chart with Whole Sign, Placidus and angles.

    This function is intentionally deterministic for a given backend, tzdata and
    methodology version.  It does not geocode, persist personal data or infer
    cultural context.
    """
    utc, quality = _resolve_datetime(birth)
    if not EPHEMERIS_START_YEAR <= utc.year <= EPHEMERIS_END_YEAR:
        raise ValueError("The bundled Swiss Ephemeris files cover 1800–2399 CE. Install the matching sepl/semo/seas files before calculating outside this range; no lower-precision fallback is used silently.")
    jd_ut = _julian_day(utc)
    positions = _body_positions(jd_ut, include_secondary)
    if birth.birth_time_known:
        cusps, ascmc, warnings = _placidus_houses(jd_ut, birth.latitude, birth.longitude)
    else:
        cusps, ascmc, warnings = None, None, ["Houses and angles were not calculated because birth_time_known=false."]
    if ascmc is None and birth.birth_time_known:
        # Angles remain astronomical points even if Placidus domification fails.
        _whole_cusps, fallback_ascmc = swe.houses_ex(jd_ut, birth.latitude, birth.longitude, b"W", swe.FLG_SWIEPH)
        ascmc = tuple(fallback_ascmc)
    if ascmc is not None:
        ascendant, midheaven, armc, vertex = ascmc[0], ascmc[1], ascmc[2], ascmc[3]
        angles = {"asc": normalize(ascendant), "dsc": normalize(ascendant + 180.0), "mc": normalize(midheaven), "ic": normalize(midheaven + 180.0), "vertex": normalize(vertex), "antivertex": normalize(vertex + 180.0)}
    else:
        armc, angles = 0.0, {}
    placements: Dict[str, HousePlacement] = {}
    for key, position in positions.items() if angles else []:
        whole = _whole_sign_house(position.longitude, angles["asc"])
        hpos = _placidus_position(jd_ut, position, birth.latitude, armc) if cusps else None
        placidus_house = int(hpos) if hpos is not None else None
        cusp_proximity = _cusp_proximity(position.longitude, hpos, cusps) if cusps else None
        integration_state, rationale = _house_integration_state(whole, placidus_house, cusp_proximity)
        robustness = "unavailable" if placidus_house is None else ("robust" if placidus_house == whole else "divergent")
        placements[key] = HousePlacement(
            key, whole, placidus_house, round(hpos, 6) if hpos is not None else None,
            robustness, cusp_proximity, integration_state, rationale,
        )
    aspects = _aspects(positions)
    factors = _conditions(positions, jd_ut, birth.latitude, birth.longitude, birth.birth_time_known) + _dispositors(positions)
    # Canonical position ledger entries allow structural configurations to be
    # traceable without inventing pseudo-evidence ids later.
    factors.extend(
        Factor(
            f"position.{key}", "shared_zodiacal", "position", [key],
            {"longitude": position.longitude, "sign": position.sign, "degree_in_sign": position.degree_in_sign},
        )
        for key, position in positions.items()
    )
    factors.extend(_placidus_house_ruler_factors(cusps))
    if angles:
        asc_sign, asc_degree = sign_for(angles["asc"])
        factors.extend([
            Factor("ascendant.natal", "angular", "ascendant", ["asc"], {
                "longitude": angles["asc"], "sign": asc_sign, "degree_in_sign": asc_degree,
            }),
            Factor("chart_ruler.natal", "angular", "chart_ruler", [SIGN_RULERS[asc_sign]], {
                "ascendant_sign": asc_sign, "ruler": SIGN_RULERS[asc_sign],
            }),
        ])
    sect_factor = next((item for item in factors if item.id == "condition.sect"), None)
    lots = _lots(angles["asc"], positions, sect_factor.data["sect"]) if sect_factor and angles else {}
    for lot, longitude in lots.items():
        sign, degree = sign_for(longitude)
        factors.append(Factor(f"lot.{lot}", "lot", "lot_position", [lot], {"longitude": longitude, "sign": sign, "degree_in_sign": degree, "whole_sign_house": _whole_sign_house(longitude, angles["asc"])}))
    for aspect in aspects:
        factors.append(Factor(aspect.id, "shared_zodiacal", "aspect", [aspect.left, aspect.right], {"kind": aspect.kind, "orb": aspect.orb, "applying": aspect.applying}))
    angle_contacts = _angle_contacts(positions, angles)
    for contact in angle_contacts:
        factors.append(Factor(f"angle.{contact.body}_{contact.angle}", "angular", "angle_contact", [contact.body, contact.angle], {"distance": contact.distance, "orb": contact.orb}))
    for key, placement in placements.items():
        factors.append(Factor(f"house.whole_sign.{key}", "whole_sign", "whole_sign_house", [key], {"house": placement.whole_sign_house}))
        if placement.placidus_house is not None:
            factors.append(Factor(f"house.placidus.{key}", "placidus", "placidus_house", [key], {"house": placement.placidus_house, "position": placement.placidus_position, "cusp_proximity": placement.cusp_proximity}))
        factors.append(Factor(
            f"house.robustness.{key}", "house_synthesis", "house_system_robustness", [key],
            {"state": placement.integration_state, "legacy_state": placement.house_system_robustness,
             "whole_sign_house": placement.whole_sign_house, "placidus_house": placement.placidus_house,
             "rationale": placement.integration_rationale},
        ))
    node = positions.get("true_node")
    if node:
        south_longitude = normalize(node.longitude + 180.0)
        south_sign, south_degree = sign_for(south_longitude)
        south_position = PlanetPosition(
            "south_node", "South Node", south_longitude, -node.latitude,
            node.distance_au, node.speed_longitude, south_sign, south_degree,
            node.retrograde, node.stationary,
        )
        south_hpos = _placidus_position(jd_ut, south_position, birth.latitude, armc) if cusps else None
        node_contacts = [aspect.id for aspect in aspects if "true_node" in (aspect.left, aspect.right)]
        factors.append(Factor(
            "node_axis.natal", "node_axis", "natal_node_axis", ["true_node"],
            {
                "north": {"longitude": node.longitude, "sign": node.sign, "degree_in_sign": node.degree_in_sign,
                          "placidus_house": placements.get("true_node").placidus_house if "true_node" in placements else None},
                "south": {"longitude": south_longitude, "sign": south_sign, "degree_in_sign": south_degree,
                          "placidus_house": int(south_hpos) if south_hpos is not None else None},
                # An aspect to the North Node is already an aspect to this one
                # geometric axis.  It is listed once, never mirrored as a
                # second South-Node vote.
                "contact_ids": node_contacts,
                "placidus_house_reliable": bool(cusps and birth.birth_time_known),
            },
        ))
    chart = Chart(
        schema_version=SCHEMA_VERSION,
        methodology_version=METHODOLOGY_VERSION,
        backend={"name": "pyswisseph", "version": swe.version, "license": "AGPL-3.0-or-later or commercial license required", "tzdata": _tzdata_version()},
        birth=birth, data_quality=quality, utc_datetime=utc.isoformat(), julian_day_ut=jd_ut,
        positions=positions, angles=angles, house_cusps_placidus=cusps, placidus_available=cusps is not None and birth.birth_time_known,
        aspects=aspects, house_placements=placements, angle_contacts=angle_contacts, factors=factors,
        lots=lots, policy=policy_manifest(), stability={}, warnings=warnings,
    )
    # Configuration records are deterministic facts with stable ids.  Keeping
    # them in the factor ledger lets the provenance guard verify a structural
    # proposition itself, rather than trusting a prose reference to its members.
    from .structure import detect_configurations
    for configuration in detect_configurations(chart):
        chart.factors.append(Factor(
            str(configuration["id"]), "structure", "configuration",
            list(configuration["bodies"]), dict(configuration),
        ))
    if not birth.birth_time_known:
        _apply_unknown_time_stability(chart, birth, include_secondary)
    elif birth.time_uncertainty_minutes and birth.time_uncertainty_minutes > 0:
        _apply_time_uncertainty(chart, birth, include_secondary)
    else:
        chart.stability.update({
            "birth_time_mode": "known_exact",
            "declared_quality": "exact",
            "declared_uncertainty_minutes": 0.0,
            "unstable_house_bodies": [],
            "unstable_placidus_house_bodies": [],
            "unstable_placidus_house_ruler_houses": [],
            "unstable_whole_sign_house_bodies": [],
            "node_axis_placidus_house_reliable": bool(cusps),
            "unstable_angle_contact_ids": [],
            "allow_house_claims": True,
            "allow_angle_claims": True,
        })
    if birth.birth_time_known and _run_sensitivity_tests:
        _apply_sensitivity_stress_tests(chart, birth, include_secondary)
    _set_house_ruler_reliability(chart)
    return chart


def _planetary_variant(birth: BirthData, local_datetime: str, include_secondary: bool) -> Tuple[Dict[str, PlanetPosition], List[Aspect]]:
    variant = replace(
        birth,
        local_datetime=local_datetime,
        birth_time_known=True,
        time_uncertainty_minutes=None,
        dst_fold=None,
    )
    utc, _quality = _resolve_datetime(variant)
    positions = _body_positions(_julian_day(utc), include_secondary)
    return positions, _aspects(positions)


def _apply_unknown_time_stability(chart: Chart, birth: BirthData, include_secondary: bool) -> None:
    """Keep only date-level facts that survive both ends of the unknown-time day."""
    day = datetime.fromisoformat(birth.local_datetime).date()
    early_positions, early_aspects = _planetary_variant(birth, f"{day.isoformat()}T00:01:00", include_secondary)
    late_positions, late_aspects = _planetary_variant(birth, f"{day.isoformat()}T23:59:00", include_secondary)
    stable_aspects = {item.id for item in early_aspects} & {item.id for item in late_aspects}
    unstable_aspects = sorted(item.id for item in chart.aspects if item.id not in stable_aspects)
    body_spans = {
        body: round(angular_distance(early_positions[body].longitude, late_positions[body].longitude), 4)
        for body in chart.positions
    }
    unstable_bodies = sorted(body for body, span in body_spans.items() if span > UNKNOWN_TIME_STABLE_BODY_SPAN)
    chart.stability.update({
        "birth_time_mode": "unknown_date_proxy",
        "declared_quality": "unknown",
        "declared_uncertainty_minutes": None,
        "endpoint_policy": "local_00:01_and_23:59_intersection",
        "unstable_aspect_ids": unstable_aspects,
        "body_span_degrees": body_spans,
        "timing_excluded_natal_bodies": unstable_bodies,
        "unstable_placidus_house_bodies": sorted(chart.house_placements),
        "unstable_placidus_house_ruler_houses": list(range(1, 13)),
        "unstable_whole_sign_house_bodies": sorted(chart.house_placements),
        "node_axis_placidus_house_reliable": False,
        "allow_house_claims": False,
        "allow_angle_claims": False,
    })
    if unstable_aspects:
        chart.data_quality.input_sensitivity.append(
            f"{len(unstable_aspects)} natal aspects were withheld because they do not persist across the unknown-time date."
        )


def _apply_time_uncertainty(chart: Chart, birth: BirthData, include_secondary: bool) -> None:
    """Quantify material house/angle sensitivity without changing the base chart."""
    minutes = float(birth.time_uncertainty_minutes or 0)
    if minutes > 720:
        chart.data_quality.warnings.append("Reported time uncertainty exceeds 12 hours; only sign-level factors should be treated as stable.")
    base = datetime.fromisoformat(birth.local_datetime)
    variants = []
    for delta in (-minutes, minutes):
        variant = BirthData(
            local_datetime=(base + timedelta(minutes=delta)).isoformat(), timezone_name=birth.timezone_name,
            latitude=birth.latitude, longitude=birth.longitude, place_label=birth.place_label,
            utc_offset_override_minutes=birth.utc_offset_override_minutes, calendar=birth.calendar, source=birth.source,
            dst_fold=birth.dst_fold,
            birth_time_known=birth.birth_time_known,
        )
        variants.append(calculate_chart(variant, include_secondary, _run_sensitivity_tests=False))
    asc_change = max(angular_distance(chart.angles["asc"], item.angles["asc"]) for item in variants)
    changed_whole = sorted({body for body in chart.house_placements if any(chart.house_placements[body].whole_sign_house != item.house_placements[body].whole_sign_house for item in variants)})
    changed_placidus = sorted({body for body in chart.house_placements if any(chart.house_placements[body].placidus_house != item.house_placements[body].placidus_house for item in variants)})
    unstable_house_ruler_houses = _cusp_sign_unstable_houses(chart, variants)
    node_axis_factor = next((factor for factor in chart.factors if factor.id == "node_axis.natal"), None)
    variant_node_axes = [next((factor for factor in item.factors if factor.id == "node_axis.natal"), None) for item in variants]
    node_axis_houses_stable = bool(node_axis_factor and all(
        item is not None
        and item.data["north"].get("placidus_house") == node_axis_factor.data["north"].get("placidus_house")
        and item.data["south"].get("placidus_house") == node_axis_factor.data["south"].get("placidus_house")
        for item in variant_node_axes
    ))
    chart.data_quality.input_sensitivity.append(f"±{minutes:g} minutes changes ASC by up to {asc_change:.2f}°.")
    if changed_whole:
        chart.data_quality.input_sensitivity.append("Whole Sign house assignment changes for: " + ", ".join(changed_whole) + ".")
    if changed_placidus:
        chart.data_quality.input_sensitivity.append("Placidus house assignment changes for: " + ", ".join(changed_placidus) + ".")
    variant_contact_sets = [
        {f"angle.{item.body}_{item.angle}" for item in variant.angle_contacts if item.angle in ("asc", "dsc", "mc", "ic")}
        for variant in variants
    ]
    base_contacts = {f"angle.{item.body}_{item.angle}" for item in chart.angle_contacts if item.angle in ("asc", "dsc", "mc", "ic")}
    stable_contacts = set.intersection(*variant_contact_sets) if variant_contact_sets else set()
    chart.stability.update({
        "birth_time_mode": "known_with_uncertainty",
        "uncertainty_minutes": minutes,
        "declared_quality": "approximate",
        "declared_uncertainty_minutes": minutes,
        # Placidus is the natal psychological house system.  Whole Sign
        # instability belongs to technique-specific logic and must not suppress
        # a stable Placidus natal placement.
        "unstable_house_bodies": changed_placidus,
        "unstable_placidus_house_bodies": changed_placidus,
        "unstable_placidus_house_ruler_houses": unstable_house_ruler_houses,
        "unstable_whole_sign_house_bodies": changed_whole,
        "node_axis_placidus_house_reliable": node_axis_houses_stable and minutes <= HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES,
        "unstable_angle_contact_ids": sorted(base_contacts - stable_contacts),
        "allow_house_claims": minutes <= HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES,
        "allow_angle_claims": minutes <= ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES,
    })
    if minutes > HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES:
        chart.data_quality.input_sensitivity.append("House claims were withheld because declared uncertainty exceeds the configured house gate.")
    if minutes > ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES:
        chart.data_quality.input_sensitivity.append("Angle-contact claims were withheld because declared uncertainty exceeds the configured angular gate.")


def _apply_sensitivity_stress_tests(chart: Chart, birth: BirthData, include_secondary: bool) -> None:
    """Record counterfactual timing sensitivity without redefining declared data.

    Stress tests are not claims that the birth time is uncertain. They reveal
    boundary sensitivity and must not silently overwrite the declared quality.
    """
    base = datetime.fromisoformat(birth.local_datetime)
    requested = tuple(float(value) for value in (birth.sensitivity_test_minutes or SENSITIVITY_STRESS_TEST_MINUTES))
    tests = []
    sensitive_bodies = set()
    base_asc_sign = int(chart.angles["asc"] // 30) if chart.angles else None
    for minutes in sorted(set(requested)):
        variants = []
        for delta in (-minutes, minutes):
            variant = replace(
                birth,
                local_datetime=(base + timedelta(minutes=delta)).isoformat(),
                time_uncertainty_minutes=None,
            )
            variants.append(calculate_chart(variant, include_secondary, _run_sensitivity_tests=False))
        asc_signs = [int(item.angles["asc"] // 30) for item in variants if item.angles]
        changed_whole = sorted({
            body for body in chart.house_placements
            if any(chart.house_placements[body].whole_sign_house != item.house_placements[body].whole_sign_house for item in variants)
        })
        changed_placidus = sorted({
            body for body in chart.house_placements
            if any(chart.house_placements[body].placidus_house != item.house_placements[body].placidus_house for item in variants)
        })
        changed_cusp_signs = _cusp_sign_unstable_houses(chart, variants)
        topology_changed = bool(base_asc_sign is not None and any(sign != base_asc_sign for sign in asc_signs))
        if topology_changed:
            sensitive_bodies.update(changed_whole or chart.house_placements.keys())
        tests.append({
            "minutes": minutes,
            "whole_sign_topology_changed": topology_changed,
            "changed_whole_sign_bodies": changed_whole,
            "changed_placidus_bodies": changed_placidus,
            "changed_placidus_cusp_sign_houses": changed_cusp_signs,
            "variant_ascendants": [round(item.angles["asc"], 6) for item in variants if item.angles],
        })
    chart.stability["sensitivity_tests"] = tests
    chart.stability["stress_sensitive_house_bodies"] = sorted(sensitive_bodies)
    declared_whole_conditional = bool(chart.stability.get("unstable_whole_sign_house_bodies")) or not chart.stability.get("allow_house_claims", True)
    chart.stability["whole_sign_topology_status"] = "conditional" if declared_whole_conditional else "stable"
    chart.stability["high_boundary_sensitivity"] = bool(sensitive_bodies)
    if sensitive_bodies:
        nearest = min(test["minutes"] for test in tests if test["whole_sign_topology_changed"])
        chart.data_quality.input_sensitivity.append(
            f"Sensitivity stress test: a ±{nearest:g}-minute counterfactual crosses the Ascendant sign boundary; disclose high boundary sensitivity. This does not replace the declared time quality."
        )
