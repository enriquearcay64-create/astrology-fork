"""Deterministic benchmark evidence utilities. These do not claim runtime isolation."""
from __future__ import annotations
import hashlib
import json
import secrets
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from .exceptions import BenchmarkIntegrityError


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(value: bytes):
    return hashlib.sha256(value).hexdigest()


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BenchmarkIntegrityError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique)


def require_equal(actual, expected, label):
    if canonical_bytes(actual) != canonical_bytes(expected):
        raise BenchmarkIntegrityError(f"Canonical mismatch: {label}")


def require_promotable(manifest):
    if manifest.get("benchmark_status") != "valid" or manifest.get("execution_kind") != "captured_live" or manifest.get("independently_reviewed") is not True:
        raise BenchmarkIntegrityError("Benchmark is not valid promotion evidence")
    # Captured Champion authentication is deferred. No local descriptor or manifest
    # flag can enable promotion until that evidence path is implemented and audited.
    raise BenchmarkIntegrityError("Legacy-weaker or unverified champion cannot satisfy promotion gate")


def verify_artifacts(run_dir):
    root = Path(run_dir).resolve()
    manifest = load_json(root / "benchmark_manifest.json")
    hashes = manifest.get("artifacts_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise BenchmarkIntegrityError("Missing artifact hash inventory")
    if manifest.get("trace_contract_version") == "1.0" or manifest.get("benchmark_status") == "valid":
        required = set(REQUIRED_TRACE_ARTIFACTS)
        if manifest.get("benchmark_status") == "valid" or (root / "benchmark_spec.json").is_file():
            required.update(REQUIRED_BENCHMARK_PROMOTION_ARTIFACTS)
        missing = required - set(hashes)
        if missing:
            raise BenchmarkIntegrityError(f"Incomplete execution trace inventory: {sorted(missing)}")
    for name, expected in hashes.items():
        path = (root / name).resolve()
        if root not in path.parents:
            raise BenchmarkIntegrityError(f"Artifact escapes run directory: {name}")
        if not path.is_file():
            raise BenchmarkIntegrityError(f"Missing expected benchmark artifact: {name}")
        if sha256(path.read_bytes()) != expected:
            raise BenchmarkIntegrityError(f"Hash mismatch for {name}")
    return manifest


def git_commit(repository):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repository, text=True).strip()


def verify_commit(repository, commit):
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise BenchmarkIntegrityError("Invalid commit SHA")
    proc = subprocess.run(["git", "cat-file", "-e", commit + "^{commit}"], cwd=repository, capture_output=True)
    if proc.returncode:
        raise BenchmarkIntegrityError(f"Unresolvable commit: {commit}")


def check_contamination(output: bytes, historical_reports, *, ancestral_paths=(), similarity_threshold=0.98):
    """Reject exact unrelated reuse; report near copies for human review (not novelty proof).

    Call on narrative prose, excluding deterministic appendices. Ancestors are supplied
    by the orchestrator from the current run lineage, never by a model response.
    """
    ancestors = {Path(p).resolve() for p in ancestral_paths}
    digest = sha256(output)
    normalized = " ".join(output.decode("utf-8").split())
    warnings = []
    for filename in historical_reports:
        path = Path(filename).resolve()
        if path in ancestors:
            continue
        other = path.read_bytes()
        if sha256(other) == digest:
            raise BenchmarkIntegrityError(f"Historical report reused: {path}")
        ratio = SequenceMatcher(None, normalized.split(), other.decode("utf-8").split(), autojunk=False).ratio()
        if ratio >= similarity_threshold:
            warnings.append({"historical_report": str(path), "similarity": ratio})
    return {"sha256": digest, "requires_review": bool(warnings), "near_copies": warnings}


def create_assignment(run_id, reports, mapping, rubric_hash, truth_hash):
    """Returns public commitment and private payload; caller must store separately."""
    if set(mapping) != set(reports) or sorted(mapping.values()) != ["candidate", "champion"]:
        raise BenchmarkIntegrityError("Invalid blind mapping")
    private = {"run_id": run_id, "nonce": secrets.token_hex(32), "mapping": mapping,
               "content_sha256": {name: sha256(data) for name, data in reports.items()},
               "rubric_sha256": rubric_hash, "ground_truth_sha256": truth_hash}
    return {"run_id": run_id, "commitment_sha256": sha256(canonical_bytes(private))}, private


def freeze_score(raw_response: bytes, payload, rubric=None, *, allow_legacy_positional=None):
    if rubric is not None:
        allow_legacy_positional = False
    elif allow_legacy_positional is None:
        allow_legacy_positional = True
    if rubric is not None:
        # Rubric supplied: live evaluation MUST use named structured dimensions. Positional fallback strictly forbidden.
        if not isinstance(payload, dict) or "dimensions" not in payload:
            raise BenchmarkIntegrityError("Expected dictionary with 'dimensions' in evaluation payload against frozen rubric")
        rows = payload["dimensions"]
        if not isinstance(rows, list) or not rows:
            raise BenchmarkIntegrityError("Expected non-empty list of dimensions in evaluation payload")
        from .benchmark_spec import extract_rubric_dimension_ids
        expected_ids = extract_rubric_dimension_ids(rubric)

        seen_ids = set()
        validated_rows = []
        for row in rows:
            if not isinstance(row, dict):
                raise BenchmarkIntegrityError("Each dimension row must be an object")
            if "dimension_id" not in row:
                raise BenchmarkIntegrityError("Named dimension schema required: missing dimension_id in evaluation row")
            dim_id = row.get("dimension_id")
            if not isinstance(dim_id, str) or dim_id not in expected_ids:
                raise BenchmarkIntegrityError(f"Unknown or missing dimension_id: {dim_id}")
            if dim_id in seen_ids:
                raise BenchmarkIntegrityError(f"Duplicate dimension_id in evaluation: {dim_id}")
            seen_ids.add(dim_id)

            alpha = row.get("alpha_score")
            beta = row.get("beta_score")
            if type(alpha) not in (int, float) or not 0 <= alpha <= 10:
                raise BenchmarkIntegrityError(f"Invalid alpha score for dimension {dim_id}: {alpha}")
            if type(beta) not in (int, float) or not 0 <= beta <= 10:
                raise BenchmarkIntegrityError(f"Invalid beta score for dimension {dim_id}: {beta}")

            alpha_ev = row.get("alpha_evidence", [])
            beta_ev = row.get("beta_evidence", [])
            if not isinstance(alpha_ev, list) or not alpha_ev or not all(isinstance(x, str) and x.strip() for x in alpha_ev):
                raise BenchmarkIntegrityError(f"Dimension {dim_id} requires non-empty alpha_evidence list of strings")
            if not isinstance(beta_ev, list) or not beta_ev or not all(isinstance(x, str) and x.strip() for x in beta_ev):
                raise BenchmarkIntegrityError(f"Dimension {dim_id} requires non-empty beta_evidence list of strings")

            mismatches = row.get("factual_mismatches", [])
            if not isinstance(mismatches, list) or any(not isinstance(x, str) for x in mismatches):
                raise BenchmarkIntegrityError(f"Dimension {dim_id} factual_mismatches must be a list of strings")

            uncertainty = row.get("uncertainty", "")
            if uncertainty is not None and not isinstance(uncertainty, str):
                raise BenchmarkIntegrityError(f"Dimension {dim_id} uncertainty must be a string or null")

            validated_rows.append({
                "dimension_id": dim_id,
                "alpha_score": alpha,
                "beta_score": beta,
                "alpha_evidence": alpha_ev,
                "beta_evidence": beta_ev,
                "factual_mismatches": mismatches,
                "uncertainty": uncertainty or "",
            })

        if seen_ids != set(expected_ids):
            missing = sorted(set(expected_ids) - seen_ids)
            raise BenchmarkIntegrityError(f"Missing rubric dimensions in evaluation: {missing}")

        id_order = {dim_id: i for i, dim_id in enumerate(expected_ids)}
        validated_rows.sort(key=lambda r: id_order[r["dimension_id"]])

        alpha_total = sum(r["alpha_score"] for r in validated_rows)
        beta_total = sum(r["beta_score"] for r in validated_rows)
        alpha_wins = sum(r["alpha_score"] > r["beta_score"] for r in validated_rows)
        beta_wins = sum(r["beta_score"] > r["alpha_score"] for r in validated_rows)
        ties = sum(r["alpha_score"] == r["beta_score"] for r in validated_rows)

        result = {
            "raw_response_sha256": sha256(raw_response),
            "dimension_count": len(expected_ids),
            "dimensions": validated_rows,
            "alpha_total": alpha_total,
            "beta_total": beta_total,
            "alpha_wins": alpha_wins,
            "beta_wins": beta_wins,
            "ties": ties,
            "overall_notes": str(payload.get("overall_notes", "")),
        }
        return {"score": result, "score_sha256": sha256(canonical_bytes(result))}

    # Rubric is None: only allowed when allow_legacy_positional is True or named dimensions without rubric
    if isinstance(payload, dict) and "dimensions" in payload:
        rows = payload["dimensions"]
        if not isinstance(rows, list) or not rows:
            raise BenchmarkIntegrityError("Expected non-empty list of dimensions in evaluation payload")
        if not allow_legacy_positional or (rows and isinstance(rows[0], dict) and "dimension_id" in rows[0]):
            expected_ids = [r.get("dimension_id") for r in rows if isinstance(r, dict)]
            if any(not d for d in expected_ids):
                raise BenchmarkIntegrityError("All dimension rows must specify dimension_id")
            if len(expected_ids) != len(set(expected_ids)):
                raise BenchmarkIntegrityError("Duplicate dimension_id in evaluation rows")
            seen_ids = set()
            validated_rows = []
            for row in rows:
                if not isinstance(row, dict):
                    raise BenchmarkIntegrityError("Each dimension row must be an object")
                dim_id = row.get("dimension_id")
                if not isinstance(dim_id, str):
                    raise BenchmarkIntegrityError(f"Unknown or missing dimension_id: {dim_id}")
                seen_ids.add(dim_id)
                alpha = row.get("alpha_score", row.get("alpha"))
                beta = row.get("beta_score", row.get("beta"))
                if type(alpha) not in (int, float) or not 0 <= alpha <= 10 or type(beta) not in (int, float) or not 0 <= beta <= 10:
                    raise BenchmarkIntegrityError(f"Invalid score values for dimension {dim_id}")
                alpha_ev = row.get("alpha_evidence", [])
                beta_ev = row.get("beta_evidence", [])
                if not isinstance(alpha_ev, list) or not alpha_ev or not isinstance(beta_ev, list) or not beta_ev:
                    raise BenchmarkIntegrityError(f"Dimension {dim_id} requires non-empty alpha and beta evidence")
                validated_rows.append({
                    "dimension_id": dim_id,
                    "alpha_score": alpha,
                    "beta_score": beta,
                    "alpha_evidence": alpha_ev,
                    "beta_evidence": beta_ev,
                    "factual_mismatches": row.get("factual_mismatches", []),
                    "uncertainty": row.get("uncertainty", "") or "",
                })
            result = {
                "raw_response_sha256": sha256(raw_response),
                "dimension_count": len(validated_rows),
                "dimensions": validated_rows,
                "alpha_total": sum(r["alpha_score"] for r in validated_rows),
                "beta_total": sum(r["beta_score"] for r in validated_rows),
                "alpha_wins": sum(r["alpha_score"] > r["beta_score"] for r in validated_rows),
                "beta_wins": sum(r["beta_score"] > r["alpha_score"] for r in validated_rows),
                "ties": sum(r["alpha_score"] == r["beta_score"] for r in validated_rows),
                "overall_notes": str(payload.get("overall_notes", "")),
            }
            return {"score": result, "score_sha256": sha256(canonical_bytes(result))}

    # Positional list fallback only allowed when explicitly enabled
    if not allow_legacy_positional:
        raise BenchmarkIntegrityError("Legacy positional scoring is forbidden in live execution; structured named dimensions required")

    scores = payload["dimensions"] if (isinstance(payload, dict) and "dimensions" in payload) else payload
    if not isinstance(scores, list) or not scores:
        raise BenchmarkIntegrityError("Expected non-empty list of scores")
    for row in scores:
        if not isinstance(row, dict) or set(row) != {"alpha", "beta"}:
            raise BenchmarkIntegrityError("Invalid score row")
        if any(type(value) not in (int, float) or not 0 <= value <= 10 for value in row.values()):
            raise BenchmarkIntegrityError("Invalid score value")
    result = {"raw_response_sha256": sha256(raw_response), "dimensions": scores,
              "dimension_count": len(scores),
              "alpha_total": sum(row["alpha"] for row in scores),
              "beta_total": sum(row["beta"] for row in scores),
              "alpha_wins": sum(row["alpha"] > row["beta"] for row in scores),
              "beta_wins": sum(row["beta"] > row["alpha"] for row in scores),
              "ties": sum(row["alpha"] == row["beta"] for row in scores)}
    return {"score": result, "score_sha256": sha256(canonical_bytes(result))}


def freeze_score_legacy_positional(raw_response: bytes, scores):
    """Historical and replay-only positional scoring; cannot be invoked by captured live evaluator."""
    return freeze_score(raw_response, scores, rubric=None, allow_legacy_positional=True)


def reveal_assignment(commitment, payload, frozen_score, raw_response):
    require_equal(commitment, {"run_id": payload["run_id"], "commitment_sha256": sha256(canonical_bytes(payload))}, "blind commitment")
    if not frozen_score or "score" not in frozen_score:
        raise BenchmarkIntegrityError("Score must be frozen before reveal")
    dims = frozen_score["score"]["dimensions"]
    if dims and isinstance(dims[0], dict) and "dimension_id" in dims[0]:
        recomputed = freeze_score(raw_response, {"dimensions": dims, "overall_notes": frozen_score["score"].get("overall_notes", "")})
    else:
        recomputed = freeze_score_legacy_positional(raw_response, dims)
    require_equal(frozen_score, recomputed, "frozen score")
    return {"assignment": payload, "score_sha256": frozen_score["score_sha256"]}


REQUIRED_TRACE_ARTIFACTS = (
    'run.json', '01-handoff.json', '01-candidate-catalog.json', 'author_selection_prompt.txt',
    'author_selection_response_raw.json', '01-author-selection-plan.json',
    '01-selection-validation.json', '01-prospective-block-plan.json',
    'author_prompt.txt', 'author_response_raw.json', '02-author-bundle.json',
    'author_draft.md', '03-provenance-guard.json', 'reviewer_prompt.txt',
    'reviewer_response_raw.json', '04-reviewer-bundle.json', 'final_reviewed_report.md',
    '05-publication-guard.json', '06-editorial-qa.json', 'canonical_technical_appendix.md',
    'evaluator_prompt.txt', 'ground_truth.json', 'evaluator_response_raw.json',
    'score_frozen.json', 'assignment_commitment.json', 'reveal_record.json',
    'runtime_execution_metadata.json',
)

REQUIRED_BENCHMARK_PROMOTION_ARTIFACTS = (
    'benchmark_spec.json', '07-author-contamination.json', '07-reviewer-contamination.json',
)


def build_trace_manifest(run_dir, repository, pipeline_version, parameters):
    """Inventory captured evidence using the generation context saved BEFORE calls."""
    root = Path(run_dir)
    origin = load_json(root / 'run.json')
    context = origin['code_context']
    verify_commit(repository, context['artifact_generation_commit_sha'])
    missing = [name for name in REQUIRED_TRACE_ARTIFACTS if not (root/name).is_file()]
    if (root / 'benchmark_spec.json').is_file() or origin.get('fixture') is False:
        missing.extend([name for name in REQUIRED_BENCHMARK_PROMOTION_ARTIFACTS if not (root/name).is_file()])
    if missing:
        raise BenchmarkIntegrityError(f"Incomplete execution trace: {sorted(set(missing))}")
    files = [f for f in root.rglob('*') if f.is_file() and f.name not in {'.writer.lock', 'benchmark_manifest.json'}]
    champ_prom_grade = None
    champ_comp_mode = None
    if (root / 'benchmark_spec.json').is_file():
        spec = load_json(root / 'benchmark_spec.json')
        champ_prom_grade = False
        champ_comp_mode = 'legacy_weaker'
    return {
        'trace_contract_version': '1.0', 'run_id': root.name,
        'benchmark_status': 'synthetic_test_fixture' if origin['fixture'] else 'pending_independent_review',
        'execution_kind': 'fixture' if origin['fixture'] else 'captured_live',
        'independently_reviewed': False,
        'champion_promotion_grade': champ_prom_grade,
        'champion_comparison_mode': champ_comp_mode,
        'artifact_generation_commit_sha': context['artifact_generation_commit_sha'],
        'generation_source_sha256': context['source_sha256'],
        'pipeline_version': pipeline_version, 'preparation_parameters': parameters,
        'artifacts_sha256': {str(f.relative_to(root)): sha256(f.read_bytes()) for f in files},
    }


def record_contamination_evidence(store, stage: str, output: bytes, repository: Path, corpus_files=None, similarity_threshold=0.98):
    """Portable contamination check persisting 07-<stage>-contamination.json and logging event."""
    repo_root = Path(repository).resolve()
    inspected_corpus = []
    target_items = []

    if store.path("benchmark_spec.json").exists():
        spec = load_json(store.path("benchmark_spec.json"))
        c_scope = spec.get("contamination_scope", {})
        spec_files = c_scope.get("corpus_files", [])
        for item in spec_files:
            rel = item["relative_path"]
            p = (repo_root / rel).resolve()
            if repo_root not in p.parents:
                raise BenchmarkIntegrityError("Contamination corpus escapes repository")
            if not p.is_file():
                raise BenchmarkIntegrityError(f"Contamination corpus file missing: {rel}")
            file_sha = sha256(p.read_bytes())
            if file_sha != item["sha256"]:
                raise BenchmarkIntegrityError(
                    f"Frozen contamination corpus hash mutated: {rel} (frozen {item['sha256']} != disk {file_sha})"
                )
            target_items.append((p, rel, file_sha))
    elif corpus_files is not None:
        for p in corpus_files:
            p_res = Path(p).resolve()
            if p_res.is_file():
                try:
                    rel = str(p_res.relative_to(repo_root))
                except ValueError:
                    rel = p_res.name
                target_items.append((p_res, rel, sha256(p_res.read_bytes())))

    output_digest = sha256(output)
    normalized_output = " ".join(output.decode("utf-8").split())
    near_copies = []
    artifact_name = f"07-{stage}-contamination.json"

    for path, rel_path, file_digest in target_items:
        inspected_corpus.append({"relative_path": rel_path, "sha256": file_digest})

        if file_digest == output_digest:
            record = {
                "stage": stage,
                "output_sha256": output_digest,
                "inspected_corpus": inspected_corpus,
                "similarity_threshold": similarity_threshold,
                "near_copies": near_copies,
                "exact_match": rel_path,
                "requires_review": True,
                "passed": False,
                "violation": f"Historical report reused: {rel_path}",
            }
            with store.lock():
                store.put_json(artifact_name, record)
                store.event(f"{stage}:contamination_failed", [artifact_name])
            raise BenchmarkIntegrityError(f"Historical report reused: {rel_path}")

        ratio = SequenceMatcher(None, normalized_output.split(), path.read_bytes().decode("utf-8").split(), autojunk=False).ratio()
        if ratio >= similarity_threshold:
            near_copies.append({"relative_path": rel_path, "similarity": ratio})

    record = {
        "stage": stage,
        "output_sha256": output_digest,
        "inspected_corpus": inspected_corpus,
        "similarity_threshold": similarity_threshold,
        "near_copies": near_copies,
        "requires_review": bool(near_copies) or not inspected_corpus,
        "passed": bool(inspected_corpus) and not near_copies,
    }
    if near_copies:
        record["violation"] = f"Near-copy contamination requires review before acceptance: {near_copies}"
        with store.lock():
            store.put_json(artifact_name, record)
            store.event(f"{stage}:contamination_failed", [artifact_name])
        raise BenchmarkIntegrityError(f"Near-copy contamination requires review before acceptance: {near_copies}")

    with store.lock():
        store.put_json(artifact_name, record)
        store.event(f"{stage}:contamination_checked", [artifact_name])

    return record


def check_benchmark_run_output(run_dir, output):
    """Gate narrative acceptance for benchmarks/<family>/runs layout."""
    run = Path(run_dir).resolve()
    if run.parent.name != 'runs':
        return None
    family = run.parent.parent
    historical = [p for p in family.rglob('*.md') if run not in p.resolve().parents]
    result = check_contamination(output, historical)
    if result['requires_review']:
        raise BenchmarkIntegrityError('Near-copy contamination requires review before acceptance')
    return result
