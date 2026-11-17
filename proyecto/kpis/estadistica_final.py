"""Estadística de la corrida final (S4-2): `resumen.csv` y `resumen.md` desde `resultados/final/`.

    python -m kpis.estadistica_final        # en la computadora o en el contenedor (no usa SUMO)

Por escenario (`ciegas` = 0 %, `p20_umbral`, `p20_rf_final`, …):

- tiempo y distancia de búsqueda, CO₂ por vehículo que estaciona: media, desviación entre semillas
  e IC 95 % *bootstrap* jerárquico (10 000 remuestreos, semilla 0): se remuestrean semillas y, dentro
  de cada una, vehículos; así el IC respeta que la réplica independiente es la semilla;
- ocupación media de la hora pico: IC *bootstrap* sobre las semillas;
- cambio relativo frente a la búsqueda a ciegas y prueba de Mann-Whitney U (vehículos, bilateral);
- falsas liberaciones por 100 sesiones con IC de Wilson (sesiones agrupadas), retardo de cierre,
  error de facturación y precisión del mapa (IC t entre semillas), umbral frente a rf_final;
- controles de cordura: teletransportes < 1 % por corrida, línea base a ±10 % de la de S3-1 y
  rf_final sin más falsas liberaciones que el umbral.
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
FINAL = AQUI / "resultados" / "final"
S3_CSV = AQUI / "resultados" / "experimentos.csv"
N_BOOT = 10_000
Z = 1.959963984540054
NOMBRE_CLF = {"umbral": "umbral", "rf": "rf_final"}


ORACULO = "p50_oraculo"  # sensibilidad: guiado con la ocupación real de SUMO (no es el sistema)


def escenario(pen: int, clf: str, oraculo: bool = False) -> str:
    if oraculo:
        return f"p{pen:02d}_oraculo"
    return "ciegas" if pen == 0 else f"p{pen:02d}_{NOMBRE_CLF[clf]}"


def cargar_corridas(final: Path = FINAL) -> pd.DataFrame:
    filas = []
    for k in sorted(final.glob("*/kpis.json")):
        d = json.loads(k.read_text(encoding="utf-8"))
        f = dict(d["fila"])
        s = d["extra"].get("kpis_sistema") or {}
        f.update({"n_sesiones": s.get("n_sesiones"), "n_falsas": s.get("n_falsas"),
                  "escenario": escenario(f["penetracion"], f["clasificador"], str(f["id"]).endswith("_oraculo")),
                  "origen": d.get("origen")})
        filas.append(f)
    df = pd.DataFrame(filas)
    for c in df.columns:
        if c not in ("id", "clasificador", "escenario", "origen"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def cargar_vehiculos(final: Path = FINAL) -> pd.DataFrame:
    partes = []
    for ruta in sorted((final / "vehiculos").glob("*.csv.gz")):
        with gzip.open(ruta, "rt", encoding="utf-8") as fh:
            d = pd.read_csv(fh)
        if d.empty:
            continue
        pen, clf, sem, *resto = ruta.name[:-7].split("_")
        if int(pen[1:]) == 0 and clf == "rf":
            continue
        d["penetracion"], d["clasificador"], d["semilla"] = int(pen[1:]), clf, int(sem[1:])
        d["escenario"] = escenario(int(pen[1:]), clf, resto == ["oraculo"])
        partes.append(d)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


# ------------------------------------------------------------------ intervalos

def boot_jerarquico(grupos: list, n: int = N_BOOT, semilla: int = 0) -> tuple:
    """IC 95 % percentil de la media: remuestrea grupos (semillas) y vehículos dentro de cada uno."""
    grupos = [np.asarray(g, dtype=float) for g in grupos if len(g)]
    if not grupos:
        return (np.nan, np.nan)
    rng = np.random.default_rng(semilla)
    k = len(grupos)
    medias = np.empty(n)
    elegidos = rng.integers(0, k, size=(n, k))
    for b in range(n):
        tot, cnt = 0.0, 0
        for j in elegidos[b]:
            g = grupos[j]
            m = g[rng.integers(0, g.size, size=g.size)]
            tot += m.sum()
            cnt += g.size
        medias[b] = tot / cnt
    return (float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5)))


def boot_simple(valores, n: int = N_BOOT, semilla: int = 0) -> tuple:
    v = np.asarray([x for x in valores if not pd.isna(x)], dtype=float)
    if v.size < 2:
        return (np.nan, np.nan)
    rng = np.random.default_rng(semilla)
    medias = v[rng.integers(0, v.size, size=(n, v.size))].mean(axis=1)
    return (float(np.percentile(medias, 2.5)), float(np.percentile(medias, 97.5)))


def wilson(exitos: int, n: int) -> tuple:
    if not n:
        return (np.nan, np.nan, np.nan)
    p = exitos / n
    den = 1 + Z ** 2 / n
    centro = (p + Z ** 2 / (2 * n)) / den
    semi = Z * math.sqrt(p * (1 - p) / n + Z ** 2 / (4 * n ** 2)) / den
    return (p, max(0.0, centro - semi), min(1.0, centro + semi))  # el redondeo puede dar -1e-17


def ic_t(valores) -> tuple:
    v = np.asarray([x for x in valores if not pd.isna(x)], dtype=float)
    if v.size < 2:
        return (float(v.mean()) if v.size else np.nan, np.nan, np.nan)
    m, s = v.mean(), v.std(ddof=1)
    semi = stats.t.ppf(0.975, v.size - 1) * s / math.sqrt(v.size)
    return (float(m), float(m - semi), float(m + semi))


# ------------------------------------------------------------------ resumen

KPI_VEH = {"busqueda": "tiempo_busqueda_s", "distancia": "distancia_busqueda_m", "co2": "co2_busqueda_g"}


def resumen(df: pd.DataFrame, veh: pd.DataFrame) -> pd.DataFrame:
    orden = ["ciegas"] + [escenario(p, c) for p in (20, 50, 80) for c in ("umbral", "rf")] + [ORACULO]
    base_veh = veh[veh["escenario"] == "ciegas"] if not veh.empty else veh
    base_run = df[df["escenario"] == "ciegas"]
    filas = []
    for esc in orden:
        g = df[df["escenario"] == esc]
        if g.empty:
            continue
        v = veh[veh["escenario"] == esc] if not veh.empty else veh
        fila = {"escenario": esc, "penetracion": int(g["penetracion"].iloc[0]),
                "clasificador": "—" if esc == "ciegas" else "oráculo" if esc == ORACULO
                else NOMBRE_CLF[g["clasificador"].iloc[0]],
                "n_semillas": int(g["semilla"].nunique()), "n_vehiculos": int(len(v))}
        for corto, col in KPI_VEH.items():
            por_sem = [v[v["semilla"] == s][col].dropna().to_numpy() for s in sorted(g["semilla"].unique())] \
                if not v.empty else []
            medias_sem = [x.mean() for x in por_sem if len(x)]
            media = float(np.concatenate(por_sem).mean()) if por_sem and any(len(x) for x in por_sem) else np.nan
            lo, hi = boot_jerarquico(por_sem)
            fila.update({f"{corto}_media": media, f"{corto}_sd_semillas": float(np.std(medias_sem, ddof=1))
                         if len(medias_sem) > 1 else np.nan, f"{corto}_ic_lo": lo, f"{corto}_ic_hi": hi})
            if esc != "ciegas" and not base_veh.empty and len(v):
                b = base_veh[col].dropna()
                fila[f"{corto}_cambio_pct"] = 100 * (media - b.mean()) / b.mean()
                fila[f"{corto}_mw_p"] = float(stats.mannwhitneyu(v[col].dropna(), b, alternative="two-sided").pvalue)
            else:
                fila[f"{corto}_cambio_pct"] = np.nan
                fila[f"{corto}_mw_p"] = np.nan
        # quién gana: búsqueda de los autos con app frente a los sin app (mismo escenario)
        for grupo, val in (("con_app", 1), ("sin_app", 0)):
            sel = v[v["con_app"].astype(int) == val]["tiempo_busqueda_s"] if len(v) and "con_app" in v else []
            fila[f"busqueda_{grupo}_media"] = float(np.mean(sel)) if len(sel) else np.nan
            fila[f"n_{grupo}"] = int(len(sel))
        occ = g["ocupacion_media"]
        lo, hi = boot_simple(occ)
        fila.update({"ocupacion_media": float(occ.mean()), "ocupacion_sd": float(occ.std(ddof=1)),
                     "ocupacion_ic_lo": lo, "ocupacion_ic_hi": hi,
                     "ocupacion_cambio_pct": np.nan if esc == "ciegas" else
                     100 * (occ.mean() - base_run["ocupacion_media"].mean()) / base_run["ocupacion_media"].mean()})
        n_ses, n_fal = int(g["n_sesiones"].fillna(0).sum()), int(g["n_falsas"].fillna(0).sum())
        p, lo, hi = wilson(n_fal, n_ses)
        fila.update({"n_sesiones": n_ses, "n_falsas": n_fal, "falsas_100": 100 * p if n_ses else np.nan,
                     "falsas_100_wilson_lo": 100 * lo if n_ses else np.nan,
                     "falsas_100_wilson_hi": 100 * hi if n_ses else np.nan})
        for col, corto in (("retardo_cierre_mediana_s", "retardo_cierre_s"), ("error_fact_medio_usd", "error_fact_usd"),
                           ("precision_mapa", "precision_mapa")):
            m, lo, hi = ic_t(g[col])
            fila.update({corto: m, f"{corto}_ic_lo": lo, f"{corto}_ic_hi": hi})
        fila["teleports_pct_max"] = float((100 * g["teleports"] / g["n_veh"]).max())
        fila["co2_kg_h_media"] = float(g["co2_busqueda_kg"].mean())
        filas.append(fila)
    return pd.DataFrame(filas)


def controles(df: pd.DataFrame, res: pd.DataFrame) -> dict:
    tele = (100 * df["teleports"] / df["n_veh"])
    c1 = {"descripcion": "menos del 1 % de vehículos con teletransporte en cada corrida",
          "max_pct": round(float(tele.max()), 3), "corridas": int(len(df)), "cumple": bool((tele < 1).all())}
    base_final = float(df[df["escenario"] == "ciegas"]["busqueda_media_s"].mean())
    c2 = {"descripcion": "línea base (0 %) a ±10 % de la de S3-1", "final_s": round(base_final, 1)}
    if S3_CSV.exists():
        s3 = pd.read_csv(S3_CSV)
        base_s3 = float(s3[s3["penetracion"] == 0]["busqueda_media_s"].mean())
        c2.update({"s3_s": round(base_s3, 1), "diferencia_pct": round(100 * (base_final - base_s3) / base_s3, 2),
                   "cumple": abs(base_final - base_s3) <= 0.10 * base_s3,
                   "nota": "S3-1 usó las semillas 1–3; la final, 1–5 (las 1–3 son las mismas corridas)."})
    else:
        c2.update({"cumple": None, "nota": "no está resultados/experimentos.csv de S3-1"})
    comp = []
    for pen in (20, 50, 80):
        u = res[(res["penetracion"] == pen) & (res["clasificador"] == "umbral")]
        r = res[(res["penetracion"] == pen) & (res["clasificador"] == "rf_final")]
        if len(u) and len(r):
            comp.append({"penetracion": pen, "umbral": round(float(u["falsas_100"].iloc[0]), 2),
                         "rf_final": round(float(r["falsas_100"].iloc[0]), 2),
                         "cumple": bool(r["falsas_100"].iloc[0] <= u["falsas_100"].iloc[0])})
    c3 = {"descripcion": "rf_final no tiene más falsas liberaciones que el umbral", "por_penetracion": comp,
          "cumple": all(c["cumple"] for c in comp) if comp else None}
    return {"teletransportes": c1, "linea_base_vs_s3": c2, "rf_final_vs_umbral": c3}


# ------------------------------------------------------------------ Markdown

def _n(x, dec=0):
    if x is None or pd.isna(x):
        return "—"
    return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",").replace("-", "−")  # signo menos tipográfico


def _ic(m, lo, hi, dec=0):
    return f"{_n(m, dec)} [{_n(lo, dec)}; {_n(hi, dec)}]"


def _p(p):
    if pd.isna(p):
        return "—"
    return "< 0,001" if p < 0.001 else _n(p, 3)


def markdown(res: pd.DataFrame, ctl: dict, df: pd.DataFrame) -> str:
    l = ["# Resumen de la corrida final (S4-2)", "",
         f"Fuente: `kpis/resultados/final/<id>/kpis.json` ({len(df)} corridas) y `resumen.csv`. "
         "IC 95 %: *bootstrap* jerárquico (semillas y vehículos, 10 000 remuestreos, semilla 0) para los KPIs "
         "por vehículo; *bootstrap* sobre semillas para la ocupación; Wilson para las falsas liberaciones "
         "(sesiones agrupadas); t de Student entre semillas para el resto. Δ: cambio frente a la búsqueda a "
         "ciegas; p: Mann-Whitney U bilateral sobre vehículos frente al 0 %.", "",
         "## KPIs de búsqueda", "",
         "| Escenario | n semillas | Vehículos | Búsqueda (s) [IC 95 %] | Δ | p | Distancia (m) [IC 95 %] | Δ | "
         "CO₂ por vehículo (g) [IC 95 %] | Δ | Ocupación (%) [IC 95 %] |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for _, r in res.iterrows():
        d = lambda k: "—" if pd.isna(r[k]) else f"{'+' if r[k] > 0 else ''}{_n(r[k], 1)} %"  # noqa: E731
        l.append(f"| {r['escenario']} | {r['n_semillas']} | {_n(r['n_vehiculos'])} | "
                 f"{_ic(r['busqueda_media'], r['busqueda_ic_lo'], r['busqueda_ic_hi'])} | {d('busqueda_cambio_pct')} | "
                 f"{_p(r['busqueda_mw_p'])} | {_ic(r['distancia_media'], r['distancia_ic_lo'], r['distancia_ic_hi'])} | "
                 f"{d('distancia_cambio_pct')} | {_ic(r['co2_media'], r['co2_ic_lo'], r['co2_ic_hi'])} | "
                 f"{d('co2_cambio_pct')} | {_ic(100 * r['ocupacion_media'], 100 * r['ocupacion_ic_lo'], 100 * r['ocupacion_ic_hi'], 1)} |")
    l += ["", "## Umbral frente a rf_final", "",
          "| Penetración | Clasificador | Sesiones | Falsas /100 [Wilson 95 %] | Retardo de cierre, mediana (s) [IC 95 %] | "
          "Error de facturación (USD) [IC 95 %] | Precisión del mapa (%) [IC 95 %] |",
          "|---:|---|---:|---:|---:|---:|---:|"]
    for _, r in res[res["escenario"] != "ciegas"].iterrows():
        l.append(f"| {r['penetracion']} % | {r['clasificador']} | {_n(r['n_sesiones'])} | "
                 f"{_ic(r['falsas_100'], r['falsas_100_wilson_lo'], r['falsas_100_wilson_hi'], 1)} | "
                 f"{_ic(r['retardo_cierre_s'], r['retardo_cierre_s_ic_lo'], r['retardo_cierre_s_ic_hi'], 1)} | "
                 f"{_ic(r['error_fact_usd'], r['error_fact_usd_ic_lo'], r['error_fact_usd_ic_hi'], 3)} | "
                 f"{_ic(100 * r['precision_mapa'], 100 * r['precision_mapa_ic_lo'], 100 * r['precision_mapa_ic_hi'], 1)} |")
    c = ctl
    l += ["", "## Controles de cordura", "",
          f"1. **Teletransportes < 1 % por corrida:** {'cumple' if c['teletransportes']['cumple'] else 'NO cumple'} "
          f"(máximo {_n(c['teletransportes']['max_pct'], 3)} % en {c['teletransportes']['corridas']} corridas).",
          f"2. **Línea base a ±10 % de S3-1:** "
          f"{'cumple' if c['linea_base_vs_s3'].get('cumple') else 'NO cumple' if c['linea_base_vs_s3'].get('cumple') is False else 'sin dato'} "
          f"(final {_n(c['linea_base_vs_s3']['final_s'], 1)} s; S3-1 {_n(c['linea_base_vs_s3'].get('s3_s'), 1)} s; "
          f"diferencia {_n(c['linea_base_vs_s3'].get('diferencia_pct'), 2)} %). {c['linea_base_vs_s3'].get('nota', '')}",
          f"3. **rf_final sin más falsas liberaciones que el umbral:** "
          f"{'cumple' if c['rf_final_vs_umbral']['cumple'] else 'NO cumple'} ("
          + "; ".join(f"{x['penetracion']} %: umbral {_n(x['umbral'], 1)} vs rf_final {_n(x['rf_final'], 1)}"
                      for x in c['rf_final_vs_umbral']['por_penetracion']) + ").", ""]
    return "\n".join(l)


def main(argv=None) -> str:
    df = cargar_corridas()
    if df.empty:
        return "sin corridas en resultados/final/"
    veh = cargar_vehiculos()
    res = resumen(df, veh)
    ctl = controles(df, res)
    res.to_csv(FINAL / "resumen.csv", index=False, float_format="%.6g", lineterminator="\n")
    (FINAL / "controles.json").write_text(json.dumps(ctl, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    (FINAL / "resumen.md").write_text(markdown(res, ctl, df), encoding="utf-8")
    return f"{len(df)} corridas → {FINAL / 'resumen.csv'}, resumen.md y controles.json"


if __name__ == "__main__":
    print(main())
