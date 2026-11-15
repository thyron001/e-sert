# Conclusiones S3 · Sesión 2: errores del clasificador y suavizado

Regenerar: `python3 -m ia.analisis_errores` (≈ 4 min), `python3 -m ia.simular_falsas --max-sesiones 300`
(≈ 4 min, necesita los episodios de `ia/grabar_episodios.py`) y `python3 -m ia.graficar_suavizado`.

## Qué se simuló
300 sesiones completas de SUMO (semillas 101–105, muestreadas al azar de 1 784 sesiones completas; estacionar →
caminar → volver → manejar), cada una con ruido GPS AR(1) de σ = 5, 10 y 15 m (ρ = 0,8). Ventanas de 30 s con paso
de 5 s → clasificador → suavizador → máquina de estados de Freddy (`proyecto/traci/estados.py`). Falsa
liberación: sesión `CERRADA` con el modo real distinto de `vehiculo`. Retardo: cierre − salida real del auto.
IC 95 % por *bootstrap* de 2 000 remuestreos sobre sesiones (las tres σ de una sesión viajan juntas).

## Las 12 combinaciones (máquina de estados de Freddy, tal como está)
| Sistema | Método | k | Falsas /100 [IC 95 %] | Retardo mediano (s) [IC 95 %] | Cierres correctos | Sin cierre |
|---|---|---|---|---|---|---|
| rf | mayoria | 1 | 0.00 [0.00; 0.00] | 12.5 [11.0; 14.0] | 3.6 % | 96.4 % |
| rf | mayoria | 3 | 0.00 [0.00; 0.00] | 13.0 [12.5; 15.0] | 2.6 % | 97.4 % |
| rf | mayoria | 5 | 0.00 [0.00; 0.00] | 17.0 [13.0; 17.0] | 1.4 % | 98.6 % |
| rf | prob_media | 1 | 0.00 [0.00; 0.00] | 12.5 [11.0; 14.0] | 3.6 % | 96.4 % |
| rf | prob_media | 3 | 0.33 [0.00; 0.78] | 12.0 [11.0; 13.0] | 3.7 % | 96.0 % |
| rf | prob_media | 5 | 0.11 [0.00; 0.33] | 13.0 [12.5; 15.0] | 3.7 % | 96.2 % |
| umbral | mayoria | 1 | 88.22 [86.44; 90.11] | 13.0 [12.0; 13.0] | 8.7 % | 3.1 % |
| umbral | mayoria | 3 | 87.44 [85.67; 89.22] | 13.0 [12.0; 13.0] | 6.6 % | 6.0 % |
| umbral | mayoria | 5 | 87.78 [85.89; 89.67] | 13.0 [12.0; 13.0] | 5.1 % | 7.1 % |
| umbral | prob_media | 1 | 88.22 [86.44; 90.11] | 13.0 [12.0; 13.0] | 8.7 % | 3.1 % |
| umbral | prob_media | 3 | 87.78 [86.00; 89.56] | 13.0 [12.0; 13.0] | 6.4 % | 5.8 % |
| umbral | prob_media | 5 | 88.11 [86.33; 89.89] | 13.0 [12.0; 13.0] | 4.9 % | 7.0 % |

## Las mismas 12 con la máquina del contrato §3 (sin `REGRESANDO → A_PIE`)
| Sistema | Método | k | Falsas /100 [IC 95 %] | Retardo mediano (s) [IC 95 %] | Cierres correctos | Sin cierre |
|---|---|---|---|---|---|---|
| rf | mayoria | 1 | 0.22 [0.00; 0.56] | 52.0 [43.5; 60.0] | 96.2 % | 3.6 % |
| rf | mayoria | 3 | 0.22 [0.00; 0.56] | 56.0 [47.0; 64.0] | 95.4 % | 4.3 % |
| rf | mayoria | 5 | 0.00 [0.00; 0.00] | 69.0 [61.0; 80.0] | 93.6 % | 6.4 % |
| rf | prob_media | 1 | 0.22 [0.00; 0.56] | 52.0 [43.5; 60.0] | 96.2 % | 3.6 % |
| rf | prob_media | 3 | 0.44 [0.00; 1.00] | 57.0 [48.0; 67.0] | 93.8 % | 5.8 % |
| rf | prob_media | 5 | 0.11 [0.00; 0.33] | 69.0 [60.0; 81.0] | 91.8 % | 8.1 % |
| umbral | mayoria | 1 | 89.44 [87.67; 91.22] | 13.0 [12.0; 13.0] | 8.1 % | 2.4 % |
| umbral | mayoria | 3 | 89.56 [87.78; 91.33] | 14.0 [13.0; 15.0] | 7.4 % | 3.0 % |
| umbral | mayoria | 5 | 89.89 [88.11; 91.67] | 14.5 [13.0; 19.5] | 6.9 % | 3.2 % |
| umbral | prob_media | 1 | 89.44 [87.67; 91.22] | 13.0 [12.0; 13.0] | 8.1 % | 2.4 % |
| umbral | prob_media | 3 | 90.00 [88.33; 91.78] | 14.0 [13.0; 15.0] | 7.2 % | 2.8 % |
| umbral | prob_media | 5 | 90.33 [88.56; 92.11] | 15.5 [13.0; 19.0] | 6.7 % | 3.0 % |

## k recomendado
**k = 1 (sin suavizar) con RF.** Criterio del prompt: mínimas falsas liberaciones con retardo mediano ≤ 60 s;
si dos k empatan dentro del IC, el menor. Con RF las falsas liberaciones son ≈ 0 para los tres k (IC superior ≤ 1
por 100 sesiones), así que empatan y gana k = 1. Suavizar más solo cuesta: con la máquina del contrato el retardo
mediano pasa de 52 s (k = 1) a 56 s (k = 3) y **69 s (k = 5, incumple los 60 s)**, y los cierres correctos bajan de
96,2 % a 93,6 %. El método (`mayoria` o `prob_media`) no importa: sus IC se solapan en todos los k y con k = 1 son
idénticos por construcción. Esto coincide con el `suavizado: histeresis, k = 1` ya guardado en `rf_v1.meta.json`.

## Conclusiones
1. **El umbral del contrato es inutilizable con ruido GPS de 5 m o más.** Produce 88,2 falsas liberaciones por 100
   sesiones [86,4; 90,1] (Freddy) y 89,4 [87,7; 91,2] (contrato). Por σ: 64,7 con σ = 5 y **100 %** de las sesiones con
   σ = 10 y 15. El ruido autocorrelacionado hace que un teléfono quieto parezca avanzar a más de 8 km/h, y basta
   deriva de 20 m para disparar `ESTACIONADO → SALIENDO`. Ningún k lo arregla (87,4–88,2 con los tres k).
2. **El RF casi no libera en falso:** 0,00–0,33 por 100 con la máquina de Freddy (IC superior ≤ 0,78) y 0,00–0,44 con la
   del contrato (IC superior ≤ 1,00). En una comprobación puntual (60 sesiones, σ = 5; no queda en los CSV) no dijo `vehiculo` para una
   persona quieta o caminando en ninguna ventana, y hacen falta dos ventanas seguidas con el auto a más de 20 m.
3. **Suavizar no reduce las falsas liberaciones del RF** (ya ≈ 0) **y sí empeora el cierre:** con la máquina del
   contrato el retardo mediano crece 52 → 56 → 69 s para k = 1, 3, 5, y los cierres correctos caen 96,2 → 95,4 →
   93,6 %. Cada ventana extra añade ≈ 5 s, como se esperaba, pero aquí no compra nada.
4. **La máquina de estados de Freddy deja sin cerrar el 96–98,6 % de las sesiones con RF** (cierres correctos
   1,4–3,7 %). Cuando el auto arranca, la ventana de 30 s todavía parece `a_pie`, la distancia ya supera 30 m y
   la regla `REGRESANDO → A_PIE` (que **no está en la tabla del contrato §3**) saca la sesión de `REGRESANDO`; desde
   `A_PIE` no hay camino a `SALIENDO`. Con la tabla literal del contrato cierran bien el 96,2 % (k = 1). El retardo
   de 12–17 s de la primera tabla es engañoso: solo cuenta el 2–4 % que logra cerrar.
5. **El RF pierde capacidad con el ruido y el retardo lo refleja.** Recall del RF en SUMO por σ = 3, 5, 8, 10, 15 m:
   `quieto` 0,95 / 0,65 / 0,38 / 0,32 / 0,18 y `vehiculo` 0,20 / 0,15 / 0,07 / 0,08 / 0,10 (escenarios del análisis de
   errores, que incluyen tráfico lento). Con la máquina del contrato y k = 1 el retardo mediano es 32 s (σ = 5), 53 s
   (σ = 10) y **81 s (σ = 15)**: solo σ ≤ 10 m cumple los 60 s.
6. **Velocidad media de la ventana.** En GeoLife (usuarios no vistos) el recall de `vehiculo` en 0–3 y 3–8 km/h es 0,20
   y 0,19 con RF y 0,00 con umbral (atascos), y 0,85 / 1,00 en 8–15 / > 15 km/h con RF. En SUMO σ = 5, el RF solo
   recupera 0,24 de `vehiculo` a > 15 km/h y 0,00 a 8–15 km/h, mientras el umbral da 1,00: la brecha de dominio de S2-3
   es en gran parte sensibilidad al ruido. `quieto` es 1,00 con RF en GeoLife frente a 0,45 del umbral en 0–3 km/h.
7. **De los 20 peores errores del RF, 5 son errores de etiqueta y 15 del modelo.** Los 5 de etiqueta son de GeoLife:
   `a_pie` anotado en trazas a 25–50 km/h. Los 10 de SUMO son del modelo (tráfico lento y normal, con σ alto).
8. **No se pudo medir el efecto de `precision_m`:** en SUMO siempre vale 4–7,5 m (no depende de σ), así que los rangos
   10–25 y > 25 m quedan vacíos; GeoLife no trae precisión. Las ventanas nunca mezclan modos (pureza ≥ 0,8): la
   transición se midió como cercanía (≤ 10 s) a un cambio de modo; el recall del RF es 0,48 en `quieto` y 0,58 en
   `vehiculo` en esas ventanas de SUMO.
9. **Las etiquetas de SUMO de S2-3 estaban sesgadas:** `remuestrear` etiquetaba todo el segmento con el modo de su
   primera fila y el 47 % de los usuarios `normal` alternan `a_pie` y `quieto`. El análisis de errores segmenta por tramos
   de modo constante; las cifras de SUMO de S2-3 deben revisarse.

## Pedidos
- **@Freddy:** (a) usar `k = 1` (sin suavizado) con RF, o `ClasificadorConEstado(usuario, k=1)`; el método da igual.
  (b) Revisar `REGRESANDO → A_PIE` en `proyecto/traci/estados.py` (conclusión 4): no está en el contrato §3 y con ella casi
  ninguna sesión cierra. (c) `ControlSesiones` acepta un `clasificador` y el controlador no tiene un parámetro de
  suavizado, así que **no se validó con la corrida `p50_rf_s1` de 1 800 s**: las estadías duran mediana 43 min y casi
  ninguna sesión terminaría en 1 800 s.
- **@Tyrone:** usar k = 1 en la corrida final de S4. [Plan] `docs/CONTRATO.md` §3 podría decir si `REGRESANDO → A_PIE`
  existe.

## Limitaciones
Solo hay ruido AR(1) (sin multitrayecto real); el buffer del teléfono empieza al estacionar (no incluye la
conducción previa, como en `ControlSesiones`); se usan sesiones completas (las que sí vuelven a manejar); 300 de 1 784.
