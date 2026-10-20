---
semana: S4
persona: Freddy
sesion: 1
titulo: Pruebas de punta a punta (pytest -m e2e)
horas: 3-4
modulo: backend
depende: [S3-Freddy-3, S3-Miguel-1]
entrega: [backend/pytest.ini, backend/tests/e2e/conftest.py, backend/tests/e2e/test_flujo_app.py, backend/tests/e2e/test_websocket.py, backend/tests/e2e/test_errores_contrato.py, backend/tests/e2e/test_simulacion_completa.py, traci/tests/e2e/test_cierre_automatico.py]
evidencias: [s1_e2e-resultados.png]
---
# S4 · Sesión 1 · Freddy 🍅: Pruebas de punta a punta (`pytest -m e2e`)

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (v1 completo) y `docs/PLAN.md` (fila S4). Primero copia
tus módulos (`traci/`, `backend/` **sin** `pagos/` ni `asistente/`, y `comun/`) desde
`proyecto/` a `semanas/S4/Freddy/codigo/`. Hasta ahora cada pieza tiene sus tests unitarios;
falta probar que **todas juntas** cumplen el contrato. La demo del lunes 16 y la unificación
final (domingo 15, 09:00) correrán esta suite. Plazo real: sábado 14, 23:59.

## Objetivo
Una suite `pytest -m e2e` que levanta el backend real y SUMO sin GUI, ejerce el flujo de la
app por HTTP y WebSocket y comprueba los invariantes del sistema (cobro, ocupación y cero
falsas liberaciones evitables).

## Pasos
1. Crea `backend/pytest.ini` (y el equivalente en `traci/`):
   ```ini
   [pytest]
   markers =
       e2e: pruebas de punta a punta (levantan backend y SUMO; lentas)
   addopts = -m "not e2e"
   ```
   Así `pytest` normal sigue rápido y `pytest -m e2e` corre solo la suite larga.
2. `backend/tests/e2e/conftest.py`:
   - `servidor`: arranca `uvicorn` en un hilo en un puerto libre (`socket.bind(("",0))`) con
     una SQLite temporal (`tmp_path`); espera a `GET /api/v1/puestos` y lo apaga al final;
   - `cliente`: `httpx.Client` con el header `X-Contrato-Version: 1`;
   - `requiere_sumo`: `pytest.skip` limpio si `shutil.which("sumo")` es `None` o falta
     `SUMO_HOME`;
   - `usuario_app`: crea `app_<uuid4>` y lo recarga con $5 por el adaptador de Payphone de
     Miguel en modo prueba si existe (`backend/pagos/`); si no, `POST /recarga` con
     `referencia_payphone="PRUEBA"` y un `# MOCK` explicado.
3. `test_flujo_app.py`, el recorrido de la app paso a paso:
   saldo 0 → `/guia` exige recargar → recarga → `/guia` devuelve un puesto libre →
   `POST /sesiones` (`ESTACIONADO`, `retenido` = bloque mínimo) → secuencia de
   `/eventos/ubicacion` y `/eventos/modo` que simula alejarse a pie 40 m, volver y salir en
   `vehiculo` 2 ventanas → la sesión llega a `CERRADA` sola, con `minutos_cobrados` según
   `tarifa.json` y la retención liberada. Comprueba también el caso trampa: alejarse a pie
   **no** libera el puesto.
4. `test_websocket.py`: conecta a `/ws/estado`, valida cada mensaje contra la unión
   discriminada de `comun/esquemas.py`, comprueba que hay como máximo un `snapshot` por
   segundo de simulación y que los mensajes `verdad` nunca llegan a un cliente tipo app.
5. `test_errores_contrato.py`: `SALDO_INSUFICIENTE`, `PUESTO_LLENO`, `SESION_NO_EXISTE` y
   `SESIONES_BLOQUEADAS` responden con el formato exacto `{"error": {"codigo","mensaje"}}`
   y el código HTTP acordado en el contrato.
6. `test_simulacion_completa.py` (`@pytest.mark.e2e`, `requiere_sumo`): corre el controlador
   sin GUI contra el backend vivo 300 s simulados, penetración 20 %, semilla 1, y comprueba:
   - cada sesión `CERRADA` tiene `traci.vehicle.isStoppedParking(veh) == False` al cerrarse;
   - `saldo = Σ recargas − Σ débitos` para todos los usuarios y ningún saldo bajo
     `−saldo_negativo_max_usd`;
   - la precisión del mapa de ocupación supera el valor de S3 menos 5 puntos;
   - el log del controlador no tiene excepciones.
7. `traci/tests/e2e/test_cierre_automatico.py`: un peatón que hace diligencias y vuelve no
   provoca cierre; el auto que sale sí, con retardo de cierre menor que 30 s.
8. Corre `pytest -m e2e --junitxml=e2e.xml --durations=0` y arregla lo que falle **en tu
   código**. Si el fallo está en el módulo de otro, déjalo como pedido con el test que lo
   reproduce. Objetivo: la suite e2e dura menos de 5 min.
9. **Evidencia** `evidencias/s1_e2e-resultados.png`: barras horizontales por test con su
   duración, verdes si pasan y rojas si fallan, leídas de `e2e.xml`, y en el título el total
   y el tiempo.

## Dónde escribir
`semanas/S4/Freddy/codigo/backend/`, `semanas/S4/Freddy/codigo/traci/` y `evidencias/`.
No edites `backend/pagos/` ni `backend/asistente/` (son de Miguel).

## Hecho cuando
- [ ] `pytest -m e2e` pasa completo en una máquina con SUMO, en menos de 5 min.
- [ ] Sin SUMO, la suite se salta limpiamente (sin errores) y los tests HTTP siguen corriendo.
- [ ] `pytest` sin marcador sigue pasando y no tarda más de 60 s.
- [ ] Los cuatro códigos de error del contrato están probados.
- [ ] Existe la evidencia `s1_e2e-resultados.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 1, Freddy). En "Pedidos a
otros": @Tyrone, el comando `pytest -m e2e` para `verificar_demo.py`; @Miguel, cualquier
diferencia de su adaptador de pagos con el contrato.
