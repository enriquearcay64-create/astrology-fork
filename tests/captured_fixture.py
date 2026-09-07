"""Reproducible OFFLINE trace recipe. Historical prose is test data, never fresh evidence.

python3 -m tests.captured_fixture --out /tmp/astrology-captured-fixture
No external model call occurs. The output manifest cannot be promoted.
"""
import argparse
from datetime import datetime
from pathlib import Path
from .legacy_fixture_adapter import current_handoff, with_editorial_sections
from .test_captured_execution import FixtureTransport, _explicit_payload, _explicit_reviewer_payload
from astrology.benchmark_integrity import load_json
from astrology.pipeline import plan_prospective_narrative_blocks, bind_prospective_plan_to_prose
from astrology.live_premium import prepare_run, continue_run, verify_captured_derivation, finalize_trace
from astrology.blind_execution import commit_blind, evaluate_blind, reveal_blind
from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE, BENCHMARK_DIR


def build_fixture(out):
    h=current_handoff()
    p=load_json(BENCHMARK_DIR/'01-author-selection-plan.json');p['packet_id']=h['packet_id'];p=with_editorial_sections(p,h)
    blocks=plan_prospective_narrative_blocks(h,author_selection_plan=p)
    draft_prose=(BENCHMARK_DIR/'author_draft.md').read_text()
    draft_sources,_,_=bind_prospective_plan_to_prose(draft_prose,blocks,h['reader_domain_manifest'])
    author_resp=_explicit_payload(draft_prose,draft_sources,h)

    final_prose=(BENCHMARK_DIR/'final_reviewed_report.md').read_text()
    final_sources,_,_=bind_prospective_plan_to_prose(final_prose,blocks,h['reader_domain_manifest'])
    reviewer_resp=_explicit_reviewer_payload(final_prose,final_sources,h)

    responses=[p, author_resp, reviewer_resp]
    cfg=h['preparation_parameters']
    store=prepare_run(out,Path(__file__).resolve().parents[1],CHART_3_BIRTH,PROFILE,fixture=True,
        as_of=datetime.fromisoformat(cfg['effective_as_of']),horizon_days=cfg['horizon_days'],include_timing=cfg['include_timing'])
    continue_run(store,FixtureTransport(responses))
    verify_captured_derivation(store)
    commit_blind(store,b'Synthetic comparison fixture, not a quality benchmark.',{'dimensions':[f'Synthetic protocol dimension {i}' for i in range(17)]})
    eval_dimensions=[{
        'dimension_id': f'Synthetic protocol dimension {i}',
        'alpha_score': 0,
        'beta_score': 0,
        'alpha_evidence': ['Synthetic scores exercise protocol only; no editorial judgment occurred.'],
        'beta_evidence': ['Synthetic scores exercise protocol only; no editorial judgment occurred.'],
        'factual_mismatches': [],
        'uncertainty': None,
    } for i in range(17)]
    evaluate_blind(store,FixtureTransport([{'dimensions': eval_dimensions, 'overall_notes': 'Synthetic evaluation'}]))
    reveal_blind(store)
    manifest=finalize_trace(store)
    print(manifest['benchmark_status'],str(store.root))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,type=Path)
    build_fixture(parser.parse_args().out)
