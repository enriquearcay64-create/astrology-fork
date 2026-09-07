"""V2.3.1b deterministic engineering tests; no model calls or premium generation."""
import copy
import json
from pathlib import Path
import pytest
from astrology.pipeline import validate_author_selection_plan, plan_prospective_narrative_blocks
from astrology.exceptions import SelectionPlanValidationError, LineageMismatchError, BenchmarkIntegrityError
from astrology.benchmark_integrity import (check_contamination, create_assignment, freeze_score,
    reveal_assignment, require_equal, require_promotable, verify_artifacts, load_json)
from astrology.premium_workflow import prepared_timing_parameters, prepare_author_from_selection
from astrology.reasoning import humanization_instructions, humanization_verifier_instructions

RUN = Path(__file__).resolve().parents[1] / 'benchmarks/chart3_mutable_earth_water/runs/run_20260905_052000'

@pytest.fixture
def inputs():
    # Only the deterministic packet and Selection are used as regression data.
    # This does not rehabilitate the invalidated model run or use its prose.
    from tests.legacy_fixture_adapter import with_editorial_sections
    h=json.loads((RUN/'01-handoff.json').read_text())
    return h,with_editorial_sections(json.loads((RUN/'01-author-selection-plan.json').read_text()),h)


def test_real_selection_positive(inputs):
    h,p=inputs
    assert validate_author_selection_plan(p,h['reader_domain_manifest'],handoff=h)==(True,[])
    assert prepare_author_from_selection(h,p)['packet_id']==h['packet_id']

@pytest.mark.parametrize('mutation',[
    lambda p:p.pop('packet_id'), lambda p:p.update(packet_id=None), lambda p:p.update(packet_id=''),
    lambda p:p.update(extra=True), lambda p:p['domains'].append(copy.deepcopy(p['domains'][0])),
    lambda p:p['domains'].pop(), lambda p:p['domains'][0].update(domain_id='unknown'),
    lambda p:p['domains'][0]['paths'].append(copy.deepcopy(p['domains'][0]['paths'][0])),
    lambda p:p['domains'][0]['paths'].pop(), lambda p:p['domains'][0]['paths'][0].update(path_id='unknown'),
    lambda p:p['domains'][0]['paths'][0].update(synthesis_ids=[{}]),
    lambda p:p['domains'][0]['paths'][0].update(decision=[]),
    lambda p:p['domains'][0]['paths'][0].update(rationale=4),
    lambda p:p['domains'][0]['paths'][0].update(merged_with_path_id=[]),
    lambda p:p['domains'][0]['paths'][0].update(extra=True),
])
def test_strict_invalid_shapes(inputs,mutation):
    h,p=inputs;mutation(p)
    ok,errors=validate_author_selection_plan(p,h['reader_domain_manifest'],handoff=h)
    assert not ok and errors
    with pytest.raises(SelectionPlanValidationError):
        plan_prospective_narrative_blocks(h,author_selection_plan=p)


def test_wrong_lineage(inputs):
    h,p=inputs;p['packet_id']='wrong'
    with pytest.raises(LineageMismatchError):plan_prospective_narrative_blocks(h,author_selection_plan=p)

@pytest.mark.parametrize('field',['candidate_catalog','approved_reasoned_syntheses'])
def test_missing_basis(inputs,field):
    h,p=inputs;h.pop(field)
    with pytest.raises(SelectionPlanValidationError):plan_prospective_narrative_blocks(h,author_selection_plan=p)


def test_catalog_tampering(inputs):
    h,p=inputs;h['candidate_catalog']['domains'][0]['paths'][0]['candidate_synthesis_ids']=[]
    assert not validate_author_selection_plan(p,h['reader_domain_manifest'],handoff=h)[0]


def test_all_omitted(inputs):
    h,p=inputs
    for row in p['domains'][0]['paths']:
        row.update(decision='omitted_no_distinct_reader_value', synthesis_ids=[], merged_with_path_id=None,rationale='No distinct value')
    assert not validate_author_selection_plan(p,h['reader_domain_manifest'],handoff=h)[0]


def test_frozen_parameters(inputs):
    h,_=inputs;h['preparation_parameters'].update(horizon_days=47,include_timing=False)
    _,horizon,timing=prepared_timing_parameters(h)
    assert horizon==47 and timing is False

@pytest.mark.parametrize('lang',['pt-BR','en'])
def test_no_numeric_paragraph_quota(lang):
    import re
    for prompt in [humanization_instructions(lang),humanization_verifier_instructions(lang)]:
        assert not re.search(r'2 (?:a|to|and) 4',prompt)


def test_exact_reuse_and_ancestral_positive(tmp_path):
    report=tmp_path/'historical.md';report.write_text('A specific report.\n')
    with pytest.raises(BenchmarkIntegrityError):check_contamination(report.read_bytes(),[report])
    assert not check_contamination(report.read_bytes(),[report],ancestral_paths=[report])['requires_review']
    assert check_contamination(b'A specific report.  \n',[report])['requires_review']


def test_mapping_binding_and_score_arithmetic():
    public,private=create_assignment('fixture',{'alpha':b'a','beta':b'b'},{'alpha':'champion','beta':'candidate'},'rubric','truth')
    rows=[{'alpha':7,'beta':9}]*14+[{'alpha':8,'beta':8}]*3
    score=freeze_score(b'raw',rows)
    assert score['score']['beta_wins']==14 and score['score']['ties']==3
    assert reveal_assignment(public,private,score,b'raw')
    changed=copy.deepcopy(private);changed['mapping']={'alpha':'candidate','beta':'champion'}
    with pytest.raises(BenchmarkIntegrityError):reveal_assignment(public,changed,score,b'raw')
    with pytest.raises(BenchmarkIntegrityError):reveal_assignment(public,private,None,b'raw')
    with pytest.raises(BenchmarkIntegrityError):reveal_assignment(public,private,score,b'changed')


def test_full_plan_comparison(inputs):
    h,p=inputs;a=plan_prospective_narrative_blocks(h,author_selection_plan=p);b=copy.deepcopy(a)
    b['sections']['opening'][0]['synthesis_ids'].append('different')
    assert set(a['sections'])==set(b['sections'])
    with pytest.raises(BenchmarkIntegrityError):require_equal(a,b,'block plan')


def test_invalid_run_cannot_promote():
    with pytest.raises(BenchmarkIntegrityError):require_promotable(load_json(RUN/'benchmark_manifest.json'))


def test_duplicate_json_and_path_escape(tmp_path):
    p=tmp_path/'duplicate.json';p.write_text('{"a":1,"a":2}')
    with pytest.raises(BenchmarkIntegrityError):load_json(p)
    (tmp_path/'benchmark_manifest.json').write_text(json.dumps({'artifacts_sha256':{'../outside':'bad'}}))
    with pytest.raises(BenchmarkIntegrityError):verify_artifacts(tmp_path)


def test_explicit_run_replay_and_substantive_tamper(tmp_path):
    """Synthetic guard regression fixture: historical prose is intentionally reused,
    never labeled fresh or used for promotion. All comparisons run on a runs/ path.
    """
    from tests.legacy_fixture_adapter import current_handoff
    from astrology.pipeline import (bind_prospective_plan_to_prose, build_author_bundle,
        validate_premium_author_bundle, build_reviewer_bundle, validate_premium_narrative)
    from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE, BENCHMARK_DIR, replay_chart3_benchmark
    from astrology.report import render_canonical_technical_appendix, validate_technical_relationship_fidelity
    from astrology.engine import calculate_chart
    from astrology.safe_view import build_safe_interpretive_view
    from astrology.editorial_qa import barnum_risk, grandiosity_and_flattery_risk, medicalization_risk
    from astrology.benchmark_integrity import sha256
    h=current_handoff()
    p=load_json(BENCHMARK_DIR/'01-author-selection-plan.json');p['packet_id']=h['packet_id']
    from tests.legacy_fixture_adapter import with_editorial_sections
    p=with_editorial_sections(p,h)
    blocks=plan_prospective_narrative_blocks(h,author_selection_plan=p)
    draft=(BENCHMARK_DIR/'author_draft.md').read_text()
    final=(BENCHMARK_DIR/'final_reviewed_report.md').read_text()
    sources,sections,_=bind_prospective_plan_to_prose(draft,blocks,h['reader_domain_manifest'])
    author=build_author_bundle(h,draft,sources,reader_selection_plan=p,reader_sections=sections)
    prov=validate_premium_author_bundle(CHART_3_BIRTH,author,profile=PROFILE,prepared_handoff=h)
    rs,ro,_=bind_prospective_plan_to_prose(final,blocks,h['reader_domain_manifest'])
    reviewer=build_reviewer_bundle(author,prov,final_report=final,narrative_block_sources=rs,reader_sections=ro)
    pub=validate_premium_narrative(reviewer,prov,CHART_3_BIRTH,profile=PROFILE,prepared_handoff=h)
    assert prov['approved'] and pub['approved']
    qa={'barnum_risk':barnum_risk(final),'grandiosity_risk':grandiosity_and_flattery_risk(final),
        'publication_approved':pub['approved'],'medicalization_risk':medicalization_risk(final),'relationship_fidelity_errors':validate_technical_relationship_fidelity(final,build_safe_interpretive_view(calculate_chart(CHART_3_BIRTH)),lang=PROFILE.preferred_language)}
    root=tmp_path/'runs'/'synthetic_guard_fixture';root.mkdir(parents=True)
    objects={'01-handoff.json':h,'01-author-selection-plan.json':p,'01-prospective-block-plan.json':blocks,
             '02-author-bundle.json':author,'03-provenance-guard.json':prov,'04-reviewer-bundle.json':reviewer,
             '05-publication-guard.json':pub,'06-editorial-qa.json':qa}
    for name,obj in objects.items():(root/name).write_text(json.dumps(obj,ensure_ascii=False))
    for name,txt in {'author_draft.md':draft,'final_reviewed_report.md':final,
        'canonical_technical_appendix.md':render_canonical_technical_appendix(CHART_3_BIRTH,profile=PROFILE,timing=h.get('timing'))}.items():(root/name).write_text(txt)
    manifest={'benchmark_status':'synthetic_test_fixture','artifacts_sha256':{f.name:sha256(f.read_bytes()) for f in root.iterdir()}}
    (root/'benchmark_manifest.json').write_text(json.dumps(manifest))
    assert replay_chart3_benchmark(root)
    # Rehash altered bytes too: exercise semantic comparison, not just outer hash.
    blocks['sections']['opening'][0]['intended_mechanism']='substantively changed'
    target=root/'01-prospective-block-plan.json';target.write_text(json.dumps(blocks))
    manifest['artifacts_sha256'][target.name]=sha256(target.read_bytes())
    (root/'benchmark_manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(BenchmarkIntegrityError,match='prospective block plan'):
        replay_chart3_benchmark(root)


def test_delivery_gate_is_fail_closed():
    from astrology.premium_workflow import require_deliverable
    good={'publication_approved':True,'relationship_fidelity_errors':[],
          'barnum_risk':{'share':0.0},'grandiosity_risk':{'share':0.0},'medicalization_risk':{'share':0.0}}
    require_deliverable(good)
    for key in good:
        bad=copy.deepcopy(good);bad.pop(key)
        with pytest.raises(BenchmarkIntegrityError):require_deliverable(bad)
    good['publication_approved']=False
    with pytest.raises(BenchmarkIntegrityError):require_deliverable(good)


def test_frozen_input_identity(inputs):
    from astrology.premium_workflow import validate_frozen_inputs
    from scripts.run_chart3_pipeline import CHART_3_BIRTH,PROFILE
    from dataclasses import replace
    h,_=inputs
    validate_frozen_inputs(h,CHART_3_BIRTH,PROFILE)
    with pytest.raises(LineageMismatchError):
        validate_frozen_inputs(h,replace(CHART_3_BIRTH,latitude=0),PROFILE)


def test_benchmark_acceptance_checks_historical_corpus(tmp_path):
    from astrology.benchmark_integrity import check_benchmark_run_output
    family=tmp_path/'chart';run=family/'runs'/'new';run.mkdir(parents=True)
    (family/'Report_Beta.md').write_bytes(b'Historical candidate')
    with pytest.raises(BenchmarkIntegrityError):check_benchmark_run_output(run,b'Historical candidate')
    (run/'author_draft.md').write_bytes(b'New author report')
    assert not check_benchmark_run_output(run,b'New author report')['requires_review']
