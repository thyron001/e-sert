# Módulo IA — Clasificador de movimiento

Clasificador de movimiento GPS para el proyecto e-sert. Distingue tres clases:
`a_pie`, `quieto` y `vehiculo`.

## Regla de derivación de `quieto`

GeoLife no etiqueta la clase `quieto`. Se deriva automáticamente durante el
ventaneo con la siguiente regla:

> Una ventana originalmente etiquetada `a_pie` o `vehiculo` se reetiqueta como
> `quieto` si cumple **ambas** condiciones:
>
> 1. **Velocidad efectiva < 0,3 m/s**: calculada como desplazamiento neto
>    (haversine entre el primer y el último punto) dividido por la duración de
>    la ventana. Esto es más robusto al ruido GPS que la mediana de velocidades
>    instantáneas.
> 2. **Desplazamiento neto < 10 m**: el dispositivo no se movió
>    significativamente durante la ventana.

**Por qué esta regla:**
- Un peatón detenido en un semáforo o un auto en un atasco tienen GPS con ruido
  que genera velocidades instantáneas aparentes de 1–5 m/s. La velocidad
  efectiva (desplazamiento/duración) filtra ese ruido.
- El umbral de 0,3 m/s equivale a ~1 km/h, muy por debajo de una caminata
  lenta (~3,5 km/h).
- El desplazamiento de 10 m descarta ventanas donde el dispositivo se movió
  poco pero de forma sostenida.

## Validación: GroupKFold por usuario

La validación cruzada usa `GroupKFold(n_splits=5)` agrupando por `usuario_id`:
**ningún usuario aparece en entrenamiento y prueba a la vez**.

**Por qué no usar KFold normal:** un KFold aleatorio mezcla ventanas del mismo
usuario en train y test. Como las ventanas solapan (paso 5 s en 30 s) y cada
persona tiene patrones propios de movimiento, el modelo aprende a reconocer
*usuarios*, no *modos*. Esto infla las métricas y el modelo falla con usuarios
nuevos. GroupKFold evita esta fuga de datos.

## Inferencia (contrato §2)

```python
from ia.inferencia import clasificar

# ventana: list[PuntoGPS] con t, lat, lon, precision_m
resultado = clasificar(ventana)
# {"modo": "vehiculo", "confianza": 0.92, "fuente": "rf"}
```

Variables de entorno:
- `ESERT_MODELO`: ruta al .joblib (default: `ia/modelos/rf_v0.joblib`)
- `ESERT_CLASIFICADOR`: `"rf"` o `"umbral"` (default: intenta RF, fallback a umbral)

## Estructura

```
ia/
├── ventanas.py           # remuestrear() y ventanear() — librería genérica
├── caracteristicas.py    # extraer(ventana) → dict con ~18 features
├── umbral.py             # línea base por umbral de velocidad
├── entrenar.py           # RF + GroupKFold + modelo final
├── evaluar.py            # métricas, matrices de confusión, evidencias
├── inferencia.py         # clasificar() del contrato §2
├── modelos/              # rf_v0.joblib + rf_v0_info.json
├── resultados/           # s1_metricas.json
├── datos/
│   ├── descargar_geolife.py
│   ├── ingesta_geolife.py
│   ├── construir_ventanas.py
│   ├── evidencias_geolife.py
│   ├── evidencias_ventanas.py
│   ├── geolife_info.json
│   └── procesados/         # parquets (gitignored)
├── tests/
│   ├── test_ingesta.py
│   ├── test_ventanas.py
│   └── test_inferencia.py
└── requirements.txt
```

## Ventana y características

- **Ventana:** 30 s de GPS a 1 Hz, paso de 5 s, cobertura mínima 80%, pureza 80%.
- **Características (18):** vel_media, vel_mediana, vel_p10, vel_p85, vel_max,
  vel_std, acc_media_abs, acc_std, jerk_medio_abs, tasa_rumbo_media,
  prop_giros_30, prop_detenido, prop_lento, rectitud, distancia_total,
  precision_media, n_paradas_arranques, desplazamiento_neto.
