#!/usr/bin/env python3
from pathlib import Path

import yaml

from featurekatalog import parse_featurekatalog

VERSIONS_DIR = Path(__file__).parent / 'versions'
OUT_DIR = Path(__file__).parent / 'constraints'


def main():
    for version_dir in sorted(VERSIONS_DIR.iterdir()):
        docx_path = version_dir / 'ler_featurekatalog.docx'
        if not docx_path.exists():
            continue
        out_dir = OUT_DIR / version_dir.name
        out_dir.mkdir(parents=True, exist_ok=True)
        for ft in parse_featurekatalog(str(docx_path)):
            if not ft['restriktioner']:
                continue
            rows = [
                {'feature_type': ft['navn'], 'name': r['Navn'], 'expression': r['Udtryk']}
                for r in ft['restriktioner']
            ]
            (out_dir / f"{ft['navn']}.yml").write_text(
                yaml.dump(rows, allow_unicode=True, sort_keys=False, width=1000)
            )


if __name__ == '__main__':
    main()
