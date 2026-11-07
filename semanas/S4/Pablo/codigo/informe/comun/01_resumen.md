## Resumen

Buscar parqueo en la zona de estacionamiento rotativo tarifado (SERT) del Centro Histórico de Cuenca consume tiempo, combustible y calles. Este trabajo construye y evalúa, íntegramente en simulación, una aplicación que detecta la llegada y la salida reales del auto, mantiene un mapa de ocupación en vivo, guía al puesto libre más cercano al destino y cobra el tiempo real de estadía.

El sistema combina SUMO para el escenario, TraCI para el control, un servidor FastAPI para sesiones y billetera, una aplicación Expo que sigue a un auto simulado (teléfono espejo) y un clasificador de movimiento con Random Forest. El clasificador decide si el usuario va a pie, quieto o en vehículo, para no liberar un puesto que sigue ocupado: la falsa liberación. Se compara contra la regla simple de velocidad mayor que 8 km/h.

Resultados principales de la corrida final:

- Tiempo medio de búsqueda con la app frente a la búsqueda a ciegas: [PENDIENTE: cifra de Tyrone S4-2].
- Falsas liberaciones por cada 100 sesiones, con umbral y con Random Forest: [PENDIENTE: cifra de Tyrone S4-2].
- Retardo mediano de cierre de la sesión: [PENDIENTE: cifra de Tyrone S4-2].

Todo es simulado: no hay datos de campo en el Centro Histórico.
