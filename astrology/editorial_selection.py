"""Author-owned opening/integration selection. No source ranking or allocation."""
from .exceptions import SelectionPlanValidationError


def validate_editorial_sections(sections, approved):
    errors = []
    if not isinstance(sections, dict) or set(sections) != {'opening', 'integration'}:
        return ['editorial_sections_required']
    for section, blocks in sections.items():
        if not isinstance(blocks, list) or not blocks:
            errors.append(f'empty_editorial_section:{section}')
            continue
        for block in blocks:
            if not isinstance(block, dict) or set(block) != {'synthesis_ids', 'intended_mechanism'}:
                errors.append(f'invalid_editorial_block:{section}')
                continue
            ids = block['synthesis_ids']
            if not isinstance(ids, list) or not ids or any(not isinstance(sid, str) for sid in ids):
                errors.append(f'invalid_editorial_sources:{section}')
                continue
            if len(ids) != len(set(ids)) or any(sid not in approved for sid in ids):
                errors.append(f'unknown_or_duplicate_editorial_source:{section}')
            if not isinstance(block['intended_mechanism'], str) or not block['intended_mechanism'].strip():
                errors.append(f'missing_editorial_mechanism:{section}')
    return errors


def compile_editorial_sections(sections):
    return {section: [dict(block, block_index=index, kind='paragraph', claim_ids=[], timing_ids=[])
                      for index, block in enumerate(blocks)] for section, blocks in sections.items()}


def conservative_editorial_sections(approved):
    """Explicit headless fixture fallback: all sources, no editorial selection."""
    ids = list(approved)
    return {section: [{'synthesis_ids': ids, 'intended_mechanism': 'Conservative test fixture; no premium editorial selection.'}]
            for section in ('opening', 'integration')}
