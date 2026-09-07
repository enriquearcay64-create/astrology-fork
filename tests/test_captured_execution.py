"""Offline execution protocol tests. Fixture responses are not premium generation."""
import copy
import json
import subprocess
from pathlib import Path
import pytest
from astrology.isolated_execution import RunStore, GeminiTransport, strict_json
from astrology.benchmark_integrity import canonical_bytes, load_json, sha256
from astrology.exceptions import BenchmarkIntegrityError, SelectionPlanValidationError
from astrology.blind_execution import commit_blind, evaluate_blind, reveal_blind, technical_truth
from astrology.live_premium import prepare_run, continue_run, verify_captured_derivation
from astrology.pipeline import plan_prospective_narrative_blocks, bind_prospective_plan_to_prose, _parse_premium_narrative
from astrology.explicit_prose import render_explicit_blocks
from tests.legacy_fixture_adapter import current_handoff, with_editorial_sections
from scripts.run_chart3_pipeline import CHART_3_BIRTH, PROFILE, BENCHMARK_DIR


class FixtureTransport:
    provider='deterministic-test-fixture'
    fixture=True
    model='fixture-no-model'
    def __init__(self, responses):
        self.responses=iter(responses)
        self.requests=[]
    def request(self, prompt):
        return GeminiTransport(self.model).request(prompt)
    def send(self, request):
        self.requests.append(request)
        return canonical_bytes({'modelVersion': self.model, 'responseId': f'fixture-{len(self.requests)}',
            'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(next(self.responses))}]}}]})


@pytest.fixture
def gitrepo(tmp_path):
    root=tmp_path/'repo';root.mkdir()
    subprocess.run(['git','init','-q',str(root)],check=True)
    subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid','commit','-q','--allow-empty','-m','Fixture'],cwd=root,check=True)
    return root


def test_stateless_transport_request_shape():
    t=GeminiTransport('configured-model')
    request=t.request('only supplied content')
    assert set(request)=={'systemInstruction','contents','tools','generationConfig'}
    assert request['tools']==[] and len(request['contents'])==1
    assert 'cachedContent' not in request and 'key' not in json.dumps(request)


def test_stage_receipts_resume_and_substitution(gitrepo,tmp_path):
    store=RunStore.create(tmp_path/'run',gitrepo,{},fixture=True)
    store.put('author_selection_prompt.txt',b'input')
    store.event('prepared',['author_selection_prompt.txt'])
    t=FixtureTransport([{'result':1}])
    assert store.invoke('selection','input',t)=={'result':1}
    assert store.invoke('selection','input',t)=={'result':1}
    assert len(t.requests)==1
    with pytest.raises(BenchmarkIntegrityError):store.invoke('selection','changed input',t)
    path=store.path('stages/selection/parsed.json');path.write_text('{"result":2}')
    with pytest.raises(BenchmarkIntegrityError):store.verify_response('selection')


def test_refuses_out_of_order_and_unreviewed_live(gitrepo,tmp_path):
    with pytest.raises(BenchmarkIntegrityError):RunStore.create(tmp_path/'live',gitrepo,{})
    store=RunStore.create(tmp_path/'fixture',gitrepo,{},fixture=True)
    with pytest.raises(BenchmarkIntegrityError):store.invoke('reviewer','wrong stage',FixtureTransport([]))


def test_raw_extraction_is_closed():
    with pytest.raises(BenchmarkIntegrityError):strict_json('{"a":1,"a":2}')
    with pytest.raises(BenchmarkIntegrityError):strict_json('{"a":NaN}')
    for candidate in [ {'finishReason':'MAX_TOKENS','content':{'parts':[{'text':'{}'}]}},
                       {'finishReason':'STOP','content':{'parts':[{'functionCall':{'name':'shell'}}]}} ]:
        with pytest.raises(BenchmarkIntegrityError):GeminiTransport.extract(canonical_bytes({'candidates':[candidate]}))


def test_code_change_invalidates_resume(gitrepo,tmp_path):
    store=RunStore.create(tmp_path/'run',gitrepo,{},fixture=True)
    (gitrepo/'astrology').mkdir();(gitrepo/'astrology/new.py').write_text('changed')
    with pytest.raises(BenchmarkIntegrityError):store.assert_code()


def test_blind_state_machine(gitrepo,tmp_path):
    store=RunStore.create(tmp_path/'run',gitrepo,{},fixture=True)
    store.put_json('01-handoff.json',{'reasoning_packet':{'facts':{'positions':{'sun':'fixture'}}},'preparation_parameters':{}})
    store.put('final_reviewed_report.md',b'new fixture text')
    store.event('reviewer:validated',['01-handoff.json','final_reviewed_report.md'])
    commit_blind(store,b'old anonymous fixture',{'dimensions':[f'dimension {i}' for i in range(17)]})
    prompt=store.path('evaluator_prompt.txt').read_text()
    assert 'ground_truth' in prompt and 'nonce' not in prompt and 'mapping' not in prompt
    with pytest.raises(BenchmarkIntegrityError):reveal_blind(store)
    structured_dimensions=[{
        'dimension_id': f'dimension {i}',
        'alpha_score': 8,
        'beta_score': 9,
        'alpha_evidence': [store.path('blind/alpha.md').read_text()],
        'beta_evidence': [store.path('blind/beta.md').read_text()],
        'factual_mismatches': [],
        'uncertainty': None,
    } for i in range(17)]
    t=FixtureTransport([{'dimensions': structured_dimensions, 'overall_notes': 'Structured evaluation pass'}])
    result=evaluate_blind(store,t)
    assert result['score']['beta_wins']==17
    assert reveal_blind(store)['assignment']['run_id']=='run'
    assert len(t.requests)==1
    assert evaluate_blind(store,t)==result


def _explicit_payload(report, sources, handoff):
    parsed=_parse_premium_narrative(report,handoff['reader_domain_manifest'])
    by_hash={s['narrative_block_sha256']:s for s in sources}
    return {'packet_id':handoff['packet_id'],'blocks':[
        {'section_id':b['section'],'kind':b['kind'],'content':b['content'],
         **{k:by_hash[b['narrative_block_sha256']][k] for k in ('synthesis_ids','claim_ids','timing_ids')}}
        for b in parsed['authored']]}


def _explicit_reviewer_payload(report, sources, handoff, verdict='approved', corrections_made=None, remaining_warnings=None, regeneration_request=None):
    base = _explicit_payload(report, sources, handoff)
    return {
        'packet_id': handoff['packet_id'],
        'verdict': verdict,
        'blocks': base['blocks'],
        'corrections_made': corrections_made or ["Polished prose rhythm and domain coherence"],
        'remaining_warnings': remaining_warnings or [],
        'regeneration_request': regeneration_request,
    }


@pytest.fixture(scope='module')
def prose_fixture():
    h=current_handoff()
    p=load_json(BENCHMARK_DIR/'01-author-selection-plan.json');p['packet_id']=h['packet_id'];p=with_editorial_sections(p,h)
    bp=plan_prospective_narrative_blocks(h,author_selection_plan=p)
    author=(BENCHMARK_DIR/'author_draft.md').read_text()
    reviewer=(BENCHMARK_DIR/'final_reviewed_report.md').read_text()
    src,_,_=bind_prospective_plan_to_prose(author,bp,h['reader_domain_manifest'])
    rs,_,_=bind_prospective_plan_to_prose(reviewer,bp,h['reader_domain_manifest'])
    return h,p,bp,_explicit_payload(author,src,h),_explicit_reviewer_payload(reviewer,rs,h)


def test_explicit_sources_no_retroactive_binding(prose_fixture):
    h,p,bp,a,r=copy.deepcopy(prose_fixture)
    rendered=render_explicit_blocks(a,h,bp)
    assert rendered['sources']
    a['blocks'][0]['synthesis_ids']=['reasoned.not_planned']
    with pytest.raises(SelectionPlanValidationError):render_explicit_blocks(a,h,bp)
    with pytest.raises(SelectionPlanValidationError):render_explicit_blocks(r,h,bp,author_scope={})


def test_author_owns_opening_and_integration(prose_fixture):
    h,p,bp,a,r=copy.deepcopy(prose_fixture)
    p['editorial_sections']['opening'].reverse()
    changed=plan_prospective_narrative_blocks(h,author_selection_plan=p)
    assert changed['sections']['opening'][0]['intended_mechanism']==p['editorial_sections']['opening'][0]['intended_mechanism']
    assert changed['sections']['opening'][0]['synthesis_ids']==p['editorial_sections']['opening'][0]['synthesis_ids']
    old=copy.deepcopy(p);old.pop('editorial_sections');old['version']='1.0'
    with pytest.raises(SelectionPlanValidationError):plan_prospective_narrative_blocks(h,author_selection_plan=old)


def test_complete_captured_fixture_no_model(gitrepo,tmp_path,prose_fixture):
    from datetime import datetime
    h,p,bp,a,r=prose_fixture
    cfg=h['preparation_parameters']
    store=prepare_run(tmp_path/'runs'/'fixture',gitrepo,CHART_3_BIRTH,PROFILE,fixture=True,
        as_of=datetime.fromisoformat(cfg['effective_as_of']),horizon_days=cfg['horizon_days'],include_timing=cfg['include_timing'])
    t=FixtureTransport([p,a,r])
    result=continue_run(store,t)
    assert result['publication_approved']
    assert verify_captured_derivation(store)
    assert len(t.requests)==3
    assert continue_run(store,t)==result and len(t.requests)==3
    store.path('final_reviewed_report.md').write_text('substituted historical report')
    with pytest.raises(BenchmarkIntegrityError):verify_captured_derivation(store)
