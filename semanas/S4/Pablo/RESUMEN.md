# S4 · Pablo 🟢 · Resumen semanal

## Sesión 1 · Modelo final congelado y model card

Se entrenó y congeló `rf_final` (Random Forest de 100 árboles, 48 MB) con ruido GPS AR(1) aplicado a las
posiciones y episodios reales de SUMO (semillas 201 y 202); dos entrenamientos dan el mismo SHA-256. En usuarios
no vistos de GeoLife el F1 macro es 0,872 (umbral 0,698); en SUMO normal sube de 0,562 (`rf_v1`) a 0,738. La
latencia de `clasificar` es de 1,35 ms (p50) y 2,12 ms (p99). `ia/inferencia.py` carga el modelo por defecto,
verifica el hash y cae al umbral si falla. Con σ de 10 a 15 m el RF puede liberar en falso si se adopta la tabla
literal del contrato; se recomienda `k = 5` en ese caso.

![](evidencias/s1_model-card-metricas.png)
