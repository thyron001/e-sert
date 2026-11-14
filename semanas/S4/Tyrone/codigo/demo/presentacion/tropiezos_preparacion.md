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
