# Resumen de la corrida final (S4-2)

Fuente: `kpis/resultados/final/<id>/kpis.json` (40 corridas) y `resumen.csv`. IC 95 %: *bootstrap* jerárquico (semillas y vehículos, 10 000 remuestreos, semilla 0) para los KPIs por vehículo; *bootstrap* sobre semillas para la ocupación; Wilson para las falsas liberaciones (sesiones agrupadas); t de Student entre semillas para el resto. Δ: cambio frente a la búsqueda a ciegas; p: Mann-Whitney U bilateral sobre vehículos frente al 0 %.

## KPIs de búsqueda

| Escenario | n semillas | Vehículos | Búsqueda (s) [IC 95 %] | Δ | p | Distancia (m) [IC 95 %] | Δ | CO₂ por vehículo (g) [IC 95 %] | Δ | Ocupación (%) [IC 95 %] |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ciegas | 5 | 4 646 | 433 [418; 448] | — | — | 1 456 [1 407; 1 506] | — | 838 [806; 871] | — | 87,4 [87,0; 87,9] |
| p20_umbral | 5 | 4 695 | 434 [423; 446] | +0,4 % | 0,865 | 1 445 [1 395; 1 487] | −0,7 % | 845 [818; 874] | +0,8 % | 87,4 [87,0; 87,9] |
| p20_rf_final | 5 | 4 695 | 434 [423; 446] | +0,4 % | 0,865 | 1 445 [1 395; 1 487] | −0,7 % | 845 [818; 874] | +0,8 % | 87,4 [87,0; 87,9] |
| p50_umbral | 5 | 4 668 | 438 [425; 451] | +1,3 % | 0,125 | 1 468 [1 421; 1 517] | +0,8 % | 853 [825; 880] | +1,7 % | 87,4 [87,0; 87,9] |
| p50_rf_final | 5 | 4 668 | 438 [425; 451] | +1,3 % | 0,125 | 1 468 [1 421; 1 517] | +0,8 % | 853 [825; 880] | +1,7 % | 87,4 [87,0; 87,9] |
| p80_umbral | 5 | 4 627 | 451 [433; 470] | +4,1 % | 0,054 | 1 450 [1 411; 1 495] | −0,4 % | 880 [839; 928] | +5,0 % | 87,4 [87,0; 87,8] |
| p80_rf_final | 5 | 4 627 | 451 [433; 470] | +4,1 % | 0,054 | 1 450 [1 411; 1 495] | −0,4 % | 880 [839; 928] | +5,0 % | 87,4 [87,0; 87,8] |
| p50_oraculo | 5 | 4 790 | 357 [344; 373] | −17,6 % | < 0,001 | 1 217 [1 181; 1 257] | −16,4 % | 690 [663; 723] | −17,7 % | 87,7 [87,3; 88,1] |

## Umbral frente a rf_final

| Penetración | Clasificador | Sesiones | Falsas /100 [Wilson 95 %] | Retardo de cierre, mediana (s) [IC 95 %] | Error de facturación (USD) [IC 95 %] | Precisión del mapa (%) [IC 95 %] |
|---:|---|---:|---:|---:|---:|---:|
| 20 % | umbral | 801 | 88,9 [86,5; 90,9] | 26,7 [10,3; 43,1] | −0,157 [−0,171; −0,143] | 57,0 [54,6; 59,4] |
| 20 % | rf_final | 289 | 0,0 [0,0; 1,3] | 22,7 [9,8; 35,6] | 0,016 [0,009; 0,023] | 57,0 [54,6; 59,4] |
| 50 % | umbral | 1 971 | 87,2 [85,6; 88,6] | 25,2 [16,0; 34,4] | −0,153 [−0,168; −0,139] | 57,0 [54,9; 59,2] |
| 50 % | rf_final | 729 | 0,0 [0,0; 0,5] | 18,8 [17,2; 20,4] | 0,018 [0,014; 0,021] | 57,1 [54,9; 59,2] |
| 80 % | umbral | 3 076 | 86,6 [85,4; 87,8] | 17,6 [12,4; 22,8] | −0,145 [−0,153; −0,138] | 57,3 [55,2; 59,4] |
| 80 % | rf_final | 1 132 | 0,0 [0,0; 0,3] | 18,4 [17,0; 19,8] | 0,015 [0,012; 0,019] | 57,3 [55,2; 59,5] |
| 50 % | oráculo | 772 | 0,0 [0,0; 0,5] | 21,3 [15,8; 26,8] | 0,016 [0,013; 0,019] | 56,0 [54,1; 57,9] |

## Controles de cordura

1. **Teletransportes < 1 % por corrida:** cumple (máximo 0,166 % en 40 corridas).
2. **Línea base a ±10 % de S3-1:** cumple (final 432,7 s; S3-1 436,1 s; diferencia −0,79 %). S3-1 usó las semillas 1–3; la final, 1–5 (las 1–3 son las mismas corridas).
3. **rf_final sin más falsas liberaciones que el umbral:** cumple (20 %: umbral 88,9 vs rf_final 0,0; 50 %: umbral 87,2 vs rf_final 0,0; 80 %: umbral 86,6 vs rf_final 0,0).
