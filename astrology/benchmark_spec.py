"""Frozen pre-generation benchmark specification and champion compatibility verification."""
from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .benchmark_integrity import canonical_bytes, sha256, load_json, require_equal, verify_commit
from .exceptions import BenchmarkIntegrityError
from .models import BirthData, LocalizationProfile


def extract_rubric_dimension_ids(rubric: Dict[str, object]) -> List[str]:
    """Extract and validate unique dimension IDs from any valid rubric."""
    dims = rubric.get("dimensions")
    if not isinstance(dims, list) or not dims:
        raise BenchmarkIntegrityError("Rubric must contain a non-empty list of dimensions")
    ids = []
    for item in dims:
        if isinstance(item, dict):
            dim_id = item.get("id") or item.get("name")
        elif isinstance(item, str):
            dim_id = item.strip()
        else:
            dim_id = None
        if not dim_id or not isinstance(dim_id, str):
            raise BenchmarkIntegrityError("Rubric dimension must have a non-empty string identifier")
        ids.append(dim_id)
    if len(ids) != len(set(ids)):
        raise BenchmarkIntegrityError("Duplicate dimension IDs in rubric")
    return ids


def validate_champion_compatibility(
    candidate_birth: BirthData,
    candidate_profile: Optional[LocalizationProfile],
    as_of: Optional[datetime],
    horizon_days: int,
    include_timing: bool,
    champion_descriptor: Dict[str, object],
    champion_report: bytes,
    repository: Path,
) -> Dict[str, object]:
    """Verify Champion compatibility against candidate chart/preparation settings."""
    if not isinstance(champion_descriptor, dict):
        raise BenchmarkIntegrityError("Champion descriptor must be an object")

    source = champion_descriptor.get("source")
    if source not in {"captured_run", "historical_legacy"}:
        raise BenchmarkIntegrityError(f"Invalid champion source: {source}")

    expected_birth_hash = sha256(canonical_bytes(asdict(candidate_birth)))
    declared_birth_hash = champion_descriptor.get("birth_data_hash")
    if declared_birth_hash != expected_birth_hash:
        raise BenchmarkIntegrityError(
            f"Champion birth data mismatch: declared {declared_birth_hash} != candidate {expected_birth_hash}"
        )

    expected_locale = candidate_profile.preferred_language if candidate_profile else "pt-BR"
    declared_locale = champion_descriptor.get("locale")
    if declared_locale != expected_locale:
        raise BenchmarkIntegrityError(
            f"Champion locale mismatch: declared {declared_locale} != candidate {expected_locale}"
        )

    if include_timing:
        if champion_descriptor.get("timing_enabled") is not True:
            raise BenchmarkIntegrityError("Champion must have timing enabled for timed benchmark")
        if champion_descriptor.get("as_of") != (as_of.isoformat() if as_of else None):
            raise BenchmarkIntegrityError("Champion as_of timing mismatch")
        if champion_descriptor.get("horizon_days") != horizon_days:
            raise BenchmarkIntegrityError("Champion horizon_days mismatch")

    declared_report_hash = champion_descriptor.get("report_sha256")
    actual_report_hash = sha256(champion_report)
    if declared_report_hash != actual_report_hash:
        raise BenchmarkIntegrityError(
            f"Champion report hash mismatch: descriptor {declared_report_hash} != bytes {actual_report_hash}"
        )

    commit_sha = champion_descriptor.get("commit_sha")
    if commit_sha:
        verify_commit(str(repository), commit_sha)

    verified = copy.deepcopy(champion_descriptor)
    verified["report_sha256"] = actual_report_hash
    verified["promotion_grade"] = (source == "captured_run")
    if source == "historical_legacy":
        verified["comparison_mode"] = "legacy_weaker"
    return verified


def create_benchmark_spec(
    candidate_birth: BirthData,
    candidate_profile: Optional[LocalizationProfile],
    handoff: Dict[str, object],
    rubric: Dict[str, object],
    champion_descriptor: Dict[str, object],
    champion_report: bytes,
    candidate_model: str,
    candidate_thinking_level: str,
    evaluator_model: str,
    repository: Path,
    candidate_commit_sha: str,
    contamination_scope: Optional[Dict[str, object]] = None,
    evaluator_thinking_level: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: int = 32768,
) -> Dict[str, object]:
    """Freeze all benchmark protocol parameters before any model generation."""
    params = handoff["preparation_parameters"]
    as_of_dt = datetime.fromisoformat(params["effective_as_of"]) if params.get("effective_as_of") else None
    horizon_days = params["horizon_days"]
    include_timing = params["include_timing"]

    if candidate_thinking_level not in {"low", "medium", "high"}:
        raise BenchmarkIntegrityError(f"Candidate thinking level must be low/medium/high, got: {candidate_thinking_level}")

    if evaluator_thinking_level is not None and evaluator_thinking_level not in {"low", "medium", "high"}:
        raise BenchmarkIntegrityError(f"Evaluator thinking level must be low/medium/high, got: {evaluator_thinking_level}")

    dimension_ids = extract_rubric_dimension_ids(rubric)

    verified_champion = validate_champion_compatibility(
        candidate_birth, candidate_profile, as_of_dt, horizon_days, include_timing,
        champion_descriptor, champion_report, repository,
    )

    chart_id = {
        "birth_data_hash": sha256(canonical_bytes(asdict(candidate_birth))),
        "locale": candidate_profile.preferred_language if candidate_profile else "pt-BR",
        "as_of": params.get("effective_as_of"),
        "horizon_days": horizon_days,
        "include_timing": include_timing,
    }

    preparation_id = {
        "packet_id": handoff["packet_id"],
        "preparation_parameters_sha256": sha256(canonical_bytes(params)),
    }

    candidate_protocol = {
        "model": candidate_model,
        "thinking_level": candidate_thinking_level,
        "temperature": temperature,
        "max_output_tokens": max_output_tokens,
        "commit_sha": candidate_commit_sha,
    }

    evaluator_protocol = {
        "model": evaluator_model,
        "thinking_level": evaluator_thinking_level,
    }

    spec = {
        "spec_version": "2.3.1c",
        "chart_identity": chart_id,
        "preparation_identity": preparation_id,
        "rubric": {
            "rubric_sha256": sha256(canonical_bytes(rubric)),
            "dimension_count": len(dimension_ids),
            "dimensions": dimension_ids,
        },
        "champion": verified_champion,
        "candidate_protocol": candidate_protocol,
        "evaluator_protocol": evaluator_protocol,
        "contamination_scope": contamination_scope or {"benchmark_family": "chart3_mutable_earth_water", "corpus_files": []},
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    return spec


def freeze_spec_in_store(store, spec: Dict[str, object]) -> Dict[str, object]:
    """Commit benchmark_spec.json into the run store before any generation request."""
    store.assert_code()
    with store.lock():
        if store.path("benchmark_spec.json").exists():
            require_equal(load_json(store.path("benchmark_spec.json")), spec, "frozen benchmark spec")
        else:
            store.put_json("benchmark_spec.json", spec)
            store.event("benchmark:spec_frozen", ["benchmark_spec.json"])
    return spec


def validate_run_against_spec(store, transport, stage: str = "selection"):
    """Verify that generation call matches the pre-frozen benchmark spec."""
    if not store.path("benchmark_spec.json").exists():
        return None

    spec = load_json(store.path("benchmark_spec.json"))
    events = store.verify()
    event_actions = [e["action"] for e in events]

    if "benchmark:spec_frozen" not in event_actions:
        raise BenchmarkIntegrityError("benchmark:spec_frozen event missing from execution trace")

    spec_event_idx = event_actions.index("benchmark:spec_frozen")
    first_req_idx = next((i for i, a in enumerate(event_actions) if a.endswith(":request")), None)
    if first_req_idx is not None and first_req_idx < spec_event_idx:
        raise BenchmarkIntegrityError("Benchmark spec was frozen AFTER generation started; protocol compromised")

    if stage in {"selection", "author", "reviewer"}:
        candidate_cfg = spec["candidate_protocol"]
        if transport.model != candidate_cfg["model"]:
            raise BenchmarkIntegrityError(
                f"Model mismatch with frozen spec: transport={transport.model} != spec={candidate_cfg['model']}"
            )
        tl = getattr(transport, "thinking_level", None)
        if tl != candidate_cfg["thinking_level"]:
            raise BenchmarkIntegrityError(
                f"Thinking level mismatch with frozen spec: transport={tl} != spec={candidate_cfg['thinking_level']}"
            )

    return spec
