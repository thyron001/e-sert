---
semana: S3
persona: Pablo
sesion: 2
titulo: Análisis de errores y efecto del suavizado en las falsas liberaciones
horas: 3-4
modulo: ia
depende: [S3-Pablo-1, S2-Pablo-3, S2-Freddy-2]
entrega: [ia/analisis_errores.py, ia/suavizado.py, ia/simular_falsas.py, ia/reportes/errores_contexto.csv, ia/reportes/suavizado_k.csv, ia/reportes/conclusiones_s3.md]
evidencias: [s2_errores-contexto.png, s2_suavizado-falsas-liberaciones.png]
---
# S3 · Sesión 2 · Pablo 🟢: Análisis de errores y efecto del suavizado en las falsas liberaciones

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (por qué importan las falsas liberaciones) y
`docs/CONTRATO.md` (sección 3). La métrica que importa al sistema **no es la exactitud por
ventana**, sino cuántas sesiones se cierran mientras el auto sigue estacionado. Un solo
`vehiculo` falso cerca del auto basta para liberar el puesto. La máquina de estados de Freddy se
lee desde `proyecto/traci/` (S2-Freddy-2); si cambió de lugar, búscala en
`origin/freddy/s3:semanas/S3/Freddy/codigo/backend/nucleo/estados.py`. Si no la encuentras, crea
una réplica marcada `# MOCK: reemplazar por la máquina de estados de Freddy`.

## Objetivo
Entender **dónde** se equivoca el clasificador y elegir, con datos, el suavizado temporal
(k = 1, 3 o 5 ventanas) que minimiza las falsas liberaciones sin disparar el retardo de cierre.

## Pasos
1. **Análisis de errores** (`ia/analisis_errores.py`) sobre el conjunto de Cuenca (nunca visto) y
   las semillas de prueba de SUMO, con umbral y rf:
   - matriz de confusión y recall por clase en cada contexto: velocidad media de la ventana
     (0–3, 3–8, 8–15, > 15 km/h), `precision_m` (< 10, 10–25, > 25 m), ventanas que contienen una
     transición de modo y tipo de teléfono (iPhone/Android, si está en los metadatos);
   - los 20 peores errores con la gráfica de su traza: separa **errores de etiqueta** (anotación
     mal hecha) de **errores del modelo**;
   - resultado en `ia/reportes/errores_contexto.csv`.
2. **Suavizado** (`ia/suavizado.py`), con estado por usuario:
   - `Suavizador(k, metodo="mayoria" | "prob_media")`: voto de mayoría sobre las últimas `k`
     ventanas (en empate gana la más reciente) o media de `predict_proba`;
   - `k = 1` equivale a no suavizar; la salida respeta `ResultadoModo`.
3. **Simulación de sesiones fuera de línea** (`ia/simular_falsas.py`):
   - toma episodios de parqueo completos: trazas de SUMO con estacionamiento y grabaciones de
     Cuenca del protocolo (estacionar → caminar → volver → manejar), con el puesto conocido;
   - ventanas de 30 s con paso 5 s → clasificador → suavizador → máquina de estados, con la
     distancia al puesto calculada desde el GPS ruidoso;
   - **falsa liberación:** `CERRADA` cuando `modo_real` en ese instante no es `vehiculo` (el auto
     sigue estacionado); **retardo:** cierre − salida real;
   - rejilla: k ∈ {1, 3, 5} × {umbral, rf} × {mayoria, prob_media} = 12 combinaciones;
   - IC 95 % por *bootstrap* sobre sesiones (`scipy.stats.bootstrap`, 2 000 remuestreos);
   - salida en `ia/reportes/suavizado_k.csv`.
4. Paraleliza la rejilla con `concurrent.futures.ProcessPoolExecutor` (una combinación por
   tarea). Si tarda más de 10 min, déjala en segundo plano y vigílala con `Monitor`.
5. **Compromiso esperado:** cada ventana extra de suavizado añade hasta 5 s de retardo
   (k = 5 → del orden de +10 a +20 s). Criterio de elección: **mínimas falsas liberaciones con
   retardo mediano ≤ 60 s**. Si dos k empatan dentro del IC, elige el menor.
6. Si el controlador de `proyecto/traci/` acepta el parámetro de suavizado, valida el k elegido
   con una corrida corta `p50_rf_s1` de 1 800 s; si no, déjalo como pedido a Freddy.
7. Escribe `ia/reportes/conclusiones_s3.md`: al menos 5 conclusiones del análisis de errores,
   la tabla de las 12 combinaciones y el k recomendado con su justificación.
8. **Evidencias:**
   - `evidencias/s2_errores-contexto.png`: recall de `vehiculo` y `quieto` por rango de velocidad
     y de precisión, umbral vs rf;
   - `evidencias/s2_suavizado-falsas-liberaciones.png`: falsas /100 (barras con IC 95 %) y retardo
     mediano (línea, eje derecho) para k = 1, 3 y 5, umbral vs rf.

## Dónde escribir
`semanas/S3/Pablo/codigo/ia/` y `evidencias/`.

## Hecho cuando
- [ ] `errores_contexto.csv` y `suavizado_k.csv` existen y se regeneran con un comando.
- [ ] La tabla tiene las 12 combinaciones, cada una con su IC 95 %.
- [ ] Hay un k recomendado que cumple retardo mediano ≤ 60 s, o se explica por qué ninguno lo
  cumple.
- [ ] `conclusiones_s3.md` tiene al menos 5 conclusiones con cifras.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 2, Pablo). En "Pedidos a otros":
@Freddy, el k y el método recomendados para el controlador y el backend en vivo; @Tyrone, usar
ese k en la corrida final de S4.
