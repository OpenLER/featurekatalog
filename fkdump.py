#!/usr/bin/env python3
"""Skriv fkdump: parse_featurekatalog()'s resultat, én YAML-fil pr. featuretype
pr. version, til fkdump/<version>/<featuretype>.yml.

Køres automatisk af `python3 app.py freeze`, men kan også køres alene.
"""
import shutil
from pathlib import Path

import yaml

from featurekatalog import parse_featurekatalog

ROOT = Path(__file__).parent
VERSIONS_DIR = ROOT / 'versions'
OUT_DIR = ROOT / 'fkdump'


def write_fkdump(version, featuretyper):
    """Erstat fkdump/<version>/ med én fil pr. featuretype, så featuretyper, der
    er forsvundet fra docx, heller ikke ligger tilbage i fkdump."""
    out_dir = OUT_DIR / version
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    for ft in featuretyper:
        (out_dir / f"{ft['navn']}.yml").write_text(
            yaml.dump(ft, allow_unicode=True, sort_keys=False, width=1000)
        )


def main():
    for version_dir in sorted(VERSIONS_DIR.iterdir()):
        docx_path = version_dir / 'ler_featurekatalog.docx'
        if docx_path.exists():
            write_fkdump(version_dir.name, parse_featurekatalog(str(docx_path)))


if __name__ == '__main__':
    main()
