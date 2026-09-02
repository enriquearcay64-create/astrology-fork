from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Optional

from astrology.models import BirthData
import astrology.pipeline as pipeline

from tests.v413_helpers import build_author_bundle as build_v13_author_bundle


def _contract_fields(kind: str) -> Dict[str, object]:
    contract = pipeline._premium_handoff_contract()
    fields = contract[f"{kind}_bundle_required_fields"]
    return {
        field: {
            "premium_handoff_contract_version": contract["version"],
            "premium_handoff_contract": contract,
            "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        }.get(field)
        for field in fields
        if field in {"premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256"}
    }


def _rich_report_and_provenance(legacy_author: Dict[str, object], manifest: Dict[str, object]) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    """Convert a frozen-style synthetic report into a valid 1.4 rich fixture."""
    legacy_report = str(legacy_author["draft_report"])
    parsed_v13 = pipeline._parse_premium_narrative_v13(legacy_report, manifest)
    if parsed_v13["errors"]:
        raise AssertionError(parsed_v13["errors"])
    old_sources = {
        str(item["paragraph_sha256"]): item
        for item in legacy_author["paragraph_sources"]
        if isinstance(item, dict)
    }
    identity_entry = parsed_v13["sections"]["identity_presence"]["prose"][0]
    identity_source = old_sources[str(identity_entry["sha256"])]
    identity_synthesis = str(identity_source["synthesis_ids"][0])

    headings = {
        "opening": manifest["opening"]["heading"],
        "integration": manifest["integration"]["heading"],
        **{str(item["id"]): item["heading"] for item in manifest["domains"]},
    }
    parts = [pipeline._premium_reader_introduction(manifest.get("locale"))]
    rich_domain = "identity_presence"
    for key in ["opening", *[str(item["id"]) for item in manifest["domains"]], "integration"]:
        parts.append(f"## {headings[key]}")
        domain = next((item for item in manifest["domains"] if str(item["id"]) == key), None)
        if domain is not None and domain.get("availability") != "available":
            parts.append(str(domain["unavailable_notice"]["text"]))
            continue
        prose = parsed_v13["sections"][key]["prose"]
        if key == rich_domain and domain is not None and domain.get("availability") == "available":
            base = str(prose[0]["text"])
            parts.append("### Uma lente para reconhecer este movimento")
            parts.append(base)
            parts.append("- Uma escolha concreta pode tornar este mecanismo mais visível.\n  A continuação permanece parte do mesmo item.")
            parts.append("2. Outra possibilidade é observar como essa tensão muda quando o contexto muda.")
            for entry in prose[1:]:
                parts.append(str(entry["text"]))
        else:
            parts.extend(str(entry["text"]) for entry in prose)
    report = "\n\n".join(parts)
    parsed = pipeline._parse_premium_narrative(report, manifest)
    if parsed["errors"]:
        raise AssertionError(parsed["errors"])
    sources = []
    for entry in parsed["authored"]:
        if entry["kind"] == "subheading":
            sources.append({
                "narrative_block_sha256": entry["narrative_block_sha256"],
                "synthesis_ids": [identity_synthesis], "claim_ids": [], "timing_ids": [],
            })
            continue
        old = old_sources.get(pipeline._canonical_hash(str(entry["content"])))
        if old is not None:
            synthesis_ids, claim_ids, timing_ids = old["synthesis_ids"], old["claim_ids"], old["timing_ids"]
        else:
            synthesis_ids, claim_ids, timing_ids = [identity_synthesis], [], []
        sources.append({
            "narrative_block_sha256": entry["narrative_block_sha256"],
            "synthesis_ids": list(synthesis_ids), "claim_ids": list(claim_ids), "timing_ids": list(timing_ids),
        })
    sections: dict[str, object] = {
        "opening": {"narrative_block_sha256s": [str(item["narrative_block_sha256"]) for item in parsed["sections"]["opening"]["authored"]]},
        "domains": [],
        "integration": {"narrative_block_sha256s": [str(item["narrative_block_sha256"]) for item in parsed["sections"]["integration"]["authored"]]},
    }
    for domain in manifest["domains"]:
        domain_id = str(domain["id"])
        sections["domains"].append({
            "domain_id": domain_id,
            "narrative_block_sha256s": [str(item["narrative_block_sha256"]) for item in parsed["sections"][domain_id]["authored"]],
        })
    return report, sources, sections


def build_author_bundle_v14(
    birth: BirthData,
    include_timing: bool = False,
    as_of=None,
    horizon_days: int = 366,
    profile=None,
    rich: bool = True,
) -> tuple[dict[str, object], dict[str, object]]:
    legacy_author, direct = build_v13_author_bundle(
        birth, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days, profile=profile,
    )
    result = pipeline.analyse_birth_chart(
        birth, profile, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days,
    )
    manifest = result["reader_domain_manifest"]
    if rich:
        report, sources, sections = _rich_report_and_provenance(legacy_author, manifest)
    else:
        report = str(legacy_author["draft_report"])
        parsed = pipeline._parse_premium_narrative(report, manifest)
        old_sources = {str(item["paragraph_sha256"]): item for item in legacy_author["paragraph_sources"] if isinstance(item, dict)}
        sources = [
            {
                "narrative_block_sha256": str(entry["narrative_block_sha256"]),
                "synthesis_ids": list(old_sources[pipeline._canonical_hash(str(entry["content"]))]["synthesis_ids"]),
                "claim_ids": list(old_sources[pipeline._canonical_hash(str(entry["content"]))]["claim_ids"]),
                "timing_ids": list(old_sources[pipeline._canonical_hash(str(entry["content"]))]["timing_ids"]),
            }
            for entry in parsed["authored"]
        ]
        sections = {
            "opening": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["opening"]["authored"]]},
            "domains": [
                {"domain_id": str(domain["id"]), "narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"][str(domain["id"])]["authored"]]}
                for domain in manifest["domains"]
            ],
            "integration": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["integration"]["authored"]]},
        }
    contract = pipeline._premium_handoff_contract()
    required = set(contract["author_bundle_required_fields"])
    author = {key: legacy_author[key] for key in required if key in legacy_author}
    author.update({
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        "packet_id": result["packet_id"],
        "prepared_chart_signature_sha256": result["prepared_chart_signature_sha256"] if "prepared_chart_signature_sha256" in result else pipeline._canonical_hash(result["chart_signature"]),
        "prepared_signature_synthesis_sha256": result["prepared_signature_synthesis_sha256"] if "prepared_signature_synthesis_sha256" in result else pipeline._canonical_hash(result["reasoned_synthesis"]),
        "reader_domain_manifest_sha256": pipeline._canonical_hash(result["reader_domain_manifest"]),
        "narrative_block_sources": sources,
        "reader_sections": sections,
        "draft_report": report,
        "draft_report_sha256": pipeline._canonical_hash(report),
    })
    author.pop("paragraph_sources", None)
    return author, {"direct": direct, "manifest": manifest}


def reviewer_bundle_v14(author: Dict[str, object], provenance: Dict[str, object]) -> Dict[str, object]:
    contract = pipeline._premium_handoff_contract()
    return {
        "packet_id": provenance["packet_id"],
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        "prepared_chart_signature_sha256": provenance["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": provenance["prepared_signature_synthesis_sha256"],
        "reader_domain_manifest_sha256": provenance["reader_domain_manifest_sha256"],
        "synthesis_bundle_sha256": provenance["synthesis_bundle_sha256"],
        "reviewed_draft_sha256": provenance["draft_report_sha256"],
        "verdict": "approved", "corrections_made": [], "remaining_warnings": [],
        "final_report": author["draft_report"],
        "final_report_sha256": pipeline._canonical_hash(author["draft_report"]),
        "narrative_block_sources": author["narrative_block_sources"],
        "reader_sections": author["reader_sections"],
        "reader_selection_plan": provenance["reader_selection_plan"],
        "reader_selection_plan_sha256": provenance["reader_selection_plan_sha256"],
        "regeneration_request": None,
    }


def build_author_bundle_v13_for_replay(
    birth: BirthData,
    include_timing: bool = False,
    as_of=None,
    horizon_days: int = 366,
    profile=None,
) -> tuple[dict[str, object], dict[str, object]]:
    """Build a frozen 1.3 fixture without exposing a 1.3 preparation path."""
    author, direct = build_v13_author_bundle(
        birth, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days, profile=profile,
    )
    current = pipeline.analyse_birth_chart(
        birth, profile, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days,
        premium_contract_version=pipeline.LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    contract = pipeline._premium_handoff_contract_v13()
    required = set(contract["author_bundle_required_fields"])
    replay = {key: author[key] for key in required if key in author}
    replay.update({
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        "packet_id": current["packet_id"],
        "prepared_chart_signature_sha256": pipeline._canonical_hash(current["chart_signature"]),
        "prepared_signature_synthesis_sha256": pipeline._canonical_hash(current["reasoned_synthesis"]),
        "reader_domain_manifest_sha256": pipeline._canonical_hash(current["reader_domain_manifest"]),
    })
    replay.pop("narrative_block_sources", None)
    return replay, {"direct": direct, "manifest": current["reader_domain_manifest"]}


def reviewer_bundle_v13_for_replay(author: Dict[str, object], provenance: Dict[str, object]) -> Dict[str, object]:
    contract = pipeline._premium_handoff_contract_v13()
    return {
        "packet_id": provenance["packet_id"],
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        "prepared_chart_signature_sha256": provenance["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": provenance["prepared_signature_synthesis_sha256"],
        "reader_domain_manifest_sha256": provenance["reader_domain_manifest_sha256"],
        "synthesis_bundle_sha256": provenance["synthesis_bundle_sha256"],
        "reviewed_draft_sha256": provenance["draft_report_sha256"],
        "verdict": "approved", "corrections_made": [], "remaining_warnings": [],
        "final_report": author["draft_report"],
        "final_report_sha256": pipeline._canonical_hash(author["draft_report"]),
        "paragraph_sources": author["paragraph_sources"],
        "reader_sections": author["reader_sections"],
        "reader_selection_plan": provenance["reader_selection_plan"],
        "reader_selection_plan_sha256": provenance["reader_selection_plan_sha256"],
        "regeneration_request": None,
    }


def prepare_legacy_premium_handoff_for_replay(
    birth: BirthData, profile=None, include_timing: bool = False, as_of=None, horizon_days: int = 366,
) -> Dict[str, object]:
    """Test-only fixture helper; production preparation remains 1.4-only."""
    current = pipeline.prepare_premium_handoff(
        birth, profile, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days,
    )
    parameters = current["preparation_parameters"]
    effective_as_of = parameters["effective_as_of"]
    from datetime import datetime
    parsed_as_of = datetime.fromisoformat(str(effective_as_of).replace("Z", "+00:00")) if effective_as_of else None
    legacy = pipeline.analyse_birth_chart(
        birth, profile, "deep", include_timing, parsed_as_of, horizon_days,
        premium_contract_version=pipeline.LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    contract = pipeline._premium_handoff_contract_v13()
    current.update({
        "packet_id": legacy["packet_id"],
        "premium_handoff_contract_version": pipeline.LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": pipeline._canonical_hash(contract),
        "prepared_chart_signature_sha256": pipeline._canonical_hash(legacy["chart_signature"]),
        "prepared_signature_synthesis_sha256": pipeline._canonical_hash(legacy["reasoned_synthesis"]),
        "prepared_signature_syntheses": legacy["reasoned_synthesis"],
        "reader_domain_manifest": legacy["reader_domain_manifest"],
        "reader_domain_manifest_sha256": pipeline._canonical_hash(legacy["reader_domain_manifest"]),
        "reader_introduction": pipeline._premium_reader_introduction(legacy["reader_domain_manifest"].get("locale")),
    })
    for bundle_kind in ("author", "reviewer"):
        required = contract[f"{bundle_kind}_bundle_required_fields"]
        descriptive = current.get(f"{bundle_kind}_bundle_contract", {})
        current[f"{bundle_kind}_bundle_contract"] = {
            field: descriptive.get(field, "frozen-1.3-replay")
            for field in required
        }
    current["reader_introduction_sha256"] = pipeline._canonical_hash(current["reader_introduction"])
    return current
