# Ensayo de la demo, lado backend y controlador (Freddy, S4-3)

**Fecha:** 2026-11-13.
**Script:** `python comun/docs/ensayo_demo_freddy.py`, desde la carpeta con `backend/`, `comun/` y `traci/`.
**Resultados en bruto:** `comun/docs/ensayo/` (`resultados.json`, `eventos.jsonl` y los logs del backend y del controlador).

## Cómo se ensayó

**La demo de Tyrone (`demo/`) no estaba publicada:** no existe `origin/tyrone/s4`, ni la
carpeta `demo/` en ninguna rama. Por eso la demo se levantó como la describe
`docs/DESPLIEGUE.md`, que es el lanzamiento que tendrá que hacer `demo/`:

- **Backend:** `uvicorn backend.api.main:app --host 0.0.0.0` en la computadora, como un proceso
  real.
  - Base SQLite en un archivo, token del simulador y el visor de Tyrone (`proyecto/visor`) servido
    en `/visor`.
- **Controlador:** `traci.correr_kpis --id p50_rf_s1 --hasta 1500 --ritmo 5 --publicar
  http://<host>:<puerto>`, dentro de `van3twin` con `docker exec`.
  - `--ritmo 5` acorta el ensayo y mantiene el mismo flujo; la demo usará `--ritmo 1`.
- **Visor:** un cliente `/ws/estado?rol=visor` que se reconecta solo, y una captura real de
  `/visor` con Chromium headless (Playwright 1.47.0) dentro del contenedor.
- **Teléfono espejo:** un cliente de `GET /espejo/candidatos` y `/ws/espejo/{veh_id}`.

## Resultados

| # | Prueba | Resultado | Causa | Arreglo | Responsable |
|---|---|---|---|---|---|
| 1 | Arranque en frío y tiempo hasta el primer `snapshot` | ✅ Backend listo en **1,41 s**; primer snapshot en el visor **3,89 s** después de lanzar el controlador | — | — | — |
| 2 | Reiniciar el backend a mitad de la demo (SIGTERM y arranque 5 s después, mismo puerto y misma base) | ✅ El **controlador no se cae**: el publicador descarta los envíos fallidos y sigue. El visor se reconecta y los snapshots vuelven **7,17 s** después del corte | — (comportamiento esperado: cola de tamaño 1, la simulación nunca espera a la red) | — | — |
| 3 | El teléfono espejo pierde el WS y se reconecta | ✅ Se cortó con la sesión abierta y se reconectó 3 s después al **mismo vehículo** (`sim_busca_0`), con la **misma `sesion_id`**. La sesión siguió hasta `CERRADA` y llegó **1 recibo**, sin duplicarse | — | — | — |
| 4 | 80 % de penetración con `sumo-gui` (600 s simulados) | ✅ **35,9 ms/paso** con GUI frente a **25,6 ms/paso** sin GUI. A `--ritmo 1` sobra margen (necesita < 1 000 ms). Captura de `sumo-gui` en t = 450 s | — | Nuevas opciones `--gui` y `--captura RUTA@T` en `correr_kpis` | Freddy |
| 5a | **Ctrl+C** al lanzador del controlador (`docker exec` sin TTY) | ❌ en el primer ensayo: **siguieron vivos `python3 -m traci.correr_kpis` y `sumo`** en el contenedor | `docker exec` sin TTY **no reenvía** la señal al proceso del contenedor. Un lanzador que muere deja la simulación corriendo y publicando | Nueva opción `--vigilar-stdin` en `traci/correr_kpis.py`, lanzando con `docker exec -i`. Al morir el cliente se cierra stdin, y la corrida se detiene **entre dos pasos** y cierra TraCI y SUMO. Salida limpia: código 130, sin traza | Freddy (arreglado); Tyrone (usarlo en `demo/`) |
| 5a′ | Repetición con el arreglo | ✅ **No quedan procesos** 3 s después del Ctrl+C | — | — | — |
| 5b | Ctrl+C al backend | ✅ uvicorn se detiene en **0,33–0,37 s** y el puerto queda libre (nadie escucha y se puede volver a abrir) | En el primer ensayo la comprobación dio «ocupado» por error: hacía `bind` sin `SO_REUSEADDR` y chocaba con conexiones en `TIME_WAIT`. uvicorn sí usa esa opción; la prueba 2 reabrió el mismo puerto | Comprobación corregida en el script del ensayo | Freddy |

**Tiempos medidos:**

| Medida | Valor |
|---|---:|
| Arranque del backend hasta `/salud` | 1,41 s (frío) y 1,32 s (reinicio) |
| Lanzamiento del controlador hasta el primer snapshot | 3,89 s |
| Corte del backend hasta el primer snapshot de nuevo | 7,17 s (incluye la espera de 5 s antes de rearrancar) |
| Snapshots recibidos por el visor en el ensayo | 1 260 |
| Corte y reconexión del teléfono espejo | 3 s; 151 mensajes `espejo` después de reconectar |
| Controlador, p80, 600 s simulados | 25,6 ms/paso sin GUI y 35,9 ms/paso con `sumo-gui` |
| Ctrl+C dentro del contenedor hasta que no quedan procesos | 1,07 s |

## Arreglos hechos en mi código

1. **`traci/correr_kpis.py`, `--vigilar-stdin`:** pide detener la corrida cuando se cierra stdin. Ahora `Ctrl+C` a un `docker exec -i` cierra también SUMO.
2. **`traci/correr_kpis.py`, detención entre pasos:** ni Ctrl+C ni el cierre de stdin interrumpen el paso en curso. Activan una marca que un *hook* revisa entre pasos, y la corrida termina con `corrida detenida en t=… s; TraCI y SUMO cerrados` (código 130). Un segundo Ctrl+C sí interrumpe de inmediato.
   - La primera versión se mandaba SIGINT a sí misma y se descartó: la señal caía en medio de un `recv` de TraCI, el `close()` fallaba con `struct.error` y SUMO terminaba con `malloc_consolidate`. Los procesos no quedaban vivos, pero la salida era sucia (código 1).
   - Comprobado con `(sleep 15; echo) | docker exec -i … --vigilar-stdin`: código 130, sin traza y sin procesos.
3. **`traci/correr_kpis.py`, `--gui` y `--captura RUTA@T`:** abren `sumo-gui` en la pantalla `:99` y guardan una captura (`traci.gui.screenshot`).
4. **`backend/tests/test_espejo.py`, prueba intermitente:** la prueba del ritmo de 1 Hz medía las pausas en el cliente y fallaba más o menos 1 de cada 20 veces con la CPU cargada. Ahora tolera el corrimiento de un mensaje y sigue exigiendo 1 Hz: cada pausa ≥ 0,5 s y cada par de pausas seguidas ≥ 1,9 s.

`pytest -m e2e` se volvió a correr tras los arreglos. Pasan 30 de 32; las 2 que fallan son las de
cero falsas liberaciones, por el clasificador (S4-1), y no por estos cambios.

## Pedidos a Tyrone para `demo/`

- **Lanzar el controlador con `docker exec -i … python3 -m traci.correr_kpis … --vigilar-stdin`**, o con `-it` si es una terminal interactiva. Si no, un Ctrl+C del lanzador deja `sumo` y el controlador vivos, publicando en el backend.
  - Para reproducirlo: lanzar `docker exec van3twin bash -lc "python3 -m traci.correr_kpis --id p50_rf_s1 --hasta 1500 --ritmo 5"` desde un `subprocess.Popen`, enviarle SIGINT y correr `docker exec van3twin pgrep -af "traci.correr_kpis|sumo"`.
- **Reinicio del backend:** el registro del modo espejo vive en memoria. Tras reiniciar, `GET /espejo/candidatos` se vuelve a llenar con el siguiente snapshot, y un teléfono que estaba siguiendo un vehículo tiene que volver a conectarse. El ensayo cortó el teléfono **antes** del reinicio; queda sin ensayar la reconexión a través de un reinicio.
- **Publicar `demo/`** para repetir este ensayo sobre el lanzador real.

## Evidencia

`semanas/S4/Freddy/evidencias/s3_ensayo-demo-freddy.png` contiene la línea de tiempo de los
eventos, con los incidentes en rojo y la repetición de Ctrl+C con el arreglo, y la captura del
visor durante la demo. Se regenera con `python -m comun.docs.grafica_ensayo <salida.png>`.
