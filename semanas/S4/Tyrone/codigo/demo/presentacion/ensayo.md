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

## Ensayos desde arranque en frío

Cada ensayo corre `python demo/presentacion/ensayo.py --vuelta N`: lanza `demo.py --local --cronometro` (con `sumo-gui`, `--ritmo 10`), sigue por `/ws/espejo` a un auto como hace la app de Miguel en modo espejo, abre el visor con `?espejo=<veh>` en Chromium y comprueba el halo, espera una sesión `CERRADA` con recibo y apaga con Ctrl+C. Los datos están en `ensayos/ensayo_<n>.json`.

| Ensayo | Fecha | Arranque (s) | Demo guiada (s) | Apagado (s) | Recibo | Halo en el visor | Tropiezos |
|---|---|---:|---:|---:|---|---|---|
| Presupuesto | — | 60 | 300 | 15 | — | — | — |
| 1 (graba plan B) | 2026-11-13 20:57 | 11,3 | 280,2 | 1,8 | `sim_busca_18`: 14,2 min, cobrado 0,13 USD (tarjeta SERT 0,25 USD) | sí (20 puntos de ruta, puesto `pa_49222376_0`) | 0 |
| 2 | 2026-11-13 21:02 | 9,8 | 156,4 | 1,2 | `sim_busca_18`: 14,2 min, cobrado 0,13 USD (tarjeta SERT 0,25 USD) | sí (20 puntos de ruta, puesto `pa_49222376_0`) | 0 |

### Ensayo 1

Arranque por componente: backend 3,3 s, controlador con `sumo-gui` 7,1 s, visor 0,3 s. Limpieza tras Ctrl+C: puertos libres = True, `sumo-gui` vivos = 0.

- `11.3 s`: demo lista (tabla de arranque)
- `14.4 s`: el teléfono espejo sigue a sim_busca_0 (destino San Sebastián, GUIADO)
- `21.7 s`: visor: halo del espejo visible, ruta 20 puntos, puesto pa_49222376_0
- `33.7 s`: el teléfono espejo sigue a sim_busca_18 (vuelve a su auto, t_sim = 204.0)
- `59.3 s`: el teléfono espejo sigue a sim_busca_30 (vuelve a su auto, t_sim = 455.0)
- `63.4 s`: el teléfono espejo sigue a sim_busca_77 (vuelve a su auto, t_sim = 494.0)
- `70.0 s`: el teléfono espejo sigue a sim_busca_85 (vuelve a su auto, t_sim = 547.0)
- `70.1 s`: el teléfono espejo sigue a sim_busca_37 (vuelve a su auto, t_sim = 548.0)
- `163.9 s`: sesión de sim_busca_18 CERRADA con recibo: cobrado $0.13 (tarjeta SERT $0.25)
- `291.4 s`: grabación del plan B: 3159 mensajes en snapshots_demo.jsonl
- Grabación del plan B: 3159 mensajes WS → `demo/plan_b/snapshots_demo.jsonl.gz`.
- Tropiezos detectados por el script: ninguno.

### Ensayo 2

Arranque por componente: backend 3,3 s, controlador con `sumo-gui` 5,8 s, visor 0,3 s. Limpieza tras Ctrl+C: puertos libres = True, `sumo-gui` vivos = 0.

- `9.8 s`: demo lista (tabla de arranque)
- `12.9 s`: el teléfono espejo sigue a sim_busca_0 (destino San Sebastián, GUIADO)
- `19.2 s`: visor: halo del espejo visible, ruta 20 puntos, puesto pa_49222376_0
- `32.1 s`: el teléfono espejo sigue a sim_busca_18 (vuelve a su auto, t_sim = 204.0)
- `57.7 s`: el teléfono espejo sigue a sim_busca_30 (vuelve a su auto, t_sim = 455.0)
- `61.9 s`: el teléfono espejo sigue a sim_busca_77 (vuelve a su auto, t_sim = 494.0)
- `68.5 s`: el teléfono espejo sigue a sim_busca_85 (vuelve a su auto, t_sim = 547.0)
- `68.6 s`: el teléfono espejo sigue a sim_busca_37 (vuelve a su auto, t_sim = 548.0)
- `165.3 s`: sesión de sim_busca_18 CERRADA con recibo: cobrado $0.13 (tarjeta SERT $0.25)
- Tropiezos detectados por el script: ninguno.

## Tropiezos de la preparación (antes de los dos ensayos)

| Tropiezo | Causa | Corrección |
|---|---|---|
| Ninguna sesión cerraba en los 120 s de `verificar_demo.py` ni en una demo de 5 min | La primera sesión de `p50_rf_s1` cierra en t = 1 223 s, y el controlador no pasa de ~7× el tiempo real | El escenario de la demo pasa a la semilla 2 (primera sesión cerrada en t = 1 014 s, según `kpis/resultados/final/sesiones/`). Sin GUI se usa libsumo (`--libsumo`, ~9×). En vivo, `ritmo: 2` en `config_demo.yaml`, para que haya cierres durante los 5 min de demo |
| Tras Ctrl+C quedaba vivo el controlador dentro del contenedor (modo sin GUI) | El patrón `--subdir demo_<sello>` empieza con guiones: `pkill`/`pgrep` lo leían como una opción y no mataban nada. Con GUI no se notaba porque el controlador terminaba al cerrarse `sumo-gui` | El patrón pasa a ser `subdir demo_<sello>` |
| `verificar_demo.py` no encontraba recibos | Seguía a los primeros 25 candidatos (autos buscando), que tardan más de 10 min simulados en cerrar. Seguir a 113 autos a la vez frenaba al controlador | Sigue a pocos candidatos y a los autos cuyo conductor ya vuelve (`REGRESANDO`/`SALIENDO`). Toma el saldo previo del último mensaje antes del recibo |
| La grabación del plan B pesaba 136 MB | 1 505 snapshots completos más `verdad` y `kpi` | Se versiona comprimida (`snapshots_demo.jsonl.gz`, 14 MB); `servidor_prueba` lee `.gz` |
| `captura.py --url http://localhost:8765/` daba 404 | Barra doble en la URL de candidatos | `rstrip("/")` |
| Marp se cerraba con `TargetCloseError` | Chromium sin *sandbox* en Linux | `CHROME_NO_SANDBOX=1` (y `CHROME_PATH` al Chromium de Playwright) |

**Lo que no se pudo ensayar en esta máquina:**
- **El teléfono físico de Miguel.** El "teléfono" del ensayo es un cliente de `/ws/espejo`, el mismo canal que usa la app.
- **El proyector.**
- **Windows/PowerShell.**

Queda en `checklist_entrega.md` hacerlo el lunes antes de la clase.

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
