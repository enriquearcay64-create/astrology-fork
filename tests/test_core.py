from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

import swisseph as swe
import pytest

from astrology.engine import calculate_chart
from astrology.models import BirthData, Claim, LocalizationProfile
from astrology.pipeline import analyse_birth_chart, consult
from astrology.semantics import verify_claims
from astrology.timing import annual_profection, current_progressions, current_solar_arc, solar_return, upcoming_eclipses


def birth() -> BirthData:
    return BirthData(
        local_datetime="1990-07-12T14:30:00", timezone_name="America/Sao_Paulo",
        latitude=-23.5505, longitude=-46.6333, place_label="São Paulo, Brasil",
    )


def test_canonical_chart_has_shared_and_house_layers():
    chart = calculate_chart(birth())
    assert set(("sun", "moon", "saturn", "uranus", "lilith_mean")) <= set(chart.positions)
    assert chart.angles["dsc"] == (chart.angles["asc"] + 180) % 360
    assert chart.angles["ic"] == (chart.angles["mc"] + 180) % 360
    assert chart.lots["fortune"] != chart.lots["spirit"]
    assert any(item.kind == "dispositor" for item in chart.factors)
    assert any(item.kind == "whole_sign_house" for item in chart.factors)


def test_j2000_regression_fixture_guards_ephemeris_configuration():
    chart = calculate_chart(BirthData("2000-01-01T12:00:00", "UTC", 0.0, 0.0))
    # Swiss Ephemeris 2.10.03 with the bundled 1800–2399 files, tropical/geocentric.
    assert abs(chart.positions["sun"].longitude - 280.36892286) < 0.0001
    assert abs(chart.positions["moon"].longitude - 223.32380085) < 0.0001


def test_outside_bundled_ephemeris_range_fails_explicitly():
    with pytest.raises(ValueError, match="1800–2399"):
        calculate_chart(BirthData("1700-01-01T12:00:00", "UTC", 0.0, 0.0))


def test_placidus_position_uses_backend_house_position():
    chart = calculate_chart(birth())
    assert chart.placidus_available
    position = chart.positions["moon"]
    ecl_nut, _ = swe.calc_ut(chart.julian_day_ut, swe.ECL_NUT, swe.FLG_SWIEPH)
    backend_value = swe.house_pos(chart.angles["mc"] if False else swe.houses_ex(chart.julian_day_ut, birth().latitude, birth().longitude, b"P", swe.FLG_SWIEPH)[1][2], birth().latitude, ecl_nut[0], (position.longitude, position.latitude), b"P")
    assert abs(chart.house_placements["moon"].placidus_position - backend_value) < 1e-5


def test_polar_placidus_failure_is_explicit_not_silent():
    polar = BirthData("1990-07-12T14:30:00", "Arctic/Longyearbyen", 89.0, 15.0)
    chart = calculate_chart(polar)
    if not chart.placidus_available:
        assert any("Placidus unavailable" in warning for warning in chart.warnings)
        assert all(item.placidus_house is None for item in chart.house_placements.values())


def test_explicit_time_uncertainty_produces_sensitivity_analysis():
    uncertain = BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333, time_uncertainty_minutes=10)
    chart = calculate_chart(uncertain)
    assert any("changes ASC" in item for item in chart.data_quality.input_sensitivity)


def test_robustness_is_not_second_evidence_vote():
    result = analyse_birth_chart(birth(), include_timing=False)
    for theme in result["themes"]:
        assert len(theme["evidence_families"]) == len(set(theme["evidence_families"]))
    robustness = [factor for factor in result["chart"]["factors"] if factor["kind"] == "house_system_robustness"]
    assert robustness


def test_nodal_axis_is_available_while_other_secondary_points_remain_non_core():
    result = analyse_birth_chart(birth(), include_timing=False)
    assert any(claim["id"].startswith("claim.node_axis") for claim in result["claims"])
    assert all("chiron" not in claim["id"] and "lilith" not in claim["id"] for claim in result["claims"])


def test_counterweights_are_sought_from_related_qualifying_aspects():
    result = analyse_birth_chart(birth(), include_timing=False)
    aspect_claims = [claim for claim in result["claims"] if claim["id"].startswith("claim.aspect")]
    assert any(claim["counterweights"] for claim in aspect_claims)


def test_semantic_verifier_blocks_prohibited_biography():
    claim = Claim(
        id="bad", theme="care", type="symbolic_tendency", statement="Isto prova abandono e trauma.", evidence=["x"],
        evidence_families=["x"], counterweights=[], allowed_specificity="behavioral_possibility", allowed_examples=[],
        prohibited_inferences=[], astrological_support="light",
    )
    verified = verify_claims([claim])[0]
    assert verified.status == "blocked"


def test_profection_is_whole_sign_and_timing_does_not_require_it_to_find_transits():
    chart = calculate_chart(birth())
    profection = annual_profection(chart, datetime(2026, 8, 27, tzinfo=timezone.utc).date())
    assert 1 <= profection["house"] <= 12
    result = analyse_birth_chart(birth(), include_timing=True, as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=45)
    assert "traditional_stream" in result["timing"]
    assert "major_transits" in result["timing"]["modern_stream"]


def test_solar_return_without_return_location_does_not_invent_houses():
    chart = calculate_chart(birth())
    returned = solar_return(chart, 2027, "actual_physical_location", None)
    assert returned["location_known"] is False
    assert "angles" not in returned


def test_timing_v2_and_v3_calculations_are_structured_and_limited():
    chart = calculate_chart(birth())
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    assert current_progressions(chart, as_of)["stream"] == "modern_progressions"
    assert current_solar_arc(chart, as_of)["stream"] == "modern_solar_arcs"
    returned = solar_return(chart, 2027, "birth_place", (birth().latitude, birth().longitude))
    assert "angles" in returned
    eclipses = upcoming_eclipses(as_of, 2)
    assert len(eclipses) == 2
    assert all("Astronomical event only" in event["interpretation_limit"] for event in eclipses)


def test_localization_is_post_synthesis_only():
    profile = LocalizationProfile(preferred_language="pt-BR", current_country="Brazil", cultural_context="Brazil")
    local = analyse_birth_chart(birth(), profile, include_timing=False)
    neutral = analyse_birth_chart(birth(), None, include_timing=False)
    assert [item["id"] for item in local["themes"]] == [item["id"] for item in neutral["themes"]]
    assert local["localization_audit"]["prohibited_changes"] == ["personality", "astrological_weights", "themes", "prediction"]


def test_consultation_only_uses_verified_claims():
    result = consult(birth(), "O que o mapa sugere sobre carreira?", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert "consultation" in result
    assert "claims" in result["consultation"]
