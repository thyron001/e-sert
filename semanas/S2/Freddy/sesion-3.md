---
semana: S2
persona: Freddy
sesion: 3
titulo: Guiado con rerouteParkingArea, sesiones y cobro en la simulación
horas: 3-4
modulo: traci
depende: [S2-Freddy-1, S2-Freddy-2, S1-Tyrone-3]
entrega: [traci/guiado.py, traci/puente_nucleo.py, traci/tests/test_guiado.py, traci/salidas/sesiones_app50_s1.csv]
evidencias: [s3_guiado-vs-ciegas.png, s3_cobros-simulados.png]
---
# S2 · Sesión 3 · Freddy 🍅: Guiado con `rerouteParkingArea`, sesiones y cobro en la simulación

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro; "el guiado usa la ocupación actual")
y `docs/CONTRATO.md` (sección 3). Tyrone prepara hoy los escenarios con `--porc-app`
(S2-3); léelos de `origin/tyrone/s2` sin editar y, si no están, genera un mock con
`generar_demanda.py` de `proyecto/sumo/` poniendo `con_app=1` al 50 % (marcado `# MOCK`).
En experimentos **el controlador importa `backend/nucleo/` directamente** (sin HTTP), y los
autos simulados nunca llaman a Payphone.

## Objetivo
Cerrar el ciclo en la simulación: los autos con app se guían al puesto libre más cercano a
su destino, abren sesión al llegar, cobran al salir y el libro de la billetera cuadra.

## Pasos
1. Crea `traci/puente_nucleo.py`: instancia `Billetera`, `ServicioSesiones` y
   `MapaOcupacion` sobre `sqlite:///:memory:` y carga `puestos.csv`. A cada usuario simulado
   `sim_<veh>` le hace una recarga inicial `U(5, 20)` USD con la semilla del escenario.
   Opcional `--publicar http://localhost:8000` para empujar snapshots al backend vivo.
2. Crea `traci/guiado.py` con `Guia(fuente_ocupacion="mapa", max_reasignaciones=3,
   periodo_revision_s=10)` como *hook*:
   - en `traci.simulation.getDepartedIDList()`, si
     `traci.vehicle.getParameter(veh, "con_app") == "1"`, estado `BUSCANDO` →
     `MapaOcupacion.recomendar(destino)` → `GUIADO` y
     `traci.vehicle.rerouteParkingArea(veh, puesto_id)`;
   - `fuente_ocupacion="mapa"` usa lo que sabe el sistema (sesiones de la app);
     `"verdad"` usa `traci.simulation.getParameter(pa, "parkingArea.occupancy")` y sirve
     solo como oráculo de comparación;
   - cada 10 s revisa si el puesto asignado se llenó antes de llegar y reasigna (máximo 3
     veces; después queda en búsqueda a ciegas con los *rerouters* de Tyrone);
   - el destino sale del `param destino` del vehículo; si la demanda no lo trae, pide a
     Tyrone que lo añada y usa el *edge* final de la ruta (`# MOCK`).
3. Integra las sesiones con la máquina de estados de S2-2:
   - `GUIADO → ESTACIONADO` al detectar el estacionamiento:
     `ServicioSesiones.iniciar(sim_<veh>, placa, puesto)` (placa sintética `SIM-<n>`), que
     retiene el bloque mínimo;
   - `SALIENDO → CERRADA`: `cerrar(sesion, t_sim, "deteccion")`, que debita y libera;
   - si `iniciar` falla por `SALDO_INSUFICIENTE` o `SESIONES_BLOQUEADAS`, el auto estaciona
     igual pero sin sesión; cuéntalo aparte.
   - Los autos sin app no abren sesiones: buscan a ciegas como en la línea base.
4. Corre `app50_s1` (75 min) **en segundo plano** y, en paralelo, `base_s1` para comparar.
   Escribe `traci/salidas/sesiones_app50_s1.csv` (`sesion_id,usuario_id,puesto_id,
   t_inicio,t_fin,minutos_reales,minutos_cobrados,debitado,motivo`).
5. **Auditoría del cobro** (`traci/auditar_cobro.py`): para cada sesión,
   `debitado == tarifa.costo(t_fin − t_inicio_real)`, donde `t_inicio_real` y `t_fin_real`
   salen del stop-output; reporta el error de facturación medio y máximo, y comprueba
   `saldo = Σ recargas − Σ débitos` para todos los usuarios.
6. **Tests** (`traci/tests/test_guiado.py`, pytest; con SUMO marcado `-m sumo`): el guiado
   nunca asigna un puesto lleno según su fuente; la reasignación ocurre al llenarse el
   puesto; un auto con app termina con exactamente una sesión cerrada; la retención queda en
   0 al final. Delega la auditoría del paso 5 en un subagente mientras haces el guiado.
7. **Evidencias:**
   - `s3_guiado-vs-ciegas.png`: histogramas superpuestos del tiempo de búsqueda de autos con
     app y sin app en `app50_s1` (usa `proyecto/kpis/kpis.py` si existe);
   - `s3_cobros-simulados.png`: minutos reales frente a cobrados por sesión, con la escalera
     de fracciones de 5 min.

## VPS (demo en línea)
Lee `docs/DESPLIEGUE.md`. `--publicar` acepta la URL del VPS: `--publicar https://demo.e-sert.tesisucuenca.com --token $ESERT_TOKEN_SIM` (token desde variable de entorno, nunca en el código). Usa una sesión `httpx` con *keep-alive*, envíos en un hilo aparte con cola de tamaño 1 (si la red se atrasa, se descarta el snapshot viejo: **la simulación nunca espera a la red**) y reintento con *backoff*.

## Dónde escribir
`semanas/S2/Freddy/codigo/traci/` y `semanas/S2/Freddy/evidencias/`. No edites `sumo/`
(es de Tyrone): lo que falte en la demanda va como pedido.

## Hecho cuando
- [ ] Con `--publicar` hacia una URL caída, la simulación sigue a la misma velocidad (prueba con una URL inválida).
- [ ] `app50_s1` corre 75 min simulados sin errores con guiado, sesiones y cobro activos.
- [ ] Cada auto con app que estacionó tiene una sesión; ninguna queda abierta al final (o
  se explica).
- [ ] El libro cuadra para todos los usuarios y la retención final es 0.
- [ ] El tiempo medio de búsqueda con app es menor que sin app en la misma corrida.
- [ ] `pytest traci/tests` pasa.
- [ ] Existen las dos evidencias PNG y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Freddy), **incluido el PDF
semanal**. En "Pedidos a otros": @Tyrone, `traci/guiado.py` reemplaza tu oráculo en S3-1 y
necesito el `param destino` en cada vehículo; @Pablo, cuántas falsas liberaciones produjo
`rf_v1` en `app50_s1`.
