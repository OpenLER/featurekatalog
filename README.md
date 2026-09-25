# featurekatalog

Et uofficielt opslagsværk over LERs datamodel, krav og fejlkoder:
**https://openler.github.io/featurekatalog/**

Jeg har tit haft brug for at tjekke, hvad der er tilladt i LER, f.eks.
hvornår hvilke attributter er påkrævede. Den officielle dokumentation er en
lang docx-fil plus en række XSD-filer, og den er besværlig at slå op i.

Derfor har jeg samlet det hele på én hjemmeside, hvor man kan browse og
finde de detaljer, man leder efter. Det er den hjemmeside, jeg ville ønske,
at LER selv havde lavet: en lommebog til alle, der arbejder med LER, også
dem, der vil bygge deres egen LER-klient.

## Hvorfor parse docx og ikke en kildefil?

Docx-filen med featurekataloget er tydeligvis maskingenereret ud fra en eller
flere kildefiler, f.eks. en XMI-fil (UML-modellen). XSD-filerne er formentlig
genereret af samme værktøj ud fra de samme kildefiler.

Det havde været mere elegant at parse kildefilen direkte. I maj 2026 skrev jeg
til Klimadatastyrelsen (tidligere SDFE) og spurgte efter den, men fik svar om,
at en sådan fil ikke findes, og at de kun har XSD- og docx-filerne.

Derfor parser featurekatalog docx og XSD. Det fungerer godt nok i praksis.

## Kilder

Sitet samler fire slags information fra fire forskellige kilder:

| Information | Kilde | Hentes af |
|---|---|---|
| Struktur: elementer, typer og typehierarki | XSD-filerne | `wrapper.py` (`SchemaEx`) |
| Attributter, restriktioner og associationsroller pr. featuretype | Featurekatalogets docx-fil | `featurekatalog.py` |
| Andre krav (G1–G4), som ikke er dokumenteret, eller som ikke kommer med i parsingen af docx | Mine egne tests mod LERs extest-API (se `ler-api-experiments`) | Håndskrevet i `templates/general_constraints.html` |
| Fejlkoder og navngivne forretningsregler | LERs API (`/api/errorcodes`) | `fetch_errorcodes.py` |

## Parsing af data fra docx

Funktionen `parse_featurekatalog()` tager en docx-fil og returnerer en
datastruktur, der kun består af lister og dicts og derfor er kompatibel med
YAML og JSON. Datastrukturen indeholder (næsten) alt, hvad der er værd at
udtrække. Jeg vil tro, at man med den rette viden ville kunne oversætte
disse data tilbage til kildefilen (f.eks. XMI).

Flask-visningen bruger alle disse data.

Noget af det eksporteres også til filer: restriktionerne. Det er de eneste
valideringsregler i docx, som ikke allerede er udtrykt i de officielle
XSD-filer. De eksporteres uden fortolkning oveni (ingen koder, kategorisering
e.l.) til `constraints/<version>/<featuretype>.yml`.

Disse filer har jeg brugt til at lave de tilsvarende XTA-filer i
[ler-xml-validator](https://github.com/OpenLER/ler-xml-validator).

## Arkitektur

Al dokumentation genereres som statisk HTML. `app.py` fletter kilderne
sammen i én Flask-app, og Frozen-Flask gemmer den som statiske filer i
`docs/`, som GitHub Pages udgiver. Parserne er skrevet med hjælp fra Claude.

## Flere versioner af datamodellen

Sitet dækker flere udgivne versioner af LER's datamodel, ikke kun den seneste.
Kildefilerne (featurekatalog-docx + XSD'er) for hver version ligger under
`versions/<version>/`:

```
versions/2.0.0/ler_featurekatalog.docx, schemas/2.0_ler.xsd, ...
versions/2.0.1/...
versions/2.1.0/...
versions/2.2.0/...
```

`app.py`'s `VERSIONS`-dict styrer hvilke der er med. `schemas/http/` og
`schemas/https/` (vendorede kopier af GML/xlink/ISO 19139/Dublin Core) er
fælles for alle versioner - de er eksterne standarder, uafhængige af LER's
egen versionering.

Hver side findes under `/<version>/`, fx `/2.2.0/restriktioner/`. Selve
roden (`/`) er en liste over de tilgængelige versioner.

## Kør som standard Flask site

```bash
pip install -r requirements.txt
python3 app.py
```

Kører en almindelig Flask dev-server med hot reload på http://127.0.0.1:5000/.
Kun relevant under development.

## Byg statiske sider og deploy til GitHub Pages

```bash
python3 app.py freeze
git add docs/
git commit -m "Opdater site"
git push
```

Skriver statisk HTML til `docs/` (via Frozen-Flask, inkl. en `.nojekyll`-fil så
GitHub ikke forsøger at Jekyll-processere sitet).

## Generér restriktioner som YAML

```bash
python3 build_constraint_yml.py
```

Skriver én YAML-fil pr. featuretype pr. version til `constraints/<version>/`
(fx `constraints/2.2.0/Ledning.yml`), med de restriktioner featuretypen har fra
den pågældende versions docx (`feature_type`, `name`, `expression`).
Featuretyper uden restriktioner får ingen fil. Kører automatisk for alle
versioner i `versions/`.

Scriptet kører uafhængigt af Flask-app'en og freeze-processen og deler kun
parseren i `featurekatalog.py`. Se "Parsing af data fra docx" for, hvorfor
kun restriktionerne eksporteres.

## Hent/opdater fejlkoder

```bash
export FEATUREKATALOG_CERT=/sti/til/cert-eller-fullchain.pem
export FEATUREKATALOG_KEY=/sti/til/client.key
python3 fetch_errorcodes.py
```

Henter LER's fulde liste over fejlkoder og navngivne forretningsregler fra
`GET /api/errorcodes` på `services-extest.ler.dk` og skriver den til
`errorcodes.json`, som vises på `/errorcodes/`-siden.

`errorcodes.json` committes til repoet, ligesom kildefilerne under
`versions/`.