"""Explicit test-only conversion of historical structural fixtures to current contracts.

Never used by production or promotion replay. Reusing prose here tests guard
regressions, not model freshness. The historical files remain byte-identical.
"""
from functools import lru_cache
import copy
import json
from pathlib import Path
from datetime import datetime
from astrology.pipeline import prepare_premium_handoff
from astrology.models import BirthData, LocalizationProfile

@lru_cache(maxsize=1)
def _current_handoff():
    old=json.loads(Path('benchmarks/chart3_mutable_earth_water/01-handoff.json').read_text())
    cfg=old['preparation_parameters']
    return prepare_premium_handoff(
        BirthData('1995-09-08T19:45:00','Europe/Paris',48.8566,2.3522,birth_time_known=True),
        profile=LocalizationProfile(preferred_language='pt-BR'),
        as_of=datetime.fromisoformat(cfg['effective_as_of']),horizon_days=cfg['horizon_days'],include_timing=cfg['include_timing'])

def current_handoff():
    return copy.deepcopy(_current_handoff())


def with_editorial_sections(plan, handoff):
    """Explicit historical fixture choices, not a production selection algorithm."""
    from astrology.pipeline import compose_canonical_domain_syntheses
    if plan.get('version') == '1.1':
        return plan
    facts=handoff['reasoning_packet']['facts']
    claims={x['id']:x for x in facts.get('allowed_claims',[])}
    _,_,mandatory=compose_canonical_domain_syntheses(claims,handoff['reader_domain_manifest'],facts.get('coverage',{}))
    relational=[x['id'] for x in handoff.get('prepared_signature_syntheses',[]) if x.get('reasoning_class') in {'integrated_pattern','theme_interaction'} and not any(c.startswith('claim.house_ruler.placidus.') for c in x.get('source_claim_ids',[]))]
    first=relational[0];second=relational[1] if len(relational)>1 else first
    mid=len(mandatory)//2
    return dict(plan,version='1.1',editorial_sections={
        'opening':[{'synthesis_ids':[first,*mandatory[:mid]],'intended_mechanism':'Historical test fixture opening'},
                   {'synthesis_ids':[second,*mandatory[mid:]],'intended_mechanism':'Historical test fixture tensions'}],
        'integration':[{'synthesis_ids':[first],'intended_mechanism':'Historical test fixture integration'}]})


def fixture_plan_prospective_narrative_blocks(handoff, *args, **kwargs):
    from astrology.pipeline import plan_prospective_narrative_blocks,build_canonical_selection_plan
    plan=kwargs.get('author_selection_plan')
    if plan is None and kwargs.get('allow_conservative_fallback'):
        plan=build_canonical_selection_plan(handoff['reader_domain_manifest'],allow_conservative_fallback=True)
        plan['packet_id']=handoff['packet_id']
    if isinstance(plan,dict) and plan.get('version')=='1.0':
        kwargs['author_selection_plan']=with_editorial_sections(plan,handoff)
    return plan_prospective_narrative_blocks(handoff,*args,**kwargs)
