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
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro) y `docs/CONTRATO.md` (secciones 3, 4 y 6b). Es
la primera sesión de S3: copia `proyecto/app/` a `semanas/S3/Miguel/codigo/app/` si no está, y
respeta su estructura (si las pantallas viven en otra carpeta, usa esa y ajusta las rutas). El
backend se lee desde `proyecto/backend/`. **Todo es simulado:** el cierre automático no lo
detecta el GPS del teléfono, lo dispara **la simulación**. El controlador TraCI detecta la salida
del auto (SALIENDO → CERRADA) y el teléfono espejo lo recibe por `WS /ws/espejo/{veh_id}` (6b),
con `recibo` en el mensaje de `CERRADA`. Freddy publica el espejo esta semana (S3-Freddy-3);
mientras no esté, usa el servidor mock de S2-3 a través de `app/src/mocks/cierreMock.ts`, marcado
`// MOCK: reemplazar cuando Freddy publique WS /ws/espejo (S3-3)`.

## Objetivo
Que la app pase sola al recibo cuando la simulación cierra la sesión del conductor espejo (sin
que el usuario toque nada), muestre un recibo claro y le diga cuánto habría pagado con la tarjeta
SERT.

## Pasos
1. **Seguimiento de la sesión** (`app/src/servicios/seguimientoSesion.ts`):
   - en modo espejo, usa el `SocketEspejo` de S2-3 (reconexión incluida) y vigila `estado` y
     `recibo` de los mensajes `espejo`; `espejo_fin` sin recibo muestra "El auto salió de la
     simulación";
   - respaldo: `GET /sesiones/{sesion.sesion_id}` cada 10 s si el WS está caído;
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
   - motivo: "La simulación detectó que te fuiste" (`deteccion`), "Cerraste la sesión" (`manual`)
     o "Cierre por falta de señal" (`timeout_sin_senal`, si Freddy lo aprueba);
   - en modo espejo, las cifras salen de `recibo` (`minutos_reales`, `minutos_cobrados`,
     `cobrado_usd`, `tarjeta_sert_usd`, `ahorro_usd`);
   - los montos que se muestran son **los del servidor**; `tarifa.ts` solo calcula la tarjeta y
     una comprobación: si difiere en más de $0,01, `console.warn`;
   - botón "¿No te fuiste? Avísanos", que guarda el caso en `AsyncStorage` para revisarlo en S4.
6. **Modo mock:** con `EXPO_PUBLIC_MOCK=1`, `cierreMock.ts` reproduce el recorrido de S1-3/S2-3 y
   emite `CERRADA` con `recibo` 20 s después de ESTACIONADO, con cifras coherentes con `tarifa.ts`.
7. Paraleliza: un subagente escribe `tarifa.ts` y sus tests mientras tú haces el seguimiento y la
   pantalla. Prueba con la simulación de Freddy siguiendo un auto hasta que salga, y además
   cerrando una sesión a mano con `curl -X POST .../api/v1/sesiones/<id>/cerrar`; comprueba que la
   app reacciona en ambos casos.
8. **Evidencia** `evidencias/s1_recibo.png`: pide al usuario la captura del recibo en un iPhone y,
   si se puede, en el Android; si hay dos, únelas lado a lado con Pillow.

## Dónde escribir
`semanas/S3/Miguel/codigo/app/` y `evidencias/`.

## Hecho cuando
- [ ] `npx jest app/src/logica` pasa con los casos de arriba.
- [ ] En modo mock, la app pasa de la sesión activa al recibo sola en ≤ 10 s tras el cierre.
- [ ] Con el backend real (o el mock de S2-3), el cierre que dispara la simulación y un cierre por
  `curl` muestran el recibo una sola vez cada uno (sin navegación doble).
- [ ] El recibo muestra la comparación con la tarjeta SERT con montos del servidor.
- [ ] Existe `s1_recibo.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 1, Miguel). En "Pedidos a otros":
@Freddy, el mensaje `espejo` de `CERRADA` debe traer `recibo` completo (6b) y `sesion.sesion_id`,
y `GET /sesiones/{id}` debe reflejar el cierre que hace la simulación.
