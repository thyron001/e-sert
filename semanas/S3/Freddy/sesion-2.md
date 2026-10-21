---
semana: S3
persona: Freddy
sesion: 2
titulo: Rendimiento y robustez - pérdida de GPS, teléfono apagado y 80 % de penetración
horas: 3-4
modulo: traci
depende: [S3-Freddy-1, S3-Pablo-1]
entrega: [traci/perfil.py, traci/robustez.py, traci/salidas_kpi/robustez.csv, traci/tests/test_robustez.py, backend/tests/test_carga.py, comun/CONTRATO.propuesto.md]
evidencias: [s2_rendimiento-80.png, s2_robustez-perdida-gps.png]
---
# S3 · Sesión 2 · Freddy 🍅: Rendimiento y robustez (pérdida de GPS, teléfono apagado y 80 % de penetración)

## Contexto
Lee `CLAUDE.md`, tu bitácora de S3-1 y `docs/CONTRATO.md` (sección 3). Tyrone corre 24
corridas con tu controlador y la de 80 % es la más pesada. Todo es simulado: la pérdida de señal en
las calles estrechas del Centro se emula en el `EmuladorGPS`, y el "teléfono apagado" es un usuario
simulado que deja de reportar. La inferencia robusta de Pablo (S3-1,
`clasificar_lote` y *fallback*) se lee de `origin/pablo/s3:semanas/S3/Pablo/codigo/ia/inferencia.py`;
si no existe, usa la de `proyecto/ia/` y un `clasificar_lote` mock marcado
`# MOCK: reemplazar cuando Pablo entregue clasificar_lote (S3-1)`.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.
- El controlador TraCI corre en el contenedor, junto a SUMO, y el backend en la computadora
  (`--host 0.0.0.0`). Desde el contenedor, la URL del backend usa `host.docker.internal` o la
  puerta de enlace, como explica `CLAUDE.md`.

## Objetivo
Saber cuánto cuesta cada paso con 80 % de usuarios, dejarlo rápido, y demostrar que el sistema no
libera puestos por error cuando el GPS falla o el teléfono se apaga.

## Pasos
1. **Perfil** (`traci/perfil.py`) con `p80_rf_s1` durante 1 800 s simulados:
   - `cProfile` más cronómetros `time.perf_counter()` por bloque: `simulationStep`, lectura de
     suscripciones, GPS, inferencia, máquina de estados, núcleo y WS;
   - reporta ms por paso (media y p95) y el **factor de tiempo real** (s simulados / s reales).
   - Metas sin GUI: factor ≥ 10 y p95 del paso < 100 ms.
2. **Optimiza** solo lo que el perfil señale, midiendo antes y después:
   - `traci.simulation.getDepartedIDList()` y `getArrivedIDList()` en lugar de `getIDList()` cada paso;
   - suscripciones para todo lo que se lea por vehículo;
   - inferir solo cada 5 s por usuario (paso de ventana del contrato) y en lote con `clasificar_lote`;
   - núcleo en `sqlite:///:memory:` con una transacción por paso;
   - opción `--libsumo` (`import libsumo as traci`) cuando no hay GUI; compara su factor con el de
     `traci`. Funciona con un proceso por corrida, como el ejecutor de Tyrone.
3. **Robustez del GPS** (`traci/robustez.py`) a 50 % de penetración, con umbral y rf:
   - pérdida independiente `p_perdida` ∈ {0,02; 0,10; 0,30};
   - ráfagas de pérdida tipo Gilbert-Elliott (cañón urbano) de 30, 60 y 120 s;
   - ruido `sigma_m` ∈ {5, 15, 30} m (multitrayecto).
   - Mide falsas liberaciones /100 y retardo de cierre con `KPIsSistema`. Corre la rejilla en
     paralelo con `multiprocessing` (contexto `spawn`, 2 semillas, 1 800 s cada corrida), en segundo
     plano, y vigílala con `/loop 5m cuenta las filas de traci/salidas_kpi/robustez.csv`.
4. **Política ante datos pobres** en la máquina de estados: si la ventana tiene menos del 50 % de
   las muestras esperadas, o la inferencia usó *fallback* con confianza < 0,5, **no hay
   transición**: se mantiene el estado. Test: con 30 % de pérdida en ráfagas no aparece ninguna
   falsa liberación nueva atribuible a ventanas incompletas.
5. **Teléfono apagado** (usuario simulado que deja de reportar): en el 10 % de las sesiones el
   emulador deja de emitir puntos GPS del usuario en `A_PIE`.
   - El silencio **nunca** cierra la sesión: el puesto sigue ocupado. Tras 120 s sin datos la
     sesión se marca `sin_senal`.
   - Si el auto se va sin teléfono, la sesión se cierra al llegar al tope (`tiempo_maximo_min`)
     con un motivo nuevo `timeout_sin_senal`. Proponlo en `comun/CONTRATO.propuesto.md` (hoy el
     contrato solo admite `deteccion` y `manual`).
   - Mide cuántas sesiones terminan así y su error de facturación; documéntalo como limitación.
6. **Carga del backend** (`backend/tests/test_carga.py`, marca `@pytest.mark.carga`, excluida por
   defecto): `httpx.AsyncClient` con 200 usuarios enviando `POST /eventos/ubicacion` a 1 Hz durante
   60 s. Meta: p95 < 50 ms y 0 respuestas 5xx; 5 clientes WS reciben snapshots a ≤ 1 Hz sin cola
   creciente.
7. **Tests** (`traci/tests/test_robustez.py`): el teléfono apagado no produce falsas liberaciones;
   la política de datos pobres retiene el estado; `--libsumo` y `traci` dan los mismos KPIs con la
   misma semilla.
8. **Evidencias:**
   - `evidencias/s2_rendimiento-80.png`: barras apiladas de ms por paso por bloque, antes y
     después de optimizar, con el factor de tiempo real en el título;
   - `evidencias/s2_robustez-perdida-gps.png`: falsas /100 vs `p_perdida` y vs duración de ráfaga,
     umbral y rf, con IC 95 % entre semillas.

## Dónde escribir
`semanas/S3/Freddy/codigo/traci/`, `semanas/S3/Freddy/codigo/backend/tests/`,
`semanas/S3/Freddy/codigo/comun/CONTRATO.propuesto.md` y `evidencias/`.

## Hecho cuando
- [ ] El perfil de 80 % reporta factor de tiempo real y p95 por paso, y se cumplen las metas o
  se documenta por qué no.
- [ ] `robustez.csv` tiene la rejilla completa con las dos semillas.
- [ ] `pytest traci/tests/test_robustez.py` pasa y `pytest -m carga backend/tests` cumple p95 < 50 ms.
- [ ] El motivo `timeout_sin_senal` está propuesto en `CONTRATO.propuesto.md`.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 2, Freddy). En "Pedidos a otros":
@Tyrone, si `--libsumo` acelera, úsalo en el ejecutor; @Pablo, la tasa de *fallback* observada;
@Miguel, el nuevo motivo `timeout_sin_senal` aparece en el recibo.
