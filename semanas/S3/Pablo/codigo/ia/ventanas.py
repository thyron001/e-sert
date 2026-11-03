"""
Remuestreo y ventaneo de trazas GPS.

Librería genérica: funciona con GeoLife, SUMO o teléfono real.
Entrada: DataFrame con columnas del contrato (usuario_id, t, lat, lon, ...).
"""
import numpy as np
import pandas as pd

from .caracteristicas import desplazamiento_neto


def remuestrear(
    df: pd.DataFrame,
    hz: int = 1,
    max_hueco_s: float = 10.0,
) -> pd.DataFrame:
    """
    Interpola lat/lon linealmente a `hz` Hz dentro de cada segmento.
    Parte el segmento cuando hay huecos mayores que `max_hueco_s`.
    """
    resultados = []
    cols_grupo = "segmento_id" if "segmento_id" in df.columns else "usuario_id"

    for seg_id, grupo in df.groupby(cols_grupo):
        grupo = grupo.sort_values("t").reset_index(drop=True)
        if len(grupo) < 2:
            continue

        t = grupo["t"].values.astype(float)
        huecos = np.diff(t)
        cortes = np.where(huecos > max_hueco_s)[0]

        limites = np.concatenate([[0], cortes + 1, [len(grupo)]])

        for k in range(len(limites) - 1):
            inicio, fin = limites[k], limites[k + 1]
            if fin - inicio < 2:
                continue
            sub = grupo.iloc[inicio:fin]
            t_sub = sub["t"].values.astype(float)
            t_nuevo = np.arange(t_sub[0], t_sub[-1], 1.0 / hz)
            if len(t_nuevo) < 2:
                continue

            lat_i = np.interp(t_nuevo, t_sub, sub["lat"].values)
            lon_i = np.interp(t_nuevo, t_sub, sub["lon"].values)

            fila = {
                "t": t_nuevo.astype(int),
                "lat": lat_i,
                "lon": lon_i,
                "usuario_id": sub["usuario_id"].iloc[0],
                "modo_real": sub["modo_real"].iloc[0] if "modo_real" in sub.columns else None,
                "segmento_id": f"{seg_id}_r{k}",
            }
            if "precision_m" in sub.columns:
                prec = sub["precision_m"].values
                if np.all(np.isnan(prec)):
                    fila["precision_m"] = np.full(len(t_nuevo), np.nan)
                else:
                    fila["precision_m"] = np.interp(
                        t_nuevo, t_sub, np.nan_to_num(prec, nan=0.0)
                    )
            if "fuente" in sub.columns:
                fila["fuente"] = sub["fuente"].iloc[0]

            resultados.append(pd.DataFrame(fila))

    if not resultados:
        return pd.DataFrame()
    return pd.concat(resultados, ignore_index=True)


def ventanear(
    df: pd.DataFrame,
    largo_s: int = 30,
    paso_s: int = 5,
    min_cobertura: float = 0.8,
    min_pureza: float = 0.8,
    umbral_quieto_vel: float = 0.3,
    umbral_quieto_desp: float = 10.0,
) -> list[dict]:
    """
    Genera ventanas de `largo_s` segundos con paso de `paso_s`.

    Derivación de quieto: una ventana a_pie o vehiculo con velocidad mediana
    < umbral_quieto_vel y desplazamiento neto < umbral_quieto_desp se
    reetiqueta como quieto.

    Devuelve lista de dicts con metadatos y la ventana (sub-DataFrame).
    """
    esperadas = largo_s  # a 1 Hz
    ventanas = []
    cols_grupo = "segmento_id" if "segmento_id" in df.columns else "usuario_id"

    for seg_id, grupo in df.groupby(cols_grupo):
        grupo = grupo.sort_values("t").reset_index(drop=True)
        t_vals = grupo["t"].values

        if len(grupo) < esperadas * min_cobertura:
            continue

        t_min, t_max = t_vals[0], t_vals[-1]
        for t_inicio in range(int(t_min), int(t_max) - largo_s + 1, paso_s):
            t_fin = t_inicio + largo_s
            mascara = (t_vals >= t_inicio) & (t_vals < t_fin)
            sub = grupo[mascara]

            if len(sub) < esperadas * min_cobertura:
                continue

            if "modo_real" in sub.columns and sub["modo_real"].notna().any():
                conteo = sub["modo_real"].value_counts()
                modo_mayoritario = conteo.index[0]
                pureza = conteo.iloc[0] / len(sub)
                if pureza < min_pureza:
                    continue
            else:
                modo_mayoritario = None
                pureza = 1.0

            desp = desplazamiento_neto(sub["lat"].values, sub["lon"].values)
            duracion = float(sub["t"].iloc[-1] - sub["t"].iloc[0])
            vel_efectiva = desp / duracion if duracion > 0 else 0.0

            reetiquetada = False
            if (
                modo_mayoritario in ("a_pie", "vehiculo")
                and vel_efectiva < umbral_quieto_vel
                and desp < umbral_quieto_desp
            ):
                modo_mayoritario = "quieto"
                reetiquetada = True

            ventanas.append({
                "usuario_id": sub["usuario_id"].iloc[0],
                "segmento_id": seg_id,
                "t_inicio": t_inicio,
                "t_fin": t_fin,
                "n_muestras": len(sub),
                "modo_real": modo_mayoritario,
                "pureza": pureza,
                "reetiquetada_quieto": reetiquetada,
                "fuente": sub["fuente"].iloc[0] if "fuente" in sub.columns else None,
                "_ventana": sub,
            })

    return ventanas
