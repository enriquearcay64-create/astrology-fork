"""Installed command-line interface for the local astrology engine."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Dict, Optional

from .engine import calculate_chart
from .models import BirthData, LocalizationProfile
from .pipeline import analyse_birth_chart, consult
from .timing import solar_return


def _load(path: str) -> Dict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _birth(data: Dict[str, object]) -> BirthData:
    allowed = {"local_datetime", "timezone_name", "latitude", "longitude", "place_label", "utc_offset_override_minutes", "time_uncertainty_minutes", "calendar", "source", "dst_fold", "birth_time_known", "sensitivity_test_minutes"}
    unknown = sorted(set(data) - allowed - {"localization_profile", "solar_return_location"})
    if unknown:
        raise ValueError("unknown input fields: " + ", ".join(unknown))
    return BirthData(**{key: value for key, value in data.items() if key in allowed})


def _profile(data: Dict[str, object]) -> Optional[LocalizationProfile]:
    profile = data.get("localization_profile")
    if not profile:
        return None
    if not isinstance(profile, dict):
        raise ValueError("localization_profile must be an object")
    allowed = {"preferred_language", "current_country", "cultural_context", "region", "source", "localization_level"}
    unknown = sorted(set(profile) - allowed)
    if unknown:
        raise ValueError("unknown localization_profile fields: " + ", ".join(unknown))
    return LocalizationProfile(**profile)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic astrology calculation and structured reading.")
    parser.add_argument("input", help="JSON with birth data and optional localization_profile")
    parser.add_argument("--depth", choices=("executive", "deep", "technical"), default="executive")
    parser.add_argument("--no-timing", action="store_true")
    parser.add_argument("--horizon-days", type=int, default=366)
    parser.add_argument("--question", help="Run constrained consultation mode")
    parser.add_argument("--solar-return-year", type=int)
    parser.add_argument("--solar-return-location-policy", choices=("birth_place", "habitual_residence", "actual_physical_location"), default="birth_place")
    parser.add_argument("--as-of", help="UTC ISO timestamp for reproducible timing")
    parser.add_argument("--format", choices=("json", "report"), default="json")
    args = parser.parse_args()
    try:
        data = _load(args.input)
        birth = _birth(data)
        profile = _profile(data)
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else None
        if as_of is not None and as_of.tzinfo is None:
            raise ValueError("--as-of must include a UTC offset")
        if args.solar_return_year:
            declared = data.get("solar_return_location")
            location = (birth.latitude, birth.longitude) if args.solar_return_location_policy == "birth_place" else (float(declared["latitude"]), float(declared["longitude"])) if isinstance(declared, dict) else None
            result = solar_return(calculate_chart(birth), args.solar_return_year, args.solar_return_location_policy, location)
        elif args.question:
            result = consult(birth, args.question, profile, as_of)
        else:
            result = analyse_birth_chart(birth, profile, args.depth, not args.no_timing, as_of, args.horizon_days)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError, RuntimeError) as error:
        json.dump({"error": type(error).__name__, "message": str(error)}, sys.stderr, ensure_ascii=False)
        print(file=sys.stderr)
        return 2
    if args.format == "report" and isinstance(result, dict) and "report" in result:
        print(result["report"])
    else:
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
        print()
    return 0
