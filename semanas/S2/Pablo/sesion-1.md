---
semana: S2
persona: Pablo
sesion: 1
titulo: Ventanas desde trazas de SUMO y ruido GPS calibrado con literatura
horas: 3-4
modulo: ia
depende: [S1-Pablo-2, S1-Freddy-3]
entrega: [ia/particion_usuarios.json, ia/particion.py, ia/datos_sumo.py, ia/ruido.py, ia/sensibilidad_sigma.py, ia/calibracion/ruido_literatura.json, ia/calibracion/FUENTES.md, ia/datos/ventanas_v2.parquet, ia/datos/ventanas_prueba_geolife.parquet, ia/tests/]
evidencias: [s1_distribuciones-features.png, s1_sensibilidad-sigma.png]
---
# S2 · Sesión 1 · Pablo 🟢: Ventanas desde trazas de SUMO y ruido GPS calibrado con literatura

## Contexto
Lee `CLAUDE.md`, `docs/CONTEXTO.md` (sección IA) y `docs/CONTRATO.md` (secciones 2 y 7). Es la
primera sesión de S2: copia `proyecto/ia/` a `semanas/S2/Pablo/codigo/ia/` si no existe la copia.
Las trazas de Freddy están en `proyecto/traci/trazas/` (`sumo_semilla<N>.csv` o la muestra de
5 000 filas); si faltan, genera trazas sintéticas con tu propio AR(1) marcadas `# MOCK`.
**Todo el proyecto es simulado**: no hay grabaciones del Centro. El ruido GPS se calibra con
valores publicados y con un análisis de sensibilidad, y la prueba final (S2-3) usará **usuarios
de GeoLife nunca vistos** y **escenarios difíciles de SUMO**. Por eso hoy se congela la partición.

## Objetivo
Crear la partición fija de usuarios de prueba, sumar ventanas de SUMO al dataset con un ruido
GPS justificado por la literatura (σ de 3 a 15 m en cañón urbano) y decidir con datos qué mezcla
de σ usar en entrenamiento.

## Pasos
1. **Partición fija** (`ia/particion.py` → `ia/particion_usuarios.json`), lo primero de todo:
   - sobre los ~69 usuarios etiquetados de GeoLife, reserva el 20 % como prueba con
     `numpy.random.default_rng(2026)`, estratificado: cada usuario de prueba debe tener ≥ 10 min
     de `a_pie` o de `vehiculo`, y el conjunto de prueba ≥ 60 min de cada clase (incluido
     `quieto` derivado). Si no se cumple, repite con la semilla siguiente y anótalo;
   - reserva también las **semillas de SUMO 101–105** para los escenarios difíciles de S2-3
     (Freddy entrena con 1–3; no las mezcles);
   - el JSON guarda `semilla`, `criterio`, `usuarios_prueba`, `usuarios_entrenamiento`,
     `semillas_sumo_prueba`, minutos por clase y el SHA-256 de la lista. **Nunca se edita
     después**: un test compara el *hash*.
2. **Valores de la literatura** (`ia/calibracion/FUENTES.md` y `ruido_literatura.json`):
   tabla `fuente | entorno | métrica | valor`. Fuentes sugeridas (verifica DOI y cifra; lo que no
   puedas confirmar se marca **"por verificar"**, nunca se inventa):
   - Zandbergen (2009), *Transactions in GIS* 13(s1): precisión de ubicaciones del iPhone (A-GPS);
   - Zandbergen y Barbeau (2011), *Journal of Navigation* 64(3): A-GPS en teléfonos;
   - Merry y Bettinger (2019), *PLoS ONE* 14(7) e0219890: GPS de teléfono en entorno urbano;
   - Groves (2011), *Journal of Navigation* 64(3): errores en cañón urbano (*shadow matching*);
   - Jun, Guensler y Ogle (2006), *Transportation Research Record* 1972: error GPS aleatorio y
     su efecto en velocidad y aceleración.
   Resultado: `sigma_m` en {3, 5, 8, 10, 15}, `rho` ∈ [0,7; 0,95] a 1 Hz (por verificar; el
   AR(1) de Freddy usa 0,8), `p_perdida` 0,02–0,10 y `precision_m ≈ sigma_m × U(0,8; 1,5)`.
3. Crea `ia/ruido.py` con `aplicar_ruido_ar1(df, sigma_m, rho, p_perdida, semilla)` (ruido por
   eje en metros, proyección local equirectangular, reconvertido a lat/lon; recalcula
   `velocidad_mps` y `precision_m`). Si las trazas de Freddy ya traen ruido, no lo apiles:
   usa sus columnas limpias o pídele una salida sin ruido (`--sin-ruido`).
4. Crea `ia/datos_sumo.py`: remuestreo a 1 Hz, ventanas de 30 s con paso de 5 s y características
   de S1-2 (reutiliza las funciones, no las dupliques). Etiqueta = modo mayoritario si cubre
   ≥ 80 % de la ventana; si no, se descarta y se cuenta. `grupo` = `usuario_id`.
5. **Análisis de sensibilidad** (`ia/sensibilidad_sigma.py`), **solo con usuarios de
   entrenamiento** y `GroupKFold(5)`: entrena el RF de S1-3 con σ_entr ∈ {0, 3, 8, 15, mezcla
   U(3, 15)} y evalúa con σ_val ∈ {3, 5, 8, 10, 15}. Matriz de macro-F1 y de la tasa
   `vehiculo → a_pie` en `ia/reportes/sensibilidad_sigma.csv`. Elige la configuración más
   robusta (la de mejor peor caso) y guárdala en `ruido_literatura.json` como `entrenamiento`.
   Corre la rejilla **en segundo plano** y vigílala con `Monitor`.
6. **Mezcla con GeoLife** → `ia/datos/ventanas_v2.parquet` (solo entrenamiento):
   - GeoLife ya trae ruido real: conserva el original y añade una copia aumentada del 50 % de
     sus segmentos con σ de la mezcla elegida; SUMO entra con ruido de la mezcla;
   - columnas `origen` (`geolife`|`sumo`), `grupo`, `modo`, `t_inicio`, `sigma_aplicado_m`,
     `aumentada` y las características; SUMO no supera el 50 % de las ventanas de cada clase;
   - balance de clases por origen; si una clase supera el 60 %, anota la estrategia para S2-2.
   Aparte, `ventanas_prueba_geolife.parquet` con los usuarios de prueba **sin aumentar**.
7. **Comparación de distribuciones**: Kolmogórov-Smirnov por clase entre GeoLife y SUMO
   (velocidad media, desviación de la velocidad, p95 de la aceleración, cambio de rumbo) en
   `ia/reportes/ks_origenes.csv`.
8. **Tests** (`ia/tests/`): `aplicar_ruido_ar1` reproduce `sigma_m` (±10 %) y `rho` (±0,05) en
   10 000 muestras; ninguna ventana mezcla dos `grupo`; **ningún usuario de prueba ni semilla
   101–105 aparece en `ventanas_v2.parquet`**; el *hash* de la partición no cambió.
   Paraleliza: un subagente hace `FUENTES.md` y `ruido.py` mientras tú haces la partición y
   `datos_sumo.py`.
9. **Evidencias** (matplotlib, `dpi=150`):
   - `s1_distribuciones-features.png`: densidades de la velocidad media por clase y origen;
   - `s1_sensibilidad-sigma.png`: mapa de calor σ_entr × σ_val de la macro-F1, con la
     configuración elegida recuadrada.

## Dónde escribir
`semanas/S2/Pablo/codigo/ia/` y `semanas/S2/Pablo/evidencias/`. Los `.parquet` grandes van en
`.gitignore`; publica una muestra y el *hash* del completo. `particion_usuarios.json` sí va al repo.

## Hecho cuando
- [ ] `particion_usuarios.json` existe con semilla, usuarios de prueba, semillas 101–105 y *hash*.
- [ ] `FUENTES.md` cita cada valor de σ y ρ o lo marca "por verificar".
- [ ] `sensibilidad_sigma.csv` existe y la mezcla de entrenamiento elegida está justificada.
- [ ] `ventanas_v2.parquet` tiene GeoLife y SUMO, las tres clases y `grupo`, sin usuarios de prueba.
- [ ] Los tests pasan, incluido el de no fuga.
- [ ] Existen las dos evidencias PNG.

## Cierre
Ejecuta el **Protocolo de cierre** de `CLAUDE.md` (S2, sesión 1, Pablo). En "Pedidos a
otros": @Freddy, los parámetros de `ruido_literatura.json` para tu `EmuladorGPS`, la opción de
trazas sin ruido y que no uses las semillas 101–105; @Miguel, la ruta de la partición, por si
algún día hay grabaciones caseras (opcionales) que validar.
