# Fuentes bibliográficas sobre ruido GPS

Tabla de referencia para calibrar el modelo de ruido AR(1) del módulo IA.

| Fuente | Entorno | Métrica | Valor |
|--------|---------|---------|-------|
| Zandbergen (2009), *Transactions in GIS* 13(s1). DOI: [10.1111/j.1467-9671.2009.01152.x](https://doi.org/10.1111/j.1467-9671.2009.01152.x) | Cielo abierto y suburbano, iPhone 3G (A-GPS) | sigma_m (error horizontal medio) | ~8 m (mediana); ~3 m en condiciones óptimas de cielo abierto (**por verificar** cifra exacta de cielo abierto) |
| Zandbergen (2009) | Cielo abierto, iPhone 3G | precision_m (percentil 95 del error horizontal) | ~10 m (**por verificar**) |
| Zandbergen y Barbeau (2011), *Journal of Navigation* 64(3). DOI: [10.1017/S0373463311000051](https://doi.org/10.1017/S0373463311000051) | Varios entornos, varios teléfonos A-GPS | sigma_m (error horizontal RMS) | 5–8 m según dispositivo y entorno (**por verificar** rango exacto) |
| Zandbergen y Barbeau (2011) | Estático, teléfonos Android | rho (autocorrelación temporal a 1 Hz) | ~0.8–0.9 (inferido de correlación serial en series estáticas) (**por verificar**) |
| Merry y Bettinger (2019), *PLoS ONE* 14(7) e0219890. DOI: [10.1371/journal.pone.0219890](https://doi.org/10.1371/journal.pone.0219890) | Urbano denso (edificios), teléfonos varios | sigma_m (error horizontal medio) | 5–10 m según dispositivo y obstrucción (**por verificar** cifras por dispositivo) |
| Merry y Bettinger (2019) | Urbano bajo dosel arbóreo | precision_m (percentil 95) | ~15 m (**por verificar**) |
| Groves (2011), *Journal of Navigation* 64(3). DOI: [10.1017/S0373463311000087](https://doi.org/10.1017/S0373463311000087) | Cañón urbano profundo (shadow matching) | sigma_m (error en cañón urbano) | 10–15 m; hasta >20 m en cañones estrechos (**por verificar** cifra de shadow matching vs. convencional) |
| Groves (2011) | Cañón urbano | p_perdida (probabilidad de pérdida de señal) | 0.05–0.10 en cañones profundos (**por verificar**) |
| Jun, Guensler y Ogle (2006), *Transportation Research Record* 1972. DOI: [10.1177/0361198106197200117](https://doi.org/10.1177/0361198106197200117) | Vehículos en movimiento, GPS dedicado | sigma_m (error posicional aleatorio) | ~5 m (desviación estándar del error aleatorio) (**por verificar**) |
| Jun, Guensler y Ogle (2006) | Vehículos en movimiento | rho (autocorrelación a 1 Hz) | ~0.7–0.85 (inferido del análisis de errores correlatados en velocidad) (**por verificar**) |
| Jun, Guensler y Ogle (2006) | Vehículos en movimiento | precision_m (efecto en velocidad) | Error en velocidad ~1–3 m/s derivado de sigma_m ~5 m a 1 Hz (**por verificar**) |

## Resumen de rangos adoptados

| Parámetro | Rango | Justificación |
|-----------|-------|---------------|
| sigma_m | {3, 5, 8, 10, 15} m | 3 m en cielo abierto (Zandbergen 2009), 5 m en movimiento (Jun et al. 2006), 8 m típico A-GPS (Zandbergen y Barbeau 2011), 10 m urbano (Merry y Bettinger 2019), 15 m cañón urbano (Groves 2011) |
| rho (1 Hz) | 0.7–0.95 | Autocorrelación temporal del error GPS a muestreo de 1 segundo (Jun et al. 2006; Zandbergen y Barbeau 2011) |
| p_perdida | 0.02–0.10 | Desde entorno suburbano (~2 %) hasta cañón urbano profundo (~10 %) (Groves 2011) |

## Notas

- Muchos valores están marcados **por verificar** porque provienen de rangos reportados en los artículos pero no se pudo confirmar la cifra exacta en esta sesión. Se recomienda verificar con acceso directo a los PDFs.
- El Centro Histórico de Cuenca tiene calles estrechas con edificios de 2–4 pisos, lo que corresponde a un entorno entre urbano moderado y cañón urbano leve. Los valores sigma_m de 8–10 m son los más representativos para este caso.
- La autocorrelación rho = 0.8 a 1 Hz se adopta como valor central para el modelo AR(1).
