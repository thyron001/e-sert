# Contexto del proyecto (definido en claude.ai, 2026-10-19)

Proyecto de Redes Vehiculares (Universidad de Cuenca): SUMO + TraCI + IA aplicado al
parqueo tarifado SERT del Centro Histórico de Cuenca.

**Nombre (propuestas):** CuadraLibre, SERT+ o ParqueaYa.

**Objetivo:** reducir el tiempo, la distancia y las emisiones de buscar parqueo en la zona
SERT, con una app que detecta la llegada y la salida reales del auto, construye un mapa de
ocupación en vivo, guía al puesto libre más cercano al destino y cobra el tiempo real.

**Entrega:** 16 de noviembre de 2026 (4 semanas desde el 19 de octubre).

## Dentro del alcance

- **SUMO:** red OSM de todo el Centro Histórico; los `parkingArea` se generan por script
  sobre los bordes de las calles tarifadas (no a mano).
- **TraCI:**
  - Al parquear se crea un peatón que hace diligencias y vuelve.
  - Emulador de GPS con ruido.
  - Máquina de estados de la sesión de parqueo.
  - Guiado con `setParkingAreaStop`.
  - El guiado usa la ocupación **actual**, no una predicción.
- **IA (la parte evaluable):** clasificador de movimiento (a pie / quieto / en vehículo)
  con Random Forest sobre ventanas de GPS.
  - Se compara contra una regla simple: "> 8 km/h = en auto".
  - Evita las *falsas liberaciones*: el conductor se baja a caminar, sale del radio y el
    sistema marca libre un puesto que sigue ocupado.
  - Datos:
    - Entrenamiento: GeoLife (solo GPS; hay que derivar la clase "quieto" y remuestrear)
      más ventanas generadas en SUMO.
    - Prueba: grabaciones propias en el Centro con los teléfonos, incluido el caso
      difícil de auto en tráfico lento.
    - SHL (Sussex-Huawei) queda como opción si después se suma el acelerómetro.
- **Escenarios:** búsqueda a ciegas (línea base) frente a la app con 20, 50 y 80 % de
  usuarios, con al menos 2 semillas.
- **KPIs:**
  - Tiempo y distancia de búsqueda, y CO₂.
  - Falsas liberaciones por cada 100 sesiones y retardo de cierre.
  - Error de facturación y precisión del mapa de ocupación.
- **Backend:** FastAPI + WebSocket, con la billetera como libro interno de movimientos:
  recarga, retención, débito y liberación.
- **Visor web:** mapa Leaflet con autos, peatones y puestos (verde/rojo) en vivo. TraCI
  convierte las posiciones a lat/lon y el backend las empuja por WebSocket. Opcionalmente
  se muestra `sumo-gui` en paralelo.
- **App Expo (React Native):** el equipo tiene 3 iPhone y 1 Android, y se prueba con
  Expo Go.
  - Sensores: `expo-location` y `expo-sensors`.
  - Sesión de parqueo, billetera y recarga con Payphone en **modo de prueba**.
  - Limitación: en iPhone el segundo plano es limitado, así que la app debe estar abierta
    en la demo.
- **Extras:**
  - Entrada por LLM en la app (opcional): "cerca de la Catedral Nueva una hora" → JSON
    `{destino, duración}`. Nunca va dentro del lazo de SUMO/TraCI.
  - Un teléfono real que aparece en el mismo mapa que la simulación.

## Reglas de cobro

Se retiene al llegar y se debita al salir:

1. **Al buscar puesto:** si el saldo es menor que el bloque mínimo, se pide recargar
   ($5 o más).
2. **Al confirmar la llegada (placa + puesto):** se retiene el bloque mínimo.
3. **Al detectar la salida real:** se debita el tiempo real, en fracciones de 5 min con un
   mínimo de cobro, y se libera la retención.
4. **Si el tiempo real supera el saldo:** se permite un saldo negativo pequeño y se
   bloquean nuevas sesiones hasta recargar. La app avisa cuando el saldo cubre menos de
   10 min.
5. **Tope de tiempo SERT:** es un parámetro, y la app avisa antes de que se cumpla.

Los autos simulados nunca llaman a Payphone; solo mueven el libro interno. Las credenciales
van en un `.env` fuera del repositorio.

## Fuera de alcance

- Predicción de ocupación futura.
- Aprendizaje por refuerzo.
- Deuna.
- Integración con la EMOV.
- Motos.
- Fraude intencional.

## Equipo

- **Tyrone + Freddy:** escenario SUMO, controlador TraCI, emulador GPS, guiado, KPIs,
  backend y visor.
- **Miguel + Pablo:** app Expo, dataset y clasificador.

## Siguiente paso (pendiente)

Armar el plan de 4 semanas con los prompts para Claude Code: dos tareas largas por persona
por semana, más un prompt de unificación cada domingo. Antes hay que fijar el **contrato de
la semana 1**: el formato de los eventos entre TraCI, el backend y la app.
