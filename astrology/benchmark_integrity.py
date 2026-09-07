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


def verify_artifacts(run_dir):
    root = Path(run_dir).resolve()
    manifest = load_json(root / "benchmark_manifest.json")
    hashes = manifest.get("artifacts_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise BenchmarkIntegrityError("Missing artifact hash inventory")
    if manifest.get("trace_contract_version") == "1.0" or manifest.get("benchmark_status") == "valid":
        missing = set(REQUIRED_TRACE_ARTIFACTS) - set(hashes)
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


def freeze_score(raw_response: bytes, scores):
    if not isinstance(scores, list) or len(scores) != 17:
        raise BenchmarkIntegrityError("Expected 17 rubric dimensions")
    for row in scores:
        if not isinstance(row, dict) or set(row) != {"alpha", "beta"}:
            raise BenchmarkIntegrityError("Invalid score row")
        if any(type(value) not in (int, float) or not 0 <= value <= 10 for value in row.values()):
            raise BenchmarkIntegrityError("Invalid score value")
    result = {"raw_response_sha256": sha256(raw_response), "dimensions": scores,
              "alpha_total": sum(row["alpha"] for row in scores),
              "beta_total": sum(row["beta"] for row in scores),
              "alpha_wins": sum(row["alpha"] > row["beta"] for row in scores),
              "beta_wins": sum(row["beta"] > row["alpha"] for row in scores),
              "ties": sum(row["alpha"] == row["beta"] for row in scores)}
    return {"score": result, "score_sha256": sha256(canonical_bytes(result))}


def reveal_assignment(commitment, payload, frozen_score, raw_response):
    require_equal(commitment, {"run_id": payload["run_id"], "commitment_sha256": sha256(canonical_bytes(payload))}, "blind commitment")
    if not frozen_score or "score" not in frozen_score:
        raise BenchmarkIntegrityError("Score must be frozen before reveal")
    require_equal(frozen_score, freeze_score(raw_response, frozen_score["score"]["dimensions"]), "frozen score")
    return {"assignment": payload, "score_sha256": frozen_score["score_sha256"]}


REQUIRED_TRACE_ARTIFACTS = (
    '01-handoff.json', '01-candidate-catalog.json', 'author_selection_prompt.txt',
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


def build_trace_manifest(run_dir, repository, pipeline_version, parameters):
    """Inventory captured evidence using the generation context saved BEFORE calls."""
    root = Path(run_dir)
    origin = load_json(root / 'run.json')
    context = origin['code_context']
    verify_commit(repository, context['artifact_generation_commit_sha'])
    missing = [name for name in REQUIRED_TRACE_ARTIFACTS if not (root/name).is_file()]
    if missing:
        raise BenchmarkIntegrityError(f"Incomplete execution trace: {missing}")
    files = [f for f in root.rglob('*') if f.is_file() and f.name not in {'.writer.lock', 'benchmark_manifest.json'}]
    return {
        'trace_contract_version': '1.0', 'run_id': root.name,
        'benchmark_status': 'synthetic_test_fixture' if origin['fixture'] else 'pending_independent_review',
        'execution_kind': 'fixture' if origin['fixture'] else 'captured_live',
        'independently_reviewed': False,
        'artifact_generation_commit_sha': context['artifact_generation_commit_sha'],
        'generation_source_sha256': context['source_sha256'],
        'pipeline_version': pipeline_version, 'preparation_parameters': parameters,
        'artifacts_sha256': {str(f.relative_to(root)): sha256(f.read_bytes()) for f in files},
    }


def check_benchmark_run_output(run_dir, output):
    """Gate narrative acceptance for the explicit benchmarks/<family>/runs layout."""
    run = Path(run_dir).resolve()
    if run.parent.name != 'runs':
        return None
    family = run.parent.parent
    historical = [p for p in family.rglob('*.md') if run not in p.resolve().parents]
    result = check_contamination(output, historical)
    if result['requires_review']:
        raise BenchmarkIntegrityError('Near-copy contamination requires review before acceptance')
    return result
