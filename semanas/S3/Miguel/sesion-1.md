---
semana: S3
persona: Miguel
sesion: 1
titulo: Cierre automático en la app y recibo comparado con la tarjeta SERT
horas: 3-4
modulo: app
depende: [S2-Miguel-1, S2-Miguel-2, S2-Freddy-1]
entrega: [app/src/servicios/seguimientoSesion.ts, app/src/pantallas/Recibo.tsx, app/src/logica/tarifa.ts, app/src/logica/__tests__/tarifa.test.ts, app/src/mocks/cierreMock.ts]
evidencias: [s1_recibo.png]
---
# S3 · Sesión 1 · Miguel 🔴: Cierre automático en la app y recibo comparado con la tarjeta SERT

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro) y `docs/CONTRATO.md` (secciones 4 y 6). Es
la primera sesión de S3: copia `proyecto/app/` a `semanas/S3/Miguel/codigo/app/` si no está, y
respeta su estructura (si las pantallas viven en otra carpeta, usa esa y ajusta las rutas). El
backend se lee desde `proyecto/backend/`. Freddy implementa esta semana (S3-Freddy-3) el cierre
automático y un mensaje WS nuevo `{"tipo": "sesion", ...}`; mientras no esté, usa
`app/src/mocks/cierreMock.ts` marcado `// MOCK: reemplazar cuando Freddy publique el mensaje WS "sesion" (S3-3)`.

## Objetivo
Que la app detecte sola que la sesión se cerró (sin que el usuario toque nada), muestre un recibo
claro y le diga cuánto habría pagado con la tarjeta SERT.

## Pasos
1. **Seguimiento de la sesión** (`app/src/servicios/seguimientoSesion.ts`):
   - con la sesión activa, escucha `/ws/estado` y filtra `tipo === "sesion"` con su `sesion_id`;
   - respaldo: `GET /sesiones/{id}` cada 10 s si el WS está caído;
   - con `AppState.addEventListener("change", ...)`, al volver a primer plano consulta enseguida;
   - al ver `estado === "CERRADA"`, navega al recibo con `navigation.replace("Recibo", {...})`
     (no se puede volver con "atrás" a la sesión activa) y procesa el cierre **una sola vez**
     (`useRef` como candado).
2. **Cierre manual:** botón "Ya me voy" con `Alert.alert` de confirmación →
   `POST /sesiones/{id}/cerrar` con `motivo: "manual"`.
3. **Tarifa en TypeScript** (`app/src/logica/tarifa.ts`), port de `proyecto/backend/nucleo/tarifa.py`
   con los valores de `comun/tarifa.json`: `minutosCobrables`, `costo` y `costoTarjetaSert`
   (bloques de 30 min por adelantado). Usa los tipos de `comun/esquemas.ts`.
4. **Tests** (`app/src/logica/__tests__/tarifa.test.ts`, Jest), con las mismas cifras que los tests
   de Freddy en `proyecto/backend/tests/`:
   - 12 min reales → 15 min cobrados; 3 min → 10 min (cobro mínimo);
   - 47 min → 50 min cobrados = $0,42 con la app; con tarjeta, 2 bloques = $0,50; ahorro $0,08;
   - 120 min → igual con ambos métodos (sin ahorro).
   Si el núcleo redondea distinto, manda el núcleo: ajusta el port, no el test de Freddy.
5. **Pantalla de recibo** (`app/src/pantallas/Recibo.tsx`):
   - placa, puesto y calle; hora de llegada y de salida en `America/Guayaquil`;
   - minutos reales, minutos cobrados, débito y saldo restante (`GET /billetera/{usuario_id}`);
   - "Con la tarjeta SERT habrías pagado $X (N bloques de 30 min). Ahorraste $Z". Si el ahorro
     es ≤ 0, "Pagaste lo mismo que con la tarjeta";
   - motivo: "Detectamos que te fuiste" (`deteccion`), "Cerraste la sesión" (`manual`) o "Cierre
     por falta de señal" (`timeout_sin_senal`, si Freddy lo aprueba);
   - los montos que se muestran son **los del servidor**; `tarifa.ts` solo calcula la tarjeta y
     una comprobación: si difiere en más de $0,01, `console.warn`;
   - botón "¿No te fuiste? Avísanos", que guarda el caso en `AsyncStorage` para revisarlo en S4.
6. **Modo mock:** con `EXPO_PUBLIC_MOCK=1`, `cierreMock.ts` emite el mensaje `sesion` 20 s después
   de confirmar la llegada, con cifras coherentes con `tarifa.ts`.
7. Paraleliza: un subagente escribe `tarifa.ts` y sus tests mientras tú haces el seguimiento y la
   pantalla. Prueba con el backend real cerrando la sesión a mano con
   `curl -X POST .../api/v1/sesiones/<id>/cerrar` y comprueba que la app reacciona.
8. **Evidencia** `evidencias/s1_recibo.png`: pide al usuario la captura del recibo en un iPhone y,
   si se puede, en el Android; si hay dos, únelas lado a lado con Pillow.

## Dónde escribir
`semanas/S3/Miguel/codigo/app/` y `evidencias/`.

## Hecho cuando
- [ ] `npx jest app/src/logica` pasa con los casos de arriba.
- [ ] En modo mock, la app pasa de la sesión activa al recibo sola en ≤ 10 s tras el cierre.
- [ ] Con el backend real, un cierre por `curl` muestra el recibo una sola vez (sin navegación
  doble).
- [ ] El recibo muestra la comparación con la tarjeta SERT con montos del servidor.
- [ ] Existe `s1_recibo.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 1, Miguel). En "Pedidos a otros":
@Freddy, el mensaje WS `sesion` debe traer `minutos_reales`, `minutos_cobrados`, `debitado` y
`costo_tarjeta`, y llegar solo al dueño de la sesión.
