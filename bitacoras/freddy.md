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
