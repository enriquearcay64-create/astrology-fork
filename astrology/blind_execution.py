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


def commit_blind(store, champion, rubric):
    with store.lock():
        events = store.verify()
        if 'reviewer:validated' not in [e['action'] for e in events]:
            raise BenchmarkIntegrityError('Validated current Reviewer output required')
        if not isinstance(rubric, dict) or not isinstance(rubric.get('dimensions'), list) or len(rubric['dimensions']) != 17:
            raise BenchmarkIntegrityError('Freeze a rubric with 17 dimensions before evaluation')
        candidate = store.path('final_reviewed_report.md').read_bytes()
        mapping = {'alpha': 'champion', 'beta': 'candidate'} if secrets.randbelow(2) else {'alpha': 'candidate', 'beta': 'champion'}
        reports = {key: candidate if label == 'candidate' else champion for key, label in mapping.items()}
        truth = technical_truth(load_json(store.path('01-handoff.json')))
        public, private = create_assignment(store.root.name, reports, mapping, sha256(canonical_bytes(rubric)), sha256(canonical_bytes(truth)))
        store.put_json('private/blind_assignment.json', private)
        store.put_json('assignment_commitment.json', public)
        store.put_json('rubric.json', rubric)
        store.put_json('ground_truth.json', truth)
        for label, report in reports.items():
            store.put('blind/' + label + '.md', report)
        prompt = ('Evaluate the two anonymous reports against the supplied rubric and deterministic technical truth. '
                  'Do not infer their models, versions or prior scores. Technical checks establish consistency with the supplied truth, not an independent ephemeris calculation. '
                  'Return JSON with exactly scores (17 objects with numeric alpha and beta scores from 0 to 10 in rubric order) and evidence '
                  '(specific passages, factual mismatches, uncertainties and reasons for each dimension). Use sober language.\n'
                  + canonical_bytes({'rubric': rubric, 'ground_truth': truth, 'reports': {k: v.decode('utf-8') for k, v in reports.items()}}).decode())
        store.put('evaluator_prompt.txt', prompt.encode())
        store.event('blind:committed', ['private/blind_assignment.json', 'assignment_commitment.json', 'rubric.json', 'ground_truth.json',
                                      'blind/alpha.md', 'blind/beta.md', 'evaluator_prompt.txt'])
        return public


def evaluate_blind(store, transport):
    if 'blind:committed' not in [e['action'] for e in store.verify()]:
        raise BenchmarkIntegrityError('Blind commitment required before judgment')
    payload = store.invoke('evaluator', store.path('evaluator_prompt.txt').read_text(), transport)
    if not isinstance(payload, dict) or set(payload) != {'scores', 'evidence'} or not payload['evidence']:
        raise BenchmarkIntegrityError('Evaluator must return structured scores and evidence')
    raw = store.path('stages/evaluator/response.raw.json').read_bytes()
    frozen = freeze_score(raw, payload['scores'])
    with store.lock():
        if store.path('score_frozen.json').exists():
            require_equal(load_json(store.path('score_frozen.json')), frozen, 'resumed score')
        else:
            store.put_json('score_frozen.json', frozen)
            store.event('evaluator:score_frozen', ['score_frozen.json'])
    return frozen


def reveal_blind(store):
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
