"""Estadística de la matriz de experimentos: IC 95 %, comparaciones pareadas y tablas (S3-2).

Corre en la computadora (no usa SUMO), desde `semanas/S3/Tyrone/codigo`:

    kpis/.venv/bin/python -m kpis.analisis            # tablas + hallazgos + visor/datos/base.json

Interfaz (la usan `kpis/figuras.py`, las tablas y los tests):

- `ic95(valores)`: media, desviación, n y semiancho `t(0,975; n−1)·s/√n` (réplica = semilla).
- `resumen(df, kpi)`: una fila por (penetración, clasificador) con `media, sd, n, semiancho, lo, hi`.
- `bootstrap_vehiculos(veh, col)`: IC complementario por *bootstrap* BCa sobre vehículos (semillas
  agrupadas, 10 000 remuestreos, `random_state=0`). Solo para la tabla, rotulado como tal.
- `pareado(df, kpi)`: `d_s = KPI(p, s) − KPI(0, s)` por semilla, IC 95 % de la media de `d` y
  cambio relativo `100·d_s/KPI(0, s)` con su IC.
- `umbral_vs_rf(df, kpi)`: `ttest_rel` por penetración (pareado por semilla) con corrección de Holm.
- Los `NaN` (corridas fallidas o KPIs pendientes) no rompen nada: cada celda lleva su `n` real.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

AQUI = Path(__file__).resolve().parent
RESULTADOS = AQUI / "resultados"
CSV = RESULTADOS / "experimentos.csv"

# KPI → (etiqueta, unidad, "menor es mejor")
KPIS = {
    "busqueda_media_s": ("Tiempo de búsqueda medio", "s", True),
    "busqueda_p90_s": ("Tiempo de búsqueda p90", "s", True),
    "distancia_busqueda_media_m": ("Distancia de búsqueda media", "m", True),
    "co2_busqueda_kg": ("CO₂ de búsqueda", "kg/h", True),
    "ocupacion_media": ("Ocupación media (hora pico)", "fracción", False),
    "falsas_lib_100": ("Falsas liberaciones", "por 100 sesiones", True),
    "retardo_cierre_mediana_s": ("Retardo de cierre (mediana)", "s", True),
    "error_fact_medio_usd": ("Error de facturación medio", "USD", True),
    "precision_mapa": ("Precisión del mapa", "fracción", False),
}
KPIS_SISTEMA = ["falsas_lib_100", "retardo_cierre_mediana_s", "error_fact_medio_usd", "precision_mapa"]


# ------------------------------------------------------------------ carga

def cargar(csv: Path = CSV) -> pd.DataFrame:
    df = pd.read_csv(csv)
    for c in KPIS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def cargar_vehiculos(dir_veh: Path = RESULTADOS / "vehiculos") -> pd.DataFrame:
    """Detalle por vehículo de todas las corridas (`<id>.csv.gz`), con penetración/clasificador/semilla."""
    partes = []
    for ruta in sorted(Path(dir_veh).glob("*.csv.gz")):
        with gzip.open(ruta, "rt", encoding="utf-8") as f:
            d = pd.read_csv(f)
        if d.empty:
            continue
        ident = ruta.name[:-len(".csv.gz")]
        pen, clf, sem = ident.split("_")
        d["penetracion"], d["clasificador"], d["semilla"] = int(pen[1:]), clf, int(sem[1:])
        partes.append(d)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


# ------------------------------------------------------------------ IC

def ic95(valores) -> dict:
    """IC 95 % t de Student de la media entre réplicas (ignora NaN)."""
    v = np.asarray([x for x in valores if x is not None and not (isinstance(x, float) and math.isnan(x))],
                   dtype=float)
    n = int(v.size)
    if n == 0:
        return {"media": np.nan, "sd": np.nan, "n": 0, "semiancho": np.nan, "lo": np.nan, "hi": np.nan}
    media = float(v.mean())
    if n == 1:
        return {"media": media, "sd": np.nan, "n": 1, "semiancho": np.nan, "lo": np.nan, "hi": np.nan}
    sd = float(v.std(ddof=1))
    semi = float(stats.t.ppf(0.975, n - 1) * sd / math.sqrt(n))
    return {"media": media, "sd": sd, "n": n, "semiancho": semi, "lo": media - semi, "hi": media + semi}


def resumen(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    """Media, sd, n e IC 95 % entre semillas por (penetración, clasificador)."""
    filas = []
    for (pen, clf), g in df.groupby(["penetracion", "clasificador"], sort=True):
        filas.append({"penetracion": pen, "clasificador": clf, "kpi": kpi, **ic95(g[kpi].tolist())})
    return pd.DataFrame(filas)


def bootstrap_vehiculos(veh: pd.DataFrame, col: str, n_resamples: int = 10_000) -> pd.DataFrame:
    """IC 95 % BCa de la media por vehículo, agrupando semillas (complemento de la tabla)."""
    filas = []
    if veh.empty:
        return pd.DataFrame(columns=["penetracion", "clasificador", "n_veh", "media", "lo", "hi"])
    for (pen, clf), g in veh.groupby(["penetracion", "clasificador"], sort=True):
        x = g[col].dropna().to_numpy(dtype=float)
        if x.size < 3:
            filas.append({"penetracion": pen, "clasificador": clf, "n_veh": int(x.size),
                          "media": float(x.mean()) if x.size else np.nan, "lo": np.nan, "hi": np.nan})
            continue
        r = stats.bootstrap((x,), np.mean, n_resamples=n_resamples, method="BCa", random_state=0)
        filas.append({"penetracion": pen, "clasificador": clf, "n_veh": int(x.size), "media": float(x.mean()),
                      "lo": float(r.confidence_interval.low), "hi": float(r.confidence_interval.high)})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ comparaciones

def linea_base(df: pd.DataFrame, kpi: str) -> pd.Series:
    """KPI de la búsqueda a ciegas (penetración 0) por semilla. Umbral y rf dan lo mismo al 0 %;
    se promedian las dos si existen (así una corrida fallida no deja la semilla sin base)."""
    b = df[df["penetracion"] == 0].groupby("semilla")[kpi].mean()
    return b


def pareado(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    """Diferencia pareada por semilla frente al 0 %: IC de la media de d y del cambio relativo (%)."""
    base = linea_base(df, kpi)
    filas = []
    for (pen, clf), g in df[df["penetracion"] > 0].groupby(["penetracion", "clasificador"], sort=True):
        g = g.set_index("semilla")[kpi]
        comunes = [s for s in g.index if s in base.index and not pd.isna(g[s]) and not pd.isna(base[s])]
        d = [g[s] - base[s] for s in comunes]
        rel = [100 * (g[s] - base[s]) / base[s] for s in comunes if base[s] != 0]
        icd, icr = ic95(d), ic95(rel)
        filas.append({"penetracion": pen, "clasificador": clf, "kpi": kpi, "n": icd["n"],
                      "dif_media": icd["media"], "dif_lo": icd["lo"], "dif_hi": icd["hi"],
                      "rel_media_pct": icr["media"], "rel_lo_pct": icr["lo"], "rel_hi_pct": icr["hi"],
                      "ic_cruza_cero": bool(icd["n"] < 2 or (icd["lo"] <= 0 <= icd["hi"]))})
    return pd.DataFrame(filas)


def umbral_vs_rf(df: pd.DataFrame, kpi: str) -> pd.DataFrame:
    """`ttest_rel` (rf − umbral, pareado por semilla) por penetración > 0, con Holm."""
    from statsmodels.stats.multitest import multipletests

    filas = []
    for pen, g in df[df["penetracion"] > 0].groupby("penetracion"):
        u = g[g["clasificador"] == "umbral"].set_index("semilla")[kpi]
        r = g[g["clasificador"] == "rf"].set_index("semilla")[kpi]
        comunes = [s for s in u.index if s in r.index and not pd.isna(u[s]) and not pd.isna(r[s])]
        p = np.nan
        if len(comunes) >= 2:
            dif = np.array([r[s] - u[s] for s in comunes])
            p = 1.0 if np.allclose(dif, dif[0]) and dif[0] == 0 else float(
                stats.ttest_rel([r[s] for s in comunes], [u[s] for s in comunes]).pvalue)
        filas.append({"penetracion": pen, "kpi": kpi, "n": len(comunes),
                      "umbral_media": float(u.mean()) if len(u) else np.nan,
                      "rf_media": float(r.mean()) if len(r) else np.nan,
                      "dif_rf_menos_umbral": float(np.mean([r[s] - u[s] for s in comunes])) if comunes else np.nan,
                      "p": p})
    out = pd.DataFrame(filas)
    validos = out["p"].notna() if len(out) else []
    out["p_holm"] = np.nan
    if len(out) and validos.any():
        out.loc[validos, "p_holm"] = multipletests(out.loc[validos, "p"], method="holm")[1]
    return out


# ------------------------------------------------------------------ tablas, hallazgos y base.json

def _fmt(media, semi, dec=1):
    if pd.isna(media):
        return "pendiente"
    if pd.isna(semi):
        return f"{media:.{dec}f} (n=1)"
    return f"{media:.{dec}f} ± {semi:.{dec}f}"


DECIMALES = {"busqueda_media_s": 0, "busqueda_p90_s": 0, "distancia_busqueda_media_m": 0, "co2_busqueda_kg": 2,
             "ocupacion_media": 3, "falsas_lib_100": 1, "retardo_cierre_mediana_s": 1,
             "error_fact_medio_usd": 3, "precision_mapa": 3}
TABLA = ["busqueda_media_s", "distancia_busqueda_media_m", "co2_busqueda_kg", "ocupacion_media",
         "falsas_lib_100", "retardo_cierre_mediana_s", "error_fact_medio_usd", "precision_mapa"]


def tabla(df: pd.DataFrame, veh: pd.DataFrame | None = None) -> pd.DataFrame:
    """Una fila por (penetración, clasificador): `media ± semiancho` (IC 95 % t, n semillas) y la
    mejora pareada del tiempo de búsqueda frente a la búsqueda a ciegas; más el IC bootstrap por
    vehículo del tiempo de búsqueda."""
    res = {k: resumen(df, k).set_index(["penetracion", "clasificador"]) for k in TABLA}
    par = pareado(df, "busqueda_media_s").set_index(["penetracion", "clasificador"])
    boot = None
    if veh is not None and not veh.empty:
        boot = bootstrap_vehiculos(veh, "tiempo_busqueda_s").set_index(["penetracion", "clasificador"])
    filas = []
    for idx in res["busqueda_media_s"].index:
        fila = {"Penetración (%)": idx[0], "Clasificador": idx[1], "n": int(res["busqueda_media_s"].loc[idx, "n"])}
        for k in TABLA:
            r = res[k].loc[idx]
            fila[f"{KPIS[k][0]} ({KPIS[k][1]})"] = _fmt(r["media"], r["semiancho"], DECIMALES[k])
        if idx in par.index:
            p = par.loc[idx]
            fila["Δ búsqueda vs a ciegas (%)"] = (f"{p['rel_media_pct']:+.1f} [{p['rel_lo_pct']:+.1f}; "
                                                 f"{p['rel_hi_pct']:+.1f}]") if p["n"] >= 2 else "—"
        else:
            fila["Δ búsqueda vs a ciegas (%)"] = "referencia"
        if boot is not None and idx in boot.index:
            b = boot.loc[idx]
            fila["Búsqueda por vehículo, bootstrap BCa (s)"] = f"{b['media']:.0f} [{b['lo']:.0f}; {b['hi']:.0f}]"
        filas.append(fila)
    return pd.DataFrame(filas)


def escribir_tablas(t: pd.DataFrame, destino: Path = RESULTADOS) -> tuple:
    md = destino / "tabla_kpis.md"
    tex = destino / "tabla_kpis.tex"
    cab = ("# Tabla de KPIs por escenario\n\n"
           "Media ± semiancho del IC 95 % (t de Student entre semillas; n = semillas). "
           "Δ: cambio relativo pareado por semilla frente a la búsqueda a ciegas (penetración 0), "
           "con su IC 95 %. La última columna es un IC complementario por *bootstrap* BCa sobre "
           "vehículos (semillas agrupadas, 10 000 remuestreos); la réplica independiente es la semilla.\n\n")
    md.write_text(cab + t.to_markdown(index=False) + "\n", encoding="utf-8")
    latex = t.to_latex(index=False, escape=True, column_format="ll" + "r" * (len(t.columns) - 2),
                       caption="KPIs por penetración y clasificador (media ± semiancho IC 95 \\%).",
                       label="tab:kpis")
    # estilo booktabs (pandas ya usa \toprule/\midrule/\bottomrule)
    tex.write_text("% Requiere \\usepackage{booktabs}\n" + latex, encoding="utf-8")
    return md, tex


def _cifra(x, dec=0):
    return f"{x:.{dec}f}".replace(".", ",")


def hallazgos(df: pd.DataFrame) -> list:
    """Frases con cifras e IC para el informe. Si un IC cruza el cero, se dice."""
    frases = []
    par_t = pareado(df, "busqueda_media_s")
    base = ic95(linea_base(df, "busqueda_media_s").tolist())
    frases.append(f"Con la búsqueda a ciegas (0 % de usuarios con app), el tiempo de búsqueda medio es "
                  f"{_cifra(base['media'])} s (IC 95 %: {_cifra(base['lo'])}–{_cifra(base['hi'])} s, "
                  f"n = {base['n']} semillas).")
    for kpi, nombre in (("busqueda_media_s", "el tiempo de búsqueda"),
                        ("distancia_busqueda_media_m", "la distancia de búsqueda"),
                        ("co2_busqueda_kg", "el CO₂ de búsqueda")):
        par = pareado(df, kpi)
        for pen in (20, 50, 80):
            sel = par[(par["penetracion"] == pen) & (par["clasificador"] == "rf")]
            if sel.empty or sel.iloc[0]["n"] < 2:
                continue
            p = sel.iloc[0]
            if kpi != "busqueda_media_s" and pen != 50:
                continue
            sg = lambda x: ("+" if x > 0 else "−" if x < 0 else "") + _cifra(abs(x), 1)  # noqa: E731
            texto = (f"Con {pen} % de usuarios (rf), {nombre} cambia {sg(p['rel_media_pct'])} % "
                     f"(IC 95 %: {sg(p['rel_lo_pct'])} a {sg(p['rel_hi_pct'])} %) frente a la búsqueda "
                     f"a ciegas, pareado por semilla (n = {int(p['n'])}).")
            if p["ic_cruza_cero"]:
                texto += " El IC cruza el cero: no hay mejora demostrada."
            frases.append(texto)
    occ = resumen(df, "ocupacion_media")
    frases.append("La ocupación media de la hora pico va de "
                  f"{_cifra(100 * occ['media'].min(), 1)} % a {_cifra(100 * occ['media'].max(), 1)} % entre escenarios: "
                  "la app no cambia cuántos autos estacionan, sino cuánto buscan.")
    fl = umbral_vs_rf(df, "falsas_lib_100")
    if fl["n"].max() if len(fl) else 0:
        for _, r in fl.iterrows():
            if r["n"] < 2:
                continue
            ir = ic95(df[(df.penetracion == r.penetracion) & (df.clasificador == "rf")]["falsas_lib_100"].tolist())
            iu = ic95(df[(df.penetracion == r.penetracion) & (df.clasificador == "umbral")]["falsas_lib_100"].tolist())
            if r.penetracion != 50:
                continue
            frases.append(f"Con 50 % de usuarios, las falsas liberaciones son {_cifra(iu['media'], 1)} por 100 "
                          f"sesiones con el umbral (IC 95 %: {_cifra(iu['lo'], 1)}–{_cifra(iu['hi'], 1)}) y "
                          f"{_cifra(ir['media'], 1)} con el RF ({_cifra(ir['lo'], 1)}–{_cifra(ir['hi'], 1)}); "
                          f"t pareada p = {_cifra(r['p'], 3)}, p de Holm = {_cifra(r['p_holm'], 3)} "
                          f"(3 comparaciones).")
    else:
        frases.append("Las falsas liberaciones (KPIs de sistema de Freddy) están pendientes en estas corridas.")
    pm = resumen(df, "precision_mapa")
    sel = pm[(pm["penetracion"].isin([0, 80])) & (pm["clasificador"] == "rf")]
    if len(sel) == 2 and sel["n"].min() >= 2:
        a, b = sel.iloc[0], sel.iloc[1]
        frases.append(f"La precisión del mapa de ocupación pasa de {_cifra(100 * a['media'], 1)} % "
                      f"(IC 95 %: {_cifra(100 * a['lo'], 1)}–{_cifra(100 * a['hi'], 1)} %) al 0 % a "
                      f"{_cifra(100 * b['media'], 1)} % ({_cifra(100 * b['lo'], 1)}–{_cifra(100 * b['hi'], 1)} %) "
                      f"con 80 % de usuarios.")
    ret = resumen(df, "retardo_cierre_mediana_s")
    r50 = ret[(ret.penetracion == 50)]
    if len(r50) and r50["n"].min() >= 2:
        partes = [f"{c}: {_cifra(r['media'], 1)} s (IC 95 %: {_cifra(r['lo'], 1)}–{_cifra(r['hi'], 1)})"
                  for c, r in r50.set_index("clasificador").iterrows()]
        frases.append("La mediana del retardo de cierre de la sesión al 50 % es " + "; ".join(partes) + ".")
    return frases


def escribir_hallazgos(df: pd.DataFrame, destino: Path = RESULTADOS / "hallazgos.md") -> Path:
    frases = hallazgos(df)
    n = len(df)
    texto = ("# Hallazgos de la matriz de experimentos\n\n"
             f"Fuente: `kpis/resultados/experimentos.csv` ({n} corridas; réplica = semilla; IC 95 % t de "
             "Student entre semillas, con n = 3 los intervalos son anchos y así se reportan). Se regenera con "
             "`python -m kpis.analisis`.\n\n" + "\n".join(f"{i}. {f}" for i, f in enumerate(frases, 1)) + "\n")
    destino.write_text(texto, encoding="utf-8")
    return destino


def exportar_base(df: pd.DataFrame, destino: Path) -> Path:
    """Medias de la búsqueda a ciegas (penetración 0) para el panel del visor (`visor/datos/base.json`)."""
    claves = {"busqueda_media_s": "busqueda_media_s", "falsas_lib_100": "falsas_liberaciones_100",
              "ocupacion_media": "ocupacion", "co2_busqueda_kg": "co2_busqueda_kg_h",
              "distancia_busqueda_media_m": "distancia_busqueda_media_m"}
    base = {}
    for k, nombre in claves.items():
        r = ic95(linea_base(df, k).tolist())
        base[nombre] = None if pd.isna(r["media"]) else round(r["media"], 4)
    datos = {"fuente": "kpis/resultados/experimentos.csv (penetración 0, media entre semillas)",
             "semillas": sorted(int(s) for s in df[df.penetracion == 0]["semilla"].unique()),
             "base": base}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(datos, indent=1, ensure_ascii=False), encoding="utf-8")
    return destino


def main(argv=None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Tablas, hallazgos y base.json desde experimentos.csv")
    ap.add_argument("--csv", default=str(CSV))
    ap.add_argument("--base-json", default=str(AQUI.parent / "visor" / "datos" / "base.json"))
    args = ap.parse_args(argv)
    df = cargar(Path(args.csv))
    veh = cargar_vehiculos()
    t = tabla(df, veh)
    md, tex = escribir_tablas(t)
    h = escribir_hallazgos(df)
    b = exportar_base(df, Path(args.base_json))
    print(t.to_string(index=False))
    print(f"\n{md}\n{tex}\n{h}\n{b}")


if __name__ == "__main__":
    main()
