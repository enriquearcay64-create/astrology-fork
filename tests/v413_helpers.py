from __future__ import annotations

from dataclasses import asdict
from typing import Dict, Iterable

from astrology.models import BirthData, ReasonedSynthesis
from astrology.pipeline import _canonical_hash, _premium_handoff_contract, _premium_reader_introduction, analyse_birth_chart, validate_premium_syntheses


def contract_fields() -> Dict[str, object]:
    contract = _premium_handoff_contract()
    return {
        "premium_handoff_contract_version": "1.2",
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": _canonical_hash(contract),
        "corrections_made": [],
        "remaining_warnings": [],
    }


def _synthesis_for_path(path: Dict[str, object], claims: Dict[str, Dict[str, object]], domain_id: str) -> ReasonedSynthesis:
    source_claims = [claims[item] for item in path["source_claim_ids"]]
    route_claim = next((item for item in source_claims if item["type"] == "placidus_house_ruler"), None)
    if route_claim:
        house = route_claim["id"].rsplit(".", 1)[-1]
        ruler_factor = next(item for item in path["primary_factor_ids"] if str(item).startswith("position."))
        synthesis_id = f"reasoned.house_ruler_context.placidus.{house}.{str(ruler_factor).removeprefix('position.')}"
    else:
        synthesis_id = f"reasoned.reader.{domain_id}"
    statement = " ".join(str(item["statement"]) for item in source_claims)
    return ReasonedSynthesis(
        id=synthesis_id, observation=statement, primary_factors=list(path["primary_factor_ids"]), modifiers=[], counterweights=[],
        reasoning_class=str(path["reasoning_class"]), confidence_within_astrological_model="light",
        possible_expressions=[statement], alternative_reading="", prohibited_extensions=[],
        source_claim_ids=list(path["source_claim_ids"]),
        source_motif_ids=[motif for item in source_claims for motif in item["authorized_motifs"]],
        composition_operations=list(path["composition_operations"]),
        derived_propositions=[{"text": statement, "sources": list(path["source_claim_ids"])}],
    )


def build_author_bundle(birth: BirthData, include_timing: bool = False, add_direct_claim: bool = False, as_of=None, horizon_days: int = 366, profile=None):
    result = analyse_birth_chart(birth, profile, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days)
    manifest = result["reader_domain_manifest"]
    claims = {item["id"]: item for item in result["claims"] if item["status"] == "allowed"}
    syntheses: Dict[str, ReasonedSynthesis] = {}
    domain_source: Dict[str, str] = {}
    domain_timing: Dict[str, list[str]] = {}
    for domain in manifest["domains"]:
        if domain["availability"] != "available":
            continue
        synthesis = _synthesis_for_path(domain["legal_coverage_paths"][0], claims, domain["id"])
        syntheses.setdefault(synthesis.id, synthesis)
        domain_source[domain["id"]] = synthesis.id
        domain_timing[domain["id"]] = list(domain["legal_coverage_paths"][0].get("timing_ids", []))

    relational = next(
        item for item in syntheses.values()
        if item.reasoning_class in {"integrated_pattern", "theme_interaction"}
        and not any(claim_id.startswith("claim.house_ruler.placidus.") for claim_id in item.source_claim_ids)
    )
    required = result["reasoning_packet"]["facts"]["coverage"]["required_evidence"]
    by_evidence = {evidence: claim for claim in claims.values() for evidence in claim["evidence"]}
    mandatory_ids = []
    for ordinal, evidence in enumerate(sorted({item for values in required.values() for item in values}), 1):
        claim = by_evidence[evidence]
        synthesis = ReasonedSynthesis(
            id=f"coverage.mandatory.{ordinal}", observation=claim["statement"], primary_factors=[evidence], modifiers=[], counterweights=[],
            reasoning_class="single_structural_factor", confidence_within_astrological_model="light",
            possible_expressions=[claim["statement"]], alternative_reading="", prohibited_extensions=[],
            source_claim_ids=[claim["id"]], source_motif_ids=claim["authorized_motifs"], composition_operations=["contextualization"],
            derived_propositions=[{"text": claim["statement"], "sources": [claim["id"]]}],
        )
        syntheses[synthesis.id] = synthesis
        mandatory_ids.append(synthesis.id)

    section_blocks: Dict[str, list[tuple[str, list[str], list[str], list[str]]]] = {
        "opening": [("This opening joins the authorised central mechanisms into one whole-chart architecture without treating them as biography.", [relational.id], [], [])],
        "integration": [("This integration returns to the authorised relational mechanism and connects its distinct consequences without repeating the full explanation.", [relational.id], [], [])],
    }
    for ordinal, synthesis_id in enumerate(mandatory_ids, 1):
        section_blocks["opening"].append((f"Mandatory natal coverage item {ordinal} remains a bounded symbolic possibility supported by its canonical synthesis.", [synthesis_id], [], []))
    for domain in manifest["domains"]:
        if domain["availability"] == "available":
            section_blocks[domain["id"]] = [(f"This is a distinct reader-facing treatment for {domain['heading']} within the authorised scope of its chart-specific path.", [domain_source[domain["id"]]], [], domain_timing[domain["id"]])]
        else:
            section_blocks[domain["id"]] = []

    direct = next((item for item in claims.values() if item["direct_paragraph_renderable"]), None)
    if add_direct_claim and direct:
        section_blocks["identity_presence"].append((str(direct["statement"]), [], [direct["id"]], []))

    heading_by_key = {"opening": manifest["opening"]["heading"], "integration": manifest["integration"]["heading"], **{item["id"]: item["heading"] for item in manifest["domains"]}}
    order = ["opening", *[item["id"] for item in manifest["domains"]], "integration"]
    report_parts = [_premium_reader_introduction(manifest.get("locale"))]
    sources = []
    ownership = {"opening": {"paragraph_sha256s": []}, "domains": [], "integration": {"paragraph_sha256s": []}}
    domain_ownership = {}
    for domain in manifest["domains"]:
        entry = {"domain_id": domain["id"], "paragraph_sha256s": []}
        ownership["domains"].append(entry)
        domain_ownership[domain["id"]] = entry
    for key in order:
        report_parts.append(f"## {heading_by_key[key]}")
        for text, synthesis_ids, claim_ids, timing_ids in section_blocks[key]:
            report_parts.append(text)
            paragraph_hash = _canonical_hash(text)
            sources.append({"paragraph_sha256": paragraph_hash, "synthesis_ids": synthesis_ids, "claim_ids": claim_ids, "timing_ids": timing_ids})
            target = ownership[key] if key in {"opening", "integration"} else domain_ownership[key]
            target["paragraph_sha256s"].append(paragraph_hash)
        domain = next((item for item in manifest["domains"] if item["id"] == key), None)
        if domain and domain["availability"] == "unavailable":
            report_parts.append(domain["unavailable_notice"]["text"])
    report = "\n\n".join(report_parts)
    synthesis_payload = [asdict(item) for item in syntheses.values()]
    judged = validate_premium_syntheses(birth, synthesis_payload, profile, include_timing=include_timing, as_of=as_of, horizon_days=horizon_days)
    author = {
        **contract_fields(), "packet_id": judged["packet_id"],
        "prepared_chart_signature_sha256": judged["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": judged["prepared_signature_synthesis_sha256"],
        "reader_domain_manifest_sha256": judged["reader_domain_manifest_sha256"],
        "reasoned_syntheses": synthesis_payload, "draft_report": report, "paragraph_sources": sources, "reader_sections": ownership,
        "synthesis_bundle_sha256": judged["synthesis_bundle_sha256"], "draft_report_sha256": _canonical_hash(report),
    }
    return author, direct


def reviewer_bundle(author: Dict[str, object], provenance: Dict[str, object]) -> Dict[str, object]:
    return {
        **contract_fields(), "packet_id": provenance["packet_id"],
        "prepared_chart_signature_sha256": provenance["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": provenance["prepared_signature_synthesis_sha256"],
        "reader_domain_manifest_sha256": provenance["reader_domain_manifest_sha256"],
        "synthesis_bundle_sha256": provenance["synthesis_bundle_sha256"], "reviewed_draft_sha256": provenance["draft_report_sha256"],
        "verdict": "approved", "final_report": author["draft_report"], "final_report_sha256": _canonical_hash(author["draft_report"]),
        "paragraph_sources": author["paragraph_sources"], "reader_sections": author["reader_sections"],
    }
