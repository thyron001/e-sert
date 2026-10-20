---
semana: S2
persona: Miguel
sesion: 1
titulo: Flujo de sesión de parqueo en la app - buscar, guiar, confirmar y activa
horas: 3-4
modulo: app
depende: [S1-Miguel-1, S2-Freddy-1]
entrega: [app/app/buscar.tsx, app/app/sesion/guiar.tsx, app/app/sesion/confirmar.tsx, app/app/sesion/activa.tsx, app/src/api/cliente.ts, app/src/estado/sesion.ts, app/src/contrato/, app/__tests__/]
evidencias: [s1_flujo-sesion.png]
---
# S2 · Sesión 1 · Miguel 🔴: Flujo de sesión de parqueo en la app (buscar → guiar → confirmar → activa)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (reglas de cobro) y `docs/CONTRATO.md` (secciones 3, 4 y
5). Es la primera sesión de S2: copia `proyecto/app/` a `semanas/S2/Miguel/codigo/app/` si
aún no existe la copia (sin `node_modules/`). La API real de Freddy se hace esta misma semana
(S2-1): léela de `proyecto/backend/` o de `origin/freddy/s2` y, mientras no responda, usa el
cliente mock de S1-1, marcado `// MOCK`. Los tipos vienen de `proyecto/comun/esquemas.ts`.
**Todo es simulado:** el teléfono no se mueve ni hace pruebas en la calle; el avance hacia el
puesto se simula en la app (y en S2-3 el modo espejo sigue a un auto de SUMO).

## Objetivo
El flujo completo de una sesión en Expo Go: elegir destino, recibir un puesto, llegar
guiado, confirmar placa y puesto, y ver la sesión activa con su costo en vivo.

## Pasos
1. **Contrato en la app**: copia `proyecto/comun/esquemas.ts` y `tarifa.json` a
   `app/src/contrato/` con la cabecera `// Copia de comun/, no editar a mano` (Metro no
   resuelve bien rutas fuera del proyecto). Añade `npm run verificar-contrato`, que compara
   el *hash* con el original y falla si difieren.
2. **Cliente API** `app/src/api/cliente.ts`: base `process.env.EXPO_PUBLIC_API_URL` (por
   ejemplo `http://192.168.1.20:8000/api/v1`, nunca `localhost` en el teléfono);
   `EXPO_PUBLIC_USE_MOCK=1` activa el mock. Funciones tipadas `getGuia`, `crearSesion`,
   `getSesion`, `cerrarSesion`, `getBilletera`; *timeout* de 8 s con `AbortController`; los
   errores `{"error": {"codigo", "mensaje"}}` se convierten en `ErrorApi` con mensajes en
   español para el usuario (`SALDO_INSUFICIENTE` → "Recarga al menos $5 para buscar puesto").
3. **Estado** `app/src/estado/sesion.ts` (zustand o `useReducer` + Context) con los estados
   del contrato que ve el usuario (`BUSCANDO`, `GUIADO`, `ESTACIONADO`…) y persistencia con
   `@react-native-async-storage/async-storage`, para que recargar la app no pierda la sesión.
4. **Pantallas** con `expo-router`:
   - `buscar.tsx`: punto de partida simulado (pulsación en el mapa o, por defecto, una esquina
     del Centro como Gran Colombia y Benigno Malo); no se usa el GPS del teléfono; destino desde una lista
     (copia de `destinos.csv` de Tyrone) o pulsación larga en el mapa (`react-native-maps`,
     que funciona en Expo Go). Antes de `GET /guia`, consulta la billetera: si
     `disponible < bloque mínimo`, lleva a la recarga (S2-2; por ahora una pantalla
     "Próximamente").
   - `sesion/guiar.tsx`: mapa con la posición simulada, el puesto y la línea recta
     (`Polyline`); un temporizador a 1 Hz avanza la posición hacia el puesto a ~8 m/s
     (`simularAvance`, con botón "Llegar ya" para la demo); distancia *haversine* en vivo. Si
     `distancia < 25 m`, pasa a confirmar. Limpia el `setInterval` al salir.
   - `sesion/confirmar.tsx`: placa con validación ecuatoriana
     `^[A-Z]{3}-?\d{3,4}$` (mayúsculas automáticas), puesto prellenado y editable;
     `POST /sesiones` → muestra `retenido`.
   - `sesion/activa.tsx`: cronómetro, minutos cobrables y costo acumulado calculados con
     `tarifa.json` (fracciones de 5 min, cobro mínimo), retenido, aviso del tope de tiempo y
     botón "Terminar" (`POST /sesiones/{id}/cerrar`, `motivo: "manual"`). El cierre
     automático es de S3.
5. **Tests** (`jest-expo`): validador de placa (válidas `ABC-1234`, `ABC123`; inválidas
   `AB-123`, `abc1234x`), cálculo de costo (12 min → 15 min cobrados, 3 → 10) idéntico al de
   Freddy, y cliente con `fetch` simulado para cada código de error.
   Delega en un subagente los tests y el script `verificar-contrato` mientras haces las
   pantallas.
6. Prueba en Expo Go (`npx expo start`; `--tunnel` si la red de la universidad bloquea) en
   un iPhone y en el Android, contra el backend real si ya existe, con el teléfono quieto en la
   mano: todo el recorrido es simulado.
7. **Evidencia** `evidencias/s1_flujo-sesion.png`: pide al usuario 4 capturas del teléfono
   (buscar, guiar, confirmar, activa) y únelas en una tira horizontal con Pillow, con un
   script `app/scripts/montaje.py` que también usarás en S2-2.

## Dónde escribir
`semanas/S2/Miguel/codigo/app/` y `semanas/S2/Miguel/evidencias/`. El `.env` local con
`EXPO_PUBLIC_API_URL` no se sube; deja un `.env.example`.

## Hecho cuando
- [ ] El flujo buscar → guiar → confirmar → activa funciona en Expo Go en iPhone y Android.
- [ ] Funciona con el backend real o, si aún no existe, con el mock (indica cuál en la
  bitácora).
- [ ] Recargar la app con una sesión activa la recupera.
- [ ] `npm test` y `npm run verificar-contrato` pasan.
- [ ] Existe la evidencia `s1_flujo-sesion.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 1, Miguel). En "Pedidos a
otros": @Freddy, cualquier diferencia entre la API real y el contrato; @Tyrone, si
`destinos.csv` sirve como lista de destinos de la app.
