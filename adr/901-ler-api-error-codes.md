# 901 LER API error codes

LER har valgt at lade den autoritative kilde for API fejlkoder
være et end point, /api/V1/ErrorCodes, som returnerer et json
dokument, med alle fejlkoder. Det er egentligt en fin løsning. 

Men nogen gange vil man måske gerne studere/læse disse koder
uden at bruge shell kommandoer som curl, jq, grep.

Jeg overvejer at vise disse koder i lerbogen.

Mange af koderne er vigtig baggrundsinfo for at forstå,
hvordan jeg bør implementere både ler-xml-validator
og lermodel. Og hele lerbogen repo er jo netop
bygget for at samle den nødvendige dokumentaiton
for at bygge disse.

## Beslutning

Jeg tilføjer en side i lerbogen,
med en liste over alle fejlkoder.
