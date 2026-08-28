from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import astrology.timing as timing
from astrology.engine import EPHEMERIS_PATH, calculate_chart
from astrology.models import BirthData
from astrology.semantics import build_claims, verify_claims


ROOT = Path(__file__).resolve().parent.parent


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def test_release_metadata_declares_cli_and_ephemeris_data_files():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "4.0.1"' in project
    assert 'astrology-skill = "astrology.cli:main"' in project
    assert '"assets/ephe/*.se1"' in project
    assert all((EPHEMERIS_PATH / name).exists() for name in ("sepl_18.se1", "semo_18.se1", "seas_18.se1"))


def test_cross_technique_timing_reuses_progression_snapshot(monkeypatch):
    chart = calculate_chart(birth())
    original = timing.current_progressions
    calls = {"count": 0}

    def counted(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(timing, "current_progressions", counted)
    result = timing.cross_technique_timing(chart, datetime(2026, 8, 27, tzinfo=timezone.utc), 1)
    assert calls["count"] == 1
    progression_families = {item["evidence_family"] for item in result["modern_stream"]["progressions"]["contacts"]}
    arc_families = {item["evidence_family"] for item in result["modern_stream"]["solar_arcs"]["contacts"]}
    assert not progression_families & arc_families


def test_semantic_verification_is_idempotent_and_does_not_overwrite_text():
    chart = calculate_chart(birth())
    claims = build_claims(chart)
    first = verify_claims(claims, chart)
    statements = [claim.statement for claim in first]
    second = verify_claims(first, chart)
    assert [claim.statement for claim in second] == statements
    assert all(claim.status == "allowed" for claim in second)


def test_timeline_clamps_cleanly_at_ephemeris_boundary():
    chart = calculate_chart(BirthData("2399-01-01T12:00:00", "UTC", 0, 0))
    timeline = timing.life_timeline(chart, 70)
    assert timeline == [] or timeline[-1]["range"] in {"0–0", "0–1"}
    assert all(int(item["range"].split("–")[0]) <= int(item["range"].split("–")[1]) for item in timeline)
