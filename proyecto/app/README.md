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
cd semanas/S2/Miguel/codigo/app   # en proyecto/app/ después de la unificación
npm install
cp .env.example .env              # y pon la IP de la computadora con el backend
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

Las variables van en `.env` (no se sube; la plantilla es `.env.example`):

```bash
EXPO_PUBLIC_API_URL=http://<ip-de-la-computadora>:8000/api/v1   # nunca localhost en el teléfono
EXPO_PUBLIC_USE_MOCK=0                                          # 1 = mock en memoria
```

- **Modo mock:** backend falso en memoria (`src/api/mock.ts`, marcado `// MOCK`) con 20
  puestos alrededor del Parque Calderón, una billetera con $5 iniciales y la tarifa del
  contrato, y 300 ms de latencia simulada.
- **API real:** el backend de Freddy (`uvicorn backend.api.main:app --host 0.0.0.0 --port 8000`).
  Toda billetera nueva empieza en $0: la app lleva a **Recarga**, que por ahora tiene una
  "recarga de prueba" sin pago (Payphone llega en S2-2).
- Ajustes guarda la URL y el modo mock en el teléfono: lo guardado manda sobre `.env`.
- `npm run probar-backend -- http://<ip>:8000/api/v1` recorre el flujo completo con el cliente
  HTTP real desde la computadora (sale con código 1 si algo no cumple el contrato).

## Flujo de sesión (S2-1): buscar → guiar → confirmar → activa

Todo es simulado: el teléfono no se mueve ni usa el GPS.

1. **Sesión → Buscar puesto** (`app/buscar.tsx`): partida por defecto en la esquina de la Gran
   Colombia y Benigno Malo (tocar el mapa la mueve), destino de `destinos.csv` de Tyrone o
   pulsación larga en el mapa. Consulta la billetera y, si `disponible` < retención, va a Recarga;
   si no, `GET /guia`.
2. **Guiado** (`app/sesion/guiar.tsx`): la posición avanza sola a 8 m/s en línea recta hacia el
   puesto (1 Hz); "Llegar ya" salta al puesto. A menos de 25 m pasa a confirmar.
3. **Confirmar** (`app/sesion/confirmar.tsx`): placa con la regla del contrato
   `^[A-Z]{3}-?\d{3,4}$` y puesto editable; `POST /sesiones` retiene $0.25.
4. **Activa** (`app/sesion/activa.tsx`): cronómetro, minutos cobrables, costo con `tarifa.json`,
   avisos de tope y saldo, y "Terminar" (`POST /sesiones/{id}/cerrar`, `motivo: "manual"`).

El estado (`src/estado/sesion.ts`, `useReducer` + Context) se guarda en AsyncStorage: al
reabrir la app vuelve al guiado o a la sesión activa.

En desarrollo, las pantallas se pueden manejar desde la terminal (simulador de iPhone):
`xcrun simctl openurl booted "exp://<ip>:8081/--/buscar?destino=0&auto=1"` y
`.../sesion/confirmar?placa=ABC-1234&auto=1`.

## Estructura

```
app/                      rutas de expo-router (cada archivo es una pantalla)
  _layout.tsx             raíz: AjustesProveedor + SesionProveedor + tema; recupera el flujo al abrir
  buscar.tsx              partida simulada, destino y GET /guia
  recarga.tsx             "Próximamente" + recarga de prueba (Payphone en S2-2)
  sesion/guiar.tsx        guiado simulado a 8 m/s con Polyline y distancia haversine
  sesion/confirmar.tsx    placa + puesto → POST /sesiones
  sesion/activa.tsx       cronómetro, costo en vivo, Terminar
  (tabs)/_layout.tsx      las 5 pestañas
  (tabs)/index.tsx        Mapa: puestos en verde (con espacio) o rojo (llenos)
  (tabs)/sesion.tsx       entrada al flujo de parqueo (o continuar el que esté en curso) y modo espejo
  (tabs)/billetera.tsx    saldo, retenido, disponible, movimientos y recarga de prueba
  (tabs)/grabador.tsx     grabador de sensores etiquetado (GPS 1 Hz + acelerómetro 10 Hz)
  (tabs)/ajustes.tsx      URL del backend, modo mock, usuario_id
src/contrato/             copia de comun/esquemas.ts y comun/tarifa.json (npm run verificar-contrato)
src/api/tipos.ts          reexporta el contrato + ErrorApi, ApiESert y tipos estrictos del espejo
src/api/tarifa.ts         TARIFA = src/contrato/tarifa.json y fórmulas de cobro
src/api/cliente.ts        cliente HTTP (8 s, X-Contrato-Version: 1), getGuia/crearSesion/getSesion/cerrarSesion/getBilletera, mensajes en español
src/api/mock.ts           backend falso en memoria con la misma interfaz ApiESert
src/api/pruebas/          prueba del mock que corre en la computadora
src/sensores/grabador.ts  clase Grabador: permisos, GPS, acelerómetro, keep-awake, volcado cada 30 s
src/sensores/formato.ts   columnas y filas del CSV del contrato (sin dependencias nativas)
src/sensores/exportar.ts  archivos en el teléfono, lista de grabaciones y compartir (expo-sharing)
src/sensores/pruebas/     prueba del formato y generador de una grabación sintética
src/espejo/recorridoMock.ts   MOCK del WS /ws/espejo: recorrido de ~60 s (BUSCANDO → CERRADA con recibo)
src/espejo/recorrido_mock.json el mismo recorrido en JSON (npm run generar-mock), para el servidor mock de S2-3
src/espejo/validar.ts     validadores en tiempo de ejecución (esMensajeEspejo, esFinEspejo)
src/espejo/componentes/   MapaEspejo, LineaTiempo, CostoVivo, BannerAvisos, ReciboEspejo
app/espejo/index.tsx      selector de conductor simulado
app/espejo/[vehId].tsx    pantalla del conductor espejo
docs/sert_reglas.md       reglas SERT verificadas con fuentes y tabla para tarifa.json
src/ajustes/              contexto de ajustes (expo-secure-store + expo-crypto)
src/estado/sesion.ts      estado del flujo (useReducer + Context) persistido en AsyncStorage
src/sesion/               placa.ts, geo.ts (haversine, simularAvance), cobro.ts (costo en vivo y avisos)
src/datos/destinos.ts     copia de proyecto/sumo/demanda/destinos.csv (python3 scripts/destinos.py)
scripts/montaje.py        une capturas en una tira horizontal (evidencias)
__tests__/                placa, tarifa (igual a tarifa.py), cliente (15 códigos), mock, estado, cobro
```

## Comprobaciones

```bash
npm test                  # jest: todos los tests (__tests__/ y src/espejo)
npm run verificar-contrato # hash de src/contrato/ = proyecto/comun/
npm run probar-backend -- http://<ip>:8000/api/v1  # flujo contra el backend real
npx tsc --noEmit          # tipos: cliente.ts y mock.ts cumplen la interfaz ApiESert
npm run prueba:mock       # tarifa, billetera y puestos del mock
npm run prueba:grabador   # formato del CSV de grabaciones
npx jest src/espejo       # recorrido mock del espejo contra CONTRATO §6b (jest-expo)
npm run generar-mock      # regenera src/espejo/recorrido_mock.json
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

## Modo espejo (teléfono = pantalla de un conductor simulado)

En la pestaña **Sesión**, el botón **Modo espejo** abre la lista de conductores simulados. Al
elegir uno, el teléfono reproduce lo que vería ese conductor:
- guiado al puesto, con la ruta en el mapa;
- la sesión, con el costo en vivo y los avisos;
- la línea de tiempo de los 7 estados;
- el recibo, con la comparación frente a la tarjeta SERT.

Por ahora los datos salen de un recorrido **mock** de unos 60 s (`src/espejo/recorridoMock.ts`). Cuando
exista el backend (S2-3), `suscribirMock` se reemplaza por el cliente del WebSocket
`/ws/espejo/{veh_id}`, que tiene la misma firma.
