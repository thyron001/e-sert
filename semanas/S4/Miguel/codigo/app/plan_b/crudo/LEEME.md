# Video de respaldo crudo (S4-2)

Los videos **no van en git**: el `.gitignore` de esta carpeta deja pasar solo este archivo.

| Pieza | Ubicación | Duración | Notas |
|---|---|---|---|
| Laptop (grabación de pantalla de macOS, Cmd+Shift+5; OBS no estaba instalado) | Mac de Miguel: `~/Downloads/Grabación de pantalla 2026-11-14 a la(s) 11.17.14 p. m..mov` | 7 min 22 s (441,6 s), 2940×1912 | Ensayo B (local), corrida `--ritmo 5 --hasta 1800`. sumo-gui por VNC y el visor con `sim_busca_4` resaltado (halo amarillo) |
| Laptop, corrida 3 | `~/Downloads/Grabación de pantalla 2026-11-14 a la(s) 11.35.19 p. m..mov` | 4 min 58 s, 2940×1912 | `--ritmo 1 --hasta 240` |
| Teléfono (grabación de Android, enviada por WhatsApp) | `~/Downloads/WhatsApp Video 2026-11-14 at 23.42.08.mp4` | 4 min 48 s, 480×1068 | WhatsApp la recomprimió (baja resolución) |
| Combinado | `plan_b/crudo/ensayo_combinado.mp4` (Mac de Miguel, fuera de git) | ~4 min 48 s, 1080 de alto | laptop desde el s 10 + teléfono; fotograma en `evidencias/s2_ensayo-montaje.png` |

**Combinar** (escalar a 1080 de alto y poner lado a lado; `-ss` es el desfase de la palmada):

```bash
ffmpeg -i laptop.mov -ss <desfase_s> -i telefono.mp4 \
  -filter_complex "[0:v]scale=-2:1080[l];[1:v]scale=-2:1080[t];[l][t]hstack" \
  -r 30 -c:v libx264 -crf 23 plan_b/crudo/ensayo_combinado.mp4
```

**Desfase de sincronización:** ~10 s (el teléfono empezó a grabar ~10 s después que la laptop). En el fotograma, los relojes de los dos marcan 23:37 y el `t_sim` coincide (112 s en el visor frente a 01:45 en el teléfono, con ~7 s de diferencia). Para S4-3 conviene afinarlo con la palmada y pedir el video original del teléfono, sin WhatsApp.

La edición final, los subtítulos y el enlace son de S4-3.
