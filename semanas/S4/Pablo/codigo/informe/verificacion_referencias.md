# Verificación de referencias de la sección de IA

Consulta: 2026-11-06, API de Crossref (`https://api.crossref.org/works/<doi>`), la página de JMLR y la
página de Microsoft Research. "Coincide" significa que el dato de Crossref/la fuente es igual al del `.bib`.

| Clave | Fuente consultada | Campos que coinciden | Estado |
|---|---|---|---|
| `zheng2008understanding` | Crossref 10.1145/1409635.1409677 | título, 5 autores, año 2008, UbiComp '08, pp. 312–321, DOI | verificada |
| `zheng2008learning` | Crossref 10.1145/1367497.1367532 | título, 4 autores, año 2008, WWW '08, pp. 247–256, DOI | verificada |
| `zheng2010geolife` | Página de Microsoft Research y PDF (primera página) | título, autores, revista (IEEE Data Eng. Bull.), año 2010 | **parcial**: no tiene DOI en Crossref y la fuente primaria no muestra volumen ni páginas; 33(2), 32–40 salen de un resumen de búsqueda web que cita la página de descarga de Microsoft. Conviene confirmarlo en el índice del IEEE TCDE antes de entregar |
| `breiman2001random` | Crossref 10.1023/A:1010933404324 | título, autor, Machine Learning 45(1), pp. 5–32, año, DOI | verificada |
| `pedregosa2011scikit` | https://jmlr.org/papers/v12/pedregosa11a.html | título, 16 autores, JMLR 12, pp. 2825–2830, año 2011 (JMLR no asigna DOI) | verificada |
| `lopez2018sumo` | Crossref 10.1109/ITSC.2018.8569938 | título, 10 autores, ITSC 2018, pp. 2575–2582, IEEE, DOI | verificada |
| `gjoreski2018shl` | Crossref 10.1109/ACCESS.2018.2858933 | título, 7 autores, IEEE Access 6, pp. 42592–42604, año, DOI | verificada |
| `zandbergen2009accuracy` | Crossref 10.1111/j.1467-9671.2009.01152.x | título (*Accuracy of iPhone Locations…*), autor, Transactions in GIS 13(s1), pp. 5–25, año, DOI | verificada |
| `zandbergen2011positional` | Crossref 10.1017/S0373463311000051 | título (*Positional Accuracy of Assisted GPS Data…*), 2 autores, J. Navigation 64(3), pp. 381–399, año, DOI | verificada |
| `merry2019smartphone` | Crossref 10.1371/journal.pone.0219890 | título, 2 autores, PLoS ONE 14(7) e0219890, año, DOI | verificada |
| `groves2011shadow` | Crossref 10.1017/S0373463311000087 | título (*Shadow Matching…*), autor, J. Navigation 64(3), pp. 417–430, año, DOI | verificada |
| `jun2006smoothing` | Búsqueda en Crossref por título y autores | título, 3 autores, TRR 1972, pp. 141–150, año 2006; DOI **10.1177/0361198106197200117** | verificada, con **corrección** |

## Diferencias con `ia/calibracion/FUENTES.md` (no se editó ese archivo)

1. **Jun, Guensler y Ogle (2006): el DOI de FUENTES.md es incorrecto.** Dice
   `10.1177/0361198106197200116`, pero ese DOI corresponde a otro artículo (Wu y Tsai, "Enhanced Roadway
   Geometry Data Collection Using an Effective Video Log Image-Processing Algorithm", TRR 1972, pp. 133–140).
   El correcto es `10.1177/0361198106197200117` (pp. 141–150). El artículo es sobre suavizado del error
   aleatorio del GPS, así que el contenido citado en FUENTES.md es plausible.
2. FUENTES.md cita a Groves (2011) solo como "*Journal of Navigation* 64(3)"; el artículo es *Shadow Matching:
   A New GNSS Positioning Technique for Urban Canyons* (pp. 417–430). Por eso la clave es `groves2011shadow`
   (no `groves2013principles`, que sería el libro, otra obra).
3. **Las cifras numéricas de FUENTES.md (σ, ρ, p_pérdida) NO se verificaron aquí**: solo se confirmaron los
   datos bibliográficos. El propio archivo las marca "por verificar" y algunas son inferencias (por ejemplo,
   ρ ≈ 0,8–0,9 "inferido"). En el informe conviene citarlas como "rango adoptado a partir de la literatura" y no
   atribuir a cada artículo una cifra exacta que no se ha leído en el PDF.

## Sintaxis

Chequeo en Python (2026-11-06): llaves balanceadas, 12 claves únicas, campos separados por comas y sin coma
sobrante en cada entrada: correcto.
