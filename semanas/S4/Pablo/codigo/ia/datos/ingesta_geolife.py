"""
Ingesta de GeoLife Trajectories 1.3.

Lee los archivos .plt de los usuarios que tienen labels.txt, mapea los modos
de transporte a las clases del proyecto (a_pie, quieto, vehiculo) y genera
un Parquet limpio con el formato CSV del contrato (docs/CONTRATO.md §7).

GeoLife usa hora GMT (UTC) según su documentación.
"""
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from tqdm import tqdm

DIR_SCRIPT = Path(__file__).resolve().parent
DIR_CRUDOS = DIR_SCRIPT / "crudos"
DIR_PROCESADOS = DIR_SCRIPT / "procesados"
ARCHIVO_PARQUET = DIR_PROCESADOS / "geolife_etiquetado.parquet"
ARCHIVO_MUESTRA = DIR_PROCESADOS / "geolife_muestra.csv"
ARCHIVO_INFO = DIR_SCRIPT / "geolife_info.json"

MAPA_MODOS = {
    "walk": "a_pie",
    "car": "vehiculo",
    "taxi": "vehiculo",
    "bus": "vehiculo",
}
MODOS_DESCARTADOS = {
    "bike", "train", "subway", "airplane", "boat", "run", "motorcycle",
}

VELOCIDAD_MAX_MPS = 50.0
LAT_MIN, LAT_MAX = -90.0, 90.0
LON_MIN, LON_MAX = -180.0, 180.0

R_TIERRA_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine en metros entre dos puntos (grados)."""
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * R_TIERRA_M * math.asin(math.sqrt(a))


def haversine_vectorizado(lat1, lon1, lat2, lon2):
    """Haversine vectorizado con NumPy (radianes de entrada en grados)."""
    rlat1, rlat2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
    return 2 * R_TIERRA_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def encontrar_raiz_geolife(dir_crudos: Path) -> Path:
    """Busca el directorio 'Data' dentro de la extracción de GeoLife."""
    for candidato in [
        dir_crudos / "Geolife Trajectories 1.3" / "Data",
        dir_crudos / "Data",
    ]:
        if candidato.is_dir():
            return candidato
    raise FileNotFoundError(
        f"No se encontró el directorio Data de GeoLife dentro de {dir_crudos}"
    )


def usuarios_con_etiquetas(raiz_data: Path) -> list[Path]:
    """Devuelve los directorios de usuarios que tienen labels.txt."""
    return sorted(
        d for d in raiz_data.iterdir()
        if d.is_dir() and (d / "labels.txt").exists()
    )


def leer_labels(archivo_labels: Path) -> pd.DataFrame:
    """Lee labels.txt: Start Time, End Time, Transportation Mode."""
    df = pd.read_csv(
        archivo_labels,
        sep="\t",
        skiprows=1,
        header=None,
        names=["inicio", "fin", "modo_original"],
    )
    df["inicio"] = pd.to_datetime(df["inicio"], format="%Y/%m/%d %H:%M:%S", utc=True)
    df["fin"] = pd.to_datetime(df["fin"], format="%Y/%m/%d %H:%M:%S", utc=True)
    df["modo_original"] = df["modo_original"].str.strip().str.lower()
    return df


def leer_plt(archivo_plt: Path) -> pd.DataFrame:
    """
    Lee un .plt de GeoLife (6 líneas de cabecera).
    Columnas: lat, lon, 0, alt_ft, dias_desde_1899, fecha, hora.
    La hora está en GMT (UTC) según la documentación de GeoLife.
    """
    df = pd.read_csv(
        archivo_plt,
        skiprows=6,
        header=None,
        names=["lat", "lon", "cero", "alt_ft", "dias", "fecha", "hora"],
    )
    df["timestamp"] = pd.to_datetime(
        df["fecha"] + " " + df["hora"], format="%Y-%m-%d %H:%M:%S", utc=True
    )
    df = df[["lat", "lon", "timestamp"]].copy()
    return df


def unir_con_etiquetas(puntos: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """
    Une puntos GPS con los intervalos de labels.txt usando merge_asof.
    Solo conserva los puntos que caen dentro de un intervalo etiquetado.
    """
    puntos = puntos.sort_values("timestamp").reset_index(drop=True)
    labels = labels.sort_values("inicio").reset_index(drop=True)

    merged = pd.merge_asof(
        puntos,
        labels.rename(columns={"inicio": "timestamp_label"}),
        left_on="timestamp",
        right_on="timestamp_label",
        direction="backward",
    )
    mascara = (
        merged["timestamp_label"].notna()
        & (merged["timestamp"] <= merged["fin"])
    )
    merged = merged[mascara].copy()
    merged.drop(columns=["timestamp_label", "fin"], inplace=True)
    return merged


def procesar_usuario(dir_usuario: Path) -> tuple[pd.DataFrame | None, dict]:
    """Procesa un usuario completo: lee todos sus .plt y los une con labels."""
    usuario_id = f"geolife_{dir_usuario.name}"
    labels = leer_labels(dir_usuario / "labels.txt")
    stats = {"puntos_totales": 0, "descartados_modo": 0, "descartados_coord": 0,
             "descartados_velocidad": 0}

    dir_trayectorias = dir_usuario / "Trajectory"
    if not dir_trayectorias.exists():
        return None, stats

    partes = []
    for plt_file in sorted(dir_trayectorias.glob("*.plt")):
        try:
            df = leer_plt(plt_file)
        except Exception:
            continue
        if df.empty:
            continue
        partes.append(df)

    if not partes:
        return None, stats

    puntos = pd.concat(partes, ignore_index=True)
    puntos = puntos.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
    stats["puntos_totales"] = len(puntos)

    merged = unir_con_etiquetas(puntos, labels)
    if merged.empty:
        return None, stats

    sin_modo = merged["modo_original"].isna()
    merged = merged[~sin_modo]

    mascara_descartado = merged["modo_original"].isin(MODOS_DESCARTADOS)
    stats["descartados_modo"] = int(mascara_descartado.sum())
    merged = merged[~mascara_descartado]

    merged["modo_real"] = merged["modo_original"].map(MAPA_MODOS)
    merged = merged[merged["modo_real"].notna()]

    if merged.empty:
        return None, stats

    fuera_rango = (
        (merged["lat"] < LAT_MIN) | (merged["lat"] > LAT_MAX)
        | (merged["lon"] < LON_MIN) | (merged["lon"] > LON_MAX)
    )
    stats["descartados_coord"] = int(fuera_rango.sum())
    merged = merged[~fuera_rango]

    merged = merged.sort_values("timestamp").reset_index(drop=True)

    segmentos = (
        (merged["modo_original"] != merged["modo_original"].shift())
        | (merged["timestamp"].diff().dt.total_seconds() > 300)
    ).cumsum()
    merged["segmento_id"] = usuario_id + "_seg" + segmentos.astype(str)

    dist = haversine_vectorizado(
        merged["lat"].values[:-1], merged["lon"].values[:-1],
        merged["lat"].values[1:], merged["lon"].values[1:],
    )
    dt = merged["timestamp"].diff().dt.total_seconds().values[1:]
    vel = np.where(dt > 0, dist / dt, 0.0)
    merged["velocidad_mps"] = np.concatenate([[np.nan], vel])

    mismo_seg = merged["segmento_id"] == merged["segmento_id"].shift()
    merged.loc[~mismo_seg, "velocidad_mps"] = np.nan

    salto = merged["velocidad_mps"].abs() > VELOCIDAD_MAX_MPS
    stats["descartados_velocidad"] = int(salto.sum())
    merged = merged[~salto]

    merged["usuario_id"] = usuario_id
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    merged["t"] = (merged["timestamp"] - epoch).dt.total_seconds().astype("int64")
    merged["precision_m"] = np.nan
    merged["fuente"] = "geolife"

    columnas = [
        "usuario_id", "t", "lat", "lon", "precision_m",
        "velocidad_mps", "modo_real", "segmento_id", "fuente", "modo_original",
    ]
    return merged[columnas].copy(), stats


def generar_info(df: pd.DataFrame, stats_acum: dict) -> dict:
    """Genera estadísticas del dataset para geolife_info.json."""
    dt_seg = df.groupby("segmento_id")["t"].apply(lambda s: s.diff().dropna())
    intervalos = dt_seg.values.astype(float)
    intervalos = intervalos[intervalos > 0]

    horas_por_clase = {}
    for modo, grupo in df.groupby("modo_real"):
        dur_total = 0.0
        for _, seg in grupo.groupby("segmento_id"):
            if len(seg) > 1:
                dur_total += seg["t"].iloc[-1] - seg["t"].iloc[0]
        horas_por_clase[modo] = round(dur_total / 3600, 2)

    horas_por_modo_original = {}
    for modo, grupo in df.groupby("modo_original"):
        dur_total = 0.0
        for _, seg in grupo.groupby("segmento_id"):
            if len(seg) > 1:
                dur_total += seg["t"].iloc[-1] - seg["t"].iloc[0]
        horas_por_modo_original[modo] = round(dur_total / 3600, 2)

    return {
        "puntos": len(df),
        "segmentos": df["segmento_id"].nunique(),
        "usuarios": df["usuario_id"].nunique(),
        "horas_por_clase": horas_por_clase,
        "horas_por_modo_original": horas_por_modo_original,
        "intervalo_muestreo": {
            "mediana_s": round(float(np.median(intervalos)), 2) if len(intervalos) > 0 else None,
            "p90_s": round(float(np.percentile(intervalos, 90)), 2) if len(intervalos) > 0 else None,
        },
        "descartados": stats_acum,
    }


def ejecutar(dir_crudos: Path = DIR_CRUDOS) -> Path:
    DIR_PROCESADOS.mkdir(parents=True, exist_ok=True)
    raiz = encontrar_raiz_geolife(dir_crudos)
    usuarios = usuarios_con_etiquetas(raiz)
    print(f"Usuarios con etiquetas: {len(usuarios)}")

    partes = []
    stats_total = {"puntos_totales": 0, "descartados_modo": 0,
                   "descartados_coord": 0, "descartados_velocidad": 0}

    for dir_u in tqdm(usuarios, desc="Usuarios"):
        df_u, st = procesar_usuario(dir_u)
        for k in stats_total:
            stats_total[k] += st[k]
        if df_u is not None and not df_u.empty:
            partes.append(df_u)

    if not partes:
        raise RuntimeError("No se obtuvieron datos de ningún usuario.")

    df = pd.concat(partes, ignore_index=True)
    df.to_parquet(ARCHIVO_PARQUET, index=False)
    print(f"Parquet guardado: {ARCHIVO_PARQUET} ({len(df)} filas)")

    muestra = df.sample(n=min(10_000, len(df)), random_state=42)
    columnas_csv = [
        "usuario_id", "t", "lat", "lon", "precision_m",
        "velocidad_mps", "modo_real", "segmento_id", "fuente",
    ]
    muestra[columnas_csv].to_csv(ARCHIVO_MUESTRA, index=False)
    print(f"Muestra CSV guardada: {ARCHIVO_MUESTRA} ({len(muestra)} filas)")

    info = generar_info(df, stats_total)
    with open(ARCHIVO_INFO, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"Info guardada: {ARCHIVO_INFO}")

    return ARCHIVO_PARQUET


if __name__ == "__main__":
    ejecutar()
