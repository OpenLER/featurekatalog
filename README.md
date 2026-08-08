# featurekatalog

Jeg har tit haft brug for at tjekke, hvad der var tilladt ift LER,
herunder hvornår hvilke attributter var påkrævede, og jeg syntes
det var besværligt/trægt at læse den officielle LER-dokumentation.

Jeg har samlet ovenstående information i en hjemmeside, i dette repo.
Resultatet publiceres på:
[https://lerinfo.github.io/featurekatalog/](https://lerinfo.github.io/featurekatalog/).

## Detaljer omkr udarbejdelsen af denne dokumentation

Al dokumentation genereres som statisk html. Disse html filer
er autogeneret vha Flask og Frozen-Flask plus mine egne
værktøjer (med hjælp fra Claude AI), der extracter info fra resourcer.

Der er tre typer af information/krav, fra tre forskellige kilder:

## Komposition af data

### XML Schema / XSD

Information omkr struktur/komposition er extracted fra XSD-filer.

### Restriktioner, attributter, m.m. fra featurekatalog

I LER's featurekatalog docx angives for hver feature type diverse
informationer i et bestemt format. Disse parses/extractes og vises
også.

### Yderligere restriktioner

Der er andre krav, som enten slet ikke er dokumenteret eller som
er dokumenteret på en måde, hvor de ikke kommer med i min
parsing af ovennævnte docx.

- `featurekatalog.py` parser `ler_featurekatalog.docx` (attributter, restriktioner,
  associationsroller pr. featuretype).
- `wrapper.py` (`SchemaEx`) parser `<version>_ler.xsd` (og de importerede
  Dimensions/Annotations-namespaces) for XSD-struktur (elementer, typehierarki).
- `app.py` fletter de to og server dem som én sammenhængende Flask-app.

### Flere versioner af datamodellen

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

Formålet er at give et maskinlæsbart udtræk af restriktionerne til brug i andre
repos/værktøjer (fx et der implementerer dem i Schematron) — uden fortolkning
oveni (ingen koder, kategorisering e.l.). Kører uafhængigt af Flask-app'en og
freeze-processen; deler kun `featurekatalog.py`-parseren.

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