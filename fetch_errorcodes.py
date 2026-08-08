#!/usr/bin/env python3
"""
fetch_errorcodes.py - henter LER's fulde liste over fejlkoder/forretningsregler
fra GET /api/errorcodes på extest, og gemmer den til errorcodes.json.

Dette er den autoritative kilde - direkte fra LER-serveren selv, ikke fra
dokumentation der kan halte bagefter (se adr/901-ler-api-error-codes.md).
errorcodes.json committes til repoet (ligesom versions/-kildefilerne), så
app.py/freeze ikke afhænger af en live forbindelse eller certifikat.

Kræver klient-certifikat via miljøvariablerne FEATUREKATALOG_CERT (cert/fullchain)
og FEATUREKATALOG_KEY (privat nøgle).

Usage:
    python3 fetch_errorcodes.py
"""
import json
import os
from pathlib import Path

import requests

LER_HOST = 'https://services-extest.ler.dk'
OUT_PATH = Path(__file__).parent / 'errorcodes.json'

CERT_FILE = os.environ['FEATUREKATALOG_CERT']
KEY_FILE = os.environ['FEATUREKATALOG_KEY']


def main():
    resp = requests.get(
        f'{LER_HOST}/api/errorcodes',
        cert=(CERT_FILE, KEY_FILE),
        headers={'Accept': 'application/json'},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    codes = data['Data'] if isinstance(data, dict) else data
    OUT_PATH.write_text(json.dumps(codes, ensure_ascii=False, indent=2) + '\n')
    print(f'Gemt {len(codes)} fejlkoder/regler til {OUT_PATH}')


if __name__ == '__main__':
    main()
