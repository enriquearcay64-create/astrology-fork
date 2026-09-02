from __future__ import annotations

from copy import deepcopy

import pytest

import astrology.pipeline as pipeline
from astrology.models import BirthData, LocalizationProfile
from tests.v414_helpers import build_author_bundle_v14, reviewer_bundle_v14


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def _approved_rich_v14(profile=None):
    handoff = pipeline.prepare_premium_handoff(birth(), profile, include_timing=False)
    author, _ = build_author_bundle_v14(birth(), include_timing=False, profile=profile)
    provenance = pipeline.validate_premium_author_bundle(
        birth(), author, profile, include_timing=False, prepared_handoff=handoff,
    )
    assert provenance["approved"], provenance["verification_errors"]
    return handoff, author, provenance


def test_v414_versions_and_canonical_payload_are_closed():
    handoff = pipeline.prepare_premium_handoff(birth(), include_timing=False)
    assert handoff["premium_handoff_contract_version"] == "1.4"
    assert handoff["premium_handoff_contract"]["version"] == "1.4"
    assert pipeline.canonical_narrative_block_payload(
        "paragraph", "  first  \r\n   second  ",
    ) == {"kind": "paragraph", "content": "first\nsecond"}
    assert pipeline.canonical_narrative_block_payload(
        "list_item", "item\n  continuation", "unordered",
    ) == {"kind": "list_item", "list_style": "unordered", "content": "item\ncontinuation"}
    assert pipeline.canonical_narrative_block_payload("subheading", "  A lens ") == {
        "kind": "subheading", "content": "A lens",
    }
    with pytest.raises(ValueError):
        pipeline.canonical_narrative_block_payload("table", "not allowed")


@pytest.mark.parametrize("profile", [None, LocalizationProfile(preferred_language="en-US")])
def test_v414_parser_recognizes_paragraphs_lists_multiline_items_and_h3(profile):
    author, meta = build_author_bundle_v14(birth(), include_timing=False, profile=profile)
    parsed = pipeline._parse_premium_narrative(author["draft_report"], meta["manifest"])
    assert parsed["errors"] == []
    identity = parsed["sections"]["identity_presence"]
    assert [item["kind"] for item in identity["authored"]] == ["subheading", "paragraph", "list_item", "list_item"]
    assert identity["authored"][2]["list_style"] == "unordered"
    assert identity["authored"][3]["list_style"] == "ordered"
    assert len(identity["subheadings"]) == 1
    assert len(identity["prose"]) == 3
    assert all(item["kind"] != "subheading" for item in parsed["eligible"])


def test_v414_attached_bullet_is_split_while_v13_keeps_historical_absorption():
    author, meta = build_author_bundle_v14(birth(), include_timing=False, rich=False)
    manifest = meta["manifest"]
    first_text = next(
        item["text"] for item in pipeline._parse_premium_narrative_v13(author["draft_report"], manifest)["sections"]["identity_presence"]["prose"]
    )
    attached = author["draft_report"].replace(first_text, first_text + "\n- attached item", 1)
    new_parser = pipeline._parse_premium_narrative(attached, manifest)
    assert new_parser["errors"] == []
    identity = new_parser["sections"]["identity_presence"]["prose"]
    assert [item["kind"] for item in identity] == ["paragraph", "list_item"]
    legacy_parser = pipeline._parse_premium_narrative_v13(attached, manifest)
    assert legacy_parser["errors"] == []
    assert len(legacy_parser["sections"]["identity_presence"]["prose"]) == 1
    assert "attached item" in legacy_parser["sections"]["identity_presence"]["prose"][0]["text"]


@pytest.mark.parametrize(
    "bad_fragment, expected",
    [
        ("#### H4", "prohibited_narrative_h4_plus"),
        ("| a | b |\n| --- | --- |", "prohibited_narrative_table"),
        ("> quoted", "prohibited_narrative_blockquote"),
        ("---", "prohibited_narrative_separator"),
        ("metadata: internal", "prohibited_narrative_metadata"),
        ("<div>html</div>", "prohibited_narrative_html_block"),
        ("```\ncode\n```", "prohibited_narrative_code_fence"),
    ],
)
def test_v414_parser_rejects_forbidden_markdown(bad_fragment, expected):
    author, meta = build_author_bundle_v14(birth(), include_timing=False, rich=False)
    report = author["draft_report"] + "\n\n" + bad_fragment
    parsed = pipeline._parse_premium_narrative(report, meta["manifest"])
    assert expected in parsed["errors"]


def test_v414_nested_list_and_sourced_h3_constraints_fail_closed():
    handoff, author, meta = _approved_rich_v14()
    nested = deepcopy(author)
    nested["draft_report"] = nested["draft_report"].replace(
        "- Uma escolha concreta pode tornar este mecanismo mais visível.\n  A continuação permanece parte do mesmo item.",
        "- Uma escolha concreta pode tornar este mecanismo mais visível.\n  - nested item\n  A continuação permanece parte do mesmo item.",
        1,
    )
    nested["draft_report_sha256"] = pipeline._canonical_hash(nested["draft_report"])
    result = pipeline.validate_premium_author_bundle(
        birth(), nested, include_timing=False, prepared_handoff=handoff,
    )
    assert "prohibited_narrative_nested_list" in result["verification_errors"]

    direct = deepcopy(author)
    allowed_claim = next(item for item in pipeline.analyse_birth_chart(birth(), include_timing=False)["claims"] if item["status"] == "allowed")
    h3_hash = next(item["narrative_block_sha256"] for item in direct["narrative_block_sources"] if item["narrative_block_sha256"] in {
        block["narrative_block_sha256"] for block in pipeline._parse_premium_narrative(direct["draft_report"], meta["reader_domain_manifest"])["subheadings"]
    })
    row = next(item for item in direct["narrative_block_sources"] if item["narrative_block_sha256"] == h3_hash)
    row["synthesis_ids"] = []
    row["claim_ids"] = [allowed_claim["id"]]
    direct_result = pipeline.validate_premium_author_bundle(
        birth(), direct, include_timing=False, prepared_handoff=handoff,
    )
    assert "subheading_requires_synthesis_source" in direct_result["verification_errors"]


def test_v414_h3_without_child_and_unavailable_expansion_are_rejected():
    handoff, author, meta = _approved_rich_v14()
    parsed = pipeline._parse_premium_narrative(author["draft_report"], meta["reader_domain_manifest"])
    h3 = parsed["subheadings"][0]["content"]
    no_child = author["draft_report"].replace(
        f"### {h3}\n\nThis is a distinct reader-facing treatment for Identidade central e presença within the authorised scope of its chart-specific path.\n\n",
        f"### {h3}\n\n",
        1,
    ).replace(
        "- Uma escolha concreta pode tornar este mecanismo mais visível.\n  A continuação permanece parte do mesmo item.\n\n",
        "",
        1,
    ).replace(
        "2. Outra possibilidade é observar como essa tensão muda quando o contexto muda.\n\n",
        "",
        1,
    )
    no_child_parsed = pipeline._parse_premium_narrative(no_child, meta["reader_domain_manifest"])
    assert "subheading_requires_child_narrative_block" in no_child_parsed["errors"]

    unavailable = next(item for item in meta["reader_domain_manifest"]["domains"] if item["availability"] != "available")
    expanded = author["draft_report"].replace(
        unavailable["unavailable_notice"]["text"],
        unavailable["unavailable_notice"]["text"] + "\n\nThis additional block is not permitted.",
        1,
    )
    expanded_result = pipeline.validate_premium_author_bundle(
        birth(), dict(author, draft_report=expanded, draft_report_sha256=pipeline._canonical_hash(expanded)),
        include_timing=False, prepared_handoff=handoff,
    )
    assert any("prose_in_unavailable_reader_domain" in item for item in expanded_result["verification_errors"])


def test_v414_sourced_h3_never_counts_as_domain_coverage():
    handoff, author, _meta = _approved_rich_v14()
    provenance = pipeline.validate_premium_author_bundle(
        birth(), author, include_timing=False, prepared_handoff=handoff,
    )
    parsed = pipeline._parse_premium_narrative(author["draft_report"], provenance["reader_domain_manifest"])
    parsed["sections"]["identity_presence"]["prose"] = []
    errors = pipeline._validate_reader_domain_coverage(
        parsed,
        author["reader_sections"],
        author["narrative_block_sources"],
        provenance["approved_reasoned_syntheses"],
        provenance["reader_domain_manifest"],
    )
    assert "missing_reader_domain_coverage:identity_presence" in errors


def test_v414_exact_shape_rejects_legacy_fields_and_unsourced_bullet():
    handoff, author, _meta = _approved_rich_v14()
    legacy = dict(author)
    legacy["paragraph_sources"] = []
    result = pipeline.validate_premium_author_bundle(
        birth(), legacy, include_timing=False, prepared_handoff=handoff,
    )
    assert "legacy_paragraph_fields_not_allowed_in_v14" in result["verification_errors"]
    assert "invalid_premium_handoff_author_bundle_shape" in result["verification_errors"]

    unsourced = deepcopy(author)
    list_hash = next(row["narrative_block_sha256"] for row in unsourced["narrative_block_sources"] if row["narrative_block_sha256"] != "" and row["narrative_block_sha256"] in {
        block["narrative_block_sha256"]
        for block in pipeline._parse_premium_narrative(unsourced["draft_report"], _meta["reader_domain_manifest"])["eligible"]
        if block["kind"] == "list_item"
    })
    unsourced["narrative_block_sources"] = [row for row in unsourced["narrative_block_sources"] if row["narrative_block_sha256"] != list_hash]
    result = pipeline.validate_premium_author_bundle(
        birth(), unsourced, include_timing=False, prepared_handoff=handoff,
    )
    assert "narrative_block_without_source_map" in result["verification_errors"]


def test_v414_public_dispatch_requires_authoritative_handoff_and_rejects_cross_version():
    author, _meta = build_author_bundle_v14(birth(), include_timing=False)
    missing = pipeline.validate_premium_author_bundle(birth(), author, include_timing=False)
    assert missing["verification_errors"] == ["missing_authoritative_prepared_handoff"]
    h13 = pipeline.prepare_premium_handoff(birth(), include_timing=False)
    h13["premium_handoff_contract_version"] = "1.3"
    cross = pipeline.validate_premium_author_bundle(birth(), author, include_timing=False, prepared_handoff=h13)
    assert not cross["approved"]
    assert any("paragraph" in error or "contract" in error for error in cross["verification_errors"])


def test_v414_publication_rechecks_final_physical_provenance_after_layout_edits():
    handoff, author, provenance = _approved_rich_v14()
    reviewer = reviewer_bundle_v14(author, provenance)
    published = pipeline.validate_premium_narrative(
        reviewer, provenance, birth(), include_timing=False, prepared_handoff=handoff,
    )
    assert published["approved"], published["verification_errors"]

    changed = deepcopy(reviewer)
    changed["final_report"] = changed["final_report"].replace(
        "- Uma escolha concreta pode tornar este mecanismo mais visível.\n  A continuação permanece parte do mesmo item.",
        "",
        1,
    ).replace("2. Outra possibilidade é observar como essa tensão muda quando o contexto muda.", "", 1)
    changed["final_report_sha256"] = pipeline._canonical_hash(changed["final_report"])
    changed["reviewed_draft_sha256"] = pipeline._canonical_hash(changed["final_report"])
    final = pipeline.validate_premium_narrative(
        changed, provenance, birth(), include_timing=False, prepared_handoff=handoff,
    )
    assert not final["approved"]
    assert any(
        error in final["verification_errors"]
        for error in ("subheading_requires_child_narrative_block", "narrative_block_without_source_map", "orphan_narrative_block_source_map")
    )

    bullet_swap = deepcopy(reviewer)
    old_paragraph = next(
        block["content"] for block in pipeline._parse_premium_narrative(author["draft_report"], provenance["reader_domain_manifest"])["sections"]["identity_presence"]["prose"]
        if block["kind"] == "paragraph"
    )
    bullet_swap["final_report"] = bullet_swap["final_report"].replace(old_paragraph, "- " + old_paragraph, 1)
    bullet_swap["final_report_sha256"] = pipeline._canonical_hash(bullet_swap["final_report"])
    result = pipeline.validate_premium_narrative(
        bullet_swap, provenance, birth(), include_timing=False, prepared_handoff=handoff,
    )
    assert not result["approved"]
    assert any("narrative_block" in error or "source_map" in error for error in result["verification_errors"])
