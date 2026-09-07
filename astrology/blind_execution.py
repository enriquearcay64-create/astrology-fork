"""Persistent blind commitment → isolated judgment → frozen score → separate reveal."""
import secrets
from .benchmark_integrity import canonical_bytes, sha256, load_json, create_assignment, freeze_score, reveal_assignment, require_equal
from .exceptions import BenchmarkIntegrityError


def technical_truth(handoff):
    facts = handoff['reasoning_packet']['facts']
    keys = ('data_reliability', 'structural_bodies', 'aspects', 'conditions', 'safe_house_context',
            'placidus_house_rulers', 'angle_contacts', 'timing_evidence', 'positions', 'natal_node_axis', 'configurations')
    return {'facts': {key: facts[key] for key in keys if key in facts},
            'preparation_parameters': handoff['preparation_parameters']}


def commit_blind(store, champion, rubric, champion_descriptor=None):
    store.assert_code()
    with store.lock():
        events = store.verify()
        if 'reviewer:validated' not in [e['action'] for e in events]:
            raise BenchmarkIntegrityError('Validated current Reviewer output required')
        from .benchmark_spec import extract_rubric_dimension_ids, validate_champion_compatibility
        dim_ids = extract_rubric_dimension_ids(rubric)

        handoff = load_json(store.path('01-handoff.json'))
        config = load_json(store.path('run.json'))['configuration']
        repo = load_json(store.path('run.json'))['repository']

        if store.path('benchmark_spec.json').exists():
            spec = load_json(store.path('benchmark_spec.json'))
            if sha256(canonical_bytes(rubric)) != spec['rubric']['rubric_sha256']:
                raise BenchmarkIntegrityError('Rubric does not match pre-frozen benchmark spec')
            if sha256(champion) != spec['champion']['report_sha256']:
                raise BenchmarkIntegrityError('Champion report does not match pre-frozen benchmark spec')
        elif champion_descriptor is not None and 'birth' in config:
            from .models import BirthData, LocalizationProfile
            from datetime import datetime
            birth = BirthData(**config['birth'])
            profile = LocalizationProfile(**config['profile']) if config.get('profile') else None
            as_of_val = config.get('as_of')
            as_of = datetime.fromisoformat(as_of_val) if as_of_val else None
            validate_champion_compatibility(
                birth, profile, as_of, config.get('horizon_days', 366),
                config.get('include_timing', True), champion_descriptor, champion, repo,
            )

        candidate = store.path('final_reviewed_report.md').read_bytes()
        mapping = {'alpha': 'champion', 'beta': 'candidate'} if secrets.randbelow(2) else {'alpha': 'candidate', 'beta': 'champion'}
        reports = {key: candidate if label == 'candidate' else champion for key, label in mapping.items()}
        truth = technical_truth(handoff)
        public, private = create_assignment(store.root.name, reports, mapping, sha256(canonical_bytes(rubric)), sha256(canonical_bytes(truth)))
        store.put_json('private/blind_assignment.json', private)
        store.put_json('assignment_commitment.json', public)
        store.put_json('rubric.json', rubric)
        store.put_json('ground_truth.json', truth)
        if champion_descriptor:
            store.put_json('champion_descriptor.json', champion_descriptor)
        for label, report in reports.items():
            store.put('blind/' + label + '.md', report)
        prompt = ('Evaluate the two anonymous reports against the supplied rubric and deterministic technical truth. '
                  'Do not infer their models, versions or prior scores. Technical checks establish consistency with the supplied truth, not an independent ephemeris calculation. '
                  'Return ONLY JSON with:\n'
                  '"dimensions": list of objects, one for each rubric dimension, with:\n'
                  '  "dimension_id": "<exact_dimension_id>",\n'
                  '  "alpha_score": <numeric 0-10>,\n'
                  '  "beta_score": <numeric 0-10>,\n'
                  '  "alpha_evidence": ["<specific quoted passages from Report Alpha>"],\n'
                  '  "beta_evidence": ["<specific quoted passages from Report Beta>"],\n'
                  '  "factual_mismatches": ["<any factual inaccuracies against technical truth>"],\n'
                  '  "uncertainty": "<any calibrated uncertainty or null>"\n'
                  '"overall_notes": "<summary justification>"\n'
                  'Use sober, objective language.\n'
                  + canonical_bytes({'rubric': rubric, 'ground_truth': truth, 'reports': {k: v.decode('utf-8') for k, v in reports.items()}}).decode())
        store.put('evaluator_prompt.txt', prompt.encode())
        artifacts = ['private/blind_assignment.json', 'assignment_commitment.json', 'rubric.json', 'ground_truth.json',
                     'blind/alpha.md', 'blind/beta.md', 'evaluator_prompt.txt']
        if champion_descriptor:
            artifacts.append('champion_descriptor.json')
        store.event('blind:committed', artifacts)
        return public


def evaluate_blind(store, transport):
    store.assert_code()
    if 'blind:committed' not in [e['action'] for e in store.verify()]:
        raise BenchmarkIntegrityError('Blind commitment required before judgment')
    if store.path('benchmark_spec.json').exists():
        spec = load_json(store.path('benchmark_spec.json'))
        if transport.model != spec['evaluator_protocol']['model']:
            raise BenchmarkIntegrityError(f"Evaluator model mismatch: {transport.model} != {spec['evaluator_protocol']['model']}")
    payload = store.invoke('evaluator', store.path('evaluator_prompt.txt').read_text(), transport)
    rubric = load_json(store.path('rubric.json'))
    raw = store.path('stages/evaluator/response.raw.json').read_bytes()
    frozen = freeze_score(raw, payload, rubric=rubric)
    with store.lock():
        if store.path('score_frozen.json').exists():
            require_equal(load_json(store.path('score_frozen.json')), frozen, 'resumed score')
        else:
            store.put_json('score_frozen.json', frozen)
            store.event('evaluator:score_frozen', ['score_frozen.json'])
    return frozen


def reveal_blind(store):
    store.assert_code()
    with store.lock():
        actions = [e['action'] for e in store.verify()]
        if 'evaluator:score_frozen' not in actions or actions.index('blind:committed') > actions.index('evaluator:score_frozen'):
            raise BenchmarkIntegrityError('Cannot reveal before committed judgment and frozen scores')
        store.verify_response('evaluator')
        reveal = reveal_assignment(load_json(store.path('assignment_commitment.json')),
            load_json(store.path('private/blind_assignment.json')), load_json(store.path('score_frozen.json')),
            store.path('stages/evaluator/response.raw.json').read_bytes())
        if store.path('reveal_record.json').exists():
            require_equal(load_json(store.path('reveal_record.json')), reveal, 'resumed reveal')
        else:
            store.put_json('reveal_record.json', reveal)
            store.event('blind:revealed', ['reveal_record.json'])
        return reveal
