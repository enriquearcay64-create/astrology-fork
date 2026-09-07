"""Frozen pre-generation benchmark specification and champion compatibility verification."""
from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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


def derive_champion_from_run(champion_run_dir: Path | str, repository: Path) -> Tuple[Dict[str, object], bytes]:
    """Derive a verified Champion descriptor and report from an existing captured run directory."""
    run_path = Path(champion_run_dir).resolve()
    if not run_path.is_dir():
        raise BenchmarkIntegrityError(f"Champion run directory not found: {run_path}")
    run_json_path = run_path / "run.json"
    handoff_path = run_path / "01-handoff.json"
    report_path = run_path / "final_reviewed_report.md"
    if not run_json_path.is_file() or not handoff_path.is_file() or not report_path.is_file():
        raise BenchmarkIntegrityError(f"Champion run missing essential artifacts: {run_path}")

    run_data = load_json(run_json_path)
    handoff_data = load_json(handoff_path)
    report_bytes = report_path.read_bytes()
    report_sha = sha256(report_bytes)

    commit_sha = run_data.get("code_context", {}).get("artifact_generation_commit_sha")
    if commit_sha:
        verify_commit(str(repository), commit_sha)

    manifest_path = run_path / "benchmark_manifest.json"
    if manifest_path.is_file():
        manifest = load_json(manifest_path)
        artifacts = manifest.get("artifacts_sha256", {})
        if artifacts.get("final_reviewed_report.md") != report_sha:
            raise BenchmarkIntegrityError("Champion manifest report hash mismatch")

    config = run_data.get("configuration", {})
    birth_hash = sha256(canonical_bytes(config.get("birth", {})))
    locale = handoff_data.get("reader_domain_manifest", {}).get("locale", "pt-BR")
    prep_params = handoff_data.get("preparation_parameters", {})
    timing_enabled = prep_params.get("include_timing", False)
    as_of = prep_params.get("effective_as_of")
    horizon_days = prep_params.get("horizon_days", 366)

    descriptor = {
        "source": "captured_run",
        "run_dir": str(run_path),
        "commit_sha": commit_sha,
        "birth_data_hash": birth_hash,
        "locale": locale,
        "timing_enabled": timing_enabled,
        "as_of": as_of,
        "horizon_days": horizon_days,
        "report_sha256": report_sha,
        "verified_captured_run": True,
        "promotion_grade": True,
    }
    return descriptor, report_bytes


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

    # Exact timing_enabled equality required, including when Candidate timing is false
    champion_timing = champion_descriptor.get("timing_enabled")
    if champion_timing is None:
        raise BenchmarkIntegrityError("Champion descriptor must specify timing_enabled (boolean)")
    if champion_timing != include_timing:
        raise BenchmarkIntegrityError(
            f"Champion timing_enabled mismatch: champion has {champion_timing}, candidate requires {include_timing}"
        )

    if include_timing:
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
    if source == "captured_run" and champion_descriptor.get("verified_captured_run") is True:
        verified["promotion_grade"] = True
        verified["comparison_mode"] = "standard"
    elif source == "captured_run":
        verified["promotion_grade"] = False
        verified["comparison_mode"] = "standard"
    else:
        verified["promotion_grade"] = False
        verified["comparison_mode"] = "legacy_weaker"
    return verified


def resolve_contamination_corpus(
    repository: Path,
    benchmark_family: Optional[str] = None,
    explicit_files: Optional[List[Path | str]] = None,
    exclude_dirs: Optional[List[Path]] = None,
) -> Dict[str, object]:
    """Resolve and freeze the contamination corpus files before generation starts."""
    repo_root = Path(repository).resolve()
    exclude_dirs = [Path(d).resolve() for d in (exclude_dirs or [])]
    target_files: List[Path] = []

    if explicit_files is not None:
        for f in explicit_files:
            p = Path(f).resolve()
            if p.is_file():
                target_files.append(p)
    elif benchmark_family:
        family_dir = repo_root / "benchmarks" / benchmark_family
        if family_dir.is_dir():
            for p in family_dir.rglob("*.md"):
                p_res = p.resolve()
                if not any(ex == p_res or ex in p_res.parents for ex in exclude_dirs):
                    target_files.append(p_res)
    else:
        target_files = []

    target_files = sorted(set(target_files))
    corpus_entries = []
    for p in target_files:
        try:
            rel = str(p.relative_to(repo_root))
        except ValueError:
            rel = p.name
        corpus_entries.append({
            "relative_path": rel,
            "sha256": sha256(p.read_bytes()),
        })

    return {
        "benchmark_family": benchmark_family,
        "corpus_files": corpus_entries,
    }


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
    evaluator_thinking_level: str = "high",
    temperature: float = 0.7,
    max_output_tokens: int = 32768,
    evaluator_temperature: float = 0.0,
    evaluator_max_output_tokens: int = 32768,
    contamination_scope: Optional[Dict[str, object]] = None,
    benchmark_family: Optional[str] = None,
    contamination_corpus_files: Optional[List[Path | str]] = None,
) -> Dict[str, object]:
    """Freeze all benchmark protocol parameters before any model generation."""
    params = handoff["preparation_parameters"]
    as_of_dt = datetime.fromisoformat(params["effective_as_of"]) if params.get("effective_as_of") else None
    horizon_days = params["horizon_days"]
    include_timing = params["include_timing"]

    if candidate_thinking_level not in {"low", "medium", "high"}:
        raise BenchmarkIntegrityError(f"Candidate thinking level must be low/medium/high, got: {candidate_thinking_level}")

    if evaluator_thinking_level is None or evaluator_thinking_level not in {"low", "medium", "high"}:
        raise BenchmarkIntegrityError(f"Evaluator thinking level must be explicit low/medium/high, got: {evaluator_thinking_level}")

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
        "temperature": evaluator_temperature,
        "max_output_tokens": evaluator_max_output_tokens,
    }

    if contamination_scope is None:
        contamination_scope = resolve_contamination_corpus(
            repository, benchmark_family=benchmark_family, explicit_files=contamination_corpus_files
        )

    spec = {
        "spec_version": "2.3.1d",
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
        "contamination_scope": contamination_scope,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
    }
    return spec


def authenticate_benchmark_spec(spec: Dict[str, object], store, transport=None) -> Dict[str, object]:
    """Deterministically authenticate benchmark spec against the actual prepared run, handoff, and candidate context."""
    if not isinstance(spec, dict):
        raise BenchmarkIntegrityError("Benchmark spec must be an object")

    handoff = load_json(store.path("01-handoff.json"))
    run_meta = load_json(store.path("run.json"))
    config = run_meta.get("configuration", {})
    code_ctx = run_meta.get("code_context", {})
    repo_root = Path(run_meta.get("repository", "")).resolve()

    chart_id = spec.get("chart_identity", {})
    expected_birth_hash = sha256(canonical_bytes(config.get("birth", {})))
    if chart_id.get("birth_data_hash") != expected_birth_hash:
        raise BenchmarkIntegrityError(
            f"Benchmark spec chart identity mismatch: spec {chart_id.get('birth_data_hash')} != run {expected_birth_hash}"
        )

    locale = handoff.get("reader_domain_manifest", {}).get("locale", "pt-BR")
    if chart_id.get("locale") != locale:
        raise BenchmarkIntegrityError(
            f"Benchmark spec locale mismatch: spec {chart_id.get('locale')} != handoff {locale}"
        )

    prep_params = handoff.get("preparation_parameters", {})
    if chart_id.get("as_of") != prep_params.get("effective_as_of"):
        raise BenchmarkIntegrityError("Benchmark spec as_of mismatch")
    if chart_id.get("horizon_days") != prep_params.get("horizon_days"):
        raise BenchmarkIntegrityError("Benchmark spec horizon_days mismatch")
    if chart_id.get("include_timing") != prep_params.get("include_timing"):
        raise BenchmarkIntegrityError("Benchmark spec include_timing mismatch")

    prep_id = spec.get("preparation_identity", {})
    if prep_id.get("packet_id") != handoff.get("packet_id"):
        raise BenchmarkIntegrityError(
            f"Benchmark spec packet_id mismatch: spec {prep_id.get('packet_id')} != handoff {handoff.get('packet_id')}"
        )
    expected_prep_hash = sha256(canonical_bytes(prep_params))
    if prep_id.get("preparation_parameters_sha256") != expected_prep_hash:
        raise BenchmarkIntegrityError(
            f"Benchmark spec preparation parameters hash mismatch: spec {prep_id.get('preparation_parameters_sha256')} != handoff {expected_prep_hash}"
        )

    cand_cfg = spec.get("candidate_protocol", {})
    run_commit = code_ctx.get("artifact_generation_commit_sha")
    if not run_meta.get("fixture") and cand_cfg.get("commit_sha") and run_commit and cand_cfg.get("commit_sha") != run_commit:
        raise BenchmarkIntegrityError(
            f"Candidate commit SHA mismatch: spec {cand_cfg.get('commit_sha')} != run {run_commit}"
        )

    if transport is not None:
        if transport.model != cand_cfg.get("model"):
            raise BenchmarkIntegrityError(
                f"Model mismatch with frozen spec: transport={transport.model} != spec={cand_cfg.get('model')}"
            )
        tl = getattr(transport, "thinking_level", None)
        if tl != cand_cfg.get("thinking_level"):
            raise BenchmarkIntegrityError(
                f"Thinking level mismatch with frozen spec: transport={tl} != spec={cand_cfg.get('thinking_level')}"
            )
        temp = getattr(transport, "temperature", None)
        if temp is None and hasattr(transport, "settings"):
            temp = transport.settings.get("temperature")
        if temp != cand_cfg.get("temperature"):
            raise BenchmarkIntegrityError(
                f"Candidate temperature mismatch with frozen spec: transport={temp} != spec={cand_cfg.get('temperature')}"
            )
        max_tok = getattr(transport, "max_output_tokens", None)
        if max_tok is None and hasattr(transport, "settings"):
            max_tok = transport.settings.get("maxOutputTokens")
        if max_tok != cand_cfg.get("max_output_tokens"):
            raise BenchmarkIntegrityError(
                f"Candidate max_output_tokens mismatch with frozen spec: transport={max_tok} != spec={cand_cfg.get('max_output_tokens')}"
            )

    # Verify frozen contamination corpus hashes
    c_scope = spec.get("contamination_scope", {})
    for item in c_scope.get("corpus_files", []):
        file_path = repo_root / item["relative_path"]
        if not file_path.is_file():
            raise BenchmarkIntegrityError(f"Frozen contamination corpus file missing: {item['relative_path']}")
        actual_sha = sha256(file_path.read_bytes())
        if actual_sha != item["sha256"]:
            raise BenchmarkIntegrityError(
                f"Frozen contamination corpus hash mutated: {item['relative_path']} (frozen {item['sha256']} != disk {actual_sha})"
            )

    return spec


def freeze_spec_in_store(store, spec: Dict[str, object], transport=None) -> Dict[str, object]:
    """Commit benchmark_spec.json into the run store after deterministic authentication."""
    store.assert_code()
    authenticate_benchmark_spec(spec, store, transport=transport)
    with store.lock():
        if store.path("benchmark_spec.json").exists():
            require_equal(load_json(store.path("benchmark_spec.json")), spec, "frozen benchmark spec")
        else:
            store.put_json("benchmark_spec.json", spec)
            store.event("benchmark:spec_frozen", ["benchmark_spec.json"])
    return spec


def validate_run_against_spec(store, transport, stage: str = "selection"):
    """Verify that generation call matches the pre-frozen benchmark spec across all settings."""
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
        authenticate_benchmark_spec(spec, store, transport=transport)

    return spec
