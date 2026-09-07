"""Captured premium execution. Deterministic guards gate each subsequent model call."""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from .models import BirthData, LocalizationProfile
from .pipeline import (prepare_premium_handoff, plan_prospective_narrative_blocks, build_author_bundle,
                       validate_premium_author_bundle, build_reviewer_bundle, validate_premium_narrative)
from .premium_workflow import (build_author_selection_prompt, prepare_author_from_selection,
    build_reviewer_prompt, validate_saved_block_plan, validate_frozen_inputs, require_deliverable)
from .explicit_prose import render_explicit_blocks
from .isolated_execution import RunStore
from .benchmark_integrity import canonical_bytes, sha256, load_json, require_equal, check_benchmark_run_output
from .exceptions import BenchmarkIntegrityError
from .report import render_canonical_technical_appendix, validate_technical_relationship_fidelity
from .editorial_qa import barnum_risk, grandiosity_and_flattery_risk, medicalization_risk
from .engine import calculate_chart
from .safe_view import build_safe_interpretive_view


def prepare_run(root, repository, birth, profile, *, as_of=None, horizon_days=366, include_timing=True, fixture=False, audit_record=None):
    configuration = {'birth': asdict(birth), 'profile': asdict(profile) if profile else None,
                     'as_of': as_of.isoformat() if as_of else None, 'horizon_days': horizon_days, 'include_timing': include_timing}
    store = RunStore.create(root, repository, configuration, fixture=fixture, audit_record=audit_record)
    handoff = prepare_premium_handoff(birth, profile, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing)
    store.put_json('01-handoff.json', handoff)
    store.put_json('01-candidate-catalog.json', handoff['candidate_catalog'])
    store.put('author_selection_prompt.txt', build_author_selection_prompt(handoff).encode())
    store.put('canonical_technical_appendix.md', render_canonical_technical_appendix(birth, profile=profile, timing=handoff.get('timing')).encode())
    store.event('prepared', ['01-handoff.json', '01-candidate-catalog.json', 'author_selection_prompt.txt', 'canonical_technical_appendix.md'])
    return store


def _save(store, action, objects=None, texts=None):
    files = []
    with store.lock():
        for name, obj in (objects or {}).items():
            if store.path(name).exists():
                require_equal(load_json(store.path(name)), obj, name)
            else:
                store.put_json(name, obj)
            files.append(name)
        for name, text in (texts or {}).items():
            data = text.encode()
            if store.path(name).exists():
                if store.path(name).read_bytes() != data:
                    raise BenchmarkIntegrityError('Changed derived artifact: ' + name)
            else:
                store.put(name, data)
            files.append(name)
        if action not in [e['action'] for e in store.verify()]:
            store.event(action, files)


def continue_run(store, transport):
    store.assert_code()
    store.verify()
    config = load_json(store.path('run.json'))['configuration']
    birth = BirthData(**config['birth'])
    profile = LocalizationProfile(**config['profile']) if config['profile'] else None
    handoff = load_json(store.path('01-handoff.json'))
    lang = handoff['reader_domain_manifest'].get('locale', 'pt-BR')
    validate_frozen_inputs(handoff, birth, profile)
    selection = store.invoke('selection', store.path('author_selection_prompt.txt').read_text(), transport)
    prepared = prepare_author_from_selection(handoff, selection, lang)
    blocks = prepared['block_plan']
    _save(store, 'selection:validated', {'01-author-selection-plan.json': selection,
        '01-selection-validation.json': {'approved': True, 'packet_id': handoff['packet_id']},
        '01-prospective-block-plan.json': blocks}, {'author_prompt.txt': prepared['author_prompt']})
    author_payload = store.invoke('author', prepared['author_prompt'], transport)
    authored = render_explicit_blocks(author_payload, handoff, blocks)
    if not load_json(store.path("run.json"))["fixture"]:
        check_benchmark_run_output(store.root, authored['report'].encode())
    author = build_author_bundle(handoff, authored['report'], authored['sources'], reader_selection_plan=selection, reader_sections=authored['sections'])
    provenance = validate_premium_author_bundle(birth, author, profile=profile, prepared_handoff=handoff)
    _save(store, 'author:guarded', {'02-author-bundle.json': author, '03-provenance-guard.json': provenance}, {'author_draft.md': authored['report']})
    if not provenance.get('approved'):
        raise BenchmarkIntegrityError('Author provenance failed; Reviewer was not invoked: ' + str(provenance.get('verification_errors')))
    reviewer_prompt = build_reviewer_prompt(handoff, blocks, author_payload, provenance, authored['materialized_scope'], lang)
    _save(store, 'author:validated', texts={'reviewer_prompt.txt': reviewer_prompt})
    reviewed_payload = store.invoke('reviewer', reviewer_prompt, transport)
    reviewed = render_explicit_blocks(reviewed_payload, handoff, blocks, author_scope=authored['materialized_scope'])
    if not load_json(store.path("run.json"))["fixture"]:
        check_benchmark_run_output(store.root, reviewed['report'].encode())
    reviewer = build_reviewer_bundle(author, provenance, final_report=reviewed['report'],
                                    narrative_block_sources=reviewed['sources'], reader_sections=reviewed['sections'])
    publication = validate_premium_narrative(reviewer, provenance, birth, profile=profile, prepared_handoff=handoff)
    qa = {'publication_approved': publication.get('approved'), 'barnum_risk': barnum_risk(reviewed['report']),
          'grandiosity_risk': grandiosity_and_flattery_risk(reviewed['report']), 'medicalization_risk': medicalization_risk(reviewed['report']),
          'relationship_fidelity_errors': validate_technical_relationship_fidelity(reviewed['report'], build_safe_interpretive_view(calculate_chart(birth)), lang=lang)}
    _save(store, 'reviewer:guarded', {'04-reviewer-bundle.json': reviewer, '05-publication-guard.json': publication, '06-editorial-qa.json': qa})
    require_deliverable(qa)
    _save(store, 'reviewer:validated', texts={'final_reviewed_report.md': reviewed['report']})
    return qa


def verify_captured_derivation(store):
    """Replay output extraction/rendering, not another model invocation."""
    store.verify()
    handoff = load_json(store.path('01-handoff.json'))
    selection = store.verify_response('selection')
    require_equal(selection, load_json(store.path('01-author-selection-plan.json')), 'captured selection')
    blocks = validate_saved_block_plan(handoff, load_json(store.path('01-prospective-block-plan.json')))
    author = render_explicit_blocks(store.verify_response('author'), handoff, blocks)
    reviewer = render_explicit_blocks(store.verify_response('reviewer'), handoff, blocks, author_scope=author['materialized_scope'])
    for result, name in ((author, 'author_draft.md'), (reviewer, 'final_reviewed_report.md')):
        if result['report'].encode() != store.path(name).read_bytes():
            raise BenchmarkIntegrityError('Report does not derive from captured response: ' + name)
    config = load_json(store.path('run.json'))['configuration']
    birth = BirthData(**config['birth'])
    profile = LocalizationProfile(**config['profile']) if config['profile'] else None
    validate_frozen_inputs(handoff, birth, profile)
    author_bundle = build_author_bundle(handoff, author['report'], author['sources'], reader_selection_plan=selection, reader_sections=author['sections'])
    provenance = validate_premium_author_bundle(birth, author_bundle, profile=profile, prepared_handoff=handoff)
    reviewer_bundle = build_reviewer_bundle(author_bundle, provenance, final_report=reviewer['report'], narrative_block_sources=reviewer['sources'], reader_sections=reviewer['sections'])
    publication = validate_premium_narrative(reviewer_bundle, provenance, birth, profile=profile, prepared_handoff=handoff)
    lang = handoff['reader_domain_manifest'].get('locale', 'pt-BR')
    qa = {'publication_approved': publication.get('approved'), 'barnum_risk': barnum_risk(reviewer['report']),
          'grandiosity_risk': grandiosity_and_flattery_risk(reviewer['report']), 'medicalization_risk': medicalization_risk(reviewer['report']),
          'relationship_fidelity_errors': validate_technical_relationship_fidelity(reviewer['report'], build_safe_interpretive_view(calculate_chart(birth)), lang=lang)}
    for name, result in {'02-author-bundle.json': author_bundle, '03-provenance-guard.json': provenance,
                         '04-reviewer-bundle.json': reviewer_bundle, '05-publication-guard.json': publication,
                         '06-editorial-qa.json': qa}.items():
        require_equal(result, load_json(store.path(name)), 'replayed ' + name)
    appendix = render_canonical_technical_appendix(birth, profile=profile, timing=handoff.get('timing'))
    if appendix.encode() != store.path('canonical_technical_appendix.md').read_bytes():
        raise BenchmarkIntegrityError('Replayed appendix mismatch')
    require_deliverable(qa)
    author_payload = store.verify_response('author')
    prompts = {'selection': build_author_selection_prompt(handoff),
               'author': prepare_author_from_selection(handoff, selection, lang)['author_prompt'],
               'reviewer': build_reviewer_prompt(handoff, blocks, author_payload, provenance, author['materialized_scope'], lang)}
    for stage, prompt in prompts.items():
        if prompt.encode() != store.path(f'stages/{stage}/prompt.txt').read_bytes():
            raise BenchmarkIntegrityError('Stage prompt does not derive from current snapshot: ' + stage)
    return True


def finalize_trace(store):
    """Preserve aliases for the portable trace contract; never promote automatically."""
    from .benchmark_integrity import build_trace_manifest
    from .blind_execution import reveal_blind
    verify_captured_derivation(store)
    if 'blind:revealed' not in [e['action'] for e in store.verify()]:
        raise BenchmarkIntegrityError('Freeze evaluation and perform the separate reveal first')
    reveal_blind(store)
    names = {'selection': 'author_selection_response_raw.json', 'author': 'author_response_raw.json',
             'reviewer': 'reviewer_response_raw.json', 'evaluator': 'evaluator_response_raw.json'}
    metadata = {}
    with store.lock():
        for stage, name in names.items():
            raw = store.path(f'stages/{stage}/response.raw.json').read_bytes()
            if store.path(name).exists():
                if store.path(name).read_bytes() != raw:
                    raise BenchmarkIntegrityError('Raw response alias differs')
            else:
                store.put(name, raw)
            metadata[stage] = {'request': load_json(store.path(f'stages/{stage}/request.json')),
                               'receipt': load_json(store.path(f'stages/{stage}/receipt.json'))}
        if not store.path('runtime_execution_metadata.json').exists():
            store.put_json('runtime_execution_metadata.json', metadata)
            store.event('trace:captured', [*names.values(), 'runtime_execution_metadata.json'])
        else:
            require_equal(metadata, load_json(store.path('runtime_execution_metadata.json')), 'runtime metadata')
        origin = load_json(store.path('run.json'))
        manifest = build_trace_manifest(store.root, origin['repository'], 'v2.3.1b', load_json(store.path('01-handoff.json'))['preparation_parameters'])
        if store.path('benchmark_manifest.json').exists():
            require_equal(manifest, load_json(store.path('benchmark_manifest.json')), 'trace manifest')
        else:
            store.put_json('benchmark_manifest.json', manifest)
    return manifest
