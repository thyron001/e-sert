## Resumen

Buscar parqueo en la zona de estacionamiento rotativo tarifado (SERT) del Centro Histórico de Cuenca consume tiempo, combustible y calles. Este trabajo construye y evalúa, íntegramente en simulación, una aplicación que detecta la llegada y la salida reales del auto, mantiene un mapa de ocupación en vivo, guía al puesto libre más cercano al destino y cobra el tiempo real de estadía.

El sistema combina SUMO para el escenario, TraCI para el control, un servidor FastAPI para sesiones y billetera, una aplicación Expo que sigue a un auto simulado (teléfono espejo) y un clasificador de movimiento con Random Forest. El clasificador decide si el usuario va a pie, quieto o en vehículo, para no liberar un puesto que sigue ocupado: la falsa liberación. Se compara contra la regla simple de velocidad mayor que 8 km/h.

Resultados principales de la corrida final:

- Tiempo medio de búsqueda a ciegas de 432,7 s; con la app sube a 434,3 s (20 %), 438,2 s (50 %) y 450,7 s (80 %), sin mejora medible en la demanda simulada.
- Falsas liberaciones por cada 100 sesiones, con umbral, 88,9 (20 %), 87,2 (50 %) y 86,6 (80 %); con Random Forest, 0 en las tres penetraciones.
- Retardo mediano de cierre de la sesión con Random Forest: 22,7 s (20 %), 18,8 s (50 %) y 18,4 s (80 %).

Todo es simulado: no hay datos de campo en el Centro Histórico.
