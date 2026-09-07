"""Offline relation-swap attacks; no client prose or model calls."""
import copy
from datetime import datetime

import pytest

from astrology.engine import calculate_chart
from astrology.models import BirthData
from astrology.safe_view import build_safe_interpretive_view
from astrology.report import validate_technical_relationship_fidelity
from astrology.live_premium import prepare_run, continue_run
from astrology.benchmark_integrity import load_json
from astrology.exceptions import BenchmarkIntegrityError
from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE
from tests.test_captured_execution import gitrepo, prose_fixture, FixtureTransport


FALSE_OCCUPANCIES = [
    'Saturno em Peixes na casa 10',
    'Júpiter em Escorpião na casa 8',
    'Júpiter na casa 11',
    'Saturno em Peixes na casa 9',
]

COMMON_SYNTAX_BYPASSES = [
    'Na casa 10 está Saturno em Peixes.',
    'Na décima casa está Saturno em Peixes.',
    'Na décima casa encontramos Saturno em Peixes.',
    'Saturno, regente da décima casa, está na casa 10.',
    'Saturno encontra-se na casa 10.',
    'Saturno se encontra na casa 10.',
    'In the tenth house is Saturn in Pisces.',
    'In the tenth house we find Saturn.',
]


def test_explicit_occupancy_and_role_boundaries():
    chart = build_safe_interpretive_view(calculate_chart(BirthData(
        '1994-07-25T00:35:00', 'America/Sao_Paulo', -18.9188, -48.2768)))
    invalid = FALSE_OCCUPANCIES + COMMON_SYNTAX_BYPASSES + [
        'Saturno ocupa a décima casa.', 'Saturno está localizado na casa 10.',
        'Saturno em Peixes, na casa 10.',
        'Saturn in Pisces in the 10th house.', 'Saturn occupies the tenth house.',
        'Jupiter is located in the eighth house.',
        'Saturno, regente da casa 10, está na casa 10.',
        'Na profecção, Saturno natal na casa 9.',
        'Em Signo Inteiro, Júpiter na casa 6.',
        'Júpiter na casa 7 em Signo Inteiro e Saturno na casa 10 em Placidus.',
    ]
    valid = [
        'Na casa 11 está Saturno em Peixes.',
        'Na décima primeira casa encontramos Saturno em Peixes.',
        'Saturno, regente da décima casa, está na casa 11.',
        'Saturno encontra-se na casa 11. Saturno se encontra na casa 11.',
        'In the eleventh house is Saturn in Pisces.',
        'In the eleventh house we find Saturn.',
        'Na casa 10, regida por Saturno, há um tema de vocação.',
        'Na profecção, na casa 9 está Saturno.',
        'Na casa 9 está Saturno em trânsito.',
        'In transit, in the eighth house is Jupiter.',
        'Em Signo Inteiro, na casa 7 está Júpiter.',
        'In the seventh house is Jupiter (whole sign).',
        'Saturno rege a casa 10. Júpiter é regente da casa 8.',
        'Saturno em Peixes na casa 11. Júpiter em Escorpião na casa 6.',
        'Saturno, regente da casa 10, está na casa 11.',
        'Saturn, ruler of the tenth house, is in the eleventh house.',
        'Jupiter occupies the sixth house. Saturn is located in the 11th house.',
        'Na profecção, Saturno na casa 9.',
        'No trânsito, Júpiter na casa 8.',
        'A profecção ativa a casa 9; Saturno é o senhor do ano.',
        'Júpiter em trânsito pela casa 8.',
        'Júpiter na casa 7 em Signo Inteiro. Jupiter in the seventh house (whole sign).',
    ]
    for text in invalid:
        assert any(e.startswith('unauthorized_natal_house_occupancy:') for e in
                   validate_technical_relationship_fidelity(text, chart)), text
    for text in valid:
        assert validate_technical_relationship_fidelity(text, chart) == [], text
    chart.house_placements.pop('saturn')
    assert validate_technical_relationship_fidelity('Saturno na casa 11.', chart)


@pytest.mark.parametrize('stage,phrase,invalid', [
    *[('author', phrase, True) for phrase in FALSE_OCCUPANCIES],
    *[('author', phrase, True) for phrase in COMMON_SYNTAX_BYPASSES[:4]],
    ('reviewer', COMMON_SYNTAX_BYPASSES[0], True),
    ('reviewer', FALSE_OCCUPANCIES[0], True),
    ('reviewer', 'Saturno, regente da casa 12, está na casa 1. '
     'Jupiter occupies the ninth house. Júpiter na casa 10 em Signo Inteiro. '
     'Na profecção, Saturno na casa 9. Na primeira casa está Saturno. '
     'Saturno, regente da décima segunda casa, está na casa 1. '
     'In the ninth house we find Jupiter.', False),
])
def test_relation_swap_never_delivers(gitrepo, tmp_path, prose_fixture, stage, phrase, invalid):
    # Existing complete synthetic protocol fixture: only prose changes. IDs and
    # ownership stay legal; production rendering computes fresh hashes.
    h, selection, _, author, reviewer = copy.deepcopy(prose_fixture)
    payload = author if stage == 'author' else reviewer
    payload['blocks'][0]['content'] += '. ' + phrase + '.'
    cfg = h['preparation_parameters']
    store = prepare_run(tmp_path/'run', gitrepo, CHART_3_BIRTH, PROFILE, fixture=True,
        as_of=datetime.fromisoformat(cfg['effective_as_of']),
        horizon_days=cfg['horizon_days'], include_timing=cfg['include_timing'])
    transport = FixtureTransport([selection, author, reviewer])
    if not invalid:
        assert continue_run(store, transport)['publication_approved']
        assert phrase in store.path('final_reviewed_report.md').read_text()
        return
    with pytest.raises(BenchmarkIntegrityError):
        continue_run(store, transport)
    assert not store.path('final_reviewed_report.md').exists()
    guard_name = '03-provenance-guard.json' if stage == 'author' else '05-publication-guard.json'
    guard = load_json(store.path(guard_name))
    assert not guard['approved']
    assert guard['verification_errors'] and all(
        e.startswith('unauthorized_natal_house_occupancy:') for e in guard['verification_errors'])
    assert len(transport.requests) == (2 if stage == 'author' else 3)
    if stage == 'reviewer':
        assert load_json(store.path('03-provenance-guard.json'))['approved']
        assert guard['report'] is None
