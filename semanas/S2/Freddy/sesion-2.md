---
semana: S2
persona: Freddy
sesion: 2
titulo: Máquina de estados y peatones que hacen diligencias
horas: 3-4
modulo: traci
depende: [S1-Freddy-3, S1-Pablo-3, S1-Tyrone-3]
entrega: [traci/estados.py, traci/peatones.py, traci/clasificacion.py, traci/tests/test_estados.py, traci/tests/test_peatones.py]
evidencias: [s2_linea-tiempo-sesion.png, s2_peaton-diligencia.png]
---
# S2 · Sesión 2 · Freddy 🍅: Máquina de estados y peatones que hacen diligencias

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (secciones 2 y 3). Trabaja sobre tu copia
`semanas/S2/Freddy/codigo/traci/` (cópiala de `proyecto/traci/` si no está). El escenario base
de Tyrone está en `proyecto/sumo/centro_base.sumocfg` y los destinos en
`proyecto/sumo/demanda/destinos.csv`. El clasificador de Pablo está en
`proyecto/ia/inferencia.py` (`clasificar(ventana) -> ResultadoModo`); si falta, usa la regla
de umbral del contrato en `traci/clasificacion.py` marcada `# MOCK`. **Aquí nace la falsa
liberación**: el conductor se baja, camina y el sistema no debe liberar el puesto.

## Objetivo
Que cada auto estacionado genere un peatón que hace una diligencia y vuelve, y que una
máquina de estados por usuario siga la sesión con las reglas del contrato usando el GPS
emulado y el clasificador.

## Pasos
1. Crea `traci/peatones.py` con `GestorPeatones(destinos_csv, semilla)` como *hook*
   `on_paso`:
   - detecta llegadas con `traci.simulation.getParkingStartingVehicleIDList()`;
   - **extiende la parada** para que el auto no se vaya solo:
     `traci.vehicle.setParkingAreaStop(veh, pa, duration=86400)` (guarda la duración
     original de la demanda como `t_estadia`);
   - crea el peatón `ped_<vehId>` con `traci.person.add(pid, edge_pa, pos_pa)`, luego
     `traci.person.appendWalkingStage(pid, ruta_ida, arrivalPos)` hacia el destino del auto
     (ruta con `traci.simulation.findRoute(..., vType="DEFAULT_PEDTYPE")`),
     `traci.person.appendWaitingStage(pid, duracion, "diligencia")` con
     `duracion = max(60, t_estadia − 2·t_caminata)` y otra `appendWalkingStage` de vuelta;
   - cuando el peatón llega de vuelta (desaparece de `traci.person.getIDList()`), llama a
     `traci.vehicle.resume(veh)`;
   - **casos difíciles** (parámetros con su valor por defecto): `p_regreso_corto=0.15`
     (vuelve al auto a buscar algo y se va otra vez) y `p_espera_en_auto=0.10` (se queda
     dentro: el modo es `quieto` a 0 m del puesto).
2. Crea `traci/clasificacion.py`: mantiene por agente un *buffer* circular de 30 s de
   `PuntoGPS` del `EmuladorGPS` de S1-3 (el del conductor: posición del auto si está
   dentro, la de `ped_<veh>` si camina) y cada 5 s llama a `clasificar(ventana)`.
3. Crea `traci/estados.py` con `MaquinaSesion` (una por usuario `sim_<veh>`) y los
   umbrales del contrato como parámetros: `dist_a_pie_m=15`, `dist_regreso_m=30`,
   `dist_salida_m=20`, `ventanas_vehiculo=2`.
   - `actualizar(modo, distancia_al_puesto_m, t_sim) -> list[Transicion]`, sin TraCI
     adentro (pura, para poder probarla);
   - registra cada transición en `traci/salidas/transiciones_<escenario>.csv`
     (`t_sim,usuario_id,desde,hacia,modo,distancia_m`);
   - al entrar a `CERRADA` comprueba `traci.vehicle.isStoppedParking(veh)`: si sigue
     estacionado, cuenta una **falsa liberación** (contador y CSV aparte).
4. Enchufa todo como *hooks* del `Controlador` (sin tocar su bucle) y corre 30 min del
   escenario base **en segundo plano**, con `--gui` opcional.
5. **Tests** (pytest, sin SUMO para la máquina de estados):
   - secuencia normal: estaciona → camina 200 m → vuelve → maneja → `CERRADA`;
   - conductor camina 200 m: nunca pasa a `CERRADA`;
   - auto en tráfico lento clasificado `a_pie` cerca del puesto: no hay falsa liberación;
   - una sola ventana `vehiculo` no basta para `SALIENDO`;
   - prueba con SUMO (`-m sumo`, 5 autos): todos los peatones vuelven y sus autos se van.
   Un subagente puede escribir los tests de `estados.py` mientras tú haces `peatones.py`.
6. **Evidencias:**
   - `s2_linea-tiempo-sesion.png`: para un usuario, estado en el tiempo (franjas de color),
     distancia al puesto y modo clasificado frente a `modo_real`;
   - `s2_peaton-diligencia.png`: captura de `sumo-gui` (`traci.gui.screenshot`) con un
     peatón caminando lejos de su auto estacionado, o su trayectoria en matplotlib.

## Dónde escribir
`semanas/S2/Freddy/codigo/traci/` y `semanas/S2/Freddy/evidencias/`.

## Hecho cuando
- [ ] `pytest traci/tests -m "not sumo"` y `pytest traci/tests -m sumo` pasan.
- [ ] En 30 min del escenario base, más del 95 % de los peatones vuelve a su auto y ningún
  auto queda estacionado para siempre.
- [ ] Las transiciones respetan las reglas y umbrales del contrato.
- [ ] Se reportan las falsas liberaciones por cada 100 sesiones con el clasificador usado.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 2, Freddy). En "Pedidos a
otros": @Pablo, la latencia medida de `clasificar` y los casos que más fallan; @Tyrone, que
los peatones `ped_*` ya salen en el snapshot.
