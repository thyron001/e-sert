# S1 · Pablo 🟢 · Resumen semanal

## Sesión 1 · Ingesta del dataset GeoLife

Descarga e ingesta completa de GeoLife Trajectories 1.3: 64 usuarios etiquetados, 3.25 millones
de puntos GPS en un Parquet limpio con las columnas del contrato. Se mapearon los modos de
transporte (walk→a_pie, car/taxi/bus→vehiculo) y se descartaron los no aplicables (bike, train,
subway, airplane, etc.). Se escribieron 18 tests unitarios y dos evidencias gráficas.

**Estadísticas del dataset:**
- 64 usuarios con datos útiles
- 3,254,173 puntos en el Parquet
- 10,418 segmentos de movimiento
- 1,193 horas a pie, 1,713 horas en vehículo
- Intervalo de muestreo: mediana 2 s, p90 5 s

![Horas por modo](evidencias/s1_geolife-horas-por-modo.png)

![Trayectorias al azar](evidencias/s1_geolife-trayectorias.png)
