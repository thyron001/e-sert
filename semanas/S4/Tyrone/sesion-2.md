---
semana: S4
persona: Tyrone
sesion: 2
titulo: Corrida final de experimentos con el modelo y el controlador finales
horas: 3-4
modulo: kpis
depende: [S4-Pablo-1, S3-Tyrone-2, S3-Freddy-2]
entrega: [kpis/corrida_final.py, kpis/resultados/final/manifiesto.json, kpis/resultados/final/resumen.csv, kpis/resultados/final/resumen.md, kpis/figuras_finales.py, informe/tyrone.md, informe/figuras/tyrone/]
evidencias: [s2_kpis-finales.png, s2_falsas-liberaciones.png]
---
# S4 · Sesión 2 · Tyrone 🔵: Corrida final de experimentos con el modelo y el controlador finales

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (escenarios y KPIs) y el ejecutor de experimentos de S3
(`proyecto/kpis/`). Los números de esta corrida son **los que van al informe y a las
diapositivas**: deben ser reproducibles y trazables a versiones concretas del código y del
modelo. Plazo real: sábado 14 de noviembre, 23:59.

## SUMO en el contenedor
Esta sesión usa SUMO. Sigue la sección **"SUMO en el contenedor `van3twin`"** de `CLAUDE.md`:
- Antes de empezar, comprueba que el repo está clonado en `van3twin-docker/results/e-sert` y
  que `docker ps` muestra `van3twin`. Si no, avisa al usuario y no sigas con la parte de SUMO.
- `git` y la edición de archivos van en la computadora. `sumo`, `netconvert`, `randomTrips.py`
  y los scripts que importan `traci` o `sumolib` van dentro del contenedor:
  `docker exec -w /home/vanet/results/e-sert/<carpeta> van3twin bash -lc "<comando>"`.
- Es SUMO 1.12 con Python 3.10. Si algo de este prompt no existe en esa versión, adáptalo y
  anótalo en la bitácora.

## Objetivo
Correr la matriz completa de escenarios con el `rf_final` congelado de Pablo y el controlador
de `proyecto/traci/`, calcular estadísticas con intervalos de confianza y escribir tu sección
del informe (`informe/tyrone.md`).

## Pasos
1. **Modelo final.** Todavía no está en `proyecto/`: tráelo de la rama de Pablo sin editarla,
   a una carpeta temporal fuera del repo (binario seguro, no uses `git show >` en PowerShell):
   `git fetch origin && git archive origin/pablo/s4 semanas/S4/Pablo/codigo/ia | tar -x -C <tmp>`.
   Comprueba que el SHA-256 de `rf_final.joblib` coincide con `rf_final.json`. Si no existe
   aún, usa `rf_v1` de `proyecto/ia/` marcado `# MOCK: reemplazar cuando Pablo congele
   rf_final` y deja la corrida preparada para repetirse.
2. Crea `kpis/corrida_final.py`, encima del ejecutor de S3 (no lo dupliques: impórtalo):
   - Matriz: penetración {0, 20, 50, 80} % × clasificador {`umbral`, `rf_final`} × semillas
     {1, 2, 3, 4, 5}. El 0 % es la búsqueda a ciegas y corre una vez por semilla: 35 corridas.
   - Corridas en paralelo con `concurrent.futures.ProcessPoolExecutor(max_workers=cpu−1)`,
     cada una con su puerto TraCI propio y su carpeta `kpis/resultados/final/<esc>_<sem>/`
     (salidas crudas en `.gitignore`; se publican solo los CSV agregados).
   - Reanudable: si `kpis.json` de una corrida ya existe, se salta.
   - Ejecútala en segundo plano y vigílala con `Monitor` (por ejemplo, contando los
     `kpis.json` terminados). Anota el tiempo total.
3. Escribe `manifiesto.json`: `git rev-parse` de `proyecto/` usado, SHA-256 del modelo,
   versión de SUMO (`sumo --version`), `sumocfg`, `--veh-hora` calibrado, semillas, fecha,
   sistema operativo y CPU.
4. **Estadística** (`resumen.csv` y `resumen.md`) por escenario:
   - media, desviación e IC 95 % *bootstrap* (10 000 remuestreos, semilla fija) de tiempo y
     distancia de búsqueda, CO₂ por vehículo que parquea y ocupación;
   - cambio relativo frente a la línea base y prueba de Mann-Whitney U (`scipy.stats`) contra
     el 0 %;
   - falsas liberaciones por 100 sesiones, retardo de cierre, error de facturación y
     precisión del mapa, con `umbral` frente a `rf_final` lado a lado (IC de Wilson para
     tasas).
5. **Controles de cordura:** menos del 1 % de vehículos con teletransporte en cada corrida;
   la línea base al 0 % queda a ±10 % de la de S3 (si no, explica por qué); `rf_final` no
   tiene más falsas liberaciones que `umbral`. Si un control falla, no maquilles: documéntalo.
6. Crea `kpis/figuras_finales.py`, que regenera todas las figuras desde `resumen.csv`
   (`dpi=300` en `informe/figuras/tyrone/`, `dpi=150` en evidencias), con colores del equipo
   y ejes en español: búsqueda frente a penetración con barras de IC, CO₂, falsas
   liberaciones umbral frente a RF, y precisión del mapa.
7. Escribe `informe/tyrone.md` (1 500–2 500 palabras) siguiendo `informe/GUIA_ESTILO.md` de
   Pablo (léelo de `origin/pablo/s4`): escenario SUMO (red, puestos, demanda, calibración
   85–95 %), diseño experimental, resultados con tablas generadas de `resumen.md`, discusión
   y limitaciones. Cada número lleva un comentario `<!-- fuente: kpis/resultados/final/resumen.csv -->`.
8. **Evidencias:** `s2_kpis-finales.png` (panel 2×2 de KPIs frente a penetración) y
   `s2_falsas-liberaciones.png` (umbral frente a RF por penetración).

## Dónde escribir
`semanas/S4/Tyrone/codigo/kpis/`, `semanas/S4/Tyrone/codigo/informe/tyrone.md`,
`semanas/S4/Tyrone/codigo/informe/figuras/tyrone/` y `evidencias/`.

## Hecho cuando
- [ ] Las 35 corridas terminaron y `resumen.csv` tiene una fila por escenario con IC 95 %.
- [ ] `manifiesto.json` permite repetir la corrida exacta.
- [ ] `python kpis/figuras_finales.py` regenera todas las figuras sin correr SUMO.
- [ ] Los controles de cordura del paso 5 están reportados (cumple o no, con cifras).
- [ ] `informe/tyrone.md` existe, sin `TODO` ni `MOCK`, con figuras enlazadas que existen.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S4, sesión 2, Tyrone). En "Pedidos a
otros": @Pablo, ruta de `informe/tyrone.md` y de `resumen.csv` (los necesitas para la sección
de IA); @Freddy, cualquier anomalía del controlador en la corrida.
