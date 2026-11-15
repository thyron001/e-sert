# Video de respaldo crudo (S4-2)

Los videos **no van en git**: el `.gitignore` de esta carpeta deja pasar solo este archivo.

| Pieza | Ubicación | Duración | Notas |
|---|---|---|---|
| Laptop (grabación de pantalla de macOS, Cmd+Shift+5; OBS no estaba instalado) | Mac de Miguel: `~/Downloads/Grabación de pantalla 2026-11-14 a la(s) 11.17.14 p. m..mov` | 7 min 22 s (441,6 s), 2940×1912 | Ensayo B (local), corrida `--ritmo 5 --hasta 1800`. sumo-gui por VNC y el visor con `sim_busca_4` resaltado (halo amarillo) |
| Teléfono (grabación de pantalla de Android) | en el teléfono de Miguel; pendiente de pasar a la Mac | — | Empieza con la misma palmada |
| Combinado | `plan_b/crudo/ensayo_combinado.mp4` (por generar) | — | ver el comando abajo |

**Combinar** (escalar a 1080 de alto y poner lado a lado; `-ss` es el desfase de la palmada):

```bash
ffmpeg -i laptop.mov -ss <desfase_s> -i telefono.mp4 \
  -filter_complex "[0:v]scale=-2:1080[l];[1:v]scale=-2:1080[t];[l][t]hstack" \
  -r 30 -c:v libx264 -crf 23 plan_b/crudo/ensayo_combinado.mp4
```

**Desfase de sincronización:** pendiente. Se mide como la diferencia entre la palmada en los dos videos.

La edición final, los subtítulos y el enlace son de S4-3.
