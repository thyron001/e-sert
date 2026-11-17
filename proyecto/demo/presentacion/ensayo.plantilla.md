# Ensayo de la presentación y de la demo

## Herramientas y versiones

- **Diapositivas:** `@marp-team/marp-cli@4.2.3` (versión fija), Node 20.19.5.
  ```bash
  cd semanas/S4/Tyrone/codigo/demo/presentacion
  python generar_diapositivas.py            # diapositivas.md desde resumen.csv
  CHROME_NO_SANDBOX=1 npx -y @marp-team/marp-cli@4.2.3 diapositivas.md --pdf --allow-local-files
  ```
  `CHROME_NO_SANDBOX=1` hace falta en Linux sin el *sandbox* de Chromium. Si Marp no encuentra un
  navegador, se le pasa `CHROME_PATH=<ruta a chrome>`.
- **Demo:** `python demo/demo.py --cronometro` (backend de Freddy, controlador con `sumo-gui` en
  el contenedor `van3twin` y visor). Ensayos automatizados con `demo/presentacion/ensayo.py`.
- **Duración prevista:** 20 min (15 de exposición + 5 de demo), según `guion.md`.

## Presupuesto de tiempo de la demo

| Fase | Presupuesto | Qué incluye |
|---|---:|---|
| Arranque | 60 s | `demo.py` hasta la tabla de arranque (backend, SUMO con GUI y visor listos) |
| Demo guiada | 300 s | un auto buscando, el teléfono espejo siguiéndolo, halo en el visor, sesión `CERRADA` con recibo |
| Apagado | 15 s | Ctrl+C hasta puertos libres y sin `sumo-gui` en el contenedor |

ENSAYOS

**Diferencias con la demo en vivo:**
- **Ritmo:** los ensayos corren a `--ritmo 10` para caber en 5 min. En vivo, `config_demo.yaml` usa
  `ritmo: 2`, lanzando la demo al empezar la exposición, así que el tiempo de la demo en vivo no se
  midió aquí.
- **Fin de la fase "demo guiada":**
  - en el ensayo 1 termina cuando acaba la grabación del plan B (280 s), aunque el recibo llegó antes;
  - en el ensayo 2 termina con el recibo.
- **Logs:** los `tiempos.json` de `demo/logs/` no se versionan (`.gitignore`); sus cifras están en
  `ensayos/ensayo_<n>.json`.

## Plan B escalonado

Se aplica de arriba abajo, sin detener la exposición. Quien presenta (Tyrone) anuncia el cambio
en una frase y sigue el guion.

1. **Falla `sumo-gui`** (no abre, se congela o el VNC no se ve):
   - Ctrl+C y `python demo/demo.py --sin-gui`, que arranca en ≈15 s;
   - se muestra solo el visor en el proyector (modo presentación `P`, recorrido `T`);
   - el teléfono espejo funciona igual, porque depende del backend y no de la GUI.
2. **Falla el backend o la red** (el visor no conecta, o el teléfono no llega al backend):
   - se reproduce la grabación del primer ensayo en el visor:
     ```bash
     cd semanas/S4/Tyrone/codigo
     visor/.venv/bin/python -m visor.servidor_prueba --snapshots demo/plan_b/snapshots_demo.jsonl.gz --puerto 8765
     # abrir http://localhost:8765/  (el visor ya apunta a ese WS)
     ```
   - el visor muestra los autos, los puestos y el panel de KPIs de la grabación. El vehículo
     espejo sale de la lista `espejos` grabada.
3. **Falla todo** (laptop o proyector):
   - se reproduce el video de respaldo de Miguel desde el USB o desde el enlace de
     `app/plan_b/ENLACE_VIDEO.md` (rama `miguel/s4`);
   - mientras no exista, se usa la grabación de pantalla del ensayo 2, en el USB.

## Antes de presentar

Ver `checklist_entrega.md`.
