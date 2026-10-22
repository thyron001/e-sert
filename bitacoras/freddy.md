# Bitácora de Freddy 🍅

**Color:** Tomate (`#FF7043`) · **Rol:** Controlador TraCI, emulador GPS, guiado y backend FastAPI

Cada sesión agrega una entrada al final (ver *Protocolo de cierre* en `CLAUDE.md`). No se borra nada.

---

## S1 · Sesión 1 · 2026-10-22 · Contrato v1 y esquemas compartidos
**Estado:** hecha
**Qué hice:**
- Revisé el contrato v0 y escribí el v1 completo y autocontenido en `comun/CONTRATO.propuesto.md`, con la sección "Cambios respecto a v0" (12 puntos).
- Huecos cerrados:
  - el controlador TraCI cierra las sesiones de los autos simulados con `POST /sesiones/{id}/cerrar` e informa las transiciones con `POST /sesiones/{id}/transicion`;
  - formato de error `{"error": {codigo, mensaje, detalle}}` con 15 códigos y su HTTP;
  - header `X-Contrato-Version: 1` y `X-Sim-Token`;
  - `POST /sim/paso`, la vía por la que el backend recibe posiciones y ocupación real;
  - mensaje WS `verdad`, solo para `?rol=visor`;
  - fórmulas de cobro, de la tarjeta SERT y de los avisos;
  - formato del CSV de trazas.
- `comun/esquemas.py`: 41 modelos Pydantic v2 y 9 enums, la unión discriminada `MensajeWS` y `FilaTraza`. Es compatible con Python 3.10.
- `comun/esquemas.ts`: espejo TypeScript escrito a mano.
- `comun/tarifa.json` + `comun/tarifa.py`: carga, validación y cálculos en centavos.
- `comun/ejemplos/`: 29 JSON y `traza.csv`.
- `comun/tests/test_esquemas.py`: 163 tests (ejemplos, 25 casos malos, tarifa, paridad `.ts` ↔ `.py` con un *parser* por regex).
- Diagrama de componentes con matplotlib (`comun/diagrama_contrato.py`).

**Archivos creados o modificados:**
- `semanas/S1/Freddy/codigo/comun/`: `CONTRATO.propuesto.md`, `esquemas.py`, `esquemas.ts`, `tarifa.json`, `tarifa.py`, `__init__.py`, `requirements.txt`, `diagrama_contrato.py`, `ejemplos/*`, `tests/*`.
- `semanas/S1/Freddy/evidencias/s1_contrato-diagrama.png`
- `semanas/S1/Freddy/explicaciones/s1_explicacion.{md,pdf}`
- `semanas/S1/Freddy/estado.json`, `semanas/S1/Freddy/RESUMEN.md`

**Decisiones y por qué:**
- La máquina de estados corre en el controlador TraCI, que tiene el GPS y la IA; el backend valida, guarda y cobra.
- La sesión nace en `ESTACIONADO`: `BUSCANDO` y `GUIADO` son estados del vehículo.
- Si hay `t_sim` al inicio y al cierre, la duración se calcula con él, para que el cobro siga el reloj de SUMO.
- El dinero se calcula en centavos con `Decimal`, para que el KPI de error de facturación no arrastre ruido de coma flotante.
- Tomé de Miguel las propuestas de `Sesion`, `Movimiento` y `ErrorApi`, para que su `tipos.ts` cambie lo mínimo.
- Los `puesto_id` siguen el `puestos.csv` de Tyrone (`pa_<edge>_<n>`, con capacidad). Como contienen `#`, nunca van en la URL.
- Nuevos parámetros de tarifa: `aviso_tiempo_min` y `tarjeta_bloque_min` (supuesto: tarjeta SERT de 1 h).

**Problemas encontrados:**
- No se pudo compilar `esquemas.ts`: la computadora no tiene Node y el contenedor tiene Node 12 sin npm. La paridad la cubren los tests.
- `explicacion_pdf.py` no admite `<code>` dentro de celdas de tabla: las tablas de la explicación van sin comillas invertidas.

**Pedidos a otros:**
- @Tyrone (visor/KPIs): el visor se conecta a `/ws/estado?rol=visor` y recibe `snapshot` (ocupación *estimada*), `kpi` (nombres reservados en §6) y el nuevo `verdad` (ocupación real, `estacionados`, `falsas_liberaciones`). Para la precisión del mapa, compara `snapshot.puestos` con `verdad.puestos`.
- @Tyrone [VPS]: en el despliegue del backend, define `SIM_TOKEN` en el `.env` de Dokploy. Las rutas `/sim/paso` y `/sesiones/{id}/transicion` lo exigen en el header `X-Sim-Token`.
- @Pablo (IA): `clasificar(ventana: list[PuntoGPS]) -> ResultadoModo` con los modelos de `comun.esquemas`. Las trazas usan las 7 columnas de §8 en orden; `segmento_id` va después, como columna extra, y para GeoLife el `usuario_id` es `geolife_<nnn>`.
- @Miguel (app): reemplaza `src/api/tipos.ts` por `comun/esquemas.ts`. Cambios que te afectan:
  - `SesionCerrada` añade `minutos_reales` y `saldo`; `Billetera` añade `bloqueada`;
  - `POST /sesiones` responde 201 y acepta `ts`/`t_sim`;
  - `CuerpoError.error` es `DetalleError` (con `detalle` opcional) y hay 15 códigos;
  - `Tarifa` añade `aviso_tiempo_min` y `tarjeta_bloque_min`;
  - avisos nuevos `saldo_agotado`, `tiempo_maximo_cerca`, `tiempo_maximo_superado` y `sesiones_bloqueadas`;
  - confirma la tarifa SERT vigente para ajustar `tarifa.json`.
- @Freddy (yo, S2): el backend implementa §4 usando `tarifa.py`, y el controlador envía `/sim/paso`, `/transicion` y `/cerrar`. Antes hay que instalar pydantic en el contenedor (`pip3 install --user -r .../comun/requirements.txt`).

**Bucle y verificación:** 2 vueltas.
- Vuelta 1: los tests pasaron, pero `pytest` a secas no encontraba `comun`; lo arreglé con `tests/__init__.py`. Una prueba de mutación (quitar un campo del `.ts` y un valor de enum) confirmó que la paridad falla cuando debe.
- Vuelta 2: el verificador independiente reportó **4/4 criterios cumplidos** y 6 incoherencias menores. Corregí estas:
  - el costo del espejo en el ejemplo del `.md` (0,15 → 0,10) y su definición;
  - IDs y horas ilustrativos que no validaban;
  - el formato de `usuario_id` en las trazas;
  - la redacción de `X-Sim-Token`;
  - el cierre por `deteccion` solo desde `SALIENDO`.

  No corregí el redondeo a 2 decimales: queda documentado como responsabilidad de quien emite el valor.
- Resultado final: 163 passed.

**Pendientes para la próxima sesión:** compilar `esquemas.ts` con `tsc` cuando haya Node 18+; instalar pydantic en el contenedor; ajustar la tarifa cuando Miguel la confirme.

**Evidencias:** ![](../semanas/S1/Freddy/evidencias/s1_contrato-diagrama.png) · [Explicación (PDF)](../semanas/S1/Freddy/explicaciones/s1_explicacion.pdf)

## S1 · Sesión 2 · 2026-10-22 · Núcleo del backend (billetera, tarifa y sesiones)
**Estado:** hecha
**Qué hice:**
- `backend/nucleo/db.py`:
  - SQLAlchemy 2 + SQLite, con URL configurable (`:memory:` o archivo);
  - tablas `usuarios`, `movimientos`, `sesiones` y `puestos`, con el dinero en centavos y las horas en UTC;
  - lector del `puestos.csv` de Tyrone y mock de 20 puestos (`# MOCK`).
- `backend/nucleo/tarifa.py`: `minutos_cobrables`, `costo`, `costo_tarjeta_sert` (bloques de 30 min) y `retencion`, sobre `comun/tarifa.py`.
- `backend/nucleo/billetera.py`: `Billetera` con `recargar`, `retener`, `debitar`, `liberar`, `estado` y `movimientos`. El saldo siempre sale del libro y las operaciones son transaccionales.
- `backend/nucleo/sesiones.py`: `ServicioSesiones` con `iniciar`, `transicion`, `cerrar`, `avisos`, `avisos_usuario`, `recibo` y `obtener`.
- `backend/nucleo/ocupacion.py`: `MapaOcupacion` con `libres_cerca` y `recomendar` (haversine).
- `backend/nucleo/errores.py`: `ErrorNucleo` con el código y el HTTP del contrato.
- 63 tests con 99 % de cobertura del núcleo; gráfica `s2_cobro-sert-vs-real.png`.
- Instalé sqlalchemy y pydantic en el contenedor `van3twin` y comprobé que el núcleo se importa y cobra bien allí (Python 3.10.12).

**Archivos creados o modificados:**
- `semanas/S1/Freddy/codigo/backend/`: `__init__.py`, `requirements.txt`, `nucleo/*`, `tests/*` y `graficas/cobro_sert_vs_real.py`.
- `semanas/S1/Freddy/codigo/comun/`: `tarifa.json` (`tarjeta_bloque_min` 60 → 30), `CONTRATO.propuesto.md` (§5: tarjeta de 30 min y definición de `saldo_bajo` durante una sesión) y `tests/test_esquemas.py`.
- Cierre: `evidencias/s2_cobro-sert-vs-real.png`, `explicaciones/s2_explicacion.{md,pdf}`, `estado.json` y `RESUMEN.md`.

**Decisiones y por qué:**
- La tarjeta SERT pasa a bloques de 30 min, como pide el prompt; en S1-1 había supuesto 60.
- El aviso se llama `tiempo_maximo_cerca` (nombre del contrato) y no `tiempo_maximo_proximo` (nombre del prompt), para no romper la paridad con `esquemas.ts`.
- El "bloqueado" se deriva de `saldo < 0` y no se guarda, para que nunca se desincronice del libro.
- El débito se aplica completo aunque el saldo baje de −$0,50 (contrato §5): el auto ya estuvo estacionado. `saldo_negativo_max_usd` solo dispara el aviso `saldo_agotado`. Es mi interpretación del paso 4 ("si queda negativo pero dentro del máximo, bloquea").
- El lugar en el puesto y la sesión única por usuario se validan en la base, dentro de la transacción, con un índice único parcial, porque el controlador TraCI y FastAPI pueden compartir la base. El mapa en memoria solo se sincroniza.
- Si la sesión tiene `t_sim` al inicio y al cierre, la duración sale del reloj de SUMO; si falta alguno, de la hora UTC.

**Problemas encontrados:**
- El test de propiedad tardaba 18 s porque revisaba a todos los usuarios en cada paso. Ahora revisa al usuario afectado en cada paso y a todos al final (11 s).
- El verificador encontró dos bugs, ya corregidos con tests de regresión:
  - dos servicios sobre la misma base podían sobrellenar un puesto;
  - `liberar` aceptaba la sesión de otro usuario.

**Pedidos a otros:**
- @Tyrone: cuando `puestos.csv` entre en `proyecto/sumo/parqueos/`, el núcleo lo carga solo (`puestos_iniciales()`). Mientras tanto usa el mock de 20 puestos.
- @Tyrone (KPIs): el sobrecobro medio de la tarjeta SERT es $0,101 por estadía (19,3 %, 1–120 min). Sirve para la exposición.
- @Miguel: la tarjeta SERT es ahora de bloques de 30 min (`tarjeta_bloque_min: 30`) y `saldo_bajo` se calcula con `saldo − costo en curso`. Confirma si la tarifa SERT real usa tarjetas de 30 min.

**Bucle y verificación:** 3 vueltas.
1. 54 tests y 99 % de cobertura.
2. Optimicé el test de propiedad.
3. El verificador independiente reportó **4/4 criterios cumplidos**, 2 bugs de lógica y 3 desviaciones menores. Corregí los dos bugs, `retener` sin control de dueño ni de disponible, `saldo_bajo` fuera de una sesión y las recargas `nan`/`inf`, y añadí 9 tests de regresión. Resultado final: 63 tests, 99 %.

**Pendientes para la próxima sesión:**
- Capa FastAPI sobre el núcleo (S2).
- `recomendar` por tiempo de manejo.
- Reemplazar el mock de puestos.

**Evidencias:** ![](../semanas/S1/Freddy/evidencias/s2_cobro-sert-vs-real.png) · [Explicación (PDF)](../semanas/S1/Freddy/explicaciones/s2_explicacion.pdf)
