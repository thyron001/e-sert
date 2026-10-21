---
semana: S2
persona: Tyrone
sesion: 1
titulo: KPIs de la línea base - búsqueda, distancia, CO2 y ocupación
horas: 3-4
modulo: kpis
depende: [S1-Tyrone-3]
entrega: [kpis/kpis.py, kpis/lectores.py, kpis/tests/, kpis/salidas/kpis_base.json]
evidencias: [s1_kpis-base.png]
---
# S2 · Sesión 1 · Tyrone 🔵: KPIs de la línea base (búsqueda, distancia, CO₂ y ocupación)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección KPIs) y `docs/CONTRATO.md` (mensaje WS `kpi`).
Es la primera sesión de S2: copia `proyecto/sumo/` y `proyecto/kpis/` (si existe) a
`semanas/S2/Tyrone/codigo/` sin sobrescribir una copia previa. El escenario base unificado el
domingo 25 está en `proyecto/sumo/centro_base.sumocfg`. El cálculo provisional de S1-3 se
convierte aquí en un módulo formal: **los mismos números alimentarán el informe y el visor**.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.

## Objetivo
Un módulo `kpis/` que, a partir de las salidas XML de SUMO, calcule por vehículo y por
escenario el tiempo y la distancia de búsqueda, el CO₂ de búsqueda y la ocupación de los
puestos, con definiciones fijas y documentadas.

## Pasos
1. Si no hay salidas en `sumo/salidas/base_1/` y `base_2/`, lanza las 2 semillas **en segundo
   plano** (`sumo -c centro_base.sumocfg --seed N`, una por proceso) y vigílalas con
   `Monitor`. Añade a la configuración `--vehroute-output` con
   `--vehroute-output.exit-times true` y `--vehroute-output.route-length true`.
2. Crea `kpis/lectores.py` con lectores en *streaming* (`sumolib.xml.parse_fast` o
   `lxml.etree.iterparse` liberando nodos), uno por salida: `leer_tripinfo`,
   `leer_stops` (stop-output: `id`, `parkingArea`, `started`, `ended`),
   `leer_vehroutes` (*edges* con `exitTimes`) y `leer_emisiones` (emission-output por
   vehículo y periodo). Devuelven `pandas.DataFrame`.
3. Crea `kpis/kpis.py` con estas **definiciones** (escríbelas también en el docstring):
   - `inicio_busqueda`: primer instante en que el vehículo entra a un *edge* a menos de
     `--radio-busqueda-m` (300 m por defecto) del destino, o al *edge* de su `parkingArea`
     objetivo original, lo que ocurra primero.
   - `fin_busqueda`: `started` de su primera parada en un `parkingArea` (stop-output).
   - `tiempo_busqueda_s = fin − inicio`; `distancia_busqueda_m` = suma de longitudes de los
     *edges* recorridos entre ambos instantes (de `vehroute` con `exitTimes`).
   - `co2_busqueda_g`: integral del CO₂ del emission-output (mg/s × periodo de 10 s) en el
     intervalo de búsqueda.
   - `ocupacion(t)`: puestos ocupados / capacidad total cada 60 s, reconstruida con los
     intervalos `[started, ended)` del stop-output; promedio en la hora pico (excluye el
     *warm-up* de 15 min).
   - Excluye el tráfico de paso (vehículos sin parada en un `parkingArea`) y reporta cuántos.
   - CLI: `python -m kpis.kpis --salidas sumo/salidas/base_1 --escenario base --semilla 1`.
     Escribe `kpis/salidas/<escenario>_<semilla>_vehiculos.csv` y `kpis_<escenario>.json`
     con media, mediana, p90 y IC 95 % (*bootstrap*, 1000 remuestreos) de cada KPI, y las
     claves `busqueda_media_s` y `falsas_liberaciones_100` (`null` hasta S3) del contrato.
4. **Tests** (`kpis/tests/`, pytest) con XML sintéticos mínimos en `kpis/tests/datos/`:
   - un auto que encuentra lugar a la primera → búsqueda ≈ 0 s;
   - un auto que da una vuelta de 3 *edges* de 100 m → 300 m y el tiempo exacto;
   - ocupación de 2 puestos con intervalos solapados → serie esperada;
   - CO₂ con 3 periodos de 1000 mg/s → 30 g.
   Delega los tests y sus XML sintéticos en un subagente `general-purpose` mientras escribes
   `kpis.py`: solo comparten la firma de las funciones, fíjala antes.
5. Corre los KPIs sobre las 2 semillas y compara con el cálculo provisional de S1-3: si
   difieren más de 10 %, explica por qué en la bitácora.
6. **Evidencia** `evidencias/s1_kpis-base.png` (matplotlib, 2×2, `dpi=150`): histograma del
   tiempo de búsqueda, histograma de distancia, CO₂ de búsqueda por vehículo y ocupación en
   el tiempo con la banda 85–95 % sombreada; título con las medias de ambas semillas.

## Dónde escribir
`semanas/S2/Tyrone/codigo/kpis/`, `semanas/S2/Tyrone/codigo/sumo/` (solo la configuración de
salidas) y `semanas/S2/Tyrone/evidencias/`. Las salidas XML siguen en `.gitignore`.

## Hecho cuando
- [ ] `pytest kpis/tests` pasa completo.
- [ ] `python -m kpis.kpis` corre sobre las 2 semillas en menos de 2 min cada una.
- [ ] `kpis_base.json` tiene los 4 KPIs con media, mediana, p90 e IC 95 %.
- [ ] La ocupación media en la hora pico sigue entre 85 y 95 %.
- [ ] Las definiciones están escritas en el docstring de `kpis.py`.
- [ ] Existe la evidencia `s1_kpis-base.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 1, Tyrone). En "Pedidos a
otros": @Freddy, la definición de `inicio_busqueda` y los nombres de claves de
`kpis_base.json`, para que tu mensaje WS `kpi` use las mismas.
