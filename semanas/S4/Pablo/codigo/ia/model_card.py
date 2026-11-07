"""
Genera ia/MODEL_CARD.md (formato de Mitchell et al., 2019) a partir de los reportes de `rf_final`.

    python3 -m ia.model_card

Todas las cifras se leen de ia/modelos/rf_final.json, ia/reportes/metricas_rf_final.json,
ia/reportes/entrenamiento_final_datos.json, ia/reportes/curvas_sigma_final.csv y
ia/reportes/suavizado_k_final*.csv; cada bloque lleva su comentario `fuente`.
"""
import json
from pathlib import Path

import pandas as pd

AQUI = Path(__file__).resolve().parent
REP = AQUI / "reportes"
CLASES = ["a_pie", "quieto", "vehiculo"]


def f(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def miles(n):
    return f"{int(n):,}".replace(",", " ")


def tabla(filas, cab):
    L = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    L += ["| " + " | ".join(str(c) for c in r) + " |" for r in filas]
    return "\n".join(L)


def main():
    meta = json.loads((AQUI / "modelos/rf_final.json").read_text())
    m = json.loads((REP / "metricas_rf_final.json").read_text())
    ent = json.loads((REP / "entrenamiento_final_datos.json").read_text())
    curvas = pd.read_csv(REP / "curvas_sigma_final.csv")
    sk = pd.read_csv(REP / "suavizado_k_final_contrato.csv")
    sf = pd.read_csv(REP / "suavizado_k_final.csv")
    F = m["fuentes"]
    geo = F["geolife_prueba"]
    h = meta["hiperparametros"]
    entr = meta["entrenamiento"]
    lat = m.get("latencia", {})
    tl = m["trafico_lento"]
    sha = meta["sha256_modelo"]

    filas_ent = [[o, c, miles(n)] for o, c, n in
                 [(r["origen"], r["modo_real"], r["n"]) for r in entr["por_origen_y_clase"]]]
    filas_met = []
    for k, etq in (("geolife_prueba", "GeoLife, usuarios no vistos"), ("sumo_normal", "SUMO normal (σ = 5 m)"),
                   ("sumo_trafico_lento", "SUMO tráfico lento (σ = 5 m)"), ("sumo_peaton_rapido", "SUMO peatón rápido (σ = 5 m)")):
        if k in F:
            r = F[k]
            ic = r["rf_final"]["bootstrap"]["macro_f1_ic95"]
            filas_met.append([etq, miles(r["n_ventanas"]), f(r["umbral"]["macro_f1"]),
                              f"{f(r['rf_final']['macro_f1'])} [{f(ic[0])}; {f(ic[1])}]"])
    filas_cls = []
    for c in CLASES:
        u, r = geo["umbral"]["por_clase"][c], geo["rf_final"]["por_clase"][c]
        filas_cls.append([c, f(u["precision"]), f(u["recall"]), f(r["precision"]), f(r["recall"]), f(r["f1"]), miles(r["support"])])
    cu = curvas[curvas["sistema"] == "umbral"].set_index("sigma")["macro_f1"]
    cr = curvas[curvas["sistema"] == "rf_final"].set_index("sigma")["macro_f1"]
    filas_sig = [[int(s), f(cu[s]), f(cr[s])] for s in cr.index]
    s1 = sk[(sk["sistema"] == "rf") & (sk["metodo"] == "mayoria")].set_index("k")
    s1f = sf[(sf["sistema"] == "rf") & (sf["metodo"] == "mayoria")].set_index("k")
    umb = sk[(sk["sistema"] == "umbral") & (sk["metodo"] == "mayoria")].set_index("k")

    vs = geo.get("vs_umbral", {}).get("rf_final", {})
    md = f"""# Model card: `rf_final`

> **MODELO CONGELADO.** A partir de esta sesión (S4-1) el modelo no cambia. Cualquier cambio posterior sería
> `rf_final_v2` y se avisa con un pedido a Tyrone, Freddy y Miguel. SHA-256 del archivo:
> `{sha}`. <!-- fuente: ia/modelos/rf_final.json:sha256_modelo -->

## 1. Detalles del modelo

- **Qué es:** clasificador Random Forest de scikit-learn {meta['sklearn_version']} que, a partir de una ventana de
  `{meta['ventana_s']} s` de GPS a 1 Hz (con paso de `{meta['paso_s']} s`), decide si el usuario va `a_pie`, `quieto` o en `vehiculo`
  (contrato §2). <!-- fuente: ia/modelos/rf_final.json -->
- **Hiperparámetros:** {h['n_estimators']} árboles, profundidad máxima {h['max_depth']}, mínimo {h['min_samples_leaf']} muestras por
  hoja, `{h['max_features']}` características por división, pesos de clase `{h['class_weight']}`, `random_state` {h['random_state']}.
  Parten del mejor resultado de S2-2 (`ia/reportes/cv_rf_v1.json`: 200 árboles y hoja mínima 3); con las ventanas ruidosas ese modelo pesaba
  106,6 MB, así que se redujo a {h['n_estimators']} árboles y hoja mínima {h['min_samples_leaf']} para quedar bajo 50 MB. <!-- fuente: ia/modelos/rf_final.json -->
- **Entrada:** 18 características por ventana (velocidad, aceleración, *jerk*, rumbo, paradas, geometría y precisión), en el orden
  de `rf_final.json`. **Salida:** `ResultadoModo = {{modo, confianza, fuente}}`.
- **Archivo:** `ia/modelos/rf_final.joblib` (`compress=3`, {f(meta['tamano_mb'], 1)} MB), con su hash en `rf_final.json`.
  `ia/inferencia.py` lo carga por defecto, verifica el SHA-256 y, si no coincide o falta, cae al umbral del contrato con un aviso
  en el registro. En ejecución se convierte a arreglos de NumPy (`ia/bosque_plano.py`) para bajar la latencia.
- **Suavizado y *fallback*:** `k = {meta['suavizado']['k']}` (sin suavizar) con la máquina de estados de Freddy actual y `k = {meta['suavizado_recomendado']['con_maquina_del_contrato']['k']}` si se adopta la tabla literal del contrato (Sección 8); el RF solo se usa con cobertura de al menos
  `{meta['fallback']['cobertura_min']}` y huecos de `{meta['fallback']['hueco_max_s']:.0f} s` o menos; con menos de `{meta['fallback']['puntos_min']}`
  puntos se devuelve el resultado previo o el umbral con confianza 0.
- **Autor:** Pablo Calle (proyecto e-sert, Redes Vehiculares, Universidad de Cuenca). **Fecha:** {meta['fecha'][:10]}.

## 2. Uso previsto

- **Uso principal:** detectar la **salida real del auto** para no liberar el puesto de parqueo antes de tiempo. La máquina de estados
  de la sesión cierra cuando dos ventanas seguidas son `vehiculo` y el teléfono está a más de `20 m` del puesto.
- **Usuarios previstos:** el controlador TraCI y el modo espejo del backend (simulación), y la app de parqueo en la zona SERT.
- **Condiciones:** GPS a `1 Hz` (se remuestrea si hace falta), ventanas de `30 s`, ruido de posición de pocos metros.

## 3. Usos fuera de alcance

- Otros modos de transporte (bicicleta, bus, tren): GeoLife se filtró a caminar y vehículo.
- Distinguir un auto en atasco a paso de peatón de una persona caminando: con solo GPS es indistinguible (Sección 8).
- Vigilancia o seguimiento de personas, o decisiones sancionatorias a partir de la clase detectada.
- Uso en campo sin validación previa: **todo el entrenamiento y la evaluación son simulados** o de otra ciudad.
- GPS de baja frecuencia (menos de 1 Hz) o ventanas de otra duración.

## 4. Factores

Velocidad de la ventana, nivel de ruido GPS (σ), precisión reportada, escenario (normal, tráfico lento, peatón rápido) y
cercanía a un cambio de modo. El análisis por contexto está en `ia/reportes/errores_contexto.csv`.

## 5. Métricas

F1 macro (promedio del F1 de las tres clases), precisión y *recall* por clase, matriz de confusión e intervalo de confianza del
95 % por *bootstrap* agrupado ({m['fuentes']['geolife_prueba']['rf_final']['bootstrap']['n_bootstrap']} remuestreos de usuarios o trayectorias). A
nivel de sistema, falsas liberaciones por 100 sesiones y retardo de cierre (S3-2).

## 6. Datos de evaluación

Solo datos nunca vistos en el entrenamiento: los 10 usuarios de GeoLife de `ia/particion_usuarios.json` y las semillas de SUMO
101 a 105 (escenarios `normal`, `trafico_lento` y `peaton_rapido`, σ = 5 m; curvas con σ de 0 a 15 m). Grabaciones caseras: no
disponibles. Las etiquetas de SUMO se calculan por tramos de modo constante.

## 7. Datos de entrenamiento

- **GeoLife** (Beijing): {ent['usuarios_geolife_entrenamiento']} usuarios que no están en la partición de prueba; la mitad de las ventanas recibe ruido AR(1)
  (σ de 3 a 15 m, ρ = 0,8) aplicado a las posiciones; la clase `quieto` se deriva (velocidad mediana < 0,3 m/s y desplazamiento
  neto < 10 m).
- **SUMO:** episodios de parqueo (estacionar, caminar, volver, manejar) de las semillas {', '.join(map(str, entr['semillas_sumo']))}, con ruido
  AR(1) en el 90 % de las ventanas.
- Las características se recalculan sobre las posiciones ruidosas con el mismo código de inferencia, y las ventanas se muestrean por clase
  (hasta 100 000 de GeoLife y 50 000 de SUMO por clase). Total: {miles(entr['n_ventanas'])} ventanas.

*Ventanas de entrenamiento por origen y clase.*

{tabla(filas_ent, ['Origen', 'Clase', 'Ventanas'])}

<!-- fuente: ia/modelos/rf_final.json:entrenamiento -->

## 8. Resultados

*F1 macro por fuente (IC 95 % del RF por *bootstrap* agrupado).*

{tabla(filas_met, ['Fuente', 'Ventanas', 'Umbral', 'RF final'])}

<!-- fuente: ia/reportes/metricas_rf_final.json -->

En usuarios no vistos de GeoLife la diferencia RF menos umbral es de {f(vs.get('delta_media', float('nan')))} puntos de F1 macro
(IC 95 %: {f(vs.get('delta_ic95', [float('nan')] * 2)[0])} a {f(vs.get('delta_ic95', [float('nan')] * 2)[1])}). <!-- fuente: ia/reportes/metricas_rf_final.json -->

*Precisión y *recall* por clase en GeoLife (usuarios no vistos).*

{tabla(filas_cls, ['Clase', 'Precisión umbral', 'Recall umbral', 'Precisión RF', 'Recall RF', 'F1 RF', 'Soporte'])}

<!-- fuente: ia/reportes/metricas_rf_final.json -->

*F1 macro frente a σ (SUMO, escenario normal).*

{tabla(filas_sig, ['σ (m)', 'Umbral', 'RF final'])}

<!-- fuente: ia/reportes/curvas_sigma_final.csv -->

**Escenarios difíciles.** Frente a `rf_v1`, `rf_final` empeora en tráfico lento (el RF clasifica el {f(100 * F['sumo_trafico_lento']['rf_final']['confusion_conteos'][2][0] / sum(F['sumo_trafico_lento']['rf_final']['confusion_conteos'][2]), 0)} % de los vehículos a paso de peatón como `a_pie`) y en peatón rápido (*recall* de `a_pie` de {f(F['sumo_peaton_rapido']['rf_final']['por_clase']['a_pie']['recall'], 2)}), a cambio de mejorar en SUMO normal. <!-- fuente: ia/reportes/metricas_rf_final.json -->

**Tráfico lento.** El F1 de `vehiculo` es {f(tl['rf_final']['f1_vehiculo'])} con el RF y {f(tl['umbral']['f1_vehiculo'])} con el umbral; el *recall*
de `vehiculo` con velocidad menor que 8 km/h es {f(tl['rf_final']['recall_vehiculo_lt_8kmh'])} y {f(tl['umbral']['recall_vehiculo_lt_8kmh'])}. <!-- fuente: ia/reportes/metricas_rf_final.json -->

**Falsas liberaciones (S3-2, repetido con `rf_final`; 300 sesiones de SUMO, σ de 5, 10 y 15 m).** El umbral cierra en falso
{f(umb.loc[1, 'falsas_100'], 1)} sesiones por 100. Con la máquina de Freddy tal como está, el RF libera en falso {f(s1f.loc[1, 'falsas_100'], 1)} por 100 con `k = 1`, pero cierra
bien solo el {f(s1f.loc[1, 'cierre_correcto_pct'], 1)} % de las sesiones. Con las transiciones literales del contrato cierra bien el {f(s1.loc[1, 'cierre_correcto_pct'], 1)} % (retardo mediano
{f(s1.loc[1, 'retardo_mediano_s'], 0)} s), pero libera en falso {f(s1.loc[1, 'falsas_100'], 1)} por 100 con `k = 1` y {f(s1.loc[5, 'falsas_100'], 1)} con `k = 5`. Por nivel de ruido (contrato, `k = 1`): {f(s1.loc[1, 'falsas_100_s5'], 1)},
{f(s1.loc[1, 'falsas_100_s10'], 1)} y {f(s1.loc[1, 'falsas_100_s15'], 1)} por 100 con σ de 5, 10 y 15 m. Esas liberaciones ocurren muy antes de la salida real (mediana
{f(-s1.loc[1, 'falsas_adelanto_mediano_s'], 0)} s antes), es decir, son liberaciones genuinas y no cierres anticipados por segundos. <!-- fuente: ia/reportes/suavizado_k_final_contrato.csv; ia/reportes/suavizado_k_final.csv -->

**Latencia de `clasificar`** en {miles(lat.get('n_llamadas', 0))} llamadas: p50 {f(lat.get('p50_ms', 0), 2)} ms, p95 {f(lat.get('p95_ms', 0), 2)} ms y p99 {f(lat.get('p99_ms', 0), 2)} ms
(meta: menos de 5 ms). <!-- fuente: ia/reportes/metricas_rf_final.json -->

![](../../evidencias/s1_model-card-metricas.png)

## 9. Consideraciones éticas y privacidad

Las trazas de GeoLife son un conjunto público anonimizado; las de SUMO son simuladas. En un despliegue real el servicio solo necesita
ventanas de 30 s de ubicación: conviene clasificar en el dispositivo o descartar las coordenadas tras clasificar, y guardar solo el
modo, la confianza y la hora. Una trayectoria permite inferir hábitos y domicilio, por lo que no debe conservarse más de lo necesario.

## 10. Limitaciones y sesgos

1. **GeoLife es Beijing:** otro tráfico, otra geometría urbana y otros hábitos de movilidad que un centro histórico andino.
2. **Con ruido de 10 a 15 m el RF sí libera en falso** (Sección 8): hace falta `k = 5` con la tabla del contrato, o más precisión de GPS.
3. **Todo es simulado y no hay datos de campo:** SUMO no modela el multitrayecto real de las fachadas del Centro Histórico.
4. **El ruido es un AR(1) calibrado con literatura** (σ de 3 a 15 m, ρ = 0,8): captura el error lento y correlacionado, no los saltos
   del multitrayecto; los valores exactos son una elección del proyecto.
5. **Tráfico lento:** un auto a paso de peatón es indistinguible de una persona caminando solo con GPS.
6. **Teléfono dentro del auto o en mano:** el modelo no sabe dónde está el teléfono; si queda en el auto, la sesión se cierra cuando
   el auto sale aunque el dueño no esté. Un acelerómetro ayudaría.
7. **Pocas semillas de SUMO en el entrenamiento** ({', '.join(map(str, entr['semillas_sumo']))}) y una sola configuración de escenario.
8. **Sin grabaciones caseras:** no hay validación con GPS real de un teléfono.
9. **Etiqueta `quieto` derivada en GeoLife:** depende de los umbrales de velocidad y desplazamiento elegidos.

## 11. Cómo reproducirlo

```bash
# 1) episodios de SUMO de entrenamiento (en el contenedor van3twin; una semilla por corrida)
docker exec -w /home/vanet/results/e-sert/semanas/S4/Pablo/codigo van3twin bash -lc "python3 ia/grabar_episodios.py --semilla 201 --hasta 4800"
# 2) ventanas con ruido sobre las posiciones y 3) entrenamiento determinista (dos corridas dan el mismo SHA-256)
python3 -m ia.datos.construir_entrenamiento_final
python3 -m ia.entrenar_final
# 4) evaluación final y tests
python3 -m ia.evaluar_final
python3 -m pytest ia/tests -q
```

Entradas con su SHA-256 en `ia/modelos/rf_final.json:entrenamiento.sha256_entradas`.
"""
    (AQUI / "MODEL_CARD.md").write_text(md, encoding="utf-8")
    print("->", AQUI / "MODEL_CARD.md")


if __name__ == "__main__":
    main()
