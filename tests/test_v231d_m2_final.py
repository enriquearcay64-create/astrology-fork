"""Adversarial protocol closure: identity, runtime, evidence and disabled promotion."""
import copy
import subprocess
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
import pytest

from astrology.exceptions import BenchmarkIntegrityError
from astrology.benchmark_integrity import (
    load_json, sha256, canonical_bytes, freeze_score, freeze_score_legacy_positional,
    record_contamination_evidence, build_trace_manifest,
)
from astrology.benchmark_spec import (
    create_benchmark_spec, freeze_spec_in_store, validate_run_against_spec,
    validate_champion_compatibility,
    resolve_contamination_corpus,
)
from astrology.isolated_execution import GeminiTransport
from astrology.live_premium import prepare_run, PIPELINE_VERSION
from astrology.explicit_prose import validate_reviewer_payload
from astrology.blind_execution import commit_blind, evaluate_blind
from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE
from tests.test_captured_execution import current_handoff


@pytest.fixture
def gitrepo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "--allow-empty", "-m", "Fixture"],
        cwd=root, check=True,
    )
    return root


@pytest.fixture
def mock_run_env(gitrepo, tmp_path):
    h = current_handoff()
    cfg = h["preparation_parameters"]
    store = prepare_run(
        tmp_path / "run", gitrepo, CHART_3_BIRTH, PROFILE, fixture=True,
        as_of=datetime.fromisoformat(cfg["effective_as_of"]),
        horizon_days=cfg["horizon_days"], include_timing=cfg["include_timing"],
    )
    return store, h, gitrepo


def test_legacy_positional_evaluator_payload_rejected_against_rubric():
    rubric = {"dimensions": [{"id": "dim1"}, {"id": "dim2"}]}
    bad_payload = {"dimensions": [{"alpha": 9, "beta": 8}, {"alpha": 7, "beta": 6}]}
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_score(b"raw", bad_payload, rubric=rubric)
    assert "Named dimension schema required: missing dimension_id" in str(exc.value)


def test_legacy_positional_evaluator_payload_rejected_in_live_mode():
    scores = [{"alpha": 9, "beta": 8}, {"alpha": 7, "beta": 6}]
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_score(b"raw", scores, rubric=None, allow_legacy_positional=False)
    assert "Legacy positional scoring is forbidden in live execution" in str(exc.value)

    # Legacy helper must succeed when explicitly called
    replayed = freeze_score_legacy_positional(b"raw", scores)
    assert replayed["score"]["alpha_wins"] == 2


def test_foreign_benchmark_spec_rejected_before_selection(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": handoff["preparation_parameters"]["effective_as_of"],
        "horizon_days": handoff["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        repository=gitrepo, candidate_commit_sha=load_json(store.path("run.json"))["code_context"]["artifact_generation_commit_sha"],
    )

    # Corrupt chart identity to simulate a spec for another chart
    bad_spec = copy.deepcopy(spec)
    bad_spec["chart_identity"]["birth_data_hash"] = "0" * 64
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_spec_in_store(store, bad_spec)
    assert "chart identity mismatch" in str(exc.value)

    # Corrupt packet_id
    bad_spec2 = copy.deepcopy(spec)
    bad_spec2["preparation_identity"]["packet_id"] = "wrong_packet"
    with pytest.raises(BenchmarkIntegrityError) as exc2:
        freeze_spec_in_store(store, bad_spec2)
    assert "packet_id mismatch" in str(exc2.value)


def test_candidate_commit_sha_mismatch_rejected_in_live_run(gitrepo, tmp_path):
    h = current_handoff()
    cfg = h["preparation_parameters"]
    from astrology.isolated_execution import code_context
    ctx = code_context(gitrepo)
    audit = {
        "verdict": "benchmark-ready",
        "commit_sha": ctx["artifact_generation_commit_sha"],
        "source_sha256": ctx["source_sha256"],
    }
    store = prepare_run(
        tmp_path / "live_run", gitrepo, CHART_3_BIRTH, PROFILE, fixture=False,
        audit_record=audit,
        as_of=datetime.fromisoformat(cfg["effective_as_of"]),
        horizon_days=cfg["horizon_days"], include_timing=cfg["include_timing"],
    )
    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": h["preparation_parameters"]["effective_as_of"],
        "horizon_days": h["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, h, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        repository=gitrepo, candidate_commit_sha="0123456789abcdef0123456789abcdef01234567",
    )
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_spec_in_store(store, spec)
    assert "Candidate commit SHA mismatch" in str(exc.value)


def test_candidate_temperature_and_max_tokens_mismatch_rejected(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": handoff["preparation_parameters"]["effective_as_of"],
        "horizon_days": handoff["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        temperature=0.7, max_output_tokens=32768,
        repository=gitrepo, candidate_commit_sha=load_json(store.path("run.json"))["code_context"]["artifact_generation_commit_sha"],
    )
    freeze_spec_in_store(store, spec)

    # Candidate with different temperature
    t_bad_temp = GeminiTransport("gemini-3.8-flash", thinking_level="high", temperature=0.2)
    with pytest.raises(BenchmarkIntegrityError) as exc:
        validate_run_against_spec(store, t_bad_temp, "selection")
    assert "Candidate temperature mismatch" in str(exc.value)

    # Candidate with different max tokens
    t_bad_tokens = GeminiTransport("gemini-3.8-flash", thinking_level="high", max_output_tokens=1024)
    with pytest.raises(BenchmarkIntegrityError) as exc2:
        validate_run_against_spec(store, t_bad_tokens, "selection")
    assert "Candidate max_output_tokens mismatch" in str(exc2.value)


def test_evaluator_thinking_model_temp_max_mismatch_rejected(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": handoff["preparation_parameters"]["effective_as_of"],
        "horizon_days": handoff["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        evaluator_temperature=0.0, evaluator_max_output_tokens=32768,
        repository=gitrepo, candidate_commit_sha=load_json(store.path("run.json"))["code_context"]["artifact_generation_commit_sha"],
    )
    freeze_spec_in_store(store, spec)

    # Set up commitment
    store.put("final_reviewed_report.md", b"# Final Report\nCandidate content.")
    with store.lock():
        store.event("reviewer:validated", ["final_reviewed_report.md"])
    commit_blind(store, b"champion report", rubric, champion_descriptor=champ_desc)

    # 1. Model mismatch
    t_bad_model = GeminiTransport("gemini-3.0-pro", thinking_level="high", temperature=0.0)
    with pytest.raises(BenchmarkIntegrityError) as exc1:
        evaluate_blind(store, t_bad_model)
    assert "Evaluator model mismatch" in str(exc1.value)

    # 2. Thinking level mismatch
    t_bad_tl = GeminiTransport("gemini-3.8-flash", thinking_level="low", temperature=0.0)
    with pytest.raises(BenchmarkIntegrityError) as exc2:
        evaluate_blind(store, t_bad_tl)
    assert "Evaluator thinking_level mismatch" in str(exc2.value)

    # 3. Temperature mismatch
    t_bad_temp = GeminiTransport("gemini-3.8-flash", thinking_level="high", temperature=0.7)
    with pytest.raises(BenchmarkIntegrityError) as exc3:
        evaluate_blind(store, t_bad_temp)
    assert "Evaluator temperature mismatch" in str(exc3.value)

    # 4. Max output tokens mismatch
    t_bad_tokens = GeminiTransport("gemini-3.8-flash", thinking_level="high", temperature=0.0, max_output_tokens=4096)
    with pytest.raises(BenchmarkIntegrityError) as exc4:
        evaluate_blind(store, t_bad_tokens)
    assert "Evaluator max_output_tokens mismatch" in str(exc4.value)


def test_self_declared_captured_run_cannot_become_promotion_grade(gitrepo):
    champ_desc = {
        "source": "captured_run",
        "verified_captured_run": True,
        "promotion_grade": True,
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": None,
        "horizon_days": 366,
        "report_sha256": sha256(b"champion report"),
    }
    verified = validate_champion_compatibility(
        CHART_3_BIRTH, PROFILE, None, 366, True,
        champ_desc, b"champion report", gitrepo,
    )
    assert verified["promotion_grade"] is False
    assert verified["source"] == "historical_legacy"

    from astrology.benchmark_integrity import require_promotable
    manifest = {
        "benchmark_status": "valid",
        "execution_kind": "captured_live",
        "independently_reviewed": True,
        "champion_promotion_grade": verified["promotion_grade"],
        "champion_comparison_mode": verified["comparison_mode"],
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        require_promotable(manifest)
    assert "Legacy-weaker or unverified champion cannot satisfy promotion gate" in str(exc.value)


def test_timing_enabled_false_vs_true_champion_mismatch_rejected(gitrepo):
    # Candidate timing is False, Champion timing is True
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": None,
        "horizon_days": 366,
        "report_sha256": sha256(b"champion report"),
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        validate_champion_compatibility(
            CHART_3_BIRTH, PROFILE, None, 366, False, # candidate timing is False!
            champ_desc, b"champion report", gitrepo,
        )
    assert "Champion timing_enabled mismatch" in str(exc.value)


def test_frozen_contamination_corpus_hash_mutation_rejected(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    corpus_file = gitrepo / "historical_chart.md"
    corpus_file.write_text("historical narrative passage")
    c_scope = resolve_contamination_corpus(gitrepo, explicit_files=[corpus_file])

    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": handoff["preparation_parameters"]["effective_as_of"],
        "horizon_days": handoff["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        repository=gitrepo, candidate_commit_sha=load_json(store.path("run.json"))["code_context"]["artifact_generation_commit_sha"],
        contamination_scope=c_scope,
    )
    freeze_spec_in_store(store, spec)

    # Mutate the file on disk after freezing
    corpus_file.write_text("tampered mutated narrative passage")

    with pytest.raises(BenchmarkIntegrityError) as exc:
        record_contamination_evidence(store, "author", b"some new candidate report", gitrepo)
    assert "Frozen contamination corpus hash mutated" in str(exc.value)


def test_contamination_failure_persisted_before_raising(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    corpus_file = gitrepo / "historical_chart.md"
    corpus_file.write_text("Exact duplicated report text.")
    c_scope = resolve_contamination_corpus(gitrepo, explicit_files=[corpus_file])

    rubric = {"dimensions": [{"id": "d1"}]}
    champ_desc = {
        "source": "historical_legacy",
        "birth_data_hash": sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
        "locale": "pt-BR",
        "timing_enabled": True,
        "as_of": handoff["preparation_parameters"]["effective_as_of"],
        "horizon_days": handoff["preparation_parameters"]["horizon_days"],
        "report_sha256": sha256(b"champion report"),
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b"champion report",
        candidate_model="gemini-3.8-flash", candidate_thinking_level="high",
        evaluator_model="gemini-3.8-flash", evaluator_thinking_level="high",
        repository=gitrepo, candidate_commit_sha=load_json(store.path("run.json"))["code_context"]["artifact_generation_commit_sha"],
        contamination_scope=c_scope,
    )
    freeze_spec_in_store(store, spec)

    # Exact duplicated output
    with pytest.raises(BenchmarkIntegrityError) as exc:
        record_contamination_evidence(store, "author", b"Exact duplicated report text.", gitrepo)
    assert "Historical report reused" in str(exc.value)

    # Artifact must be persisted on disk despite the exception!
    art = load_json(store.path("07-author-contamination.json"))
    assert art["passed"] is False
    assert art["requires_review"] is True
    assert "Historical report reused" in art["violation"]


def test_final_trace_identifies_v231d(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    from astrology.benchmark_integrity import REQUIRED_TRACE_ARTIFACTS
    for name in REQUIRED_TRACE_ARTIFACTS:
        p = store.path(name)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"dummy trace artifact")
    manifest = build_trace_manifest(
        store.root, gitrepo, PIPELINE_VERSION, handoff["preparation_parameters"]
    )
    assert manifest["pipeline_version"] == "v2.3.1d"


def test_reviewer_approved_with_empty_corrections_made_accepted(mock_run_env):
    store, handoff, gitrepo = mock_run_env
    payload = {
        "packet_id": handoff["packet_id"],
        "verdict": "approved",
        "blocks": [
            {
                "section_id": "opening",
                "kind": "paragraph",
                "content": "Opening text",
                "synthesis_ids": [],
                "claim_ids": [],
                "timing_ids": [],
            }
        ],
        "corrections_made": [],
        "remaining_warnings": [],
        "regeneration_request": None,
    }
    validated = validate_reviewer_payload(payload, handoff["packet_id"])
    assert validated["corrections_made"] == []
    assert validated["verdict"] == "approved"


def test_promotion_gate_rejects_all_self_declared_authority():
    from astrology.benchmark_integrity import require_promotable
    for champion in ({}, {"champion_promotion_grade": True, "champion_comparison_mode": "standard"}):
        with pytest.raises(BenchmarkIntegrityError):
            require_promotable(dict(benchmark_status="valid", execution_kind="captured_live",
                                   independently_reviewed=True, **champion))


def test_external_spec_cannot_declare_champion_authority(mock_run_env):
    from astrology.benchmark_spec import authenticate_benchmark_spec
    store, _, _ = mock_run_env
    for champion in ({}, {"source": "captured_run", "verified_captured_run": True, "promotion_grade": True},
                     {"source": "historical_legacy", "promotion_grade": True, "comparison_mode": "legacy_weaker"}):
        with pytest.raises(BenchmarkIntegrityError, match="Only historical_legacy"):
            authenticate_benchmark_spec({"champion": champion}, store)


def test_empty_corpus_is_not_a_passing_check(mock_run_env):
    store, _, repo = mock_run_env
    record = record_contamination_evidence(store, "author", b"new text", repo)
    assert record["inspected_corpus"] == []
    assert record["passed"] is False and record["requires_review"] is True


def test_named_legacy_evaluator_scores_rejected():
    row = {"dimension_id": "x", "alpha": 9, "beta": 8,
           "alpha_evidence": ["..."], "beta_evidence": ["..."]}
    with pytest.raises(BenchmarkIntegrityError):
        freeze_score(b"raw", {"dimensions": [row]}, rubric={"dimensions": ["x"]})


@pytest.mark.parametrize('stage,protocol', [('run-captured', 'candidate_protocol'), ('evaluate-captured', 'evaluator_protocol')])
def test_cli_uses_frozen_transport_settings(tmp_path, monkeypatch, stage, protocol, capsys):
    import sys
    import astrology.cli as cli
    import astrology.live_premium as live
    import astrology.blind_execution as blind
    root = tmp_path / 'run'
    root.mkdir()
    cfg = dict(model='explicit-test-model', thinking_level='high', temperature=0.13, max_output_tokens=12345)
    (root / 'benchmark_spec.json').write_bytes(canonical_bytes({protocol: cfg}))
    (root / '01-handoff.json').write_text('{}')
    (root / 'assignment_commitment.json').write_text('{}')
    inp = tmp_path / 'input.json'
    inp.write_bytes(canonical_bytes(asdict(CHART_3_BIRTH)))
    monkeypatch.setattr(cli, 'validate_frozen_inputs', lambda *a: None)
    seen = []
    def execute(store, transport):
        seen.append((transport.model, transport.thinking_level, transport.temperature, transport.max_output_tokens))
        return {}
    monkeypatch.setattr(live, 'continue_run', execute)
    monkeypatch.setattr(blind, 'evaluate_blind', execute)
    args = ['astrology-skill', str(inp), '--premium-stage', stage, '--run-dir', str(root)]
    monkeypatch.setattr(sys, 'argv', args)
    assert cli.main() == 0
    assert seen == [('explicit-test-model', 'high', 0.13, 12345)]
    monkeypatch.setattr(sys, 'argv', args + ['--model', 'wrong'])
    assert cli.main() != 0
    assert len(seen) == 1


def test_cli_prepares_snapshot_once(tmp_path, monkeypatch):
    import sys
    import astrology.cli as cli
    import astrology.live_premium as live
    import astrology.benchmark_spec as specs
    from astrology.isolated_execution import RunStore
    handoff = current_handoff()
    root = tmp_path / 'run'
    inp, desc, rubric, report, audit = [tmp_path / n for n in ('input.json', 'desc.json', 'rubric.json', 'report.md', 'audit.json')]
    inp.write_bytes(canonical_bytes({**asdict(CHART_3_BIRTH), 'localization_profile': asdict(PROFILE)}))
    descriptor = dict(source='historical_legacy', birth_data_hash=sha256(canonical_bytes(asdict(CHART_3_BIRTH))),
                      locale='pt-BR', timing_enabled=True,
                      as_of=handoff['preparation_parameters']['effective_as_of'],
                      horizon_days=handoff['preparation_parameters']['horizon_days'], report_sha256=sha256(b'old'))
    desc.write_bytes(canonical_bytes(descriptor)); rubric.write_bytes(canonical_bytes({'dimensions':['x']}))
    report.write_bytes(b'old'); audit.write_text('{}')
    calls=[]
    def prepare(*args, **kwargs):
        calls.append(kwargs['as_of'])
        root.mkdir()
        store=RunStore(root)
        store.put_json('01-handoff.json', handoff)
        store.put_json('run.json', {'code_context':{'artifact_generation_commit_sha':'test-commit'}})
        return store
    monkeypatch.setattr(live, 'prepare_run', prepare)
    monkeypatch.setattr(cli, 'prepare_premium_handoff', lambda *a, **kw: pytest.fail('Second snapshot preparation'))
    frozen=[]
    monkeypatch.setattr(specs, 'freeze_spec_in_store', lambda store, spec: frozen.append(spec))
    monkeypatch.setattr(sys, 'argv', ['astrology-skill',str(inp),'--premium-stage','prepare-run','--run-dir',str(root),
        '--audit-record',str(audit),'--rubric',str(rubric),'--champion-report',str(report),'--champion-descriptor',str(desc),
        '--model','test-model','--thinking-level','high','--evaluator-model','test-eval','--evaluator-thinking-level','high'])
    assert cli.main()==0
    assert calls==[None]
    assert frozen[0]['preparation_identity']['packet_id']==handoff['packet_id']
    assert frozen[0]['chart_identity']['as_of']==handoff['preparation_parameters']['effective_as_of']


@pytest.mark.parametrize('evidence', ['...', 'Generic praise absent from either report'])
def test_unanchored_evidence_never_freezes_score(gitrepo, tmp_path, evidence):
    from astrology.isolated_execution import RunStore
    from tests.test_captured_execution import FixtureTransport
    store=RunStore.create(tmp_path/'evidence-run',gitrepo,{},fixture=True)
    store.put_json('01-handoff.json',{'reasoning_packet':{'facts':{}},'preparation_parameters':{}})
    store.put('final_reviewed_report.md',b'Candidate passage')
    store.event('reviewer:validated',['01-handoff.json','final_reviewed_report.md'])
    commit_blind(store,b'Champion passage',{'dimensions':['x']})
    payload={'dimensions':[{'dimension_id':'x','alpha_score':9,'beta_score':8,
                           'alpha_evidence':[evidence],'beta_evidence':[evidence]}]}
    with pytest.raises(BenchmarkIntegrityError, match='quote the corresponding report'):
        evaluate_blind(store,FixtureTransport([payload]))
    assert store.path('stages/evaluator/response.raw.json').exists()
    assert not store.path('score_frozen.json').exists()
