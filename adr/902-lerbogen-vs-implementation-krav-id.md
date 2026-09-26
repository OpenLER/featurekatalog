# 902 Lerbogen vs. implementation: krav-ID'er

Jeg har identificeret en række krav til XML, der hverken valideres i XSD eller
udtrykkes i featurekatalogets "restriktioner". 

Disse krav har jeg indtil videre kaldt "andre krav",
og de er ikke knyttet til nogen særlig version af featurekatalog.

Der kan også være enkelte krav hér, som faktisk ikke er krav
hos LER-api. Fx. accepterer LER-serveren et etableringstidspunkt
med værdien "2024-02-30", som ikke er en gyldig dato.
Jeg er i tvivl om, præcist hvordan den
håndterer det, men jeg kan i hvert fald konstatere, at den
betragter det for at være før skæringsdato (1. juli 2023).

Jeg er i gang med også at skrive en validator, ler-xml-validator,
som tjekker både XSD, restriktionerne fra featurekatalog,
samt disse "andre krav".

I min validator, så vil jeg gerne tildele en kode til hver af
disse violations, fx. G1, G2, etc. Og måske også bruge subcodes,
fx. G5.1, G5.2, etc.

Nu er spørgsmålet, hvor sådanne koder skal tildeles. At tildele
koder til forskellige violations hænger også sammen med, hvordan
man vælger at betragte de forskellige krav. For nogle generelle
krav gælder at det både kan nedfældes som ét samlet krav, eller
som et antal seperate krav.

Det er lettere at bygge en pæn implementation af en validator,
hvis validatoren arbejder ud fra krav, der er lette at validere
enkelvist.

Nu er spørgsmålet så: Skal jeg skrive lerbogen således, at
jeg allerede i lerbogen tænker på en senere implementation,
ved at dokumentere kravene på en måde, hvor de let kan implementeres.

Hvis ja, så følger der en række fordele:
- lerxml er lettere at implementere, fordi alle valg er truffet i lerbog
- lerxml kan bruge de koder, der er anvendt i lerbog, og der
  er ikke behov for at lerxml har sin egen reference med fejlkoder
- lerxml kan pege direkte til permalinks på lerbogen
- undgår redundant beskrivelse af fejl

Argumenter imod at lægge dette ansvar i lerbogen:
- Der er mange måder at implementere en validator
- Ved at lave så fingranulerede krav i lerbogen, så låser vi lidt,
  hvordan en validator kan bygges, og det er jo netop meningen,
  at alle skal kunne læse og bruge lerbogen

## Beslutning

Jeg lægger ansvaret i lerbogen. Jeg synes simpelthen, at OpenLER generelt bliver
lidt pænere og mere elegant, og det opvejer ulemperne.

- Lerbogen tildeler ID'er til krav og bestemmer opdelingen (G5, G5.1 …).
- lerxml bruger lerbogens ID som kode for violations, der svarer til et krav.
- Severity, beskedtekster og lerxml's egne koder (XSD, XTA, W1, GEOM3) hører til i lerxml.