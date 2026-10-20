---
semana: S1
persona: Miguel
sesion: 2
titulo: Grabador de sensores etiquetado
horas: 3-4
modulo: app
depende: [S1-Miguel-1]
entrega: [app/app/(tabs)/grabador.tsx, app/src/sensores/grabador.ts, app/src/sensores/exportar.ts, datos/herramientas/graficar_grabacion.py]
evidencias: [s2_grabador-pantalla.png, s2_primera-grabacion.png]
---
# S1 · Sesión 2 · Miguel 🔴: Grabador de sensores etiquetado

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (sección 7, formato de trazas). Esto arregla la debilidad
principal del plan original: **evaluar el clasificador con datos reales de Cuenca**, no solo
con datos inventados por SUMO. Pablo usará estas grabaciones como conjunto de prueba en S2.
El caso que ningún dataset trae, *auto en tráfico lento a velocidad de peatón*, solo lo
pueden grabar ustedes.

## Objetivo
Una pantalla para grabar sesiones etiquetadas de GPS (1 Hz) y acelerómetro (10 Hz) que
exporte CSV en el formato exacto del contrato.

## Pasos
1. `app/src/sensores/grabador.ts`:
   - Pide permisos con `Location.requestForegroundPermissionsAsync()`.
   - GPS: `Location.watchPositionAsync({accuracy: Location.Accuracy.BestForNavigation, timeInterval: 1000, distanceInterval: 0})`.
     Guarda `t`, lat/lon, `coords.accuracy` como `precision_m` y `coords.speed` como
     `velocidad_mps`. Si `speed` es nulo o −1, deja el campo vacío.
   - Acelerómetro: `Accelerometer.setUpdateInterval(100)` de `expo-sensors`, guardado en un
     archivo aparte (`t,ax,ay,az`) por si se usa luego.
   - Mantén la pantalla encendida con `expo-keep-awake`. En iPhone, Expo Go no graba en
     segundo plano.
   - Guarda en memoria y vuelca a disco cada 30 s con `expo-file-system`, para no perder
     datos si la app se cierra.
2. Pantalla `grabador`:
   - Selector de etiqueta: `a_pie`, `quieto`, `vehiculo` y **`vehiculo_lento`** (se exporta
     como `modo_real=vehiculo` con la columna extra `escenario=trafico_lento`).
   - Selector de quién graba (Tyrone, Freddy, Pablo o Miguel) y de teléfono (iOS o Android).
   - Botones grandes Iniciar y Detener.
   - Contador de muestras, precisión GPS actual y duración.
   - **Cambio de etiqueta en caliente** sin detener la grabación (por ejemplo, al bajarse
     del auto), registrando el instante del cambio.
3. `app/src/sensores/exportar.ts` exporta `<fecha>_<persona>_<telefono>.csv` con las
   columnas exactas del contrato
   (`usuario_id,t,lat,lon,precision_m,velocidad_mps,modo_real`) más `escenario,telefono,persona`,
   y lo comparte con `expo-sharing` para mandarlo por correo o Drive.
4. `datos/herramientas/graficar_grabacion.py` (Python):
   - lee un CSV exportado y valida las columnas contra el contrato;
   - dibuja la traza coloreada por etiqueta y la velocidad en el tiempo con las franjas de
     etiqueta;
   - reporta la duración por etiqueta y la precisión media.
5. **Prueba real corta:** graba 5 min caminando y 5 min quieto, exporta y grafica.
6. **Evidencias:**
   - `s2_grabador-pantalla.png`: captura de la pantalla de grabación.
   - `s2_primera-grabacion.png`: la salida del script de graficado.

## Dónde escribir
`semanas/S1/Miguel/codigo/app/` y `semanas/S1/Miguel/codigo/datos/`.

## Hecho cuando
- [ ] La grabación funciona en iOS y Android; el CSV tiene las columnas del contrato y una
  frecuencia de unos 1 Hz.
- [ ] El cambio de etiqueta en caliente queda reflejado en el CSV.
- [ ] El script de graficado valida y dibuja la prueba real.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S1, sesión 2, Miguel). En "Pedidos a
otros": todo el grupo debe instalar Expo Go para la jornada de grabación de la sesión 3.
