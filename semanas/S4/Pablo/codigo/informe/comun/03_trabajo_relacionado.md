## Trabajo relacionado

**Búsqueda de parqueo.** Shoup estudió el efecto de dar vueltas buscando estacionamiento en el tránsito de las zonas centrales [@shoup2006cruising]. Este proyecto toma esa motivación y la evalúa en un escenario simulado de Cuenca, con y sin una aplicación que guía al puesto libre.

**Simulación de tráfico y acoplamiento.** SUMO es el simulador microscópico de tráfico que usamos [@lopez2018sumo]. TraCI permite controlarlo en línea desde un programa externo [@wegener2008traci], que es como el controlador crea peatones, emula el GPS, sigue la sesión de cada usuario y guía a los autos.

**Detección del modo de transporte con GPS.** El proyecto GeoLife publicó trayectorias reales y trabajos sobre cómo inferir el modo de transporte a partir de datos GPS crudos [@zheng2008learning; @zheng2008understanding; @zheng2010geolife]. Usamos esas trayectorias como fuente de entrenamiento y de prueba con usuarios no vistos. Un enfoque complementario es el conjunto SHL, que incluye sensores inerciales [@gjoreski2018shl]; queda como trabajo futuro por exigir el acelerómetro.

**Modelo y documentación.** El clasificador es un Random Forest [@breiman2001random] implementado con scikit-learn [@pedregosa2011scikit]. Para documentar el modelo congelado se sigue el formato de las *model cards* [@mitchell2019modelcards].

**Diferencia con lo anterior.** La métrica que nos importa no es la exactitud por ventana de GPS, sino cuántas sesiones se cierran mientras el auto sigue estacionado (falsas liberaciones por 100 sesiones) y cuánto tarda en cerrarse una sesión correcta, medidas en el sistema completo.
