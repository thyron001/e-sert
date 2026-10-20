---
semana: S3
persona: Freddy
sesion: 3
titulo: Clasificación en vivo de teléfonos reales y cierre automático de sesión
horas: 3-4
modulo: backend
depende: [S2-Freddy-1, S2-Miguel-3, S3-Pablo-1, S3-Freddy-2]
entrega: [backend/en_vivo/clasificador_vivo.py, backend/en_vivo/sesiones_vivo.py, backend/nucleo/estados.py, backend/herramientas/reproducir_grabacion.py, backend/tests/test_en_vivo.py, comun/CONTRATO.propuesto.md]
evidencias: [s3_cierre-automatico-real.png]
---
# S3 · Sesión 3 · Freddy 🍅: Clasificación en vivo de teléfonos reales y cierre automático de sesión

## Contexto
Lee `CLAUDE.md`, `docs/CONTRATO.md` (secciones 2, 3, 4 y 6) y tus bitácoras de S3-1 y S3-2.
Hasta ahora la máquina de estados solo corría dentro de TraCI. Esta sesión la lleva al backend
para los **teléfonos reales**: la app de Miguel manda ubicaciones (`origen: "app"`) y el backend
decide cuándo el usuario se fue y cierra la sesión solo. Miguel (S3-Miguel-1) espera el aviso de
cierre para mostrar el recibo. Las grabaciones reales se leen de `proyecto/datos/`; la inferencia,
de la rama de Pablo (S3-1) o de `proyecto/ia/`.

## Objetivo
Clasificar en vivo cada teléfono con ventanas de 30 s, correr la misma máquina de estados que en
la simulación y cerrar la sesión automáticamente, sin falsas liberaciones en las grabaciones.

## Pasos
1. **Una sola máquina de estados:** mueve la lógica de transiciones a `backend/nucleo/estados.py`
   (Python puro, sin TraCI) y haz que `traci/` la importe. Los tests de S2 deben seguir pasando.
2. **Clasificador en vivo** (`backend/en_vivo/clasificador_vivo.py`):
   - un `collections.deque(maxlen=60)` por `usuario_id` `app_…`, alimentado desde
     `POST /eventos/ubicacion`;
   - cada 5 s **según el `ts` del teléfono** (no el reloj del servidor), si la ventana cubre 30 s,
     llama a `ia.inferencia.clasificar(ventana)` con el suavizado de Pablo (k = 3 por defecto,
     configurable; S3-Pablo-2 fija el valor);
   - ejecútalo con `fastapi.concurrency.run_in_threadpool` para no bloquear el bucle; meta:
     < 20 ms por evento en p95;
   - guarda el resultado como un evento de modo (`fuente: "rf"`) y publícalo en
     `snapshot.telefonos[].modo`.
3. **Sesiones en vivo** (`backend/en_vivo/sesiones_vivo.py`):
   - distancias al puesto con *haversine* desde `puestos.csv`;
   - el GPS real tiene 10–25 m de error: usa `max(umbral_contrato, 1,5 · precision_m)` para los
     umbrales de 15, 30 y 20 m. Propón la regla en `comun/CONTRATO.propuesto.md`;
   - aplica la política de datos pobres de S3-2 (sin transición con ventanas incompletas);
   - nunca cierres si las 2 últimas ventanas tienen confianza < 0,6.
4. **Cierre automático:** en `SALIENDO → CERRADA`, llama a `ServicioSesiones.cerrar(motivo="deteccion")`.
   - `POST /sesiones/{id}/cerrar` se vuelve idempotente: un segundo cierre devuelve el mismo
     recibo con `200`.
   - Envía por WS un mensaje nuevo
     `{"tipo": "sesion", "sesion_id", "usuario_id", "estado", "motivo", "minutos_reales",
     "minutos_cobrados", "debitado", "costo_tarjeta"}`, solo al usuario dueño de la sesión.
     Añádelo a `CONTRATO.propuesto.md` y a `comun/esquemas.py` y `esquemas.ts`.
5. **Reproductor de grabaciones** (`backend/herramientas/reproducir_grabacion.py`):
   `python -m backend.herramientas.reproducir_grabacion proyecto/datos/<archivo>.csv --velocidad 10`.
   Crea usuario y sesión al inicio, publica cada fila como ubicación con su `ts` y, al final,
   compara el cierre detectado con la salida real (primera ventana `vehiculo` tras el episodio
   `quieto`/`a_pie` junto al auto, según `modo_real`).
6. **Tests** (`backend/tests/test_en_vivo.py`) con `fastapi.testclient.TestClient`:
   - una traza sintética estaciona → camina 5 min → vuelve → maneja: cierra una sola vez y el
     WS recibe un solo mensaje `sesion`;
   - la misma traza con 60 s de silencio en `A_PIE` no cierra;
   - eventos desordenados por `ts` no generan transiciones falsas;
   - el doble cierre es idempotente.
7. Reproduce **todas** las grabaciones de `proyecto/datos/` en paralelo (un subagente o un
   `multiprocessing.Pool` con un backend por proceso en puertos distintos) y tabula los resultados
   en `backend/herramientas/resultados_vivo.csv`. Si hay tiempo, pide al usuario una prueba corta
   con un teléfono real en el Centro.
8. **Evidencia** `evidencias/s3_cierre-automatico-real.png`: línea de tiempo de una grabación con
   `modo_real` vs modo detectado, distancia al puesto, estados de la sesión y una línea vertical
   en el cierre.

## Dónde escribir
`semanas/S3/Freddy/codigo/backend/`, `semanas/S3/Freddy/codigo/traci/` (solo el import de
`estados.py`), `semanas/S3/Freddy/codigo/comun/` y `evidencias/`.

## Hecho cuando
- [ ] `pytest backend/tests/test_en_vivo.py` pasa y los tests de TraCI siguen en verde.
- [ ] En las grabaciones de `proyecto/datos/`: 0 falsas liberaciones y, en al menos el 80 %,
  cierre a menos de 60 s de la salida real.
- [ ] El p95 del procesamiento por evento es menor que 20 ms.
- [ ] El mensaje WS `sesion` está en el contrato propuesto y en los esquemas Python y TS.
- [ ] Existen `s3_cierre-automatico-real.png` y el PDF semanal.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 3, Freddy), **incluido el PDF
semanal**. En "Pedidos a otros": @Miguel, formato del mensaje `sesion` y del recibo; @Pablo, la
latencia y la confianza observadas en vivo; @Tyrone, los teléfonos ya traen `modo` en el snapshot.
