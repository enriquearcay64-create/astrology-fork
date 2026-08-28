from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from astrology.engine import calculate_chart
from astrology.models import BirthData, ReasonedSynthesis
from astrology.pipeline import analyse_birth_chart
from astrology.reasoning import validate_reasoned_syntheses
from astrology.safe_view import build_safe_interpretive_view
from astrology.timing import group_activation_instances
from astrology.editorial_qa import barnum_risk, semantic_cross_report_similarity
from astrology.report import _transit_windows


def boundary_birth() -> BirthData:
    # At this location/date the ASC is 29° Capricorn and +5m enters Aquarius.
    return BirthData("1990-07-12T00:55:00", "America/Sao_Paulo", -23.5505, -46.6333)


def _event(when: str, branch: str = "positive", motion: str = "direct", cycle: str = "saturn:2026-05-01") -> dict:
    return {
        "id": f"raw.{when}.{branch}", "transit_body": "saturn", "target": "sun",
        "aspect": "quincunx", "aspect_branch": branch, "exact_at": when, "motion_at_closest": motion, "retrograde_cycle_id": cycle,
        "orb_at_minimum": 0.1, "priority": 4,
    }


def test_stress_test_is_separate_from_declared_time_quality_and_discloses_boundary_sensitivity():
    raw = calculate_chart(boundary_birth())
    assert raw.stability["declared_quality"] == "exact"
    assert raw.stability["declared_uncertainty_minutes"] == 0.0
    assert raw.stability["whole_sign_topology_status"] == "stable"
    assert raw.stability["high_boundary_sensitivity"] is True
    assert any(item["minutes"] == 5.0 and item["whole_sign_topology_changed"] for item in raw.stability["sensitivity_tests"])

    result = analyse_birth_chart(boundary_birth(), report_depth="deep", include_timing=False)
    assert result["chart"]["house_placements"]  # raw factual audit record remains complete
    assert result["safe_interpretive_view"]["house_placements"]
    assert not result["safe_interpretive_view"]["conditional_house_scenarios"]
    assert any(claim["type"] == "topical_tendency" for claim in result["claims"] if claim["status"] == "allowed")
    assert "teste contrafactual de sensibilidade" in result["report"]


def test_safe_view_keeps_exact_time_houses_but_declared_uncertainty_still_blocks_them():
    view = build_safe_interpretive_view(calculate_chart(boundary_birth()))
    assert view.house_placements
    assert not view.conditional_house_scenarios
    uncertain = build_safe_interpretive_view(calculate_chart(BirthData(**{**boundary_birth().__dict__, "time_uncertainty_minutes": 181})))
    assert not uncertain.house_placements
    assert set(uncertain.conditional_house_scenarios) == set(uncertain.positions)
    semantic_chart = view.semantic_chart()
    assert semantic_chart.house_placements


def test_declared_uncertainty_blocks_profections_and_hierarchy_but_stress_test_does_not_overrule_exact_time():
    result = analyse_birth_chart(boundary_birth(), report_depth="executive", include_timing=True)
    profection = result["timing"]["traditional_stream"]
    assert profection["time_lord"]
    uncertain = analyse_birth_chart(BirthData(**{**boundary_birth().__dict__, "time_uncertainty_minutes": 181}), report_depth="executive", include_timing=True)
    assert uncertain["timing"]["traditional_stream"]["status"] == "unavailable"
    assert not any("asc_ruler" in item["roles"] for item in uncertain["hierarchy"].values())


def test_activation_instance_groups_retrograde_passes_but_not_years_or_branches():
    nearby = group_activation_instances([
        _event("2026-01-10T00:00:00+00:00"),
        _event("2026-06-10T00:00:00+00:00", motion="retrograde"),
        _event("2026-10-10T00:00:00+00:00", motion="direct"),
    ])
    assert len(nearby) == 1 and len(nearby[0]["passes"]) == 3

    recurring = group_activation_instances([
        _event("2026-01-10T00:00:00+00:00"),
        _event("2030-01-10T00:00:00+00:00", motion="retrograde", cycle="saturn:2030-05-01"),
    ])
    assert len(recurring) == 2
    assert recurring[0]["semantic_family"] == recurring[1]["semantic_family"]
    assert recurring[0]["activation_instance"] != recurring[1]["activation_instance"]

    branches = group_activation_instances([
        _event("2026-01-10T00:00:00+00:00", "positive"),
        _event("2026-03-10T00:00:00+00:00", "negative"),
    ])
    assert len(branches) == 2


def test_renderer_preserves_separate_activation_instances():
    recurring = group_activation_instances([
        _event("2026-01-10T00:00:00+00:00"),
        _event("2030-01-10T00:00:00+00:00", motion="retrograde", cycle="saturn:2030-05-01"),
    ])
    assert len(_transit_windows(recurring, 10)) == 2


def test_reasoned_synthesis_is_traceable_but_not_registry_prose():
    result = analyse_birth_chart(
        BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333),
        as_of=datetime(2026, 8, 27, tzinfo=timezone.utc),
        horizon_days=30,
    )
    assert result["reasoned_synthesis"]
    assert all(item["status"] == "allowed" for item in result["reasoned_synthesis"])
    assert result["narrative_plan"]["opening"]["observation"]
    assert "closed factual packet" in result["llm_reasoning_instructions"]


def test_reasoned_synthesis_rejects_prohibited_or_unknown_extensions():
    view = build_safe_interpretive_view(calculate_chart(boundary_birth()))
    bad = ReasonedSynthesis(
        id="bad", observation="This proves trauma.", primary_factors=["invented.factor"], modifiers=[], counterweights=[],
        reasoning_class="integrated_pattern", confidence_within_astrological_model="strong", possible_expressions=["diagnosis"],
        alternative_reading="", prohibited_extensions=[],
    )
    checked = validate_reasoned_syntheses([bad], view)[0]
    assert checked.status == "blocked"
    assert {"unknown_or_unsafe_factor", "prohibited_extension_in_reasoning"} <= set(checked.verification_errors)


def test_editorial_semantic_qa_flags_broad_reuse_without_treating_it_as_a_verdict():
    reports = {
        "A": "You are strong but sensitive in ways that matter every day. You value freedom in every context.",
        "B": "You are strong but sensitive in ways that matter every day. You value freedom in every context.",
        "C": "A specific Saturn–Mercury pattern asks for a practical adjustment.",
    }
    semantic = semantic_cross_report_similarity(reports, threshold=0.5)
    assert semantic["pairwise"]["A-B"]["interchangeable_sentence_count"] >= 1
    assert barnum_risk(reports["A"])["share"] > 0
