# App e-sert (Expo) · Miguel 🔴

App móvil del proyecto e-sert: mapa de puestos SERT, sesión de parqueo, billetera, grabador de
sensores y ajustes. Se prueba con **Expo Go** (3 iPhone y 1 Android, sin cuenta de Apple).

## Versiones fijadas

| Pieza | Versión |
|---|---|
| **Expo SDK** | **58** (`expo ~58.0.17`) |
| React Native | 0.88.0 |
| React | 19.3.0 |
| expo-router | ~58.0.25 |
| react-native-maps | 1.29.11 |
| TypeScript | ~6.0.3 |

Expo Go en el teléfono tiene que ser la versión compatible con el **SDK 58**. Si la tienda
trae una más nueva y el QR dice "incompatible", actualiza el proyecto con
`npx expo install expo@latest --fix`. No mezcles versiones a mano.

Para añadir librerías usa siempre `npx expo install <paquete>`, no `npm install`, para que
la versión cuadre con el SDK.

## Cómo correrla

```bash
cd semanas/S1/Miguel/codigo/app   # en proyecto/app/ después de la unificación
npm install
npx expo start
```

1. Instala **Expo Go** en el teléfono (App Store o Play Store).
2. Escanea el QR que imprime la terminal:
   - iPhone: con la cámara;
   - Android: desde Expo Go, con "Scan QR code".
3. El teléfono y la computadora tienen que estar en **la misma red Wi-Fi**. Si no lo están,
   o si la red del aula bloquea el tráfico entre equipos:

   ```bash
   npx expo start --tunnel
   ```

## Backend: mock o API real

- **Modo mock** (por defecto mientras no exista el backend de Freddy): un backend falso en
  memoria (`src/api/mock.ts`) con 20 puestos alrededor del Parque Calderón, una billetera
  con $5 iniciales y la tarifa del contrato, y 300 ms de latencia simulada.
- **API real:** en la pestaña **Ajustes**, apaga "Modo mock". La URL base sale de
  `EXPO_PUBLIC_API_URL` y se puede cambiar en Ajustes. El cliente le añade `/api/v1`.

  ```bash
  EXPO_PUBLIC_API_URL=https://demo.e-sert.tesisucuenca.com npx expo start
  # o un backend local: EXPO_PUBLIC_API_URL=http://<ip-de-la-laptop>:8000
  ```

## Estructura

```
app/                      rutas de expo-router (cada archivo es una pantalla)
  _layout.tsx             raíz: AjustesProveedor + tema
  (tabs)/_layout.tsx      las 5 pestañas
  (tabs)/index.tsx        Mapa: puestos en verde (con espacio) o rojo (llenos)
  (tabs)/sesion.tsx       sesión activa (confirmar llegada / cerrar a mano)
  (tabs)/billetera.tsx    saldo, retenido, disponible, movimientos y recarga de prueba
  (tabs)/grabador.tsx     grabador de sensores etiquetado (GPS 1 Hz + acelerómetro 10 Hz)
  (tabs)/ajustes.tsx      URL del backend, modo mock, usuario_id
src/api/tipos.ts          tipos del contrato e interfaz ApiESert  (SINCRONIZAR con comun/esquemas.ts)
src/api/tarifa.ts         tarifa del contrato y cálculo de cobro   (SINCRONIZAR con comun/tarifa.json)
src/api/cliente.ts        cliente HTTP real (fetch, X-Contrato-Version: 1, errores {error:{codigo,mensaje}})
src/api/mock.ts           backend falso en memoria con la misma interfaz ApiESert
src/api/pruebas/          prueba del mock que corre en la computadora
src/sensores/grabador.ts  clase Grabador: permisos, GPS, acelerómetro, keep-awake, volcado cada 30 s
src/sensores/formato.ts   columnas y filas del CSV del contrato (sin dependencias nativas)
src/sensores/exportar.ts  archivos en el teléfono, lista de grabaciones y compartir (expo-sharing)
src/sensores/pruebas/     prueba del formato y generador de una grabación sintética
src/ajustes/              contexto de ajustes (expo-secure-store + expo-crypto)
```

## Comprobaciones

```bash
npx tsc --noEmit          # tipos: cliente.ts y mock.ts cumplen la interfaz ApiESert
npm run prueba:mock       # tarifa, billetera y puestos del mock
npm run prueba:grabador   # formato del CSV de grabaciones
npx expo-doctor           # dependencias compatibles con el SDK
```

## Grabador (pestaña Grabador)

1. Elige quién graba, el teléfono y la etiqueta, y pulsa **Iniciar**. La primera vez acepta el permiso de ubicación.
2. Durante la grabación la etiqueta se puede cambiar sin detener: por ejemplo, de "Vehículo" a
   "A pie" al bajarse del auto. Cada cambio queda con su hora.
3. **Detener** y luego **Compartir** (CSV del GPS) o **Acel.** (CSV del acelerómetro).
4. Mantén la pantalla abierta: en iPhone, Expo Go no graba en segundo plano.
5. Las etiquetas de vehículo las graba **el acompañante**, nunca quien maneja.

Formato y herramientas: ver `../datos/README.md`.

**Prueba en el simulador de iOS (solo en desarrollo):** la pantalla acepta deep links para
manejarla sin tocar la pantalla. Por ejemplo:
`xcrun simctl openurl booted "exp://<ip>:8081/--/grabador?accion=iniciar&etiqueta=a_pie&n=1"`,
donde `accion` puede ser `iniciar`, `etiqueta` o `detener`. La ubicación se simula con
`xcrun simctl location booted start --speed=1.4 -`, pasando los puntos por stdin.
