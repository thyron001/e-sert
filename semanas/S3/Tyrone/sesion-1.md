---
semana: S3
persona: Tyrone
sesion: 1
titulo: Ejecutor de experimentos - penetración × clasificador × semillas
horas: 3-4
modulo: kpis
depende: [S2-Tyrone-1, S2-Tyrone-3, S2-Freddy-3, S2-Pablo-2]
entrega: [kpis/matriz.yaml, kpis/correr_una.py, kpis/experimentos.py, kpis/resultados/experimentos.csv, kpis/resultados/metadatos.json, kpis/tests/test_experimentos.py]
evidencias: [s1_matriz-progreso.png]
---
# S3 · Sesión 1 · Tyrone 🔵: Ejecutor de experimentos (penetración × clasificador × semillas)

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (escenarios y KPIs) y `docs/PLAN.md`. Es la primera sesión
de S3: copia `proyecto/kpis/` y `proyecto/sumo/` (unificados el domingo 1 de noviembre) a
`semanas/S3/Tyrone/codigo/` si aún no están. El controlador con guiado (S2-Freddy-3) se **lee**
desde `proyecto/traci/` y el modelo `rf_v1` desde `proyecto/ia/modelos/`. Los KPIs de sistema de
Freddy (S3-Freddy-1) se escriben esta misma semana: léelos sin editar de
`origin/freddy/s3:semanas/S3/Freddy/codigo/traci/kpis_sistema.py`; si no existen, crea un mock
`# MOCK: reemplazar cuando Freddy entregue kpis_sistema.py (S3-1)` que devuelva `NaN` en sus
columnas. Todo el análisis de S3-2 y la corrida final de S4 dependen de este ejecutor.

## Objetivo
Un ejecutor reproducible, paralelo y **reanudable** que corra la matriz completa
penetración {0, 20, 50, 80} % × clasificador {umbral, rf} × semillas {1, 2, 3} = 24 corridas y
deje un CSV consolidado con sus metadatos.

## Pasos
1. Crea `kpis/matriz.yaml`:
   ```yaml
   escenario: centro_base          # sumo/centro_base.sumocfg
   penetracion: [0, 20, 50, 80]    # % de vehículos con app
   clasificador: [umbral, rf]
   semillas: [1, 2, 3]
   duracion_s: 4500                # 15 min de warm-up + 60 min medidos
   warmup_s: 900
   modelo_rf: ia/modelos/rf_v1.joblib
   procesos: auto                  # min(os.cpu_count() - 1, 6)
   timeout_corrida_s: 1800
   ```
2. Crea `kpis/correr_una.py` con `correr(cfg: dict) -> dict`, aislada y sin estado global:
   - ID de corrida `p{pen:02d}_{clf}_s{sem}` (por ejemplo `p50_rf_s2`).
   - **Números aleatorios comunes:** la demanda depende solo de la semilla. Para asignar
     `con_app`, sortea `u_i ~ U(0,1)` por vehículo con `random.Random(semilla)` y usa
     `con_app = u_i < pen/100`. Así los usuarios del 20 % están dentro de los del 50 % y del 80 %.
   - `traci.start([...], label=id, port=sumolib.miscutils.getFreeSocketPort())` con `--seed`,
     `--no-step-log`, `--duration-log.disable` y salidas en `sumo/salidas/<id>/`.
   - Llama a `kpis.kpis` (S2-1) para búsqueda, distancia, CO₂ y ocupación (excluye el
     *warm-up*) y a `KPIsSistema.resumen()` de Freddy (o el mock).
   - Guarda además el detalle por vehículo en `kpis/resultados/vehiculos/<id>.csv.gz`.
3. Crea `kpis/experimentos.py`, CLI
   `python -m kpis.experimentos --matriz kpis/matriz.yaml [--procesos N] [--solo ID] [--forzar] [--rapida] [--dry-run]`:
   - `multiprocessing.get_context("spawn")` (obligatorio en Windows) y `Pool(maxtasksperchild=1)`,
     porque TraCI guarda estado por proceso. Lanza con `apply_async` y recoge con
     `get(timeout=timeout_corrida_s)`.
   - **Reanudable:** cada corrida escribe `resultados/corridas/<id>.json` de forma atómica
     (`.tmp` + `os.replace`). Al arrancar, salta las que ya tienen JSON con el mismo
     `hash_config` (SHA-256 del cfg canónico + hashes de la red, `parqueos.add.xml` y el modelo).
   - Un fallo deja `<id>.error.json` con el *traceback*, reintenta 1 vez y no detiene a las demás.
   - Escribe una línea por evento en `resultados/progreso.log` (`2026-11-02T15:04Z fin p20_rf_s1 312 s`).
   - `--rapida`: `duracion_s=600`, `warmup_s=120` y solo `p00_umbral_s1` y `p50_rf_s1`.
4. Al terminar, consolida `resultados/experimentos.csv` (una fila por corrida): `id, penetracion,
   clasificador, semilla, n_veh, n_busca, busqueda_media_s, busqueda_p90_s,
   distancia_busqueda_media_m, co2_busqueda_kg, ocupacion_media, falsas_lib_100,
   retardo_cierre_mediana_s, error_fact_medio_usd, precision_mapa, teleports, duracion_real_s`.
   Y `resultados/metadatos.json`: fecha UTC, `git rev-parse HEAD`, `sumo --version`, Python,
   hashes de entradas, procesos, duración total y corridas fallidas.
5. **Tests** (`kpis/tests/test_experimentos.py`, con `--rapida`):
   - con penetración 0, `umbral` y `rf` dan KPIs idénticos para la misma semilla (no hay usuarios
     que clasificar): es la prueba de determinismo;
   - repetir una corrida da el mismo JSON (salvo `duracion_real_s`);
   - matar el proceso a mitad y relanzar no repite corridas ya escritas;
   - los conjuntos `con_app` están anidados (20 % ⊂ 50 % ⊂ 80 %).
6. Mide una corrida sola para estimar el total y el *speedup* (`--rapida` con 1 y 4 procesos).
   Luego lanza la matriz **en segundo plano** y vigílala con `Monitor` sobre `progreso.log` o con
   `/loop 5m cuenta las corridas en kpis/resultados/corridas y reporta X/24`. Mientras corre, un
   subagente escribe los tests y otro la gráfica de evidencia.
7. **Evidencia** `evidencias/s1_matriz-progreso.png`: mapa de calor 4 × 2 (penetración ×
   clasificador) con el tiempo de búsqueda medio de las semillas y la anotación `n/3` en cada
   celda; en el título, la duración total y el número de procesos.

## Dónde escribir
`semanas/S3/Tyrone/codigo/kpis/`, `semanas/S3/Tyrone/codigo/sumo/` y `evidencias/`. Añade
`kpis/resultados/vehiculos/` y `sumo/salidas/` al `.gitignore` si no están.

## Hecho cuando
- [ ] `python -m kpis.experimentos --rapida` termina en menos de 5 min y deja el CSV.
- [ ] La matriz completa tiene 24/24 corridas en `experimentos.csv`, o las fallidas están
  documentadas con su `.error.json`.
- [ ] Relanzar tras una interrupción no repite corridas (test).
- [ ] Penetración 0 da los mismos KPIs con `umbral` y `rf` (test).
- [ ] Con 4 procesos el *speedup* es de al menos 2,5× frente a 1 proceso.
- [ ] `metadatos.json` está completo y existe `s1_matriz-progreso.png`.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S3, sesión 1, Tyrone). En "Pedidos a otros":
@Freddy, confirma las claves exactas de `KPIsSistema.resumen()`; @Pablo, confirma la ruta y el
hash de `rf_v1` que usaste.
