---
semana: S3
persona: Miguel
sesion: 2
titulo: Avisos de saldo bajo, tiempo máximo y bloqueo por saldo negativo
horas: 3-4
modulo: app
depende: [S3-Miguel-1, S2-Miguel-2]
entrega: [app/src/logica/calcularAvisos.ts, app/src/logica/__tests__/calcularAvisos.test.ts, app/src/servicios/avisos.ts, app/src/pantallas/Bloqueo.tsx]
evidencias: [s2_avisos.png]
---
# S3 · Sesión 2 · Miguel 🔴: Avisos de saldo bajo, tiempo máximo y bloqueo por saldo negativo

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro 1, 4 y 5) y tu bitácora de S3-1. El núcleo de
Freddy ya calcula avisos (`ServicioSesiones.avisos`, S1-Freddy-2) y rechaza sesiones con
`SESIONES_BLOQUEADAS`; la app debe **anticiparse** y avisar con notificaciones locales. Recuerda la
limitación de iPhone: en segundo plano la app hace poco, así que además de la notificación se
muestra un aviso dentro de la app.

## Objetivo
Avisar a tiempo cuando el saldo cubre menos de 10 min, antes de llegar al tope SERT, y bloquear
nuevas sesiones con saldo negativo hasta recargar.

## Pasos
1. Instala con `npx expo install expo-notifications`. En Expo Go **funcionan las notificaciones
   locales**, no las *push* remotas: usa solo locales.
   - permisos con `Notifications.requestPermissionsAsync()` al iniciar la primera sesión;
   - Android: canal `Notifications.setNotificationChannelAsync("avisos", { importance: AndroidImportance.HIGH })`;
   - `Notifications.setNotificationHandler` para mostrarlas también en primer plano (usa los
     nombres de campos de la versión instalada del SDK, por ejemplo `shouldShowBanner`).
2. **Lógica pura** (`app/src/logica/calcularAvisos.ts`):
   `calcularAvisos(sesion, billetera, tarifa, ahora) -> Aviso[]`, con
   `Aviso = { tipo, cuando: Date, titulo, cuerpo }`:
   - `saldo_bajo`: `minutosCubiertos = disponible / (valor_hora_usd / 60)`; avisa en
     `inicio + minutosCubiertos − aviso_saldo_min` (10 min);
   - `tiempo_maximo`: avisa 10 min antes de `inicio + tiempo_maximo_min`. Pide a Freddy un
     parámetro `aviso_tope_antes_min` en `tarifa.json`; mientras tanto usa 10 como constante;
   - si dos avisos caen a menos de 1 min, se combinan en uno;
   - avisos con `cuando` en el pasado se disparan de inmediato.
3. **Programación** (`app/src/servicios/avisos.ts`):
   - al confirmar la llegada, programa con `Notifications.scheduleNotificationAsync({ content,
     trigger: { type: SchedulableTriggerInputTypes.DATE, date } })` y guarda los IDs;
   - al cerrar la sesión, `cancelScheduledNotificationAsync(id)` para cada uno;
   - tras una recarga, cancela y reprograma;
   - en primer plano, banner propio dentro de la app con el mismo texto.
4. **Bloqueo** (`app/src/pantallas/Bloqueo.tsx`):
   - si la billetera tiene `saldo < 0` o `POST /sesiones` devuelve `SESIONES_BLOQUEADAS`, el botón
     "Buscar puesto" se desactiva y se muestra la deuda con el botón "Recargar" (flujo Payphone de
     prueba de S2-Miguel-2);
   - regla 1: si el disponible es menor que el bloque mínimo, pide recargar al menos $5;
   - tras recargar, vuelve a consultar la billetera y desbloquea si corresponde.
5. **Tests** (`calcularAvisos.test.ts`, Jest con `jest.useFakeTimers()`):
   - disponible $0,25 (30 min) → `saldo_bajo` a los 20 min;
   - disponible $1,00 (120 min) con tope 120 → los dos avisos a los 110 min se combinan en uno;
   - saldo −$0,20 → bloqueado; recarga de $5 → desbloqueado;
   - al cerrar, no queda ninguna notificación programada (mock de `expo-notifications`);
   - recargar a mitad de la sesión mueve el aviso de saldo bajo.
6. **Modo demo:** `EXPO_PUBLIC_ESCALA_TIEMPO=60` hace que 1 min de la regla dure 1 s, para mostrar
   los avisos en la exposición sin esperar.
7. Un subagente puede escribir los tests de `calcularAvisos` (lógica pura) mientras tú integras
   `expo-notifications` y la pantalla de bloqueo.
8. **Evidencia** `evidencias/s2_avisos.png`: pide al usuario tres capturas del teléfono (saldo
   bajo, tope próximo y bloqueo) y únelas en una sola imagen con Pillow.

## Dónde escribir
`semanas/S3/Miguel/codigo/app/` y `evidencias/`.

## Hecho cuando
- [ ] `npx jest app/src/logica` pasa, incluidos los casos de arriba.
- [ ] En el teléfono, con la escala de tiempo de demo, llegan los avisos de saldo bajo y de tope.
- [ ] Cerrar la sesión cancela todas las notificaciones pendientes.
- [ ] Con saldo negativo no se puede iniciar sesión y, tras recargar, sí.
- [ ] Existe `s2_avisos.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 2, Miguel). En "Pedidos a otros":
@Freddy, agrega `aviso_tope_antes_min` a `tarifa.json` y expón los avisos del núcleo en
`GET /sesiones/{id}`.
