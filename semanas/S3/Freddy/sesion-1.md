---
semana: S3
persona: Freddy
sesion: 1
titulo: KPIs de sistema - falsas liberaciones, retardo de cierre, facturación y mapa
horas: 3-4
modulo: traci
depende: [S2-Freddy-2, S2-Freddy-3, S2-Pablo-2]
entrega: [traci/kpis_sistema.py, traci/verdad.py, traci/tests/test_kpis_sistema.py, traci/salidas_kpi/ejemplo_p50_rf_s1.json]
evidencias: [s1_kpis-sistema.png]
---
# S3 · Sesión 1 · Freddy 🍅: KPIs de sistema (falsas liberaciones, retardo de cierre, facturación y mapa)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (KPIs) y `docs/CONTRATO.md` (secciones 3 y 6). Es la primera
sesión de S3: copia `proyecto/traci/`, `proyecto/backend/` (sin `pagos/` ni `asistente/`) y
`proyecto/comun/` a `semanas/S3/Freddy/codigo/` si no están. El modelo `rf_v1` se lee desde
`proyecto/ia/`. **Tyrone necesita esta pieza hoy mismo** (S3-Tyrone-1): publica pronto la
interfaz en tu rama, aunque los números se pulan después.

## Objetivo
Medir dentro de la simulación los cuatro KPIs que dependen del controlador y entregarlos con una
interfaz estable que el ejecutor de experimentos de Tyrone pueda llamar.

## Pasos
1. Crea `traci/verdad.py`, la "verdad de SUMO" por paso:
   - para cada vehículo con app, el estado físico de estacionamiento. Usa
     `traci.vehicle.subscribe(veh, [tc.VAR_STOPSTATE])` y el bit de *parking*
     (`(stopState & 2) != 0`) en lugar de llamar a `isStoppedParking` en cada paso; un test
     comprueba que ambos coinciden en una corrida corta;
   - `t_llegada_real` = primer paso estacionado y `t_salida_real` = primer paso en que deja de
     estarlo;
   - ocupación real por puesto con `traci.parkingarea.getVehicleCount(pa)` y, por separado,
     contando solo los vehículos con `param con_app = 1` (`getVehicleIDs` + filtro).
2. Crea `traci/kpis_sistema.py` con `KPIsSistema(controlador, nucleo, intervalo_mapa_s=60)`, que
   se registra como *hook* `on_paso` y escucha las transiciones de la máquina de estados:
   - **Falsa liberación:** en el paso en que una sesión pasa a `CERRADA`,
     `traci.vehicle.isStoppedParking(veh)` sigue en `True`. Se reporta
     `falsas_lib_100 = 100 · n_falsas / n_sesiones_cerradas` (solo vehículos con app).
   - **Retardo de cierre:** `t_cerrada − t_salida_real` en segundos, solo en cierres correctos;
     reporta mediana, p90 y máximo. Las sesiones sin cierre al final se cuentan aparte
     (`sin_cierre`).
   - **Error de facturación:** `minutos_reales = (t_salida_real − t_llegada_real)/60`;
     `error = debitado − tarifa.costo(minutos_reales)` con signo, más su valor absoluto medio.
     Compara también con `tarifa.costo_tarjeta_sert(minutos_reales)`: `ahorro = tarjeta − debitado`.
   - **Precisión del mapa:** cada 60 s simulados compara `MapaOcupacion` con la verdad, puesto
     por puesto: exactitud del estado libre/lleno (`libre = ocupados < capacidad`), MAE de
     ocupados y número de **libres fantasma** (libre en el mapa, lleno en la realidad). Calcula
     dos versiones: contra la ocupación total y contra la ocupación solo de usuarios con app.
     El mapa **solo conoce a los usuarios de la app**: que la primera sea baja con 20 % es un
     hallazgo esperado, no un error; la segunda debe estar cerca de 1,0.
3. Interfaz para Tyrone (no la cambies sin avisar):
   - `resumen() -> dict` con `falsas_lib_100, n_sesiones, n_falsas, sin_cierre,
     retardo_cierre_mediana_s, retardo_cierre_p90_s, error_fact_medio_usd, error_fact_abs_max_usd,
     ahorro_vs_tarjeta_medio_usd, precision_mapa, precision_mapa_app, libres_fantasma_medio`;
   - `detalle_sesiones() -> pandas.DataFrame` (una fila por sesión) y `serie_mapa() -> DataFrame`.
4. Publica los valores por WS como `{"tipo": "kpi"}` cada 10 s simulados y la verdad como
   `{"tipo": "verdad"}` (solo en simulación, nunca para la app), según tu contrato v1.
5. **Tests** (`traci/tests/test_kpis_sistema.py`) con un `traci` falso para los casos unitarios:
   - cierre mientras sigue estacionado → 1 falsa liberación;
   - cierre 12 s después de salir → retardo 12 s y 0 falsas;
   - estadía de 47 min cobrada por el núcleo → error 0;
   - 4 puestos, el mapa conoce 2 de 3 ocupados → exactitud y MAE calculados a mano;
   - integración: `p50_rf_s1` durante 900 s simulados escribe
     `traci/salidas_kpi/ejemplo_p50_rf_s1.json` con todas las claves.
6. Mide el costo: con `KPIsSistema` activo el tiempo por paso no debe subir más de 15 %.
7. Paraleliza: un subagente escribe los tests unitarios con el `traci` falso mientras tú
   implementas; la corrida de integración va en segundo plano vigilada con `Monitor`.
8. **Evidencia** `evidencias/s1_kpis-sistema.png`, 2 × 2: falsas /100 umbral vs rf (p50, s1);
   histograma del retardo de cierre; debitado vs costo ideal y vs tarjeta SERT; serie temporal
   de la precisión del mapa (total y solo app).

## Dónde escribir
`semanas/S3/Freddy/codigo/traci/` y `evidencias/`.

## Hecho cuando
- [ ] `pytest traci/tests/test_kpis_sistema.py` pasa, incluido el test de equivalencia con
  `isStoppedParking`.
- [ ] El JSON de ejemplo tiene todas las claves de `resumen()` y ningún `NaN` inesperado.
- [ ] La precisión solo con usuarios de app es ≥ 0,95 en la corrida de ejemplo.
- [ ] El sobrecosto por paso es menor que 15 %.
- [ ] Existe `s1_kpis-sistema.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 1, Freddy). En "Pedidos a otros":
@Tyrone, ruta, firma y claves de `KPIsSistema.resumen()`; @Pablo, cifra de falsas liberaciones
con umbral y rf para tu análisis de suavizado.
