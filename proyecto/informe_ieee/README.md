# Informe IEEE del Examen Interciclo (RVH)

Artículo en formato IEEE Conference (`IEEEtran`, modo `conference`), en español.

| Archivo | Qué es |
|---|---|
| `esert_ieee.tex` | fuente del artículo (se puede subir tal cual a Overleaf con `referencias.bib` y `figuras/`) |
| `referencias.bib` | bibliografía; los seis artículos del estado del arte se verificaron en Crossref y Semantic Scholar |
| `esert_ieee.pdf` | el PDF compilado |
| `generar_figuras.py` | figuras `busqueda`, `co2`, `falsas` y `rutas` desde `kpis/resultados/final/resumen.csv` y `datos/rutas.csv` |
| `comparar_rutas.py` | puesto más cercano en línea recta frente a ruta de manejo más corta (300 puntos, semilla 1) |

Regenerar todo, dentro del contenedor `van3twin` y desde `proyecto/`:

```bash
python3 informe_ieee/comparar_rutas.py
python3 informe_ieee/generar_figuras.py
cd informe_ieee && pdflatex esert_ieee && bibtex esert_ieee && pdflatex esert_ieee && pdflatex esert_ieee
```

LaTeX no viene en la imagen del contenedor; se instaló con
`apt-get install texlive-latex-recommended texlive-publishers texlive-lang-spanish texlive-fonts-recommended texlive-latex-extra`.
`figuras/visor3d.png` es una captura del visor 3D con el servidor de prueba del visor.
