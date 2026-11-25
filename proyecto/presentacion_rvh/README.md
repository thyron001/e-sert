# Presentaciones

| Archivo | Qué es |
|---|---|
| `presentacion.html` | **Propuesta para la DGM** (5 min, 25-nov-2026), publicada como artefacto en claude.ai. Necesita los archivos de `dgm/` publicados junto a ella (`js/`, `datos/`, `img/`). |
| `e-sert_dgm.html` | La misma propuesta en un solo archivo (datos e imágenes incrustados), para abrir desde el disco. Se regenera con `python3 armar_independiente.py`. |
| `presentacion_examen.html` | Exposición del Examen Interciclo de RVH (10 min, un color por orador). |
| `guion_tyrone.md`, `guion_tyrone.mp3` | Lo que dice Tyrone en la exposición del interciclo, en texto y en audio. |

La diapositiva 3 de la propuesta es el visor 3D de e-sert (`dgm/js/vista3d.js`, copia de `visor/js/vista3d.js`)
reproduciendo en bucle un minuto grabado de la simulación (`dgm/datos/repeticion.json`, de
`visor/datos/snapshots_muestra.jsonl`), con un popup que explica qué es e-sert y un botón al visor en vivo.

Teclas: flechas para avanzar, **N** notas, **E** explicación, **F** pantalla completa, **R** cronómetro.
