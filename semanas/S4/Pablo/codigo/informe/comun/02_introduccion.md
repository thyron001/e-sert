## Introducción

Dar vueltas buscando un lugar donde estacionar es una fuente conocida de congestión y de emisiones en las zonas urbanas centrales [@shoup2006cruising]. En Cuenca, el Centro Histórico tiene un sistema de estacionamiento rotativo tarifado, el SERT, que administra la EMOV EP y cuya ordenanza fija una tasa base de 0,25 por media hora o fracción [@concejo2012sert]. <!-- fuente: informe/referencias.bib -->

En el SERT se paga por adelantado, en bloques de media hora, con una tarjeta o con la aplicación oficial AppSERT, y no por el tiempo real de estadía. <!-- fuente: proyecto/app/docs/sert_reglas.md --> Este proyecto propone una aplicación que detecta cuándo el auto llega y cuándo se va, publica un mapa de ocupación, guía al puesto libre más cercano al destino y cobra el tiempo exacto. Detectar la salida es la parte delicada: si el conductor se baja a caminar y el sistema lo toma por una salida, marca libre un puesto que sigue ocupado. A ese error lo llamamos **falsa liberación**.

### Objetivos

- Medir si la aplicación reduce el tiempo, la distancia y las emisiones de la búsqueda de parqueo frente a una línea base sin ella.
- Detectar la llegada y la salida reales con un clasificador de movimiento sobre el GPS del teléfono, y medirlo por sus falsas liberaciones y su retardo de cierre.
- Cobrar el tiempo real con una billetera de movimientos (recarga, retención, débito y liberación).

### Alcance

Todo el proyecto es simulado. El escenario corre en SUMO [@lopez2018sumo] y lo controla TraCI [@wegener2008traci]; el teléfono no envía su GPS, sino que sigue a un vehículo simulado y muestra lo que vería su conductor. No se hicieron pruebas de campo en el Centro. Quedan fuera la predicción de ocupación futura, el aprendizaje por refuerzo, la integración con la EMOV y las motos.

### Organización del informe

Las secciones siguientes describen la arquitectura (controlador TraCI, emulador GPS, backend), el escenario y los experimentos, el clasificador de movimiento, la aplicación móvil, los resultados integrados, las conclusiones y el trabajo futuro. Cada cifra lleva un comentario con el archivo del que sale.
