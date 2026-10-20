---
semana: S2
persona: Tyrone
sesion: 3
titulo: Escenarios con penetración de app y registro de la ocupación real
horas: 3-4
modulo: sumo
depende: [S1-Tyrone-3, S2-Tyrone-1]
entrega: [sumo/escenarios/generar_escenarios.py, sumo/escenarios/*.sumocfg, kpis/registrar_ocupacion.py, kpis/salidas/ocupacion_real_*.csv]
evidencias: [s3_penetracion-escenarios.png, s3_ocupacion-real.png]
---
# S2 · Sesión 3 · Tyrone 🔵: Escenarios con penetración de app y registro de la ocupación real

## Contexto
Lee `CLAUDE.md` y `docs/CONTEXTO.md` (sección Escenarios). Se comparan la búsqueda a ciegas
y la app con 0, 20, 50 y 80 % de usuarios, con al menos 2 semillas. El guiado real lo
integra Freddy en esta misma sesión (S2-3) y el ejecutor completo es de S3-1, así que hoy
dejas **los escenarios y la verdad de referencia** listos. La ocupación real es la base del
KPI "precisión del mapa" que Freddy calcula en S3-1.

## Objetivo
Generar escenarios comparables (misma demanda, distinto `con_app`) y un registrador TraCI
de la ocupación real de cada `parkingArea`, probados de punta a punta con 8 corridas.

## Pasos
1. Añade a `sumo/demanda/generar_demanda.py` el parámetro `--porc-app` (0 por defecto):
   - Usa un **generador aleatorio separado** (`numpy.random.default_rng([semilla, 7])`)
     para sortear `u_i ~ U(0,1)` por vehículo que busca; `con_app = 1` si `u_i < porc_app`.
     Así los usuarios del 20 % están contenidos en los del 50 % y del 80 % (escenarios
     anidados) y la demanda es idéntica entre escenarios de la misma semilla.
   - El tráfico de paso siempre lleva `con_app = 0`.
2. Crea `sumo/escenarios/generar_escenarios.py`: produce `{base,app20,app50,app80}_s{1,2}`
   con su `.rou.xml` y su `.sumocfg` (salidas en `sumo/salidas/<escenario>_s<N>/`) y un
   `escenarios.json` con la lista, la semilla, el porcentaje y el *hash* SHA-256 de la
   demanda. Comprueba que el número de vehículos y las horas de salida coinciden entre los 4
   escenarios de cada semilla.
3. Crea `kpis/registrar_ocupacion.py` como *hook* `on_paso` compatible con el `Controlador`
   de Freddy (`proyecto/traci/controlador.py`; si no está, un bucle TraCI mínimo marcado
   `# MOCK`):
   - cada `--periodo-s` (60 s por defecto) lee, para cada `parkingArea`,
     `traci.simulation.getParameter(pa, "parkingArea.occupancy")` y
     `"parkingArea.capacity"`;
   - escribe `kpis/salidas/ocupacion_real_<escenario>_s<N>.csv` con las columnas
     `t_sim,puesto_id,ocupados,capacidad`;
   - comprueba contra el stop-output de S2-1: la ocupación total debe coincidir en ±1 puesto
     en cada instante.
4. **Guiado provisional** solo para probar el flujo: si el guiado de Freddy no está en
   `proyecto/traci/` ni en `origin/freddy/s2`, crea `sumo/escenarios/guiado_oraculo.py`
   (`# MOCK: reemplazar por traci/guiado.py de Freddy en S3-1`) que, al insertarse un
   vehículo con `traci.vehicle.getParameter(veh, "con_app") == "1"`, elige el
   `parkingArea` libre más cercano a su destino y llama a
   `traci.vehicle.rerouteParkingArea(veh, pa)`. Así ya se ve una diferencia en los KPIs.
5. Corre las 8 corridas (4 escenarios × 2 semillas) **en paralelo como procesos en segundo
   plano** (`subprocess.Popen`, máximo `os.cpu_count() - 1` a la vez) y vigílalas con
   `Monitor` o `/loop 3m revisa qué corridas terminaron`. Luego aplica `kpis.kpis` a cada una.
6. Tabla `kpis/salidas/resumen_escenarios.csv`: escenario, semilla, búsqueda media,
   distancia media, CO₂ de búsqueda y ocupación media en la hora pico.
7. **Evidencias** (matplotlib, `dpi=150`):
   - `s3_penetracion-escenarios.png`: tiempo de búsqueda medio (con IC 95 %) frente al % de
     app, una línea por semilla, marcado como "guiado provisional" si se usó el mock;
   - `s3_ocupacion-real.png`: mapa de calor puesto × tiempo de la ocupación real de
     `app50_s1`.

## Dónde escribir
`semanas/S2/Tyrone/codigo/sumo/`, `semanas/S2/Tyrone/codigo/kpis/` y
`semanas/S2/Tyrone/evidencias/`. Los CSV de ocupación grandes van en `.gitignore`; publica
uno de muestra.

## Hecho cuando
- [ ] Los 8 escenarios existen y la demanda es idéntica entre escenarios de la misma
  semilla (mismo número de vehículos y horas de salida).
- [ ] Los usuarios con app están anidados: los de `app20` ⊂ `app50` ⊂ `app80`.
- [ ] `ocupacion_real_*.csv` coincide con el stop-output en ±1 puesto.
- [ ] Las 8 corridas terminan sin errores y con menos de 1 % de teletransportes.
- [ ] Existen las dos evidencias PNG y el PDF semanal (paso 6 del protocolo).

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 3, Tyrone), **incluido el PDF
semanal**. En "Pedidos a otros": @Freddy, la ruta y el formato de `ocupacion_real_*.csv`
para el KPI de precisión del mapa, y que `traci/guiado.py` reemplace el oráculo en S3-1.
