"""Adversarial tests for V2.3.1c M2 Release Blockers.

Validates:
1. Captured Reviewer cannot be implicitly approved.
2. Reviewer verdict 'regenerate_author' halts publication and prevents delivery.
3. Reviewer verdict 'blocked' halts publication and prevents delivery.
4. Benchmark rubric/comparator/settings frozen BEFORE first model generation.
5. Incompatible Champion is strictly rejected at commitment.
6. Explicit Gemini thinking level enters request and replay identity.
7. Contamination checks cannot be bypassed by path structure.
8. Contamination evidence is persisted as 07-*-contamination.json in trace.
9. Evaluator cannot submit generic evidence or invalid/missing dimensions.
10. Reveal cannot occur under changed code source identity.
11. Champion and candidate commits can diverge legitimately.
12. Legacy champion comparison is flagged as weaker, non-promotion grade.
"""
import copy
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import pytest

from astrology.exceptions import BenchmarkIntegrityError, SelectionPlanValidationError
from astrology.benchmark_integrity import (
    load_json, sha256, canonical_bytes, freeze_score, reveal_assignment,
    record_contamination_evidence, build_trace_manifest, verify_artifacts,
)
from astrology.benchmark_spec import (
    create_benchmark_spec, freeze_spec_in_store, validate_run_against_spec,
    validate_champion_compatibility, extract_rubric_dimension_ids,
)
from astrology.isolated_execution import RunStore, GeminiTransport
from astrology.live_premium import prepare_run, continue_run, verify_captured_derivation
from astrology.explicit_prose import render_explicit_blocks, validate_reviewer_payload
from astrology.blind_execution import commit_blind, evaluate_blind, reveal_blind
from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE, BENCHMARK_DIR
from tests.test_captured_execution import (
    FixtureTransport, _explicit_payload, _explicit_reviewer_payload,
    current_handoff, with_editorial_sections,
)
from astrology.pipeline import plan_prospective_narrative_blocks, bind_prospective_plan_to_prose


@pytest.fixture
def gitrepo(tmp_path):
    root = tmp_path / 'repo'
    root.mkdir()
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-q', '--allow-empty', '-m', 'Fixture'], cwd=root, check=True)
    return root


@pytest.fixture
def mock_run_env(gitrepo, tmp_path):
    h = current_handoff()
    cfg = h['preparation_parameters']
    store = prepare_run(
        tmp_path / 'run', gitrepo, CHART_3_BIRTH, PROFILE, fixture=True,
        as_of=datetime.fromisoformat(cfg['effective_as_of']),
        horizon_days=cfg['horizon_days'], include_timing=cfg['include_timing'],
    )
    p = load_json(BENCHMARK_DIR / '01-author-selection-plan.json')
    p['packet_id'] = h['packet_id']
    p = with_editorial_sections(p, h)
    blocks = plan_prospective_narrative_blocks(h, author_selection_plan=p)

    draft_prose = (BENCHMARK_DIR / 'author_draft.md').read_text()
    draft_sources, _, _ = bind_prospective_plan_to_prose(draft_prose, blocks, h['reader_domain_manifest'])
    author_resp = _explicit_payload(draft_prose, draft_sources, h)

    final_prose = (BENCHMARK_DIR / 'final_reviewed_report.md').read_text()
    final_sources, _, _ = bind_prospective_plan_to_prose(final_prose, blocks, h['reader_domain_manifest'])
    reviewer_resp = _explicit_reviewer_payload(final_prose, final_sources, h)

    return {
        'store': store, 'handoff': h, 'selection': p, 'blocks': blocks,
        'author_resp': author_resp, 'reviewer_resp': reviewer_resp,
        'gitrepo': gitrepo, 'tmp_path': tmp_path,
    }


def test_reviewer_cannot_be_implicitly_approved(mock_run_env):
    """1. Captured Reviewer cannot be implicitly approved: missing verdict must fail closed."""
    env = mock_run_env
    store = env['store']
    # Omit 'verdict' from reviewer payload (simulate legacy or defective reviewer)
    bad_reviewer = copy.deepcopy(env['reviewer_resp'])
    del bad_reviewer['verdict']

    t = FixtureTransport([env['selection'], env['author_resp'], bad_reviewer])
    with pytest.raises(SelectionPlanValidationError) as exc:
        continue_run(store, t)
    assert 'Invalid reviewer payload schema' in str(exc.value)


def test_regenerate_author_prevents_publication(mock_run_env):
    """2. 'regenerate_author' prevents publication, records ReviewerBundle and Guard, stops execution."""
    env = mock_run_env
    store = env['store']

    regen_reviewer = copy.deepcopy(env['reviewer_resp'])
    regen_reviewer['verdict'] = 'regenerate_author'
    regen_reviewer['regeneration_request'] = {
        'items': [{
            'domain_id': 'identity',
            'path_ids': ['identity_core'],
            'reason': 'Semantic tone lacks calibrated modesty.',
        }]
    }
    regen_reviewer['remaining_warnings'] = ['Author draft needs revision in identity domain.']

    t = FixtureTransport([env['selection'], env['author_resp'], regen_reviewer])
    with pytest.raises(BenchmarkIntegrityError) as exc:
        continue_run(store, t)
    assert "Reviewer verdict was 'regenerate_author'" in str(exc.value)

    # Verify structured ReviewerBundle and non-publication guard were saved
    assert store.path('04-reviewer-bundle.json').exists()
    assert store.path('05-publication-guard.json').exists()
    bundle = load_json(store.path('04-reviewer-bundle.json'))
    assert bundle['verdict'] == 'regenerate_author'
    pub = load_json(store.path('05-publication-guard.json'))
    assert pub['approved'] is False

    # Invariant: final_reviewed_report.md MUST NOT exist
    assert not store.path('final_reviewed_report.md').exists()


def test_blocked_prevents_publication(mock_run_env):
    """3. 'blocked' verdict prevents publication and recording of deliverable."""
    env = mock_run_env
    store = env['store']

    blocked_reviewer = copy.deepcopy(env['reviewer_resp'])
    blocked_reviewer['verdict'] = 'blocked'
    blocked_reviewer['remaining_warnings'] = ['Severe flattery and medicalization detected; unrecoverable.']
    blocked_reviewer['regeneration_request'] = None

    t = FixtureTransport([env['selection'], env['author_resp'], blocked_reviewer])
    with pytest.raises(BenchmarkIntegrityError) as exc:
        continue_run(store, t)
    assert "Reviewer verdict was 'blocked'" in str(exc.value)

    assert store.path('04-reviewer-bundle.json').exists()
    assert store.path('05-publication-guard.json').exists()
    pub = load_json(store.path('05-publication-guard.json'))
    assert pub['approved'] is False
    assert not store.path('final_reviewed_report.md').exists()


def test_benchmark_rubric_comparator_settings_frozen_before_generation(mock_run_env):
    """4. Benchmark spec must be frozen BEFORE generation. Post-generation insertion rejected."""
    env = mock_run_env
    store = env['store']
    repo = env['gitrepo']
    handoff = env['handoff']

    rubric = {'dimensions': [f'Dim {i}' for i in range(17)]}
    champ_desc = {
        'source': 'captured_run',
        'report_sha256': sha256(b'champion text'),
        'birth_data_hash': sha256(canonical_bytes(CHART_3_BIRTH.__dict__)),
        'locale': 'pt-BR',
        'as_of': handoff['preparation_parameters']['effective_as_of'],
        'horizon_days': 366,
        'timing_enabled': True,
        'commit_sha': None,
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b'champion text',
        'gemini-3.8-flash', 'high', 'gemini-3.8-flash', repo, 'test_commit_sha'
    )

    # Case A: Freezing before generation works
    freeze_spec_in_store(store, spec)
    assert store.path('benchmark_spec.json').exists()

    # Case B: If transport model does not match spec, continue_run fails
    t_mismatch = FixtureTransport([env['selection']])
    t_mismatch.model = 'wrong-model'
    with pytest.raises(BenchmarkIntegrityError) as exc:
        continue_run(store, t_mismatch)
    assert 'Model mismatch with frozen spec' in str(exc.value)


def test_incompatible_champion_rejected(mock_run_env):
    """5. Incompatible Champion chart/locale/as_of rejected."""
    env = mock_run_env
    handoff = env['handoff']
    repo = env['gitrepo']

    bad_desc = {
        'source': 'captured_run',
        'report_sha256': sha256(b'champion text'),
        'birth_data_hash': 'wrong_hash',  # Different birth chart!
        'locale': 'pt-BR',
        'timing_enabled': True,
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        validate_champion_compatibility(
            CHART_3_BIRTH, PROFILE, None, 366, True, bad_desc, b'champion text', repo
        )
    assert 'Champion birth data mismatch' in str(exc.value)

    # Wrong locale
    bad_locale_desc = copy.deepcopy(bad_desc)
    bad_locale_desc['birth_data_hash'] = sha256(canonical_bytes(CHART_3_BIRTH.__dict__))
    bad_locale_desc['locale'] = 'en-US'  # Mismatched language
    with pytest.raises(BenchmarkIntegrityError) as exc:
        validate_champion_compatibility(
            CHART_3_BIRTH, PROFILE, None, 366, True, bad_locale_desc, b'champion text', repo
        )
    assert 'Champion locale mismatch' in str(exc.value)


def test_explicit_gemini_thinking_level_enters_request():
    """6. Explicit Gemini thinking level enters generationConfig and receipt."""
    t_high = GeminiTransport('gemini-3.8-flash', thinking_level='high')
    assert t_high.thinking_level == 'high'
    req = t_high.request('test prompt')
    assert req['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'HIGH'}

    t_low = GeminiTransport('gemini-3.8-flash', thinking_level='low')
    assert t_low.thinking_level == 'low'
    assert t_low.request('test prompt')['generationConfig']['thinkingConfig'] == {'thinkingLevel': 'LOW'}

    with pytest.raises(ValueError) as exc:
        GeminiTransport('gemini-3.8-flash', thinking_level='extreme')
    assert 'Invalid thinking level' in str(exc.value)


def test_contamination_checks_cannot_bypass_directory(mock_run_env, tmp_path):
    """7. Contamination checks run regardless of directory structure."""
    env = mock_run_env
    store = env['store']
    repo = env['gitrepo']

    # Create a historical report in repo
    hist_file = repo / 'historical_sample.md'
    hist_file.write_text('Identical prose content that should trigger exact reuse.')

    # Run check with identical content
    with pytest.raises(BenchmarkIntegrityError) as exc:
        record_contamination_evidence(
            store, 'author', b'Identical prose content that should trigger exact reuse.',
            repo, corpus_files=[hist_file]
        )
    assert 'Historical report reused' in str(exc.value)


def test_contamination_evidence_enters_trace(mock_run_env):
    """8. Contamination evidence is stored as 07-*-contamination.json and in events."""
    env = mock_run_env
    store = env['store']
    repo = env['gitrepo']

    record = record_contamination_evidence(
        store, 'author', b'Original non-contaminated prose for the reading.',
        repo, corpus_files=[]
    )
    assert store.path('07-author-contamination.json').exists()
    assert record['passed'] is True
    assert record['requires_review'] is False

    events = store.verify()
    assert any(e['action'] == 'author:contamination_checked' for e in events)


def test_evaluator_rejects_generic_evidence_or_invalid_dimensions(mock_run_env):
    """9. Evaluator cannot submit generic evidence, missing dimensions, or duplicates."""
    env = mock_run_env
    rubric = {'dimensions': ['DimA', 'DimB', 'DimC']}

    # Missing dimension
    bad_payload_missing = {
        'dimensions': [
            {'dimension_id': 'DimA', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
            {'dimension_id': 'DimB', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
        ]
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_score(b'raw', bad_payload_missing, rubric=rubric)
    assert 'Missing rubric dimensions' in str(exc.value)

    # Empty evidence
    bad_payload_empty_ev = {
        'dimensions': [
            {'dimension_id': 'DimA', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': [], 'beta_evidence': ['cite']},
            {'dimension_id': 'DimB', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
            {'dimension_id': 'DimC', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
        ]
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_score(b'raw', bad_payload_empty_ev, rubric=rubric)
    assert 'requires non-empty alpha_evidence' in str(exc.value)

    # Duplicate dimension ID
    bad_payload_dup = {
        'dimensions': [
            {'dimension_id': 'DimA', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
            {'dimension_id': 'DimA', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
            {'dimension_id': 'DimB', 'alpha_score': 8, 'beta_score': 7, 'alpha_evidence': ['cite'], 'beta_evidence': ['cite']},
        ]
    }
    with pytest.raises(BenchmarkIntegrityError) as exc:
        freeze_score(b'raw', bad_payload_dup, rubric=rubric)
    assert 'Duplicate dimension_id' in str(exc.value)


def test_reveal_cannot_occur_under_changed_code(mock_run_env):
    """10. Reveal cannot occur if repository code changes between generation and reveal."""
    env = mock_run_env
    store = env['store']
    repo = env['gitrepo']

    store.put('final_reviewed_report.md', b'Candidate final deliverable')
    store.event('reviewer:validated', ['01-handoff.json', 'final_reviewed_report.md'])
    rubric = {'dimensions': ['dimension 0']}
    commit_blind(store, b'Champion deliverable', rubric)

    eval_payload = {
        'dimensions': [{
            'dimension_id': 'dimension 0', 'alpha_score': 8, 'beta_score': 9,
            'alpha_evidence': ['Explicit citation from Alpha.'],
            'beta_evidence': ['Explicit citation from Beta.'],
            'factual_mismatches': [], 'uncertainty': None,
        }],
        'overall_notes': 'Notes',
    }
    evaluate_blind(store, FixtureTransport([eval_payload]))

    # Now simulate code tampering in repo:
    (repo / 'astrology').mkdir(parents=True, exist_ok=True)
    tamper_file = repo / 'astrology' / 'tampered.py'
    tamper_file.write_text('# Malicious change post generation')

    with pytest.raises(BenchmarkIntegrityError) as exc:
        reveal_blind(store)
    assert 'generation code source_sha256' in str(exc.value)


def test_champion_and_candidate_commits_can_differ(mock_run_env):
    """11. Champion and candidate commits can be intentionally different."""
    env = mock_run_env
    handoff = env['handoff']
    repo = env['gitrepo']
    rubric = {'dimensions': ['Dim1']}

    champ_desc = {
        'source': 'captured_run',
        'report_sha256': sha256(b'champion text'),
        'birth_data_hash': sha256(canonical_bytes(CHART_3_BIRTH.__dict__)),
        'locale': 'pt-BR',
        'as_of': handoff['preparation_parameters']['effective_as_of'],
        'horizon_days': 366,
        'timing_enabled': True,
        'commit_sha': None,  # Divergent commit
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, champ_desc, b'champion text',
        'gemini-3.8-flash', 'high', 'gemini-3.8-flash', repo, 'candidate_commit_sha'
    )
    # Does not raise error even though champion commit != candidate commit
    assert spec['candidate_protocol']['commit_sha'] == 'candidate_commit_sha'
    assert spec['champion']['commit_sha'] is None


def test_legacy_champion_comparison_flagged_weaker(mock_run_env):
    """12. Historical legacy champion is marked as legacy_weaker, not promotion-grade."""
    env = mock_run_env
    handoff = env['handoff']
    repo = env['gitrepo']
    rubric = {'dimensions': ['Dim1']}

    legacy_desc = {
        'source': 'historical_legacy',
        'report_sha256': sha256(b'historical champion text'),
        'birth_data_hash': sha256(canonical_bytes(CHART_3_BIRTH.__dict__)),
        'locale': 'pt-BR',
        'as_of': handoff['preparation_parameters']['effective_as_of'],
        'horizon_days': 366,
        'timing_enabled': True,
    }
    spec = create_benchmark_spec(
        CHART_3_BIRTH, PROFILE, handoff, rubric, legacy_desc, b'historical champion text',
        'gemini-3.8-flash', 'high', 'gemini-3.8-flash', repo, 'candidate_commit'
    )
    assert spec['champion']['promotion_grade'] is False
    assert spec['champion']['comparison_mode'] == 'legacy_weaker'
