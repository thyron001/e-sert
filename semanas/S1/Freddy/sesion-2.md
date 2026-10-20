---
semana: S1
persona: Freddy
sesion: 2
titulo: Núcleo del backend - billetera, tarifa y sesiones
horas: 3-4
modulo: backend
depende: [S1-Freddy-1]
entrega: [backend/nucleo/billetera.py, backend/nucleo/tarifa.py, backend/nucleo/sesiones.py, backend/nucleo/ocupacion.py, backend/tests/]
evidencias: [s2_cobro-sert-vs-real.png]
---
# S1 · Sesión 2 · Freddy 🍅: Núcleo del backend (billetera, tarifa y sesiones)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección de reglas de cobro) y tu
`comun/CONTRATO.propuesto.md`. Hay una decisión de arquitectura clave: **la lógica vive en
un núcleo de Python puro, sin HTTP**. Así, el controlador TraCI la importa directamente en
los experimentos (cientos de autos, rápido y reproducible), y FastAPI (S2) es solo una capa
delgada encima para la app y la demo.

## Objetivo
Implementar y probar el núcleo: el libro de movimientos de la billetera, el cálculo de la
tarifa, el ciclo de vida de la sesión y el mapa de ocupación.

## Pasos
1. Crea `backend/nucleo/db.py` con SQLAlchemy 2 y SQLite. La URL se configura
   (`sqlite:///:memory:` en experimentos y archivo en la demo). Tablas:
   - `usuarios`
   - `movimientos` (`id`, `usuario_id`, `tipo`, `monto`, `sesion_id`, `ts`)
   - `sesiones`
   - `puestos`, cargada desde `puestos.csv`; mientras no exista, usa un mock de 20 puestos.
2. Crea `backend/nucleo/tarifa.py` con funciones puras basadas en `comun/tarifa.json`:
   - `minutos_cobrables(minutos_reales)`: redondea hacia arriba a la `fraccion_min` y aplica
     el `cobro_minimo_min`.
   - `costo(minutos_reales)`.
   - `costo_tarjeta_sert(minutos_reales)`: bloques de 30 min por adelantado, para comparar.
3. Crea `backend/nucleo/billetera.py`, una clase `Billetera` con `recargar`, `retener`,
   `debitar`, `liberar`, `estado(usuario)` → `{saldo, retenido, disponible}` y
   `movimientos(usuario)`.
   - El saldo **nunca** se guarda: se calcula del libro.
   - Las operaciones son atómicas (transacción).
4. Crea `backend/nucleo/sesiones.py` con `ServicioSesiones`:
   - `iniciar(usuario, placa, puesto)`: valida que el disponible alcance para el bloque
     mínimo, que el usuario no tenga sesiones bloqueadas por saldo negativo y que el puesto
     tenga lugar. Luego retiene.
   - `cerrar(sesion, ts, motivo)`: calcula los minutos reales, debita, libera la retención y,
     si el saldo queda negativo pero dentro del máximo, marca al usuario como bloqueado.
   - `avisos(sesion, ahora)`: devuelve `saldo_bajo` o `tiempo_maximo_proximo`.
5. Crea `backend/nucleo/ocupacion.py` con `MapaOcupacion`: ocupación por puesto **según los
   eventos de la app**, no la real; `libres_cerca(lat, lon, radio_m)`; y
   `recomendar(destino_lat, destino_lon)`, que elige el puesto libre más cercano al destino
   (distancia *haversine*; el tiempo de manejo se mejora en S2).
6. **Tests** (`backend/tests/`, pytest, cobertura > 85 % del núcleo):
   - 12 min reales → 15 min cobrados;
   - 3 min → 10 min (cobro mínimo);
   - recargar 5, iniciar, cerrar a los 47 min → saldo correcto y retención liberada;
   - saldo insuficiente → error `SALDO_INSUFICIENTE`;
   - saldo negativo → la siguiente sesión se bloquea hasta recargar;
   - puesto lleno → `PUESTO_LLENO`;
   - `recomendar` nunca devuelve un puesto lleno;
   - `saldo = Σ recargas − Σ débitos` siempre se cumple (test tipo propiedad con 200
     operaciones aleatorias).
7. **Evidencia** `evidencias/s2_cobro-sert-vs-real.png`: el costo con la tarjeta SERT
   (escalones de 30 min) frente al costo real por fracciones, para estadías de 1 a 120 min,
   con el área entre curvas sombreada como "sobrecobro". Esta gráfica va directa a la
   exposición.

## Dónde escribir
`semanas/S1/Freddy/codigo/backend/` (incluye `requirements.txt`) y `evidencias/`.

## Hecho cuando
- [ ] `pytest backend/tests` pasa, con cobertura del núcleo superior al 85 % (`pytest-cov`).
- [ ] El núcleo no importa FastAPI ni nada HTTP.
- [ ] Todas las reglas de cobro de `CONTEXTO.md` tienen al menos un test.
- [ ] Existe la evidencia `s2_cobro-sert-vs-real.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 2, Freddy).
