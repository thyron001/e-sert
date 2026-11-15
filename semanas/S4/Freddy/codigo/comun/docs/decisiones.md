# Registro de decisiones de arquitectura (e-sert)

Cada bloque tiene cuatro partes: el contexto, la decisión que se tomó, las alternativas que se
descartaron y las consecuencias que tiene. Las decisiones están en el orden en que se tomaron
durante el proyecto. El contrato del que hablan es `docs/CONTRATO.md`, y los archivos citados
están en `proyecto/`.

---

## D1 · El controlador usa el núcleo directamente, sin pasar por HTTP

**Contexto.**
- En una corrida de 1 800 s con 80 % de autos con app hay unos 400 conductores simulados.
- Cada uno abre, actualiza y cierra su sesión y mueve su billetera.
- Si todo eso pasara por HTTP, cada paso de SUMO esperaría a la red. Además, los experimentos de KPIs dependerían de que el backend estuviera vivo.

**Decisión.**
- El controlador TraCI importa `backend/nucleo/` como biblioteca, a través de `traci/puente_nucleo.py` (`PuenteNucleo`).
- `PuenteNucleo` arma sobre `sqlite:///:memory:` las mismas clases que usa la API: `Billetera`, `ServicioSesiones` y `MapaOcupacion`.
- Hacia el backend vivo solo se envían dos cosas, y ninguna es bloqueante:
  - un snapshot por segundo simulado (`POST /interno/snapshot`), desde un hilo con cola de tamaño 1;
  - los KPIs (`POST /sim/kpi`).

**Alternativas descartadas.**
- *Todo por HTTP*: más fiel al uso real, pero con unos 2–5 ms por llamada multiplica el tiempo por paso y acopla los experimentos a la red.
- *Un núcleo duplicado dentro de `traci/`*: dos implementaciones de las mismas reglas que terminarían divergiendo.

**Consecuencias.**
- Las reglas de cobro y de transiciones son **un solo código**, que prueban `backend/tests/` y que usan los dos caminos.
- El diagrama `seq_vehiculo_simulado.mmd` muestra los dos caminos.
- `backend/nucleo/` debe seguir siendo Python puro, compatible con 3.10 (la versión del contenedor) y sin FastAPI.
- Las sesiones de los autos simulados no aparecen en la base del backend: se ven en el visor a través del snapshot.
- Las pruebas e2e de S4 cubren el camino HTTP con usuarios `app_<uuid>` (`traci/cierre_remoto.py`).

---

## D2 · SQLite como base de datos

**Contexto.**
- Es una demo con decenas de usuarios reales como máximo.
- Un solo proceso `uvicorn` corre en un VPS liviano (Dokploy).
- El equipo no administra servidores de bases de datos.

**Decisión.**
- SQLite a través de SQLAlchemy 2 (`backend/nucleo/db.py`).
- La URL se toma de `ESERT_DB_URL`:
  - `sqlite:///./e-sert.db` en local;
  - `sqlite:////data/esert.db` en el VPS, con el volumen `/data`;
  - `sqlite:///:memory:` en las corridas y en las pruebas.
- Cada operación del núcleo es una transacción (`BaseDatos.transaccion`).

**Alternativas descartadas.**
- *PostgreSQL*: más robusto con concurrencia, pero exige otro servicio en Dokploy, más credenciales y más pasos para levantar el plan B.
- *Guardar en memoria sin persistencia*: se perdería la billetera en cada redeploy.

**Consecuencias.**
- Despliegue de un solo contenedor.
- Las pruebas usan la misma base que producción.
- Las escrituras se serializan. La prueba de carga de S3-2 dio una latencia suficiente para la demo.
- Si el proyecto creciera, el cambio a PostgreSQL es solo la URL, porque se usa SQLAlchemy.

---

## D3 · Suscripciones de TraCI en lugar de llamadas sueltas

**Contexto.**
- Cada llamada de TraCI es un viaje de ida y vuelta por socket.
- Con unos 5 000 autos de tráfico de fondo, leer posición, velocidad y estado de parada auto por auto domina el tiempo por paso.

**Decisión.**
- `traci/controlador.py` usa `vehicle.subscribe` y `person.subscribe` con las variables que necesitan los *hooks*. Solo se suscriben los autos que buscan parqueo (`filtro_vehiculos`, clase `busca`).
- La ocupación real se cuenta por eventos de parqueo (`getParkingStarting/EndingVehiclesIDList`), porque `parkingarea.subscribe` no existe en SUMO 1.12.
- También se probó `libsumo`, disponible como opción `libsumo=True` de `correr_kpis.correr` y `ConfigControlador`.

**Alternativas descartadas.**
- *Llamadas `get*` por auto en cada paso*: simples, pero varias veces más lentas (perfil de S3-2).
- *Leer las salidas XML de SUMO al final*: no sirve para una demo en vivo.

**Consecuencias.**
- El tiempo por paso con 80 % de penetración queda en decenas de ms (cifra medida en `arquitectura.md`).
- Los *hooks* leen `ctrl.vehiculos`, el diccionario suscrito, y no llaman a TraCI por su cuenta.
- Una rareza de SUMO 1.12: con `libsumo`, las personas creadas con `person.add` no aparecen en `getDepartedPersonIDList`, así que se usa `person.getIDList()`.

---

## D4 · El guiado usa la ocupación actual, no una ocupación predicha

**Contexto.**
- Al asignar un puesto se puede mirar cuántas plazas están libres **ahora** o estimar cuántas lo estarán **cuando el auto llegue**.

**Decisión.**
- `traci/guiado.py` (`Guia`) y `GET /guia` eligen el puesto **con plazas libres ahora** más cercano al destino.
- Esa ocupación sale del mapa del sistema (fuente `mapa`) o, para comparar, de la verdad de SUMO (fuente `verdad`).
- Si el puesto asignado se llena antes de que el auto llegue, se reasigna: cada 10 s, como máximo 3 veces, y después el auto busca a ciegas.
- No se reencamina hacia puestos sin ruta (`findRoute`).

**Alternativas descartadas.**
- *Predicción de ocupación* (series temporales por puesto): necesita historia que no tenemos y es difícil de validar en las semanas del curso.
- *Reservas*: cambian el modelo de negocio, porque el SERT no reserva.

**Consecuencias.**
- Es una regla simple y explicable, y el contrato la fija: «nunca devuelve un puesto lleno».
- El costo son las reasignaciones cuando hay mucha demanda, que se miden como KPI en S3-1.
- La calidad del guiado depende directamente de la del mapa: una falsa liberación produce «libres fantasma».

---

## D5 · La billetera es un libro de movimientos

**Contexto.**
- Hay recargas con Payphone, retenciones al llegar, débitos al salir y liberaciones de la retención.
- Un saldo guardado en un solo campo se desincroniza ante fallos parciales y no deja auditar.

**Decisión.**
- `backend/nucleo/billetera.py` guarda **solo movimientos**: `recarga`, `retencion`, `debito` y `liberacion`.
- Cada movimiento lleva su monto en **centavos enteros**, siempre positivo; el tipo indica el sentido.
- Los demás valores se derivan:

| Valor | Cálculo |
|---|---|
| `saldo` | recargas − débitos |
| `retenido` | retenciones − liberaciones |
| `disponible` | saldo − retenido |
| `bloqueada` | saldo < 0 |

**Alternativas descartadas.**
- *Un campo `saldo` que se actualiza*: más simple, pero sin historia y con riesgo de carreras.
- *Montos en `float`*: errores de redondeo en los cobros por fracción.

**Consecuencias.**
- Siempre se cumple `saldo = Σ recargas − Σ débitos`. Lo comprueban las pruebas de propiedades (`test_propiedad.py`) y la suite e2e (`test_simulacion_completa.py`).
- `GET /billetera/{id}` devuelve los movimientos, y la app puede mostrar el historial.
- Una recarga de Payphone se acredita **una sola vez**: la intención guarda su estado (módulo de Miguel).

---

## D6 · `verdad` solo existe en la simulación

**Contexto.**
- En la realidad nadie sabe con certeza si un auto sigue estacionado: el sistema solo ve el teléfono.
- En la simulación sí se sabe, con `isStoppedParking`, y es justo lo que permite medir las falsas liberaciones.

**Decisión.**
- La ocupación real de SUMO, los autos estacionados y las falsas liberaciones viajan en un mensaje aparte, `verdad`.
- Ese mensaje solo se envía a los clientes `rol=visor` de `/ws/estado`.
- La app (`rol=publico`) nunca lo recibe, aunque pida `verdad=1`.
- El `snapshot` público lleva el **mapa del sistema**, no la verdad.
- `backend/api/ws.py` filtra por cliente, y la suite e2e (`test_websocket.py`) lo prueba.

**Alternativas descartadas.**
- *Mezclar la verdad en el snapshot*: la app «haría trampa» con información que en la realidad no existe, y no se podría evaluar el sistema.
- *No publicar la verdad*: el visor no podría mostrar en vivo el contraste entre el mapa y la realidad.

**Consecuencias.**
- La demo enseña lado a lado lo que cree el sistema y lo que pasa de verdad.
- Los KPIs (falsas liberaciones, precisión del mapa) salen de comparar las dos fuentes.
- En un despliegue real, el mensaje `verdad` simplemente no existiría, y nada más cambia.
