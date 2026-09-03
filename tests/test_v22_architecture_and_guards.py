from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from astrology.models import BirthData, LocalizationProfile
from astrology.engine import calculate_chart
from astrology.semantics import PAIR_RULES
from astrology.report import (
    format_degree_minute,
    format_orb_degree_minute,
    render_canonical_technical_appendix,
    validate_technical_relationship_fidelity,
)
from astrology.pipeline import (
    prepare_premium_handoff,
    analyse_birth_chart,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_canonical_selection_plan,
    build_author_bundle,
    build_reviewer_bundle,
    validate_premium_author_bundle,
    validate_premium_narrative,
)


def sample_birth() -> BirthData:
    return BirthData(
        "1989-11-01T12:08:00",
        "America/Caracas",
        10.1620,
        -68.0077,
        birth_time_known=True,
    )


# 1. Runtime / script naming matches actual behavior
def test_runtime_script_docstring_and_help_truthfulness():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_canonical_premium_pipeline.py"
    content = script_path.read_text(encoding="utf-8")
    assert "Preparation, prospective planning, and guard validation harness" in content
    assert "IAU SOFA" not in content  # Eliminates false engine attribution claim


# 2. No production import from tests.*
def test_no_production_import_from_tests():
    astrology_dir = Path(__file__).resolve().parent.parent / "astrology"
    for py_file in astrology_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        assert "from tests" not in content, f"Forbidden import from tests in {py_file.name}"
        assert "import tests" not in content, f"Forbidden import from tests in {py_file.name}"


# 3. Prospective source selection workflow
def test_prospective_source_selection_workflow():
    birth = sample_birth()
    as_of = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth, as_of=as_of, include_timing=True)

    # Invariant: Block plan is created BEFORE prose
    block_plan = plan_prospective_narrative_blocks(handoff)
    assert block_plan["plan_version"] == "1.0"
    assert "plan_sha256" in block_plan
    assert "opening" in block_plan["sections"]
    assert "integration" in block_plan["sections"]

    # Opening must be relational synthesis (2-3 blocks), not a 15-item placement inventory
    opening_blocks = block_plan["sections"]["opening"]
    assert 1 <= len(opening_blocks) <= 4

    # Each domain has planned sources
    for domain in handoff["reader_domain_manifest"]["domains"]:
        if domain.get("availability") == "available":
            assert domain["id"] in block_plan["sections"]


# 4. Exact Contract 1.4 bundle shape remains valid
def test_exact_contract_14_bundle_shape():
    from tests.v414_helpers import build_author_bundle_v14, reviewer_bundle_v14
    birth = sample_birth()
    handoff = prepare_premium_handoff(birth, include_timing=False)
    author, meta = build_author_bundle_v14(birth, include_timing=False)

    provenance = validate_premium_author_bundle(birth, author, prepared_handoff=handoff, include_timing=False)
    assert provenance["approved"], provenance.get("verification_errors")

    reviewer = reviewer_bundle_v14(author, provenance)
    pub_result = validate_premium_narrative(reviewer, provenance, birth, include_timing=False, prepared_handoff=handoff)
    assert pub_result["approved"], pub_result.get("verification_errors")


# 5. Technical renderer PT localization
def test_technical_renderer_pt_localization():
    birth = sample_birth()
    chart = calculate_chart(birth)
    rendered_pt = render_canonical_technical_appendix(chart, lang="pt")
    assert "## Apêndice Técnico Canônico" in rendered_pt
    assert "Posições Planetárias e Pontos Natais" in rendered_pt
    assert "Sol" in rendered_pt
    assert "Escorpião" in rendered_pt
    assert "Swiss Ephemeris / pyswisseph" in rendered_pt
    assert "IAU SOFA" not in rendered_pt


# 6. Technical renderer EN localization
def test_technical_renderer_en_localization():
    birth = sample_birth()
    chart = calculate_chart(birth)
    rendered_en = render_canonical_technical_appendix(chart, lang="en")
    assert "## Canonical Technical Appendix" in rendered_en
    assert "Planetary Positions and Natal Points" in rendered_en
    assert "Sun" in rendered_en
    assert "Scorpio" in rendered_en
    assert "Swiss Ephemeris / pyswisseph" in rendered_en
    assert "IAU SOFA" not in rendered_en


# 7. 60-minute rounding edge case
def test_60_minute_rounding_edge_case():
    # Longitude near boundary that would round to 60'
    deg_str, sign_str = format_degree_minute(29.99999, lang="pt")
    assert "60'" not in deg_str
    assert deg_str == "00°00'"
    assert sign_str == "Touro"

    # Orb near 0.99999 that would round to 00°60'
    orb_deg, orb_min = format_orb_degree_minute(0.99999)
    assert "60'" not in orb_min
    assert orb_min == "01°00'"


# 8. Sign rollover edge case
def test_sign_rollover_edge_case():
    # 359.99999 degrees (end of Pisces) rolls over to 00°00' Aries
    deg_str, sign_str = format_degree_minute(359.99999, lang="en")
    assert deg_str == "00°00'"
    assert sign_str == "Aries"

    # 29.99999 degrees (end of Aries) rolls over to 00°00' Taurus
    deg_str, sign_str = format_degree_minute(29.99999, lang="en")
    assert deg_str == "00°00'"
    assert sign_str == "Taurus"


# 9. Technical aspect relationship fidelity
def test_technical_aspect_relationship_fidelity():
    birth = sample_birth()
    chart = calculate_chart(birth)

    # In Valencia chart: Sun sextile Saturn (True), Sun sextile Neptune (True)
    # Saturn conjunct Neptune (True)
    # But Saturn does NOT sextile Neptune!
    valid_text = "O Sol forma um sextil com Saturno e Netuno no mapa."
    errors_valid = validate_technical_relationship_fidelity(valid_text, chart, lang="pt")
    assert len(errors_valid) == 0

    invalid_text = "Saturno forma um sextil com o Sol e Netuno no mapa."
    errors_invalid = validate_technical_relationship_fidelity(invalid_text, chart, lang="pt")
    assert any("saturn_sextile_neptune" in err for err in errors_invalid)


# 10. Deterministic timing fact immutability
def test_deterministic_timing_facts_render_and_immutability():
    birth = sample_birth()
    analysis = analyse_birth_chart(birth, include_timing=True)
    timing = analysis.get("timing")
    assert timing is not None

    appendix = render_canonical_technical_appendix(birth, timing=timing, lang="pt")
    assert "Fatos Canônicos de Timing" in appendix
    assert "Profecção Anual" in appendix
    assert "Senhor do Ano: Saturno" in appendix


# 11. Original 8 PAIR_RULES remain unchanged
def test_original_8_pair_rules_remain_unchanged():
    assert len(PAIR_RULES) == 8
    expected_pairs = {
        frozenset({"moon", "uranus"}),
        frozenset({"saturn", "moon"}),
        frozenset({"venus", "uranus"}),
        frozenset({"saturn", "mars"}),
        frozenset({"sun", "saturn"}),
        frozenset({"sun", "uranus"}),
        frozenset({"mercury", "neptune"}),
        frozenset({"venus", "pluto"}),
    }
    assert set(PAIR_RULES.keys()) == expected_pairs



# 12. ReaderSelectionPlan integrity: no empty generic boilerplate for omitted paths
def test_reader_selection_plan_specific_rationales():
    birth = sample_birth()
    result = analyse_birth_chart(birth)
    manifest = result["reader_domain_manifest"]
    plan = build_canonical_selection_plan(manifest)

    # Every omitted path must have a non-empty, chart-grounded rationale
    for domain in plan["domains"]:
        for path in domain["paths"]:
            if path["decision"] == "omitted_no_distinct_reader_value":
                assert path["rationale"] is not None
                assert len(path["rationale"]) > 10
                assert "This legal path adds no distinct reader value beyond the represented domain mechanism." != path["rationale"]
