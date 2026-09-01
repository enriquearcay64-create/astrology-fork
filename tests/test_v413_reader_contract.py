from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone
import json
import sys
import pytest

import astrology.cli as cli
from astrology.config import PREMIUM_HANDOFF_CONTRACT_VERSION
from astrology.models import BirthData, LocalizationProfile, ReasonedSynthesis
from astrology.pipeline import (
    PREMIUM_READER_INTRODUCTION,
    PREMIUM_READER_INTRODUCTIONS,
    _canonical_hash,
    _parse_premium_narrative,
    analyse_birth_chart,
    paragraph_source_template,
    prepare_premium_handoff,
    validate_premium_author_bundle,
    validate_premium_narrative,
    validate_premium_syntheses,
)
from astrology.reasoning import READER_DOMAIN_DEFINITIONS, humanization_instructions, humanization_verifier_instructions
from tests.v413_helpers import build_author_bundle, reviewer_bundle


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def _source_for_section(author, section_key: str):
    if section_key in {"opening", "integration"}:
        paragraph_hash = author["reader_sections"][section_key]["paragraph_sha256s"][0]
    else:
        section = next(item for item in author["reader_sections"]["domains"] if item["domain_id"] == section_key)
        paragraph_hash = section["paragraph_sha256s"][0]
    return next(item for item in author["paragraph_sources"] if item["paragraph_sha256"] == paragraph_hash)


def test_v413_manifest_has_exact_domains_four_path_kinds_and_scoped_authority():
    result = analyse_birth_chart(birth(), include_timing=False)
    manifest = result["reader_domain_manifest"]
    assert [item["id"] for item in manifest["domains"]] == [item["id"] for item in READER_DOMAIN_DEFINITIONS]
    assert [item["position"] for item in manifest["domains"]] == list(range(1, 17))
    assert set(manifest["rules"]["path_kinds"]) == {"claim_anchored", "topical_placidus", "house_ruler_context", "timing_natal"}
    assert all({path["kind"] for path in item["legal_coverage_paths"]}.issubset(set(manifest["rules"]["path_kinds"])) for item in manifest["domains"])
    assert all(item["availability"] == "available" for item in manifest["domains"][:15])
    assert manifest["domains"][15]["availability"] == "unavailable"
    assert manifest["domains"][15]["unavailable_notice"]

    by_id = {item["id"]: item for item in manifest["domains"]}
    forbidden = {
        "money_resources_value": "position.venus",
        "home_roots_private_life": "position.moon",
        "work_vocation_visibility": "position.saturn",
        "friendship_community_belonging": "position.uranus",
        "shadow_defenses_patterns": "position.pluto",
    }
    for domain_id, factor_id in forbidden.items():
        assert all(factor_id not in path["primary_factor_ids"] for path in by_id[domain_id]["legal_coverage_paths"])
    creativity = by_id["creativity_pleasure_aliveness"]["legal_coverage_paths"]
    assert next(path for path in creativity if "position.sun" in path["primary_factor_ids"])["authorized_scope"] == "vitality and aliveness"
    assert next(path for path in creativity if "position.venus" in path["primary_factor_ids"])["authorized_scope"] == "pleasure and values"
    body = by_id["body_energy_routine"]["legal_coverage_paths"]
    assert not any(path.get("placidus_house") == 12 for path in body)
    assert not any(claim_id.startswith("claim.house_ruler") and path["kind"] == "claim_anchored" for item in manifest["domains"] for path in item["legal_coverage_paths"] for claim_id in path["source_claim_ids"])
    friendship = by_id["friendship_community_belonging"]
    assert friendship["emphasis"] == "low"
    assert any(path["kind"] == "house_ruler_context" and path.get("placidus_house") == 11 for path in friendship["legal_coverage_paths"])


@pytest.mark.parametrize("candidate", [
    birth(),
    BirthData("1982-02-03T08:15:00", "America/New_York", 40.7128, -74.0060),
    BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333, time_uncertainty_minutes=240),
])
def test_v413_routing_shortcuts_stay_closed_across_distinct_and_house_withheld_charts(candidate):
    manifest = analyse_birth_chart(candidate, include_timing=False)["reader_domain_manifest"]
    by_id = {item["id"]: item for item in manifest["domains"]}
    forbidden = {
        "money_resources_value": "position.venus",
        "home_roots_private_life": "position.moon",
        "work_vocation_visibility": "position.saturn",
        "friendship_community_belonging": "position.uranus",
        "shadow_defenses_patterns": "position.pluto",
    }
    for domain_id, factor_id in forbidden.items():
        assert all(
            not (path["kind"] == "claim_anchored" and factor_id in path["primary_factor_ids"])
            for path in by_id[domain_id]["legal_coverage_paths"]
        )

    creativity = by_id["creativity_pleasure_aliveness"]["legal_coverage_paths"]
    assert all(
        set(path["primary_factor_ids"]).isdisjoint({"position.moon", "position.mars", "position.saturn"})
        for path in creativity if path["kind"] == "claim_anchored"
    )
    if candidate.time_uncertainty_minutes == 240:
        assert {tuple(path["primary_factor_ids"]) for path in creativity} == {("position.sun",), ("position.venus",)}
        body = by_id["body_energy_routine"]["legal_coverage_paths"]
        assert {tuple(path["primary_factor_ids"]) for path in body} == {("position.mars",), ("position.sun",)}


def test_v413_reader_architecture_does_not_change_legacy_audit_sidecar_plan():
    result = analyse_birth_chart(birth(), include_timing=False)
    plan = result["narrative_plan"]
    assert plan["sequence"] == "chart signature → differentiated themes → relevant areas → timing → integration"
    assert "reader_architecture" not in plan
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    assert '"reader_architecture"' not in handoff["audit_sidecar"]
    assert '"sequence": "chart signature → differentiated themes → relevant areas → timing → integration"' in handoff["audit_sidecar"]


def test_v413_prepared_signature_is_frozen_before_author_coverage_syntheses():
    author, _direct = build_author_bundle(birth(), include_timing=False)
    baseline = validate_premium_syntheses(birth(), author["reasoned_syntheses"], include_timing=False)
    ordinary = next(item for item in author["reasoned_syntheses"] if item["reasoning_class"] == "single_structural_factor")
    duplicate = dict(ordinary, id="reasoned.audit.duplicate.coverage")
    expanded = validate_premium_syntheses(birth(), [*author["reasoned_syntheses"], duplicate], include_timing=False)
    assert expanded["approved"]
    assert expanded["chart_signature"] == baseline["chart_signature"]
    assert expanded["prepared_chart_signature_sha256"] == baseline["prepared_chart_signature_sha256"]
    assert expanded["prepared_signature_synthesis_sha256"] == baseline["prepared_signature_synthesis_sha256"]
    assert expanded["narrative_plan"] == baseline["narrative_plan"]


def test_v413_complete_author_and_reviewer_contract_passes():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"], provenance["verification_errors"]
    final = validate_premium_narrative(reviewer_bundle(author, provenance), provenance, birth(), include_timing=False, prepared_handoff=handoff)
    assert final["approved"], final["verification_errors"]
    parsed = _parse_premium_narrative(author["draft_report"], provenance["reader_domain_manifest"])
    assert not parsed["errors"]
    assert len(parsed["sections"]) == 18
    assert len(paragraph_source_template(author["draft_report"], provenance["reader_domain_manifest"])) == len(author["paragraph_sources"])


def test_v413_fixed_reader_introduction_is_required_and_outside_interpretive_provenance():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    assert provenance["approved"], provenance["verification_errors"]

    parsed = _parse_premium_narrative(author["draft_report"], provenance["reader_domain_manifest"])
    assert not parsed["errors"]
    assert parsed["reader_introduction"]["text"] == PREMIUM_READER_INTRODUCTION
    introduction_hash = _canonical_hash(PREMIUM_READER_INTRODUCTION)
    assert introduction_hash not in {item["paragraph_sha256"] for item in author["paragraph_sources"]}
    assert all(
        introduction_hash not in section["paragraph_sha256s"]
        for section in [author["reader_sections"]["opening"], *author["reader_sections"]["domains"], author["reader_sections"]["integration"]]
    )
    assert len(parsed["sections"]) == 18
    assert sum(line.startswith("## ") for line in author["draft_report"].splitlines()) == 18

    titled = deepcopy(author)
    titled["draft_report"] = "# Leitura Premium Complete\n\n" + titled["draft_report"]
    titled["draft_report_sha256"] = _canonical_hash(titled["draft_report"])
    titled_result = validate_premium_author_bundle(birth(), titled, include_timing=False, prepared_handoff=handoff)
    assert titled_result["approved"], titled_result["verification_errors"]

    final = validate_premium_narrative(
        reviewer_bundle(author, provenance), provenance, birth(), include_timing=False, prepared_handoff=handoff,
    )
    assert final["approved"], final["verification_errors"]


@pytest.mark.parametrize(
    ("language", "introduction_key", "heading"),
    [("pt-BR", "pt", "### Como entrar nesta leitura"), ("en-US", "en", "### How to enter this reading")],
)
def test_v413_reader_introduction_is_selected_and_hashed_by_locale(language, introduction_key, heading):
    profile = LocalizationProfile(preferred_language=language)
    handoff = prepare_premium_handoff(birth(), profile, include_timing=False)
    expected = PREMIUM_READER_INTRODUCTIONS[introduction_key]
    assert handoff["reader_introduction"] == expected
    assert handoff["reader_introduction"].startswith(heading)
    assert handoff["reader_introduction_sha256"] == _canonical_hash(expected)
    rule = handoff["premium_handoff_contract"]["reader_section_rules"]["fixed_reader_introduction"]
    assert rule["sha256_by_language"][introduction_key] == _canonical_hash(expected)


def test_v413_english_introduction_passes_author_and_publication_end_to_end():
    profile = LocalizationProfile(preferred_language="en-US", current_country="US")
    handoff = prepare_premium_handoff(birth(), profile, include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False, profile=profile)
    assert author["draft_report"].startswith(PREMIUM_READER_INTRODUCTIONS["en"])

    provenance = validate_premium_author_bundle(
        birth(), author, profile=profile, include_timing=False, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    publication = validate_premium_narrative(
        reviewer_bundle(author, provenance), provenance, birth(), profile=profile,
        include_timing=False, prepared_handoff=handoff,
    )
    assert publication["approved"], publication["verification_errors"]


def test_v413_cross_locale_introduction_and_handoff_substitution_fail_closed():
    english_profile = LocalizationProfile(preferred_language="en-US", current_country="US")
    english_handoff = prepare_premium_handoff(birth(), english_profile, include_timing=False)
    portuguese_handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False, profile=english_profile)

    substituted_report = deepcopy(author)
    substituted_report["draft_report"] = substituted_report["draft_report"].replace(
        PREMIUM_READER_INTRODUCTIONS["en"], PREMIUM_READER_INTRODUCTIONS["pt"], 1,
    )
    substituted_report["draft_report_sha256"] = _canonical_hash(substituted_report["draft_report"])
    report_result = validate_premium_author_bundle(
        birth(), substituted_report, profile=english_profile, include_timing=False,
        prepared_handoff=english_handoff,
    )
    assert not report_result["approved"]
    assert "invalid_premium_reader_introduction" in report_result["verification_errors"]

    handoff_result = validate_premium_author_bundle(
        birth(), author, profile=english_profile, include_timing=False,
        prepared_handoff=portuguese_handoff,
    )
    assert not handoff_result["approved"]
    assert "authoritative_handoff_reader_introduction_mismatch" in handoff_result["verification_errors"]


def test_v413_self_consistent_reader_introduction_mutation_fails_authority():
    profile = LocalizationProfile(preferred_language="en-US", current_country="US")
    handoff = prepare_premium_handoff(birth(), profile, include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False, profile=profile)
    provenance = validate_premium_author_bundle(
        birth(), author, profile=profile, include_timing=False, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    reviewer = reviewer_bundle(author, provenance)
    altered = deepcopy(handoff)
    altered["reader_introduction"] += "\n\nForged product copy."
    altered["reader_introduction_sha256"] = _canonical_hash(altered["reader_introduction"])

    result = validate_premium_author_bundle(
        birth(), author, profile=profile, include_timing=False, prepared_handoff=altered,
    )
    assert not result["approved"]
    assert "invalid_authoritative_handoff_reader_introduction" in result["verification_errors"]
    assert "authoritative_handoff_reader_introduction_mismatch" in result["verification_errors"]
    publication = validate_premium_narrative(
        reviewer, provenance, birth(), profile=profile, include_timing=False,
        prepared_handoff=altered,
    )
    assert not publication["approved"]
    assert "invalid_authoritative_handoff_reader_introduction" in publication["verification_errors"]
    assert "authoritative_handoff_reader_introduction_mismatch" in publication["verification_errors"]


def test_v413_fixed_reader_introduction_rejects_missing_altered_and_extra_preamble_content():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)

    missing = deepcopy(author)
    missing["draft_report"] = missing["draft_report"].replace(PREMIUM_READER_INTRODUCTION + "\n\n", "", 1)
    missing["draft_report_sha256"] = _canonical_hash(missing["draft_report"])
    missing_result = validate_premium_author_bundle(birth(), missing, include_timing=False, prepared_handoff=handoff)
    assert not missing_result["approved"]
    assert "missing_premium_reader_introduction" in missing_result["verification_errors"]

    altered = deepcopy(author)
    altered["draft_report"] = altered["draft_report"].replace("Leia com abertura, mas também com liberdade.", "Leia sem liberdade.", 1)
    altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
    altered_result = validate_premium_author_bundle(birth(), altered, include_timing=False, prepared_handoff=handoff)
    assert not altered_result["approved"]
    assert "invalid_premium_reader_introduction" in altered_result["verification_errors"]

    extra = deepcopy(author)
    extra["draft_report"] = extra["draft_report"].replace(
        PREMIUM_READER_INTRODUCTION + "\n\n", PREMIUM_READER_INTRODUCTION + "\n\nProsa extra antes da abertura canônica.\n\n", 1,
    )
    extra["draft_report_sha256"] = _canonical_hash(extra["draft_report"])
    extra_result = validate_premium_author_bundle(birth(), extra, include_timing=False, prepared_handoff=handoff)
    assert not extra_result["approved"]
    assert "reader_prose_outside_canonical_section" in extra_result["verification_errors"]


def test_v413_heading_ownership_and_nonprose_escape_hatches_fail_closed():
    author, _direct = build_author_bundle(birth(), include_timing=False)
    manifest = analyse_birth_chart(birth(), include_timing=False)["reader_domain_manifest"]
    emotional_heading = next(item["heading"] for item in manifest["domains"] if item["id"] == "emotional_security")
    missing_heading = dict(author, draft_report=author["draft_report"].replace(f"## {emotional_heading}\n\n", "", 1))
    missing_heading["draft_report_sha256"] = _canonical_hash(missing_heading["draft_report"])
    assert "missing_reader_section_heading" in validate_premium_author_bundle(birth(), missing_heading, include_timing=False)["verification_errors"]

    duplicate_domain = deepcopy(author)
    duplicate_domain["reader_sections"]["domains"][1] = deepcopy(duplicate_domain["reader_sections"]["domains"][0])
    assert "duplicate_reader_domain_section" in validate_premium_author_bundle(birth(), duplicate_domain, include_timing=False)["verification_errors"]

    reused = deepcopy(author)
    reused["reader_sections"]["domains"][0]["paragraph_sha256s"].append(reused["reader_sections"]["opening"]["paragraph_sha256s"][0])
    errors = validate_premium_author_bundle(birth(), reused, include_timing=False)["verification_errors"]
    assert "reader_paragraph_owned_by_multiple_sections" in errors

    with_table = dict(author, draft_report=author["draft_report"].replace(f"## {emotional_heading}", f"## {emotional_heading}\n\n| hidden | claim |\n|---|---|\n| unsupported | prose |", 1))
    with_table["draft_report_sha256"] = _canonical_hash(with_table["draft_report"])
    assert "nonprose_content_inside_reader_section" in validate_premium_author_bundle(birth(), with_table, include_timing=False)["verification_errors"]

    attached_to_heading = dict(
        author,
        draft_report=author["draft_report"].replace(
            f"## {emotional_heading}", f"## {emotional_heading}\nUnsupported prose attached directly to a heading.", 1,
        ),
    )
    attached_to_heading["draft_report_sha256"] = _canonical_hash(attached_to_heading["draft_report"])
    assert "premium_heading_must_be_isolated" in validate_premium_author_bundle(birth(), attached_to_heading, include_timing=False)["verification_errors"]

    outside = dict(author, draft_report="Unsupported prose before the canonical opening.\n\n" + author["draft_report"])
    outside["draft_report_sha256"] = _canonical_hash(outside["draft_report"])
    assert "reader_prose_outside_canonical_section" in validate_premium_author_bundle(birth(), outside, include_timing=False)["verification_errors"]

    unknown = dict(author, draft_report=author["draft_report"].replace(f"## {emotional_heading}", "## Invented reader domain", 1))
    unknown["draft_report_sha256"] = _canonical_hash(unknown["draft_report"])
    assert "unknown_reader_section_heading" in validate_premium_author_bundle(birth(), unknown, include_timing=False)["verification_errors"]


def test_v413_short_prose_has_no_word_or_paragraph_quota():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    section = next(item for item in author["reader_sections"]["domains"] if item["domain_id"] == "emotional_security")
    old_hash = section["paragraph_sha256s"][0]
    old_text = next(item["text"] for item in _parse_premium_narrative(author["draft_report"], analyse_birth_chart(birth(), include_timing=False)["reader_domain_manifest"])["prose"] if item["sha256"] == old_hash)
    new_text = "Brief, specific, authorised emotional regulation."
    new_hash = _canonical_hash(new_text)
    changed = deepcopy(author)
    changed["draft_report"] = changed["draft_report"].replace(old_text, new_text, 1)
    changed["draft_report_sha256"] = _canonical_hash(changed["draft_report"])
    next(item for item in changed["reader_sections"]["domains"] if item["domain_id"] == "emotional_security")["paragraph_sha256s"] = [new_hash]
    source = next(item for item in changed["paragraph_sources"] if item["paragraph_sha256"] == old_hash)
    source["paragraph_sha256"] = new_hash
    result = validate_premium_author_bundle(birth(), changed, include_timing=False, prepared_handoff=handoff)
    assert result["approved"], result["verification_errors"]


def test_v413_unavailable_notice_is_exact_nonprose_and_cannot_be_expanded():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    domain = next(item for item in provenance["reader_domain_manifest"]["domains"] if item["id"] == "active_life_chapter")
    section = next(item for item in author["reader_sections"]["domains"] if item["domain_id"] == domain["id"])
    assert section["paragraph_sha256s"] == []
    assert domain["unavailable_notice"]["text"] in author["draft_report"]

    altered = dict(author, draft_report=author["draft_report"].replace(domain["unavailable_notice"]["text"], domain["unavailable_notice"]["text"] + " Unsupported addition.", 1))
    altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
    errors = validate_premium_author_bundle(birth(), altered, include_timing=False, prepared_handoff=handoff)["verification_errors"]
    assert "prose_in_unavailable_reader_domain:active_life_chapter" in errors

    orphan = deepcopy(author)
    orphan["paragraph_sources"].append({"paragraph_sha256": domain["unavailable_notice"]["sha256"], "synthesis_ids": [], "claim_ids": [], "timing_ids": []})
    assert "orphan_paragraph_source_map" in validate_premium_author_bundle(birth(), orphan, include_timing=False, prepared_handoff=handoff)["verification_errors"]


def test_v413_unavailable_section_rejects_every_extra_physical_block():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    domain = next(item for item in provenance["reader_domain_manifest"]["domains"] if item["id"] == "active_life_chapter")
    notice = domain["unavailable_notice"]["text"]
    payloads = {
        "h1": "# Added title",
        "h3": "### Added subheading",
        "separator": "---",
        "unknown_metadata": "<!-- author metadata -->",
        "list": "- Added item",
        "table": "| Added | data |\n|---|---|\n| x | y |",
        "duplicate_notice": notice,
        "altered_notice": notice[:-1] + "!",
        "ordinary_prose": "Additional ordinary prose is not permitted here.",
    }
    for label, extra in payloads.items():
        altered = deepcopy(author)
        altered["draft_report"] = altered["draft_report"].replace(notice, notice + "\n\n" + extra, 1)
        altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
        result = validate_premium_author_bundle(birth(), altered, include_timing=False, prepared_handoff=handoff)
        assert not result["approved"], (label, result["verification_errors"])


def test_v413_publication_guard_recomputes_authoritative_prepared_identities():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    mutations = {
        "chart_signature_body": lambda value: value["chart_signature"].update(mode="forged"),
        "prepared_signature_hash": lambda value: value.update(prepared_chart_signature_sha256="forged"),
        "prepared_synthesis_hash": lambda value: value.update(prepared_signature_synthesis_sha256="forged"),
        "manifest_body_and_hash": lambda value: (
            value["reader_domain_manifest"]["rules"].update(forged=True),
            value.update(reader_domain_manifest_sha256=_canonical_hash(value["reader_domain_manifest"])),
        ),
    }
    for label, mutate in mutations.items():
        altered_provenance = deepcopy(provenance)
        mutate(altered_provenance)
        result = validate_premium_narrative(reviewer_bundle(author, altered_provenance), altered_provenance, birth(), include_timing=False, prepared_handoff=handoff)
        assert not result["approved"], (label, result["verification_errors"])


def test_v413_publication_guard_rejects_complete_lineage_substitution_against_original_handoff():
    original_handoff = prepare_premium_handoff(birth(), include_timing=False)
    substituted_birth = BirthData("1982-02-03T08:15:00", "America/New_York", 40.7128, -74.0060)
    substituted_handoff = prepare_premium_handoff(substituted_birth, include_timing=False)
    substituted_author, _direct = build_author_bundle(substituted_birth, include_timing=False)
    substituted_provenance = validate_premium_author_bundle(
        substituted_birth, substituted_author, include_timing=False, prepared_handoff=substituted_handoff,
    )
    assert substituted_provenance["approved"], substituted_provenance["verification_errors"]

    result = validate_premium_narrative(
        reviewer_bundle(substituted_author, substituted_provenance),
        substituted_provenance,
        substituted_birth,
        include_timing=False,
        prepared_handoff=original_handoff,
    )
    assert "authoritative_handoff_packet_id_mismatch" in result["verification_errors"]


def test_v413_cli_author_guard_authenticates_the_supplied_prepared_handoff(monkeypatch, capsys):
    candidate_a = birth()
    candidate_b = BirthData("1982-02-03T08:15:00", "America/New_York", 40.7128, -74.0060)
    handoff_a = prepare_premium_handoff(candidate_a, include_timing=False)
    handoff_b = prepare_premium_handoff(candidate_b, include_timing=False)
    author_a, _direct = build_author_bundle(candidate_a, include_timing=False)
    author_b, _direct = build_author_bundle(candidate_b, include_timing=False)

    def cli_author_validation(candidate, author, handoff):
        payloads = {
            "input.json": {
                "local_datetime": candidate.local_datetime,
                "timezone_name": candidate.timezone_name,
                "latitude": candidate.latitude,
                "longitude": candidate.longitude,
            },
            "author.json": author,
            "handoff.json": handoff,
        }
        monkeypatch.setattr(cli, "_load", lambda path: payloads[path])
        monkeypatch.setattr(sys, "argv", [
            "astrology-skill", "input.json", "--premium-stage", "validate-synthesis",
            "--premium-handoff", "handoff.json", "--premium-synthesis", "author.json", "--no-timing",
        ])
        assert cli.main() == 0
        return json.loads(capsys.readouterr().out)

    assert cli_author_validation(candidate_a, author_a, handoff_a)["approved"]
    assert cli_author_validation(candidate_b, author_b, handoff_b)["approved"]
    assert not cli_author_validation(candidate_b, author_b, handoff_a)["approved"]
    assert not cli_author_validation(candidate_a, author_a, {
        "preparation_parameters": {"effective_as_of": None, "horizon_days": 366, "include_timing": False},
    })["approved"]


def test_v413_publication_guard_rejects_mutated_authoritative_handoff_bodies_and_parameters():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=handoff)
    reviewer = reviewer_bundle(author, provenance)
    mutations = {
        "signature": lambda value: (
            value["chart_signature"].update(mode="forged"),
            value.update(prepared_chart_signature_sha256=_canonical_hash(value["chart_signature"])),
        ),
        "synthesis_basis": lambda value: (
            value["prepared_signature_syntheses"][0].update(observation="forged"),
            value.update(prepared_signature_synthesis_sha256=_canonical_hash(value["prepared_signature_syntheses"])),
        ),
        "manifest": lambda value: (
            value["reader_domain_manifest"]["rules"].update(forged=True),
            value.update(reader_domain_manifest_sha256=_canonical_hash(value["reader_domain_manifest"])),
        ),
        "reader_introduction": lambda value: value.update(reader_introduction="forged product copy"),
        "packet": lambda value: value.update(packet_id="forged"),
        "effective_as_of": lambda value: value["preparation_parameters"].update(effective_as_of="2026-08-27T00:00:00+00:00"),
    }
    for label, mutate in mutations.items():
        altered = deepcopy(handoff)
        mutate(altered)
        result = validate_premium_narrative(
            reviewer, provenance, birth(), include_timing=False, prepared_handoff=altered,
        )
        assert any(error.startswith("authoritative_handoff_") for error in result["verification_errors"]), (label, result["verification_errors"])


def test_v413_preparation_materializes_effective_as_of_into_packet_lineage():
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=None, horizon_days=1)
    effective_as_of = datetime.fromisoformat(handoff["preparation_parameters"]["effective_as_of"])
    replay = prepare_premium_handoff(birth(), include_timing=True, as_of=effective_as_of, horizon_days=1)
    assert replay["packet_id"] == handoff["packet_id"]


def test_v413_publication_guard_binds_timed_parameters_and_runtime_profile():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    provenance = validate_premium_author_bundle(
        birth(), author, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    assert validate_premium_author_bundle(
        birth(), author, include_timing=True, horizon_days=45, prepared_handoff=handoff,
    )["approved"]
    reviewer = reviewer_bundle(author, provenance)
    assert validate_premium_narrative(reviewer, provenance, birth(), as_of=as_of, horizon_days=45, prepared_handoff=handoff)["approved"]
    assert validate_premium_narrative(reviewer, provenance, birth(), horizon_days=45, prepared_handoff=handoff)["approved"]

    mutations = {
        "effective_as_of": (lambda value: value["preparation_parameters"].update(effective_as_of="2026-08-28T00:00:00+00:00"), datetime(2026, 8, 28, tzinfo=timezone.utc), 45, True),
        "horizon_days": (lambda value: value["preparation_parameters"].update(horizon_days=46), as_of, 46, True),
        "include_timing": (lambda value: value["preparation_parameters"].update(include_timing=False), as_of, 45, False),
    }
    for label, (mutate, runtime_as_of, horizon_days, include_timing) in mutations.items():
        altered = deepcopy(handoff)
        mutate(altered)
        author_result = validate_premium_author_bundle(
            birth(), author, as_of=runtime_as_of, horizon_days=horizon_days,
            include_timing=include_timing, prepared_handoff=altered,
        )
        assert not author_result["approved"], (label, author_result["verification_errors"])
        result = validate_premium_narrative(
            reviewer, provenance, birth(), as_of=runtime_as_of, horizon_days=horizon_days,
            include_timing=include_timing, prepared_handoff=altered,
        )
        assert not result["approved"], (label, result["verification_errors"])

    profile = LocalizationProfile(preferred_language="en-US", current_country="US")
    author_profile_result = validate_premium_author_bundle(
        birth(), author, profile=profile, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert not author_profile_result["approved"], author_profile_result["verification_errors"]
    profile_result = validate_premium_narrative(
        reviewer, provenance, birth(), profile=profile,
        as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert not profile_result["approved"], profile_result["verification_errors"]


def test_v413_wrong_domain_anchor_direct_claim_and_nonrelational_layers_fail():
    author, direct = build_author_bundle(birth(), include_timing=False, add_direct_claim=True)
    money_source = _source_for_section(author, "money_resources_value")
    identity_source = _source_for_section(author, "identity_presence")
    wrong = deepcopy(author)
    next(item for item in wrong["paragraph_sources"] if item["paragraph_sha256"] == money_source["paragraph_sha256"])["synthesis_ids"] = list(identity_source["synthesis_ids"])
    assert "missing_reader_domain_coverage:money_resources_value" in validate_premium_author_bundle(birth(), wrong, include_timing=False)["verification_errors"]

    direct_only = deepcopy(author)
    row = next(item for item in direct_only["paragraph_sources"] if item["paragraph_sha256"] == money_source["paragraph_sha256"])
    row["synthesis_ids"], row["claim_ids"] = [], [direct["id"]]
    assert "missing_reader_domain_coverage:money_resources_value" in validate_premium_author_bundle(birth(), direct_only, include_timing=False)["verification_errors"]

    single = next(item for item in author["reasoned_syntheses"] if item["reasoning_class"] == "single_structural_factor")["id"]
    weak_layers = deepcopy(author)
    for key in ("opening", "integration"):
        paragraph_hash = weak_layers["reader_sections"][key]["paragraph_sha256s"][0]
        next(item for item in weak_layers["paragraph_sources"] if item["paragraph_sha256"] == paragraph_hash)["synthesis_ids"] = [single]
    errors = validate_premium_author_bundle(birth(), weak_layers, include_timing=False)["verification_errors"]
    assert "reader_opening_requires_relational_synthesis" in errors
    assert "reader_integration_requires_relational_synthesis" in errors


def test_v413_every_domain_paragraph_requires_its_own_legal_path():
    author, _direct = build_author_bundle(birth(), include_timing=False)
    manifest = analyse_birth_chart(birth(), include_timing=False)["reader_domain_manifest"]
    money = next(item for item in manifest["domains"] if item["id"] == "money_resources_value")
    following = manifest["domains"][money["position"]]
    identity_source = _source_for_section(author, "identity_presence")
    extra_text = "This extra paragraph tries to import a different domain's otherwise authorised synthesis."
    extra_hash = _canonical_hash(extra_text)
    altered = deepcopy(author)
    altered["draft_report"] = altered["draft_report"].replace(
        f"## {following['heading']}", f"{extra_text}\n\n## {following['heading']}", 1,
    )
    altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
    next(item for item in altered["reader_sections"]["domains"] if item["domain_id"] == money["id"])["paragraph_sha256s"].append(extra_hash)
    altered["paragraph_sources"].append({
        "paragraph_sha256": extra_hash,
        "synthesis_ids": list(identity_source["synthesis_ids"]),
        "claim_ids": [],
        "timing_ids": [],
    })
    errors = validate_premium_author_bundle(birth(), altered, include_timing=False)["verification_errors"]
    assert "reader_domain_paragraph_outside_legal_path:money_resources_value" in errors


def test_v413_independently_built_venus_synthesis_cannot_cover_money():
    author, _direct = build_author_bundle(birth(), include_timing=False)
    result = analyse_birth_chart(birth(), include_timing=False)
    venus = next(item for item in result["claims"] if item["id"].startswith("claim.position.venus.") and item["status"] == "allowed")
    independently_built = ReasonedSynthesis(
        id="reasoned.adversarial.venus_only", observation=venus["statement"], primary_factors=list(venus["evidence"]),
        modifiers=[], counterweights=[], reasoning_class="single_structural_factor", confidence_within_astrological_model="light",
        possible_expressions=[venus["statement"]], alternative_reading="", prohibited_extensions=[], source_claim_ids=[venus["id"]],
        source_motif_ids=list(venus["authorized_motifs"]), composition_operations=["contextualization"],
        derived_propositions=[{"text": venus["statement"], "sources": [venus["id"]]}],
    )
    altered = deepcopy(author)
    altered["reasoned_syntheses"].append(asdict(independently_built))
    money_source = _source_for_section(altered, "money_resources_value")
    next(item for item in altered["paragraph_sources"] if item["paragraph_sha256"] == money_source["paragraph_sha256"])["synthesis_ids"] = [independently_built.id]
    judged = validate_premium_syntheses(birth(), altered["reasoned_syntheses"], include_timing=False)
    assert judged["approved"]
    altered["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]
    result = validate_premium_author_bundle(birth(), altered, include_timing=False)
    assert not result["approved"]
    assert "missing_reader_domain_coverage:money_resources_value" in result["verification_errors"]


def test_v413_timing_row_must_link_to_the_cited_natal_timing_synthesis():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    provenance = validate_premium_author_bundle(
        birth(), author, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    active_source = _source_for_section(author, "active_life_chapter")
    cited = next(item for item in author["reasoned_syntheses"] if item["id"] == active_source["synthesis_ids"][0])
    unrelated = next(item for item in provenance["timing_evidence_ids"] if item not in cited["primary_factors"])
    altered = deepcopy(author)
    next(item for item in altered["paragraph_sources"] if item["paragraph_sha256"] == active_source["paragraph_sha256"])["timing_ids"] = [unrelated]
    errors = validate_premium_author_bundle(
        birth(), altered, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )["verification_errors"]
    assert "reader_timing_source_not_linked_to_cited_synthesis" in errors
    assert "missing_reader_domain_coverage:active_life_chapter" in errors


def test_v413_timing_path_rejects_unrelated_admitted_id_padded_into_synthesis_and_row():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    provenance = validate_premium_author_bundle(
        birth(), author, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    active_source = _source_for_section(author, "active_life_chapter")
    cited_id = active_source["synthesis_ids"][0]
    cited = next(item for item in author["reasoned_syntheses"] if item["id"] == cited_id)
    unrelated = next(item for item in provenance["timing_evidence_ids"] if item not in cited["primary_factors"])
    altered = deepcopy(author)
    altered_cited = next(item for item in altered["reasoned_syntheses"] if item["id"] == cited_id)
    altered_cited["primary_factors"].append(unrelated)
    next(item for item in altered["paragraph_sources"] if item["paragraph_sha256"] == active_source["paragraph_sha256"])["timing_ids"].append(unrelated)
    judged = validate_premium_syntheses(birth(), altered["reasoned_syntheses"], include_timing=True, as_of=as_of, horizon_days=45)
    assert judged["approved"]
    altered["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]
    result = validate_premium_author_bundle(
        birth(), altered, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert not result["approved"], result["verification_errors"]


def test_v413_timing_domain_accepts_complete_set_of_multiple_satisfied_paths():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    provenance = validate_premium_author_bundle(
        birth(), author, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    active_domain = next(item for item in provenance["reader_domain_manifest"]["domains"] if item["id"] == "active_life_chapter")
    grouped = {}
    for path in active_domain["legal_coverage_paths"]:
        key = (tuple(path["source_claim_ids"]), tuple(factor for factor in path["primary_factor_ids"] if not factor.startswith("timing.")))
        grouped.setdefault(key, []).append(path)
    first_path, second_path = next(paths[:2] for paths in grouped.values() if len(paths) >= 2)
    natal_factors = [factor for factor in first_path["primary_factor_ids"] if not factor.startswith("timing.")]
    timing_ids = [*first_path["timing_ids"], *second_path["timing_ids"]]
    claim = next(item for item in provenance["allowed_claims"] if item["id"] == first_path["source_claim_ids"][0])

    active_source = _source_for_section(author, "active_life_chapter")
    cited_id = active_source["synthesis_ids"][0]
    altered = deepcopy(author)
    cited = next(item for item in altered["reasoned_syntheses"] if item["id"] == cited_id)
    cited.update(
        primary_factors=[*natal_factors, *timing_ids],
        source_claim_ids=list(first_path["source_claim_ids"]),
        source_motif_ids=list(claim["authorized_motifs"]),
        composition_operations=list(first_path["composition_operations"]),
        reasoning_class="natal_timing_interaction",
        derived_propositions=[{"text": cited["observation"], "sources": list(first_path["source_claim_ids"])}],
    )
    next(item for item in altered["paragraph_sources"] if item["paragraph_sha256"] == active_source["paragraph_sha256"])["timing_ids"] = timing_ids
    judged = validate_premium_syntheses(birth(), altered["reasoned_syntheses"], include_timing=True, as_of=as_of, horizon_days=45)
    assert judged["approved"], judged["reasoned_synthesis"]
    altered["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]

    result = validate_premium_author_bundle(
        birth(), altered, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    assert result["approved"], result["verification_errors"]


def test_v413_timing_domain_rejects_partial_rows_absent_ids_and_wrong_natal_ancestry():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff = prepare_premium_handoff(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    author, _direct = build_author_bundle(birth(), include_timing=True, as_of=as_of, horizon_days=45)
    provenance = validate_premium_author_bundle(
        birth(), author, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
    )
    active_domain = next(item for item in provenance["reader_domain_manifest"]["domains"] if item["id"] == "active_life_chapter")
    paths_by_natal = {}
    for path in active_domain["legal_coverage_paths"]:
        key = (tuple(path["source_claim_ids"]), tuple(factor for factor in path["primary_factor_ids"] if not factor.startswith("timing.")))
        paths_by_natal.setdefault(key, []).append(path)
    first_path, second_path = next(paths[:2] for paths in paths_by_natal.values() if len(paths) >= 2)
    wrong_natal_path = next(path for path in active_domain["legal_coverage_paths"] if set(path["source_claim_ids"]).isdisjoint(first_path["source_claim_ids"]))
    active_source = _source_for_section(author, "active_life_chapter")
    cited_id = active_source["synthesis_ids"][0]
    claims = {item["id"]: item for item in provenance["allowed_claims"]}

    def author_with_paths(paths, row_timing_ids, extra_timing_ids=()):
        altered = deepcopy(author)
        cited = next(item for item in altered["reasoned_syntheses"] if item["id"] == cited_id)
        source_claim_ids = list(dict.fromkeys(claim_id for path in paths for claim_id in path["source_claim_ids"]))
        natal_factors = list(dict.fromkeys(
            factor for path in paths for factor in path["primary_factor_ids"] if not factor.startswith("timing.")
        ))
        timing_ids = list(dict.fromkeys(
            [timing_id for path in paths for timing_id in path["timing_ids"]] + list(extra_timing_ids)
        ))
        cited.update(
            primary_factors=[*natal_factors, *timing_ids], source_claim_ids=source_claim_ids,
            source_motif_ids=list(dict.fromkeys(motif for claim_id in source_claim_ids for motif in claims[claim_id]["authorized_motifs"])),
            composition_operations=list(first_path["composition_operations"]), reasoning_class="natal_timing_interaction",
            derived_propositions=[{"text": cited["observation"], "sources": source_claim_ids}],
        )
        next(item for item in altered["paragraph_sources"] if item["paragraph_sha256"] == active_source["paragraph_sha256"])["timing_ids"] = list(row_timing_ids)
        judged = validate_premium_syntheses(birth(), altered["reasoned_syntheses"], include_timing=True, as_of=as_of, horizon_days=45)
        assert judged["approved"], judged["reasoned_synthesis"]
        altered["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]
        return validate_premium_author_bundle(
            birth(), altered, include_timing=True, as_of=as_of, horizon_days=45, prepared_handoff=handoff,
        )

    timing_one, timing_two = first_path["timing_ids"][0], second_path["timing_ids"][0]
    partial = author_with_paths([first_path, second_path], [timing_one])
    assert not partial["approved"]
    assert "missing_reader_domain_coverage:active_life_chapter" in partial["verification_errors"]

    absent_from_synthesis = author_with_paths([first_path], [timing_one, timing_two])
    assert not absent_from_synthesis["approved"]
    assert "reader_timing_source_not_linked_to_cited_synthesis" in absent_from_synthesis["verification_errors"]

    wrong_natal = author_with_paths(
        [wrong_natal_path], [wrong_natal_path["timing_ids"][0], timing_one], extra_timing_ids=[timing_one],
    )
    assert not wrong_natal["approved"]
    assert "missing_reader_domain_coverage:active_life_chapter" in wrong_natal["verification_errors"]


@pytest.mark.parametrize("preamble", [
    "# First title\n\n# Second title",
    "---\n\n---",
])
def test_v413_preopening_preamble_rejects_duplicate_titles_and_separators(preamble):
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    author, _direct = build_author_bundle(birth(), include_timing=False)
    baseline = validate_premium_author_bundle(
        birth(), author, include_timing=False, prepared_handoff=handoff,
    )
    assert baseline["approved"], baseline["verification_errors"]
    altered = deepcopy(author)
    altered["draft_report"] = preamble + "\n\n" + altered["draft_report"]
    altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
    result = validate_premium_author_bundle(
        birth(), altered, include_timing=False, prepared_handoff=handoff,
    )
    assert not result["approved"], result["verification_errors"]
    assert "invalid_premium_document_preamble" in result["verification_errors"]
    assert "missing_authoritative_prepared_handoff" not in result["verification_errors"]


def test_v413_handoff_12_hashes_and_contract_are_fail_closed():
    handoff = prepare_premium_handoff(birth(), include_timing=False)
    assert PREMIUM_HANDOFF_CONTRACT_VERSION == "1.3"
    assert handoff["premium_handoff_contract_version"] == "1.3"
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        assert handoff[field]
    introduction_rule = handoff["premium_handoff_contract"]["reader_section_rules"]["fixed_reader_introduction"]
    assert introduction_rule["sha256_by_language"]["pt"] == _canonical_hash(PREMIUM_READER_INTRODUCTION)
    assert introduction_rule["sha256_by_language"]["en"] == _canonical_hash(PREMIUM_READER_INTRODUCTIONS["en"])
    assert introduction_rule["selection"] == "reader_domain_manifest_locale"
    assert introduction_rule["provenance"] == "fixed_product_copy_excluded_from_paragraph_sources_and_reader_section_ownership"
    author, _direct = build_author_bundle(birth(), include_timing=False)
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        altered = dict(author, **{field: "bad"})
        assert f"{field}_mismatch" in validate_premium_author_bundle(birth(), altered, include_timing=False)["verification_errors"]
    legacy = dict(author, premium_handoff_contract_version="1.2")
    assert "premium_handoff_contract_version_mismatch" in validate_premium_author_bundle(birth(), legacy, include_timing=False)["verification_errors"]


def test_v413_runtime_instructions_require_whole_person_scope_and_review():
    author = humanization_instructions("en-US")
    reviewer = humanization_verifier_instructions("en-US")
    for text in ("whole-chart opening", "16 canonical headings", "authorized_scope", "low emphasis", "deterministic notice", "prepared ChartSignature"):
        assert text in author
    for text in ("all three layers", "superficial domain", "authorized_scope", "supporting factor", "Low emphasis", "deterministic unavailable notice"):
        assert text in reviewer


def test_v413_humanisation_instructions_preserve_distinct_authorised_depth():
    author = humanization_instructions("en-US")
    reviewer = humanization_verifier_instructions("en-US")
    for text in (
        "Humanisation changes expression; it does not reduce what the chart understands",
        "never a one-paragraph default",
        "legal house-5 route",
        "legal house-6 route",
        "complete nodal axis",
        "several legal natal-timing interactions",
    ):
        assert text in author
    for text in (
        "distinct authorised mechanisms were developed before prose was compressed",
        "generic self-help",
        "Cut padding, not depth",
        "entire nodal axis",
        "gendered wording when none was supplied",
        "consistently in the requested language",
        "memorable synthesis rather than a summary",
    ):
        assert text in reviewer
