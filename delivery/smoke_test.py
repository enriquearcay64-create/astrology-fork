"""Portable smoke test for the subject-neutral PDF renderer."""
import json
from pathlib import Path

from render import render


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'fixtures' / 'delivery.json'


def main() -> None:
    render(CONFIG)
    qa = json.loads((ROOT / 'fixtures' / 'output' / 'pdf' / 'qa.json').read_text())
    assert len(qa['pdfs']) == 2
    assert all(not item['out_of_bounds'] for item in qa['pdfs'])
    assert all(not item['missing_or_reordered_reading_blocks'] for item in qa['pdfs'])
    assert all(Path(item['path']).is_file() for item in qa['pdfs'])
    print('Delivery smoke test passed: two PDFs, complete text order, no geometry findings.')


if __name__ == '__main__':
    main()
