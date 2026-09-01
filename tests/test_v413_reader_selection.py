from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone

from astrology.pipeline import _canonical_hash, analyse_birth_chart, prepare_premium_handoff, validate_premium_author_bundle, validate_premium_narrative, validate_premium_syntheses
from tests.test_v413_reader_contract import _source_for_section, birth
from tests.v413_helpers import _synthesis_for_path, build_author_bundle, reviewer_bundle


def _handoff_and_author(*, include_timing=False, as_of=None):
    horizon = 45 if include_timing else 366
    handoff = prepare_premium_handoff(birth(), include_timing=include_timing, as_of=as_of, horizon_days=horizon)
    author, _ = build_author_bundle(birth(), include_timing=include_timing, as_of=as_of, horizon_days=horizon)
    return handoff, author, horizon


def _refresh_author_hashes(author, *, include_timing=False, as_of=None, horizon_days=366):
    judged = validate_premium_syntheses(birth(), author["reasoned_syntheses"], include_timing=include_timing, as_of=as_of, horizon_days=horizon_days)
    author["synthesis_bundle_sha256"] = judged["synthesis_bundle_sha256"]
    author["reader_selection_plan_sha256"] = _canonical_hash(author["reader_selection_plan"])


def test_reader_selection_default_fixture_accounts_for_every_available_path():
    handoff, author, horizon = _handoff_and_author()
    result = validate_premium_author_bundle(birth(), author, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert result["approved"], result["verification_errors"]
    plan = result["reader_selection_plan"]
    assert plan == author["reader_selection_plan"]
    assert result["reader_selection_plan_sha256"] == _canonical_hash(plan)
    assert all(entry["paths"] for entry in plan["domains"])


def test_reader_selection_rejects_missing_duplicate_reordered_and_invented_paths():
    handoff, author, horizon = _handoff_and_author()
    mutations = {
        "missing": lambda p: p["domains"][0]["paths"].pop(),
        "duplicate": lambda p: p["domains"][0]["paths"].append(deepcopy(p["domains"][0]["paths"][0])),
        "reordered": lambda p: p["domains"][0]["paths"].reverse(),
        "invented": lambda p: p["domains"][0]["paths"].__setitem__(0, {**p["domains"][0]["paths"][0], "path_id": "reader_path.invented"}),
    }
    for label, mutate in mutations.items():
        altered = deepcopy(author)
        mutate(altered["reader_selection_plan"])
        altered["reader_selection_plan_sha256"] = _canonical_hash(altered["reader_selection_plan"])
        result = validate_premium_author_bundle(birth(), altered, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
        assert not result["approved"], (label, result["verification_errors"])
        assert any("reader_selection_path_mismatch" in item for item in result["verification_errors"])


def test_reader_selection_rejects_missing_domain_provenance_and_unapproved_synthesis():
    handoff, author, horizon = _handoff_and_author()
    domain = author["reader_selection_plan"]["domains"][0]
    represented = next(item for item in domain["paths"] if item["decision"] == "represented")
    missing_provenance = deepcopy(author)
    missing_provenance["reader_selection_plan"]["domains"][0]["paths"][0]["synthesis_ids"] = [
        _source_for_section(author, "emotional_security")["synthesis_ids"][0]
    ]
    missing_provenance["reader_selection_plan_sha256"] = _canonical_hash(missing_provenance["reader_selection_plan"])
    result = validate_premium_author_bundle(birth(), missing_provenance, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert "reader_selection_synthesis_missing_domain_provenance:" + represented["path_id"] in result["verification_errors"]
    unapproved = deepcopy(author)
    unapproved["reader_selection_plan"]["domains"][0]["paths"][0]["synthesis_ids"] = ["reasoned.unapproved"]
    unapproved["reader_selection_plan_sha256"] = _canonical_hash(unapproved["reader_selection_plan"])
    result = validate_premium_author_bundle(birth(), unapproved, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert "reader_selection_unapproved_synthesis:" + represented["path_id"] in result["verification_errors"]


def test_reviewer_cannot_forge_or_publish_a_mutated_selection_plan():
    handoff, author, horizon = _handoff_and_author()
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert provenance["approved"], provenance["verification_errors"]
    reviewer = reviewer_bundle(author, provenance)
    reviewer["reader_selection_plan"] = deepcopy(reviewer["reader_selection_plan"])
    reviewer["reader_selection_plan"]["domains"][0]["paths"][0]["rationale"] = "forged"
    reviewer["reader_selection_plan_sha256"] = _canonical_hash(reviewer["reader_selection_plan"])
    result = validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert not result["approved"]
    assert "reader_selection_plan_body_mismatch" in result["verification_errors"]


def test_reader_selection_allows_independent_valid_syntheses_to_cover_a_merge_cluster():
    handoff, author, horizon = _handoff_and_author()
    core = analyse_birth_chart(birth(), include_timing=False)
    domain = next(item for item in core["reader_domain_manifest"]["domains"] if item["id"] == "identity_presence")
    first_path, second_path = domain["legal_coverage_paths"][:2]
    claims = {item["id"]: item for item in core["claims"] if item["status"] == "allowed"}
    second = asdict(_synthesis_for_path(second_path, claims, domain["id"]))
    second["id"] = "reasoned.reader.identity_presence.second"
    altered = deepcopy(author)
    altered["reasoned_syntheses"].append(second)
    text = "A second authorised identity mechanism is developed separately, so the reader can meet its distinct way of beginning without forcing it into one artificial synthesis."
    text_hash = _canonical_hash(text)
    next_heading = core["reader_domain_manifest"]["domains"][1]["heading"]
    altered["draft_report"] = altered["draft_report"].replace(f"## {next_heading}", f"{text}\n\n## {next_heading}", 1)
    altered["draft_report_sha256"] = _canonical_hash(altered["draft_report"])
    identity = next(item for item in altered["reader_sections"]["domains"] if item["domain_id"] == "identity_presence")
    identity["paragraph_sha256s"].append(text_hash)
    altered["paragraph_sources"].append({"paragraph_sha256": text_hash, "synthesis_ids": [second["id"]], "claim_ids": [], "timing_ids": []})
    plan_domain = next(item for item in altered["reader_selection_plan"]["domains"] if item["domain_id"] == "identity_presence")
    first, second_entry = plan_domain["paths"][:2]
    first.update({"decision": "represented", "synthesis_ids": [first["synthesis_ids"][0], second["id"]], "merged_with_path_id": None, "rationale": None})
    second_entry.update({"decision": "merged_with_represented", "synthesis_ids": [], "merged_with_path_id": first_path["id"], "rationale": "The two valid syntheses form one reader-facing identity cluster."})
    _refresh_author_hashes(altered)
    result = validate_premium_author_bundle(birth(), altered, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert result["approved"], result["verification_errors"]


def test_reader_selection_rejects_noncontributing_padding_in_a_represented_set():
    handoff, author, horizon = _handoff_and_author()
    altered = deepcopy(author)
    identity = next(item for item in altered["reader_selection_plan"]["domains"] if item["domain_id"] == "identity_presence")
    identity["paths"][0]["synthesis_ids"].append(_source_for_section(author, "emotional_security")["synthesis_ids"][0])
    altered["reader_selection_plan_sha256"] = _canonical_hash(altered["reader_selection_plan"])
    result = validate_premium_author_bundle(birth(), altered, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert not result["approved"]
    assert f"reader_selection_synthesis_missing_domain_provenance:{identity['paths'][0]['path_id']}" in result["verification_errors"]


def test_reviewer_regeneration_is_authenticated_and_never_publishes():
    handoff, author, horizon = _handoff_and_author()
    provenance = validate_premium_author_bundle(birth(), author, include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    reviewer = reviewer_bundle(author, provenance)
    path = provenance["reader_selection_plan"]["domains"][0]["paths"][0]["path_id"]
    reviewer.update({
        "verdict": "regenerate_author",
        "regeneration_request": {"items": [{"domain_id": "identity_presence", "path_ids": [path], "reason": "Distinct mechanism needs development."}]},
    })
    result = validate_premium_narrative(reviewer, provenance, birth(), include_timing=False, horizon_days=horizon, prepared_handoff=handoff)
    assert not result["approved"]
    assert result["semantic_status"] == "author_regeneration_required"
    assert result["next_step"] == "regenerate_author"
    assert result["report"] is None


def test_reader_selection_timing_cluster_rejects_partial_and_unrelated_sets():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    handoff, author, horizon = _handoff_and_author(include_timing=True, as_of=as_of)
    active = next(item for item in author["reader_selection_plan"]["domains"] if item["domain_id"] == "active_life_chapter")
    represented = next(item for item in active["paths"] if item["decision"] == "represented")
    path = next(item for item in analyse_birth_chart(birth(), include_timing=True, as_of=as_of, horizon_days=horizon)["reader_domain_manifest"]["domains"] if item["id"] == "active_life_chapter")["legal_coverage_paths"][0]
    altered = deepcopy(author)
    synthesis = next(item for item in altered["reasoned_syntheses"] if item["id"] == represented["synthesis_ids"][0])
    unrelated = next(item for item in validate_premium_syntheses(birth(), author["reasoned_syntheses"], include_timing=True, as_of=as_of, horizon_days=horizon)["timing_evidence_ids"] if item not in synthesis["primary_factors"])
    synthesis["primary_factors"].append(unrelated)
    _refresh_author_hashes(altered, include_timing=True, as_of=as_of, horizon_days=horizon)
    result = validate_premium_author_bundle(birth(), altered, include_timing=True, as_of=as_of, horizon_days=horizon, prepared_handoff=handoff)
    assert not result["approved"]
    assert f"reader_selection_timing_cluster_mismatch:{represented['path_id']}" in result["verification_errors"]
