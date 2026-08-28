"""Versioned timing streams.  They describe symbolic activation windows, never events."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import swisseph as swe

from .config import ASPECTS, BODY_CODES, EPHEMERIS_END_YEAR, EPHEMERIS_START_YEAR, SIGN_RULERS
from .engine import EPHEMERIS_PATH, angular_distance, normalize, sign_for, signed_delta
from .models import Chart

TIMING_VERSION = "3.0.0"
MAJOR_TRANSIT_BODIES = ("jupiter", "saturn", "uranus", "neptune", "pluto", "true_node")
ACTIVATION_INSTANCE_MAX_GAP_DAYS = 540
swe.set_ephe_path(str(EPHEMERIS_PATH))


def _aware_utc(value: datetime, field: str = "datetime") -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field} must include a UTC offset")
    return value.astimezone(timezone.utc)


def _ensure_jd_range(jd: float) -> None:
    year = swe.revjul(jd, swe.GREG_CAL)[0]
    if not EPHEMERIS_START_YEAR <= year <= EPHEMERIS_END_YEAR:
        raise ValueError(f"Timing date is outside the bundled ephemeris range {EPHEMERIS_START_YEAR}–{EPHEMERIS_END_YEAR}")


def _jd_for_datetime(value: datetime) -> float:
    value = _aware_utc(value)
    _jdet, jdut = swe.utc_to_jd(value.year, value.month, value.day, value.hour, value.minute, value.second + value.microsecond / 1_000_000.0, swe.GREG_CAL)
    return jdut


def _datetime_for_jd(jd: float) -> str:
    year, month, day, hour_float = swe.revjul(jd, swe.GREG_CAL)
    instant = datetime(year, month, day, tzinfo=timezone.utc) + timedelta(hours=hour_float)
    return instant.replace(microsecond=0).isoformat()


def _longitude(jd_ut: float, body: str) -> float:
    _ensure_jd_range(jd_ut)
    _label, code_name = BODY_CODES[body]
    xx, flags = swe.calc_ut(jd_ut, getattr(swe, code_name), swe.FLG_SWIEPH | swe.FLG_SPEED)
    if not flags & swe.FLG_SWIEPH:
        raise RuntimeError(f"Swiss Ephemeris file backend was not used for timing body {body}")
    return normalize(xx[0])


def _deviation(transit_longitude: float, target_longitude: float, angle: float) -> float:
    return abs(angular_distance(transit_longitude, target_longitude) - angle)


def _aspect_branch(transit_longitude: float, target_longitude: float, aspect: str) -> str:
    """Distinguish the two geometric branches of non-symmetric aspects."""
    if aspect in ("conjunction", "opposition"):
        return "direct"
    angle = ASPECTS[aspect]
    delta = signed_delta(transit_longitude, target_longitude)
    return "positive" if abs(delta - angle) <= abs(delta + angle) else "negative"


def group_activation_instances(events: List[Dict[str, object]], maximum_gap_days: int = ACTIVATION_INSTANCE_MAX_GAP_DAYS) -> List[Dict[str, object]]:
    """Group retrograde passes, never recurring activations years apart.

    A semantic family describes a kind of contact.  An activation instance is a
    particular temporal episode.  Keeping both lets later narrative code refer
    to continuity without presenting 2026 and 2030 as one window.
    """
    buckets: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for event in events:
        branch = str(event.get("aspect_branch", "direct"))
        key = "_".join((str(event["transit_body"]), str(event["target"]), str(event["aspect"]), branch))
        buckets[key].append(event)
    grouped: List[Dict[str, object]] = []
    for key, members in sorted(buckets.items()):
        current: List[Dict[str, object]] = []
        ordinal = 0
        for event in sorted(members, key=lambda item: str(item["exact_at"])):
            instant = datetime.fromisoformat(str(event["exact_at"]))
            if current and (instant - datetime.fromisoformat(str(current[-1]["exact_at"]))).days > maximum_gap_days:
                grouped.append(_activation_group(key, ordinal, current))
                ordinal += 1
                current = []
            current.append(event)
        if current:
            grouped.append(_activation_group(key, ordinal, current))
    return sorted(grouped, key=lambda item: (str(item["window_start"]), str(item["activation_instance"])))


def _activation_group(key: str, ordinal: int, passes: List[Dict[str, object]]) -> Dict[str, object]:
    representative = min(passes, key=lambda item: float(item["orb_at_minimum"]))
    semantic_family = "transit_{}_{}_{}".format(representative["transit_body"], representative["aspect"], representative["target"])
    activation_instance = f"{key}_branch_{ordinal + 1}"
    return {
        **representative,
        "id": f"activation.{activation_instance}",
        "semantic_family": semantic_family,
        "evidence_family": semantic_family,  # compatible alias; not a timing window key
        "activation_instance": activation_instance,
        "passes": passes,
        "window_start": passes[0]["exact_at"],
        "window_end": passes[-1]["exact_at"],
        "window_priority": max(int(item["priority"]) for item in passes),
    }


def _refine_minimum(body: str, target: float, angle: float, left: float, right: float) -> Tuple[float, float]:
    """Ternary refinement around a sampled local minimum; deterministic, no event claim."""
    for _ in range(24):
        a = left + (right - left) / 3.0
        b = right - (right - left) / 3.0
        if _deviation(_longitude(a, body), target, angle) <= _deviation(_longitude(b, body), target, angle):
            right = b
        else:
            left = a
    jd = (left + right) / 2.0
    return jd, _deviation(_longitude(jd, body), target, angle)


def major_transits(chart: Chart, as_of: Optional[datetime] = None, horizon_days: int = 366, orb_limit: float = 1.0) -> List[Dict[str, object]]:
    """Find exact-ish major transit windows by sampling then refining local minima."""
    if horizon_days < 1:
        raise ValueError("horizon_days must be positive")
    as_of = _aware_utc(as_of or datetime.now(timezone.utc), "as_of")
    start = _jd_for_datetime(as_of)
    _ensure_jd_range(start + horizon_days + 2)
    excluded_targets = {"chiron", "lilith_mean"} | set(chart.stability.get("timing_excluded_natal_bodies", []))
    target_points = {key: item.longitude for key, item in chart.positions.items() if key not in excluded_targets}
    target_points.update({key: value for key, value in chart.angles.items() if key in ("asc", "mc", "dsc", "ic")})
    days = list(range(-1, horizon_days + 2))
    sampled = {body: [_longitude(start + day, body) for day in days] for body in MAJOR_TRANSIT_BODIES}
    events: List[Dict[str, object]] = []
    seen = set()
    for body in MAJOR_TRANSIT_BODIES:
        for target_name, target_longitude in target_points.items():
            for aspect_name, angle in ASPECTS.items():
                if body == "true_node" and not (target_name == "true_node" and aspect_name in ("conjunction", "opposition")):
                    continue
                deviations = [_deviation(longitude, target_longitude, angle) for longitude in sampled[body]]
                for index in range(1, len(days) - 1):
                    if deviations[index] <= deviations[index - 1] and deviations[index] <= deviations[index + 1] and deviations[index] <= orb_limit:
                        jd, deviation = _refine_minimum(body, target_longitude, angle, start + days[index - 1], start + days[index + 1])
                        if deviation > orb_limit:
                            continue
                        day_key = (body, target_name, aspect_name, round(jd, 1))
                        if day_key in seen:
                            continue
                        seen.add(day_key)
                        derived_label = None
                        if body == target_name and aspect_name == "conjunction":
                            derived_label = {"saturn": "Saturn Return", "jupiter": "Jupiter Return", "true_node": "Nodal Return"}.get(body, body.title() + " Return")
                        elif body == target_name and aspect_name == "opposition" and body == "uranus":
                            derived_label = "Uranus Opposition"
                        transit_longitude = _longitude(jd, body)
                        events.append({
                            "id": f"transit.{body}_{aspect_name}_{target_name}.{round(jd, 4)}", "stream": "modern_transits",
                            "transit_body": body, "target": target_name, "aspect": aspect_name, "exact_at": _datetime_for_jd(jd),
                            "aspect_branch": _aspect_branch(transit_longitude, target_longitude, aspect_name),
                            "orb_at_minimum": round(deviation, 4), "derived_event_label": derived_label,
                            "evidence_family": f"transit_{body}_{aspect_name}_{target_name}",
                            "priority": (4 if derived_label else 3 if target_name in ("asc", "mc", "sun", "moon") else 2) + (1 if deviation <= 0.25 else 0),
                            "interpretation_limit": "symbolic activation window; not a prediction of a concrete event",
                        })
    return group_activation_instances(events)


def annual_profection(chart: Chart, as_of: Optional[date] = None) -> Dict[str, object]:
    """Traditional stream: Whole Sign annual profection only."""
    if not chart.angles:
        return {"stream": "traditional_profections", "status": "unavailable", "house": None, "sign": None, "time_lord": None, "interpretation_limit": "Annual profection requires a known birth time and Ascendant."}
    if chart.stability.get("whole_sign_topology_status") == "conditional" or not chart.stability.get("allow_house_claims", True):
        return {
            "stream": "traditional_profections", "status": "conditional", "house": None, "sign": None, "time_lord": None,
            "interpretation_limit": "Annual profection is withheld because the Whole Sign topology changes in the birth-time sensitivity test.",
        }
    birth_local = datetime.fromisoformat(chart.birth.local_datetime).date()
    as_of = as_of or datetime.now(timezone.utc).date()
    age = as_of.year - birth_local.year - ((as_of.month, as_of.day) < (birth_local.month, birth_local.day))
    if age < 0:
        raise ValueError("as_of cannot precede the birth date for annual profection")
    house = age % 12 + 1
    asc_start = int(chart.angles["asc"] // 30) * 30
    sign, _degree = sign_for(asc_start + (house - 1) * 30)
    lord = SIGN_RULERS[sign]
    try:
        start = birth_local.replace(year=birth_local.year + age)
    except ValueError:  # Feb 29
        start = birth_local.replace(year=birth_local.year + age, day=28)
    try:
        end = birth_local.replace(year=birth_local.year + age + 1)
    except ValueError:
        end = birth_local.replace(year=birth_local.year + age + 1, day=28)
    return {
        "stream": "traditional_profections", "age": age, "house": house, "sign": sign, "time_lord": lord,
        "start": start.isoformat(), "end": end.isoformat(),
        "interpretation_limit": "Traditional contextualisation; it does not veto an independently important modern transit.",
    }


def current_progressions(chart: Chart, as_of: Optional[datetime] = None) -> Dict[str, object]:
    """Secondary progression snapshot using one ephemeris day per life year."""
    as_of = _aware_utc(as_of or datetime.now(timezone.utc), "as_of")
    birth_utc = datetime.fromisoformat(chart.utc_datetime).astimezone(timezone.utc)
    age_years = (as_of - birth_utc).total_seconds() / (365.2425 * 86400.0)
    if age_years < 0:
        raise ValueError("as_of cannot precede birth for secondary progressions")
    progressed_jd = chart.julian_day_ut + age_years
    excluded = set(chart.stability.get("timing_excluded_natal_bodies", []))
    positions = {body: round(_longitude(progressed_jd, body), 6) for body in ("sun", "moon", "mercury", "venus", "mars") if body not in excluded}
    contacts = _directed_contacts(positions, chart, 1.0, "progressed")
    return {"stream": "modern_progressions", "as_of": as_of.isoformat(), "age_years": round(age_years, 5), "progressed_jd_ut": progressed_jd, "positions": positions, "contacts": contacts, "interpretation_limit": "Secondary progression contacts are symbolic timing indicators, not event predictions."}


def current_solar_arc(chart: Chart, as_of: Optional[datetime] = None, progressions: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    progressions = progressions or current_progressions(chart, as_of)
    arc = normalize(progressions["positions"]["sun"] - chart.positions["sun"].longitude)
    excluded = set(chart.stability.get("timing_excluded_natal_bodies", []))
    directed = {body: round(normalize(position.longitude + arc), 6) for body, position in chart.positions.items() if body in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn") and body not in excluded}
    return {"stream": "modern_solar_arcs", "as_of": progressions["as_of"], "solar_arc_degrees": round(arc, 6), "directed_positions": directed, "contacts": _directed_contacts(directed, chart, 1.0, "solar_arc"), "interpretation_limit": "Solar arcs are a separate modern stream and are not extra votes for the same event."}


def _directed_contacts(positions: Dict[str, float], chart: Chart, orb_limit: float, family_prefix: str) -> List[Dict[str, object]]:
    excluded = {"chiron", "lilith_mean", "true_node"} | set(chart.stability.get("timing_excluded_natal_bodies", []))
    targets = {body: position.longitude for body, position in chart.positions.items() if body not in excluded}
    targets.update({name: value for name, value in chart.angles.items() if name in ("asc", "mc")})
    contacts: List[Dict[str, object]] = []
    for body, longitude in positions.items():
        for target, natal_longitude in targets.items():
            if body == target:
                continue
            for aspect, angle in ASPECTS.items():
                orb = _deviation(longitude, natal_longitude, angle)
                if orb <= orb_limit:
                    contacts.append({"body": body, "target": target, "aspect": aspect, "orb": round(orb, 4), "evidence_family": f"{family_prefix}_{body}_{aspect}_{target}"})
                    break
    return sorted(contacts, key=lambda item: (item["orb"], item["body"], item["target"]))


def solar_return(chart: Chart, year: int, location_policy: str = "birth_place", location: Optional[Tuple[float, float]] = None) -> Dict[str, object]:
    """Compute the exact-ish return instant; houses require an explicit location policy."""
    target = chart.positions["sun"].longitude
    if location_policy not in {"birth_place", "habitual_residence", "actual_physical_location"}:
        raise ValueError("invalid solar return location policy")
    if location is not None and (not -90 <= location[0] <= 90 or not -180 <= location[1] <= 180):
        raise ValueError("solar return location coordinates are out of range")
    birth_utc = datetime.fromisoformat(chart.utc_datetime).astimezone(timezone.utc)
    nominal = datetime(year, birth_utc.month, min(birth_utc.day, 28 if birth_utc.month == 2 else birth_utc.day), birth_utc.hour, birth_utc.minute, tzinfo=timezone.utc)
    center = _jd_for_datetime(nominal)
    left, right = center - 2.0, center + 2.0
    for _ in range(35):
        a = left + (right - left) / 3.0
        b = right - (right - left) / 3.0
        if angular_distance(_longitude(a, "sun"), target) <= angular_distance(_longitude(b, "sun"), target):
            right = b
        else:
            left = a
    jd = (left + right) / 2.0
    result: Dict[str, object] = {
        "stream": "solar_return", "year": year, "exact_return_utc": _datetime_for_jd(jd),
        "location_policy": location_policy, "location_known": bool(location),
        "interpretive_module_status": "technical_support_available",
        "interpretation_limit": "The return instant is available as technical support. A full Solar Return interpretation is not claimed until natal-return hierarchy, rulers, angularity and contacts are synthesised.",
    }
    if location is not None:
        latitude, longitude = location
        try:
            cusps, ascmc = swe.houses_ex(jd, latitude, longitude, b"P", swe.FLG_SWIEPH)
            result["angles"] = {"asc": normalize(ascmc[0]), "mc": normalize(ascmc[1])}
            result["placidus_cusps"] = list(cusps)
        except swe.Error as error:
            result["warning"] = f"Placidus unavailable for declared return location: {error}"
    return result


def upcoming_eclipses(as_of: Optional[datetime] = None, count: int = 4) -> List[Dict[str, object]]:
    """Astronomical eclipse dates; no personal claim is attached without chart contact analysis."""
    if count < 0 or count > 20:
        raise ValueError("eclipse count must be between 0 and 20")
    jd = _jd_for_datetime(_aware_utc(as_of or datetime.now(timezone.utc), "as_of"))
    events: List[Dict[str, object]] = []
    while len(events) < count:
        flags, times = swe.sol_eclipse_when_glob(jd, swe.FLG_SWIEPH, 0, False)
        events.append({"kind": "solar_eclipse", "maximum_utc": _datetime_for_jd(times[0]), "flags": flags, "interpretation_limit": "Astronomical event only; personal relevance requires separately documented contacts."})
        jd = times[0] + 1.0
        if len(events) >= count:
            break
        flags, times = swe.lun_eclipse_when(jd, swe.FLG_SWIEPH, 0, False)
        events.append({"kind": "lunar_eclipse", "maximum_utc": _datetime_for_jd(times[0]), "flags": flags, "interpretation_limit": "Astronomical event only; personal relevance requires separately documented contacts."})
        jd = times[0] + 1.0
    return sorted(events, key=lambda item: item["maximum_utc"])[:count]


def _cycle_occurrences(chart: Chart, body: str, aspect_name: str, age_start: float, age_end: float, orb_limit: float = 0.7) -> List[Dict[str, object]]:
    """Search an age interval for actual orbital contacts, not a canonical-age label."""
    target = chart.positions[body].longitude
    angle = ASPECTS[aspect_name]
    start_jd = chart.julian_day_ut + age_start * 365.2425
    end_jd = chart.julian_day_ut + age_end * 365.2425
    days = range(-1, int(end_jd - start_jd) + 2)
    values = [_deviation(_longitude(start_jd + day, body), target, angle) for day in days]
    result: List[Dict[str, object]] = []
    for index in range(1, len(values) - 1):
        if values[index] <= values[index - 1] and values[index] <= values[index + 1] and values[index] <= orb_limit:
            jd, deviation = _refine_minimum(body, target, angle, start_jd + days[index - 1], start_jd + days[index + 1])
            result.append({"body": body, "aspect": aspect_name, "exact_at": _datetime_for_jd(jd), "orb_at_minimum": round(deviation, 4)})
    return result


def _group_cycle_passes(events: List[Dict[str, object]], maximum_gap_days: int = ACTIVATION_INSTANCE_MAX_GAP_DAYS) -> List[Dict[str, object]]:
    groups: List[List[Dict[str, object]]] = []
    for event in sorted(events, key=lambda item: item["exact_at"]):
        instant = datetime.fromisoformat(str(event["exact_at"]))
        if not groups or (instant - datetime.fromisoformat(str(groups[-1][-1]["exact_at"]))).days > maximum_gap_days:
            groups.append([event])
        else:
            groups[-1].append(event)
    output = []
    for passes in groups:
        representative = min(passes, key=lambda item: item["orb_at_minimum"])
        output.append({
            **representative,
            "passes": passes,
            "window_start": passes[0]["exact_at"],
            "window_end": passes[-1]["exact_at"],
            "semantic_family": f"cycle_{representative['body']}_{representative['aspect']}",
            "activation_instance": f"cycle_{representative['body']}_{representative['aspect']}_{len(output) + 1}",
            "evidence_family": f"cycle_{representative['body']}_{representative['aspect']}",
        })
    return output


def life_timeline(chart: Chart, max_age: int = 70) -> List[Dict[str, object]]:
    """Narrative age containers populated only with actually calculated cycles."""
    if not 1 <= max_age <= 120:
        raise ValueError("max_age must be between 1 and 120")
    ephemeris_end_jd = _jd_for_datetime(datetime(EPHEMERIS_END_YEAR, 12, 31, 0, 0, tzinfo=timezone.utc))
    supported_age = max(0, int((ephemeris_end_jd - chart.julian_day_ut) / 365.2425))
    effective_max_age = min(max_age, supported_age)
    containers = [(start, min(start + 9, effective_max_age)) for start in range(0, effective_max_age + 1, 10)]
    if not containers:
        return []
    calculated_cycles: List[Dict[str, object]] = []
    for body, aspect in (
        ("jupiter", "conjunction"),
        ("saturn", "square"), ("saturn", "opposition"), ("saturn", "conjunction"),
        ("true_node", "opposition"), ("true_node", "conjunction"),
        ("uranus", "square"), ("uranus", "opposition"),
        ("chiron", "conjunction"),
    ):
        # The natal contact is the baseline, not a developmental return.
        if effective_max_age >= 1:
            calculated_cycles.extend(_group_cycle_passes(_cycle_occurrences(chart, body, aspect, 1.0, effective_max_age)))
    output: List[Dict[str, object]] = []
    for start_age, end_age in containers:
        phase_start = chart.julian_day_ut + start_age * 365.2425
        phase_end = chart.julian_day_ut + (end_age + 1) * 365.2425
        activations = [cycle for cycle in calculated_cycles if phase_start <= _jd_for_datetime(datetime.fromisoformat(cycle["exact_at"])) < phase_end]
        output.append({
            "range": f"{start_age}–{end_age}", "activations": activations,
            "dominant_themes": sorted({cycle["body"] for cycle in activations}),
            "note": ("Timeline truncated at the bundled ephemeris boundary; " if effective_max_age < max_age else "") + "Containers remain empty unless a configured orbital cycle was calculated; absence of an item is not interpreted.",
        })
    return output


def developmental_intervals(chart: Chart, timeline: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Turn calculated activation instances into emergent life intervals.

    Decades remain a navigation index.  The interpretive unit is an interval of
    actual activations, never an empty age bucket or a canonical-age slogan.
    """
    events = [item for phase in timeline for item in phase.get("activations", [])]
    groups: List[List[Dict[str, object]]] = []
    for item in sorted(events, key=lambda value: str(value["window_start"])):
        start = datetime.fromisoformat(str(item["window_start"]))
        if groups and (start - datetime.fromisoformat(str(groups[-1][-1]["window_end"]))).days <= 1461:
            groups[-1].append(item)
        else:
            groups.append([item])
    birth = datetime.fromisoformat(chart.utc_datetime)
    result = []
    for index, group in enumerate(groups, 1):
        start = datetime.fromisoformat(str(group[0]["window_start"]))
        end = datetime.fromisoformat(str(group[-1]["window_end"]))
        bodies = sorted({str(item["body"]) for item in group})
        start_age = round((start - birth).days / 365.2425, 1)
        end_age = round((end - birth).days / 365.2425, 1)
        label, pressure, potential, ask = _interval_language(bodies)
        result.append({
            "id": f"developmental_interval_{index}",
            "age_range": f"{start_age:g}–{end_age:g}",
            "window_start": group[0]["window_start"],
            "window_end": group[-1]["window_end"],
            "activations": group,
            "bodies": bodies,
            "importance": "strong" if "saturn" in bodies and len(bodies) > 1 else "moderate" if len(bodies) > 1 else "light",
            "developmental_label": label,
            "possible_pressures": pressure,
            "potential": potential,
            "what_this_period_may_ask": ask,
            "interpretation_limit": "This interval groups calculated symbolic activations. It does not identify events, biography or a required outcome.",
        })
    return result


def _interval_language(bodies: List[str]) -> Tuple[str, str, str, str]:
    if "saturn" in bodies and "uranus" in bodies:
        return ("Reestruturação e atualização", "a tensão entre manter o que sustenta e atualizar o que limita", "revisar estruturas sem confundir mudança com ruptura", "escolher uma alteração concreta e observar se ela preserva o que é essencial")
    if "saturn" in bodies:
        return ("Consolidação e responsabilidade", "maior contato com limites, ritmos e consequências", "dar forma sustentável ao que já importa", "distinguir compromisso escolhido de rigidez automática")
    if "uranus" in bodies:
        return ("Mudança e atualização", "impulso de romper antes de saber o que substituir", "testar alternativas e recuperar margem de escolha", "experimentar sem desorganizar tudo de uma vez")
    if "jupiter" in bodies:
        return ("Expansão e ampliação", "crescer mais rápido do que os critérios acompanham", "ampliar visão, repertório ou circulação", "escolher onde expansão realmente melhora a vida concreta")
    if "true_node" in bodies:
        return ("Direção e reorientação", "assumir uma direção apenas por pressão externa", "revisar sentido e continuidade", "notar quais escolhas se repetem porque têm valor, não apenas urgência")
    return ("Revisão de ciclo", "mudanças de ritmo ou ênfase", "observar uma transição sem antecipar uma história", "usar as datas como contexto de observação, não como previsão")


def cross_technique_timing(chart: Chart, as_of: Optional[datetime] = None, horizon_days: int = 366) -> Dict[str, object]:
    as_of = _aware_utc(as_of or datetime.now(timezone.utc), "as_of")
    transits = major_transits(chart, as_of, horizon_days)
    if chart.birth.utc_offset_override_minutes is not None:
        local_zone = timezone(timedelta(minutes=chart.birth.utc_offset_override_minutes))
    else:
        local_zone = ZoneInfo(chart.birth.timezone_name)
    profection = annual_profection(chart, as_of.astimezone(local_zone).date())
    progressions = current_progressions(chart, as_of)
    solar_arcs = current_solar_arc(chart, as_of, progressions)
    # A profection may contextualise, but never veto modern transit events.
    clusters: List[Dict[str, object]] = []
    for event in transits:
        instant = datetime.fromisoformat(str(event["exact_at"]))
        event_bodies = {str(event["transit_body"]), str(event["target"])}
        within_window = bool(clusters) and (instant - datetime.fromisoformat(str(clusters[-1]["start"]))).days <= 45
        shares_focus = bool(clusters) and bool(event_bodies.intersection(clusters[-1]["bodies"]))
        if within_window and shares_focus:
            clusters[-1]["event_ids"].append(event["id"])
            clusters[-1]["bodies"].extend([event["transit_body"], event["target"]])
            clusters[-1]["end"] = event["exact_at"]
            clusters[-1]["max_priority"] = max(clusters[-1]["max_priority"], event["priority"])
        else:
            clusters.append({"start": event["exact_at"], "end": event["exact_at"], "event_ids": [event["id"]], "bodies": [event["transit_body"], event["target"]], "max_priority": event["priority"]})
    for cluster in clusters:
        cluster["bodies"] = sorted(set(cluster["bodies"]))
        independent = 1 + int(bool(profection["time_lord"]) and profection["time_lord"] in cluster["bodies"])
        cluster["technique_convergence"] = "moderate" if independent > 1 else "single_stream"
        cluster["intensity"] = "very_strong" if cluster["max_priority"] >= 5 and independent > 1 else "strong" if cluster["max_priority"] >= 4 else "relevant"
    near = [event for event in transits if datetime.fromisoformat(str(event["exact_at"])) <= as_of + timedelta(days=min(horizon_days, 180))]
    convergence: Dict[str, set] = defaultdict(set)
    if profection["time_lord"]:
        convergence[str(profection["time_lord"])].add("annual_profection")
    for event in near:
        if event["priority"] >= 3:
            convergence[str(event["transit_body"])].add("major_transit")
            convergence[str(event["target"])].add("major_transit_target")
    for contact in progressions["contacts"]:
        convergence[str(contact["body"])].add("secondary_progression")
        convergence[str(contact["target"])].add("secondary_progression_target")
    for contact in solar_arcs["contacts"]:
        convergence[str(contact["body"])].add("solar_arc")
        convergence[str(contact["target"])].add("solar_arc_target")
    convergence_rows = []
    for body, techniques in convergence.items():
        independent_streams = {item.replace("_target", "") for item in techniques}
        convergence_rows.append({
            "body": body, "techniques": sorted(techniques), "independent_stream_count": len(independent_streams),
            "intensity": "major_developmental_period" if len(independent_streams) >= 4 else "very_strong" if len(independent_streams) == 3 else "strong" if len(independent_streams) == 2 else "background",
        })
    convergence_rows.sort(key=lambda item: (-item["independent_stream_count"], item["body"]))
    current_phase = {
        "as_of": as_of.isoformat(), "traditional_focus": {"house": profection["house"], "time_lord": profection["time_lord"]},
        "active_bodies": [item["body"] for item in convergence_rows], "convergence": convergence_rows,
        "selected_transit_ids": [event["id"] for event in sorted(near, key=lambda item: (-item["priority"], item["exact_at"]))[:6]],
        "progression_contacts": progressions["contacts"][:4], "solar_arc_contacts": solar_arcs["contacts"][:4],
        "emerging": [item["body"] for item in convergence_rows if item["independent_stream_count"] >= 2],
        "integration_question": "Which active theme requires a contextual choice rather than a prediction?",
        "interpretation_limit": "Current phase is a convergence summary of symbolic techniques, not a forecast of events.",
    }
    return {
        "timing_version": TIMING_VERSION, "traditional_stream": profection,
        "modern_stream": {"major_transits": transits, "progressions": progressions, "solar_arcs": solar_arcs},
        "transit_clusters": clusters, "current_phase": current_phase,
        "deduplication_policy": "Derived cycle labels point to originating transits; repeated passes share one evidence family and one window.",
    }
