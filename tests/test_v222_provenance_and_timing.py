"""Adversarial test suite for V2.2.2 candidate.

Verifies:
1. Fail-closed prospective block assignment: unmaterialized syntheses (score == 0) are never silently attached.
2. Missing domain provenance causes fail-closed rejection by Provenance Guard.
3. Opening mandatory sources are not backfilled when unmentioned.
4. Exact timing perfection vs closest approach distinction in schema and appendix table rendering.
5. Structural legality validation for Author-owned ReaderSelectionPlan.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from astrology.models import BirthData, LocalizationProfile
from astrology.pipeline import (
    prepare_premium_handoff,
    plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose,
    build_author_bundle,
    validate_premium_syntheses,
    validate_premium_author_bundle,
    validate_author_selection_plan,
    build_canonical_selection_plan,
    _canonical_hash,
    _parse_premium_narrative,
)
from astrology.report import (
    format_canonical_timing_activation,
    render_canonical_technical_appendix,
)
from scripts.run_chart3_pipeline import DRAFT_REPORT, CHART_3_BIRTH
from tests.test_v221_timing_and_selection import sample_birth


def test_v222_unmaterialized_planned_synthesis_not_silently_attached():
    """Verify Issue 1: a planned synthesis with 0 semantic score is never silently attached to blocks."""
    profile = LocalizationProfile(preferred_language="pt-BR")
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=profile)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    # In DRAFT_REPORT, desire_action_limits discusses Marte.
    # We create an adversarial report where desire_action_limits discusses completely unrelated topics (no Mars, no ruler).
    tampered_draft = DRAFT_REPORT.replace(
        "A assertividade opera a partir de Marte domiciliado em Escorpião",
        "A assertividade opera a partir de uma postura calma e reflexiva",
    ).replace(
        "Governando a segunda casa de recursos e a nona casa de convicções, Marte vincula a defesa de limites",
        "Governando o equilíbrio interior e a tranquilidade, a conduta vincula a defesa de limites",
    )

    sources, sections, trace = bind_prospective_plan_to_prose(tampered_draft, block_plan, manifest)

    # Verify that the Mars synthesis is recorded as unmaterialized
    unmaterialized_sids = [u["synthesis_id"] for u in trace.get("unmaterialized_planned_sources", [])]
    mars_synth_id = "reasoned.reader_path.desire_action_limits.claim_anchored.1"
    assert mars_synth_id in unmaterialized_sids

    # Verify that no block in desire_action_limits received the Mars synthesis
    parsed = _parse_premium_narrative(tampered_draft, manifest)
    desire_hashes = [str(b["narrative_block_sha256"]) for b in parsed["sections"]["desire_action_limits"]["authored"]]
    for s in sources:
        if s["narrative_block_sha256"] in desire_hashes:
            assert mars_synth_id not in s["synthesis_ids"]

    # Verify that Provenance Guard FAILS CLOSED because a represented synthesis is missing domain provenance
    all_synths = list(block_plan.get("composed_syntheses", []))
    for ps in handoff.get("prepared_signature_syntheses", []):
        if ps["id"] not in [x["id"] for x in all_synths]:
            all_synths.append(ps)

    checked = validate_premium_syntheses(CHART_3_BIRTH, all_synths, premium_contract_version="1.4")
    approved_synths = [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"]
    expected_synthesis_hash = _canonical_hash(approved_synths)
    author_bundle = build_author_bundle(
        handoff, tampered_draft, sources,
        reader_selection_plan=block_plan["selection_plan"],
        reasoned_syntheses=all_synths,
        reader_sections=sections,
        synthesis_bundle_sha256=expected_synthesis_hash,
    )
    prov_res = validate_premium_author_bundle(CHART_3_BIRTH, author_bundle, profile=profile, prepared_handoff=handoff)
    assert prov_res["approved"] is False
    assert any("reader_selection_synthesis_missing_domain_provenance" in err or "untraceable_narrative_block_source" in err for err in prov_res["verification_errors"])


def test_v222_missing_domain_provenance_causes_fail_closed_rejection():
    """Verify Issue 1: if a domain has 0 materialized syntheses, blocks remain empty and trigger untraceable_narrative_block_source."""
    profile = LocalizationProfile(preferred_language="pt-BR")
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=profile)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    # Empty out astrological content in emotional_security
    tampered_draft = DRAFT_REPORT.replace(
        "A segurança emocional reside na décima segunda casa, onde a Lua em Peixes demanda espaços regulares",
        "A segurança interior reside na calma pessoal, onde a vivência diária demanda espaços regulares",
    ).replace(
        "Esse mundo privado conversa diretamente com a quarta casa em Gêmeos, cujo regente Mercúrio opera na sétima casa em Virgem.",
        "Esse mundo privado conversa diretamente com a busca de paz, cujo princípio opera na serenidade de espírito.",
    )

    sources, sections, trace = bind_prospective_plan_to_prose(tampered_draft, block_plan, manifest)
    parsed = _parse_premium_narrative(tampered_draft, manifest)
    emotional_hashes = [str(b["narrative_block_sha256"]) for b in parsed["sections"]["emotional_security"]["authored"]]

    # Both blocks in emotional_security must have empty synthesis_ids because 0 domain syntheses materialized
    for s in sources:
        if s["narrative_block_sha256"] in emotional_hashes:
            assert s["synthesis_ids"] == []

    all_synths = list(block_plan.get("composed_syntheses", []))
    for ps in handoff.get("prepared_signature_syntheses", []):
        if ps["id"] not in [x["id"] for x in all_synths]:
            all_synths.append(ps)

    checked = validate_premium_syntheses(CHART_3_BIRTH, all_synths, premium_contract_version="1.4")
    approved_synths = [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"]
    expected_synthesis_hash = _canonical_hash(approved_synths)
    author_bundle = build_author_bundle(
        handoff, tampered_draft, sources,
        reader_selection_plan=block_plan["selection_plan"],
        reasoned_syntheses=all_synths,
        reader_sections=sections,
        synthesis_bundle_sha256=expected_synthesis_hash,
    )
    prov_res = validate_premium_author_bundle(CHART_3_BIRTH, author_bundle, profile=profile, prepared_handoff=handoff)
    assert prov_res["approved"] is False
    assert "untraceable_narrative_block_source" in prov_res["verification_errors"]


def test_v222_opening_mandatory_sources_not_backfilled_when_unmentioned():
    """Verify Issue 1: Opening blocks only receive mandatory syntheses actually cited, without fallback padding."""
    profile = LocalizationProfile(preferred_language="pt-BR")
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=profile)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    # Opening with only Sun and Moon mentioned, omitting Saturn, Mars, Jupiter, Stellium etc.
    minimal_opening = (
        "## Arquitetura do mapa\n\n"
        "A arquitetura do mapa expressa a vitalidade do Sol em harmonia reflexiva com a sensibilidade receptiva da Lua.\n\n"
        "Esta síntese fundamental orienta toda a leitura integrativa de forma relacional e equilibrada."
    )
    # Splice into report
    parts = DRAFT_REPORT.split("## Arquitetura do mapa")
    rest = parts[1].split("## Identidade central e presença")[1]
    tampered = parts[0] + minimal_opening + "\n\n## Identidade central e presença" + rest

    sources, sections, trace = bind_prospective_plan_to_prose(tampered, block_plan, manifest)
    parsed = _parse_premium_narrative(tampered, manifest)
    opening_hashes = [str(b["narrative_block_sha256"]) for b in parsed["sections"]["opening"]["authored"]]

    # Block 1 of opening only mentions generic text, so it must ONLY contain relational synthesis, NO mandatory padding!
    block1_source = next(s for s in sources if s["narrative_block_sha256"] == opening_hashes[1])
    assert len(block1_source["synthesis_ids"]) == 1  # Only relational synthesis

    # Unmaterialized mandatories in opening must be tracked
    assert len(trace["unmaterialized_mandatories"]) > 0


def test_v222_exact_timing_vs_closest_approach_distinction():
    """Verify Issue 2: Exact timing perfection and closest approach are strictly distinguished in schema and rendering."""
    profile = LocalizationProfile(preferred_language="pt-BR")
    as_of = datetime(2026, 9, 1, tzinfo=timezone.utc)

    # 1. Activation with perfected exact peak
    exact_activation = {
        "id": "transit.saturn_trine_moon.1",
        "technique": "Major Transit",
        "transit_body": "Saturno",
        "aspect": "trígono",
        "target": "Lua",
        "window_start": "2026-08-15",
        "window_end": "2026-10-15",
        "exact_at": "2026-09-10",
        "closest_approach_at": "2026-09-09",
        "primary_factors": ["aspect.saturn_trine_moon"],
    }
    fmt_exact = format_canonical_timing_activation(exact_activation, profile)
    assert fmt_exact["perfected"] is True
    assert fmt_exact["peak_type"] == "exact"
    assert fmt_exact["peak_date"] == "2026-09-10"
    assert fmt_exact["peak_display"] == "2026-09-10 (Exatidão)"

    # 2. Activation with only closest approach (no perfection in window)
    approach_activation = {
        "id": "transit.jupiter_quincunx_sun.2",
        "technique": "Major Transit",
        "transit_body": "Júpiter",
        "aspect": "quincúncio",
        "target": "Sol",
        "window_start": "2026-11-01",
        "window_end": "2027-01-15",
        "exact_at": None,
        "closest_approach_at": "2026-12-05",
        "primary_factors": ["aspect.jupiter_quincunx_sun"],
    }
    fmt_approach = format_canonical_timing_activation(approach_activation, profile)
    assert fmt_approach["perfected"] is False
    assert fmt_approach["peak_type"] == "closest_approach"
    assert fmt_approach["peak_date"] == "2026-12-05"
    assert fmt_approach["peak_display"] == "2026-12-05 (Aprox. Máxima)"

    # 3. Technical appendix table rendering check
    timing_data = {
        "modern_stream": {
            "major_transits": [exact_activation, approach_activation],
        }
    }
    appendix = render_canonical_technical_appendix(CHART_3_BIRTH, timing=timing_data, lang="pt")
    assert "| Pico (Tipo) |" in appendix
    assert "2026-09-10 (Exatidão)" in appendix
    assert "2026-12-05 (Aprox. Máxima)" in appendix


def test_v222_validate_author_selection_plan_legality_and_rejection():
    """Verify Issue 3: validate_author_selection_plan validates structural legality and rejects illegal plans."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]

    # 1. Valid plan built by build_canonical_selection_plan
    valid_plan = build_canonical_selection_plan(manifest)
    is_valid, errors = validate_author_selection_plan(valid_plan, manifest)
    assert is_valid is True
    assert errors == []

    # 2. Rejection: missing domain
    bad_plan_missing_domain = {
        "version": "1.0",
        "domains": [d for d in valid_plan["domains"] if d["domain_id"] != "identity_presence"],
    }
    valid_res, errors = validate_author_selection_plan(bad_plan_missing_domain, manifest)
    assert valid_res is False
    assert any("missing_domain:identity_presence" in e for e in errors)

    # 3. Rejection: illegal decision string
    import copy
    bad_plan_illegal_decision = copy.deepcopy(valid_plan)
    bad_plan_illegal_decision["domains"][0]["paths"][0]["decision"] = "ignored"
    valid_res, errors = validate_author_selection_plan(bad_plan_illegal_decision, manifest)
    assert valid_res is False
    assert any("invalid_decision" in e for e in errors)

    # 4. Rejection: merge pointing to non-existent path
    bad_plan_merge = copy.deepcopy(valid_plan)
    bad_plan_merge["domains"][0]["paths"][0]["decision"] = "merged_with_represented"
    bad_plan_merge["domains"][0]["paths"][0]["merged_with_path_id"] = "non_existent_path"
    bad_plan_merge["domains"][0]["paths"][0]["rationale"] = "Rationale test"
    bad_plan_merge["domains"][0]["paths"][0]["synthesis_ids"] = []
    valid_res, errors = validate_author_selection_plan(bad_plan_merge, manifest)
    assert valid_res is False
    assert any("invalid_merge_target" in e for e in errors)

    # 5. Rejection: omitted path with empty rationale
    bad_plan_empty_rationale = copy.deepcopy(valid_plan)
    found_omit = False
    for d in bad_plan_empty_rationale["domains"]:
        for p in d["paths"]:
            if p["decision"] == "omitted_no_distinct_reader_value":
                p["rationale"] = "   "
                found_omit = True
                break
        if found_omit:
            break
    assert found_omit
    valid_res, errors = validate_author_selection_plan(bad_plan_empty_rationale, manifest)
    assert valid_res is False
    assert any("missing_omission_rationale" in e for e in errors)
