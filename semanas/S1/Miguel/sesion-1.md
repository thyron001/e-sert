---
semana: S1
persona: Miguel
sesion: 1
titulo: Proyecto Expo, navegación y cliente API
horas: 3-4
modulo: app
depende: []
entrega: [app/, app/src/api/cliente.ts, app/src/api/mock.ts, app/README.md]
evidencias: [s1_app-pantallas.png]
---
# S1 · Sesión 1 · Miguel 🔴: Proyecto Expo, navegación y cliente API

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección App Expo) y `docs/CONTRATO.md` (secciones 4 y
6). El equipo tiene 3 iPhone y 1 Android, así que se usa **Expo (React Native) con Expo
Go**, sin cuenta de desarrollador de Apple. El backend de Freddy todavía no existe: la app
arranca con un **mock** que responde igual que el contrato, y luego se cambia a la API real
con una variable.

## Objetivo
Crear el proyecto Expo con TypeScript, la navegación y las pantallas base, y un cliente de
API tipado contra el contrato, con modo mock. Debe abrirse en un iPhone y en un Android.

## Pasos
1. Crea `app/` con `npx create-expo-app@latest app --template tabs`, que usa TypeScript y
   `expo-router`.
   - Fija la versión del SDK de Expo en `app/README.md`.
   - Quita las pantallas de ejemplo.
2. Crea las pestañas de `expo-router`:
   - `index` (Mapa): mapa del Centro con los puestos;
   - `sesion`: sesión activa;
   - `billetera`;
   - `grabador`: se usa en la sesión 2;
   - `ajustes`: URL del backend, modo mock activado o desactivado, y un `usuario_id`
     generado con `expo-crypto` `randomUUID()` y guardado en `expo-secure-store`.
3. Mapa: usa `react-native-maps`, que funciona en Expo Go.
   - Región inicial: el Parque Calderón (-2.8975, -79.0045).
   - Dibuja los puestos de `GET /puestos` como círculos verdes si `ocupados < capacidad` y
     rojos si no.
4. `app/src/api/tipos.ts`: copia los tipos de `comun/esquemas.ts` de Freddy. Léelos de su
   rama si aún no están en `proyecto/`; si no existen, escríbelos desde `docs/CONTRATO.md` y
   marca `// SINCRONIZAR con comun/esquemas.ts`.
5. `app/src/api/cliente.ts`: funciones tipadas para cada endpoint de la sección 4.
   - La URL base sale de `EXPO_PUBLIC_API_URL` o de los ajustes.
   - Header `X-Contrato-Version: 1`.
   - Maneja errores con el formato `{error:{codigo,mensaje}}`.
6. `app/src/api/mock.ts`: la misma interfaz, con 20 puestos falsos alrededor del Parque
   Calderón, una billetera en memoria que aplica la tarifa del contrato (bloque mínimo,
   fracciones de 5 min) y una latencia simulada de 300 ms. El interruptor está en Ajustes.
7. `app/README.md` explica cómo correrla:
   - `npx expo start`;
   - escanear el QR con Expo Go;
   - si el teléfono no está en la misma red, `npx expo start --tunnel`.
8. Prueba en **un iPhone y un Android** (pide a un compañero el Android si hace falta).
   Anota en la bitácora cualquier diferencia de permisos o de mapa.
9. **Evidencia** `evidencias/s1_app-pantallas.png`: pide al usuario capturas del teléfono
   del Mapa y de Ajustes, y únelas en una sola imagen con Pillow (lado a lado, con un rótulo
   de iOS o Android).

## Dónde escribir
`semanas/S1/Miguel/codigo/app/`. No subas `node_modules/` ni `.expo/` (revisa
`.gitignore`).

## Hecho cuando
- [ ] La app abre en Expo Go en iOS y en Android, con las 5 pestañas navegables.
- [ ] El mapa muestra los puestos del mock en sus colores.
- [ ] `cliente.ts` y `mock.ts` cumplen la misma interfaz TypeScript, y `npx tsc --noEmit`
  pasa sin errores.
- [ ] Existe la evidencia PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 1, Miguel).
