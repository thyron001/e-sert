---
semana: S2
persona: Pablo
sesion: 1
titulo: Ventanas desde trazas de SUMO y ruido calibrado con grabaciones reales
horas: 3-4
modulo: ia
depende: [S1-Pablo-2, S1-Freddy-3, S1-Miguel-3]
entrega: [ia/datos_sumo.py, ia/calibrar_ruido.py, ia/ruido.py, ia/calibracion/ruido_cuenca.json, ia/datos/ventanas_v2.parquet, ia/tests/]
evidencias: [s1_distribuciones-features.png, s1_ruido-calibrado.png]
---
# S2 · Sesión 1 · Pablo 🟢: Ventanas desde trazas de SUMO y ruido calibrado con grabaciones reales

## Contexto
Lee `CLAUDE.md` y `docs/CONTRATO.md` (secciones 2 y 7). Es la primera sesión de S2: copia
`proyecto/ia/` a `semanas/S2/Pablo/codigo/ia/` si no existe la copia. Las trazas de Freddy
están en `proyecto/traci/trazas/` (`sumo_semilla<N>.csv` o la muestra de 5 000 filas) y las
grabaciones de Miguel en `proyecto/datos/`. Si falta algo, usa un mock marcado `# MOCK`
(por ejemplo, trazas sintéticas generadas con tu propio AR(1)). **Regla de oro**: los datos
de Cuenca son el conjunto de prueba de S2-3; aquí solo se usa un subconjunto pequeño de
calibración, separado y documentado.

## Objetivo
Sumar al dataset ventanas generadas en SUMO y hacer que su ruido GPS se parezca al de los
teléfonos reales del Centro, con parámetros medidos y no supuestos.

## Pasos
1. **Partición de los datos de Cuenca** (`ia/particion_cuenca.json`): elige por grabación
   (nunca por fila) un subconjunto de calibración, como máximo el 20 % de las grabaciones y
   solo segmentos `quieto`; el resto queda reservado para S2-3. Guarda los IDs y la semilla.
2. Crea `ia/calibrar_ruido.py` sobre los segmentos `quieto` de calibración:
   - error de posición = distancia de cada punto a la mediana del segmento (en metros,
     proyección local equirectangular);
   - estima `sigma_m` (desviación por eje), `rho` (autocorrelación con *lag* 1 por eje),
     `p_perdida` (huecos > 1,5 s), el *jitter* del periodo de muestreo y la distribución de
     `precision_m` reportada (iOS frente a Android si hay metadatos);
   - escribe `ia/calibracion/ruido_cuenca.json` con valores e IC 95 % (*bootstrap* por
     segmento).
3. Crea `ia/ruido.py` con `aplicar_ruido_ar1(df, sigma_m, rho, p_perdida, semilla)` para
   **aumentar** trazas limpias o poco ruidosas (GeoLife y SUMO) con el ruido medido. Si las
   trazas de Freddy ya traen ruido con otros parámetros, no lo apiles: documenta la
   diferencia y pídele a Freddy que regenere con `ruido_cuenca.json`.
4. Crea `ia/datos_sumo.py`: lee las trazas de SUMO, las pasa por el mismo remuestreo a 1 Hz,
   ventanas de 30 s con paso de 5 s y características de S1-2 (reutiliza las funciones; no
   las dupliques). Etiqueta de la ventana = modo mayoritario si cubre ≥ 80 % de la ventana;
   si no, descártala y cuéntala. `grupo` = `usuario_id` (para `GroupKFold`).
5. Une todo en `ia/datos/ventanas_v2.parquet` con las columnas `origen`
   (`geolife`|`sumo`), `grupo`, `modo`, `t_inicio` y las características. Imprime el balance
   de clases por origen; si una clase supera el 60 %, anota la estrategia
   (`class_weight` o submuestreo) para S2-2.
6. **Comparación de distribuciones**: para velocidad media, desviación de la velocidad,
   p95 de la aceleración y cambio de rumbo, prueba de Kolmogórov-Smirnov por clase entre
   GeoLife, SUMO y la calibración de Cuenca. Tabla en `ia/reportes/ks_origenes.csv`.
7. **Tests** (`ia/tests/`): `aplicar_ruido_ar1` reproduce `sigma_m` (±10 %) y `rho`
   (±0,05) en 10 000 muestras; ninguna ventana mezcla dos `grupo`; ningún ID de la partición
   de prueba de Cuenca aparece en `ventanas_v2.parquet`.
   Paraleliza: un subagente hace `calibrar_ruido.py` + su gráfica mientras tú haces
   `datos_sumo.py`; el procesamiento de las 3 semillas puede ir en segundo plano.
8. **Evidencias** (matplotlib, `dpi=150`):
   - `s1_distribuciones-features.png`: densidades de la velocidad media por clase y origen;
   - `s1_ruido-calibrado.png`: dispersión del error de un segmento quieto real frente a uno
     simulado con `ruido_cuenca.json`, más sus autocorrelaciones.

## Dónde escribir
`semanas/S2/Pablo/codigo/ia/` y `semanas/S2/Pablo/evidencias/`. Los `.parquet` grandes van
en `.gitignore`; publica una muestra y el *hash* del completo.

## Hecho cuando
- [ ] `ruido_cuenca.json` existe con `sigma_m`, `rho`, `p_perdida` y sus IC.
- [ ] `ventanas_v2.parquet` tiene ventanas de GeoLife y de SUMO, las tres clases y la columna
  `grupo`.
- [ ] Los tests pasan, incluido el de no fuga de datos de Cuenca.
- [ ] `ks_origenes.csv` existe y la bitácora comenta qué origen se parece más a Cuenca.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 1, Pablo). En "Pedidos a
otros": @Freddy, los parámetros de `ruido_cuenca.json` para tu `EmuladorGPS`; @Miguel, qué
casos faltan en las grabaciones (por ejemplo, más auto en tráfico lento).
