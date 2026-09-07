"""Render model-declared blocks and provenance without inferring sources from prose."""
from .exceptions import SelectionPlanValidationError
from .pipeline import _parse_premium_narrative, _narrative_block_entry

BLOCK_FIELDS = {'section_id', 'kind', 'content', 'synthesis_ids', 'claim_ids', 'timing_ids'}


def render_explicit_blocks(payload, handoff, block_plan, author_scope=None):
    if not isinstance(payload, dict) or set(payload) != {'packet_id', 'blocks'} or payload.get('packet_id') != handoff['packet_id']:
        raise SelectionPlanValidationError('Explicit prose packet/shape mismatch')
    rows = payload['blocks']
    if not isinstance(rows, list) or not rows:
        raise SelectionPlanValidationError('Explicit blocks required')
    manifest = handoff['reader_domain_manifest']
    specs = [('opening', manifest['opening']['heading']),
             *[(d['id'], d['heading']) for d in manifest['domains']],
             ('integration', manifest['integration']['heading'])]
    groups = {key: [] for key, _ in specs}
    available = block_plan['sections']
    for row in rows:
        if not isinstance(row, dict) or set(row) != BLOCK_FIELDS:
            raise SelectionPlanValidationError('Invalid explicit block shape')
        section = row['section_id']
        if not isinstance(section, str) or section not in available:
            raise SelectionPlanValidationError('Unknown/unavailable explicit section')
        if row['kind'] not in ('paragraph', 'list_item', 'subheading') or not isinstance(row['content'], str) or not row['content'].strip():
            raise SelectionPlanValidationError('Invalid explicit prose content')
        for field in ('synthesis_ids', 'claim_ids', 'timing_ids'):
            value = row[field]
            if not isinstance(value, list) or any(not isinstance(x, str) for x in value) or len(value) != len(set(value)):
                raise SelectionPlanValidationError('Invalid explicit source IDs')
        allowed = {sid for block in available[section] for sid in block['synthesis_ids']}
        if not row['synthesis_ids'] or not set(row['synthesis_ids']) <= allowed or row['claim_ids']:
            raise SelectionPlanValidationError('Unplanned explicit source attribution')
        if author_scope is not None and not set(row['synthesis_ids']) <= set(author_scope.get(section, [])):
            raise SelectionPlanValidationError('Reviewer expanded Author materialized authority')
        allowed_timing = {tid for block in available[section] for tid in block['timing_ids']}
        if not set(row['timing_ids']) <= allowed_timing:
            raise SelectionPlanValidationError('Unplanned timing attribution')
        groups[section].append(row)
    parts = [handoff['reader_introduction']]
    ordered = []
    for section, heading in specs:
        parts.append('## ' + heading.removeprefix('## ').strip())
        if section not in available:
            domain = next(d for d in manifest['domains'] if d['id'] == section)
            parts.append(domain['unavailable_notice']['text'])
            continue
        if not groups[section]:
            raise SelectionPlanValidationError('Missing explicit section: ' + section)
        for row in groups[section]:
            prefix = {'paragraph': '', 'list_item': '- ', 'subheading': '### '}[row['kind']]
            parts.append(prefix + row['content'].strip())
            ordered.append(row)
    report = '\n\n'.join(parts)
    parsed = _parse_premium_narrative(report, manifest)
    if parsed['errors'] or len(parsed['authored']) != len(ordered):
        raise SelectionPlanValidationError('Explicit blocks do not match parsed narrative: ' + ', '.join(parsed['errors']))
    sources, scope = [], {}
    for row, physical in zip(ordered, parsed['authored']):
        expected = _narrative_block_entry(row['kind'], row['content'], row['section_id'], 'unordered' if row['kind'] == 'list_item' else None)
        if expected['narrative_block_sha256'] != physical['narrative_block_sha256'] or row['section_id'] != physical['section']:
            raise SelectionPlanValidationError('Explicit block rendering changed content/ownership')
        sources.append({'narrative_block_sha256': physical['narrative_block_sha256'], **{f: row[f] for f in ('synthesis_ids', 'claim_ids', 'timing_ids')}})
        if row['kind'] != 'subheading':
            scope.setdefault(row['section_id'], set()).update(row['synthesis_ids'])
    def ownership(section):
        return {'narrative_block_sha256s': [r['narrative_block_sha256'] for r in parsed['sections'][section]['authored']]}
    sections = {'opening': ownership('opening'), 'integration': ownership('integration'),
                'domains': [dict(domain_id=d['id'], **ownership(d['id'])) for d in manifest['domains'] if d['availability'] == 'available']}
    return {'report': report, 'sources': sources, 'sections': sections, 'materialized_scope': {k: sorted(v) for k, v in scope.items()}}
