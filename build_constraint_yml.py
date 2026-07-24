#!/usr/bin/env python3
from pathlib import Path

import yaml

from featurekatalog import parse_featurekatalog

DOCX_PATH = Path(__file__).parent / 'versions' / '2.2.0' / 'ler_featurekatalog.docx'
OUT_DIR = Path(__file__).parent / 'constraints'


def main():
    OUT_DIR.mkdir(exist_ok=True)
    for ft in parse_featurekatalog(str(DOCX_PATH)):
        if not ft['restriktioner']:
            continue
        rows = [
            {'feature_type': ft['navn'], 'name': r['Navn'], 'expression': r['Udtryk']}
            for r in ft['restriktioner']
        ]
        (OUT_DIR / f"{ft['navn']}.yml").write_text(
            yaml.dump(rows, allow_unicode=True, sort_keys=False, width=1000)
        )


if __name__ == '__main__':
    main()
