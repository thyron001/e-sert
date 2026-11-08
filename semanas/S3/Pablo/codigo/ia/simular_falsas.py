"""
Simulación fuera de línea de sesiones de parqueo: falsas liberaciones y retardo de cierre según
el suavizado temporal (k) y el método.

Cada episodio (grabado con `ia/grabar_episodios.py`) es una sesión completa de SUMO:
estacionar -> caminar -> volver -> manejar. A la traza limpia se le aplica ruido GPS AR(1)
(sigma 5, 10 y 15 m); luego, cada 5 s sobre ventanas de 30 s:

    ventana -> clasificador (umbral | rf) -> Suavizador(k, metodo) -> MaquinaSesion de Freddy

* Falsa liberación: la sesión pasa a CERRADA mientras el modo real no es `vehiculo`.
* Retardo: instante de cierre menos el instante en que el auto sale de verdad.

    python3 -m ia.simular_falsas                 # rejilla de 12 combinaciones -> reportes/suavizado_k.csv
    python3 -m ia.simular_falsas --max-sesiones 80 --workers 1   # prueba rápida

Memoria: se clasifica por tandas y solo se guardan arrays numéricos; la rejilla corre en procesos
(fork) que comparten esos arrays sin copiarlos.
"""
from __future__ import annotations

import argparse
import gc
import multiprocessing as mp
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ_IA = Path(__file__).resolve().parent
SALIDAS = RAIZ_IA / "sumo" / "salidas"
REPORTES = RAIZ_IA / "reportes"

sys.path.append(str(RAIZ_IA.parents[4] / "proyecto"))
try:
    from traci.estados import MaquinaSesion  # máquina de estados real de Freddy (contrato §3)
except Exception:  # pragma: no cover
    MaquinaSesion = None  # MOCK: reemplazar por la máquina de estados de Freddy si no se encuentra

from ia.suavizado import CLASES, Suavizador  # noqa: E402

SIGMAS = (5, 10, 15)
KS = (1, 3, 5)
SISTEMAS = ("umbral", "rf")
METODOS = ("mayoria", "prob_media")
VENTANA_S = 30.0
PASO_S = 5.0
RETARDO_MAX_S = 60.0
N_BOOT = 2000
R_TIERRA = 6_371_000.0
IDX = {c: i for i, c in enumerate(CLASES)}


# ── Datos ──────────────────────────────────────────────────────────────────


@dataclass
class Episodio:
    uid: str
    t: np.ndarray            # tiempos limpios (1 Hz)
    lat: np.ndarray
    lon: np.ndarray
    modo: np.ndarray         # modo real por segundo (str)
    puesto: tuple[float, float]
    t_salida: float          # primer instante con modo real `vehiculo`


def cargar_episodios(semillas=(101, 102, 103, 104, 105), max_sesiones: int | None = None,
                     min_tras_salida_s: float = 20.0, semilla: int = 2026) -> list[Episodio]:
    """Episodios completos (el auto llegó a salir) de los CSV de `grabar_episodios.py`."""
    eps: list[Episodio] = []
    for s in semillas:
        ruta = SALIDAS / f"episodios_s{s}.csv"
        if not ruta.exists():
            continue
        df = pd.read_csv(ruta)
        df = df[np.isfinite(df["lat"]) & np.isfinite(df["lon"])]  # SUMO a veces da posiciones inf
        df = df[np.isfinite(df["puesto_lat"]) & np.isfinite(df["puesto_lon"])]
        for uid, g in df.groupby("usuario_id", sort=False):
            g = g.sort_values("t")
            modo = g["modo_real"].to_numpy()
            salida = np.flatnonzero(modo == "vehiculo")
            if salida.size == 0:
                continue
            t = g["t"].to_numpy(dtype=float)
            if t[-1] - t[salida[0]] < min_tras_salida_s:
                continue
            eps.append(Episodio(f"{s}_{uid}", t, g["lat"].to_numpy(), g["lon"].to_numpy(), modo,
                                (float(g["puesto_lat"].iloc[0]), float(g["puesto_lon"].iloc[0])),
                                float(t[salida[0]])))
    if max_sesiones is not None and len(eps) > max_sesiones:
        idx = np.random.default_rng(semilla).choice(len(eps), max_sesiones, replace=False)
        eps = [eps[i] for i in sorted(idx)]
    return eps


def _haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * R_TIERRA * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def ruido(eps: list[Episodio], sigma: float, semilla: int) -> list[dict]:
    """Aplica ruido AR(1) (ia.ruido) a todas las trazas; devuelve las trazas ruidosas por episodio."""
    from ia.ruido import aplicar_ruido_ar1

    df = pd.concat(
        [pd.DataFrame({"usuario_id": e.uid, "t": e.t, "lat": e.lat, "lon": e.lon,
                       "precision_m": np.nan, "velocidad_mps": 0.0, "modo_real": e.modo}) for e in eps],
        ignore_index=True)
    sucio = aplicar_ruido_ar1(df, sigma_m=sigma, semilla=semilla)
    out = {}
    for uid, g in sucio.groupby("usuario_id", sort=False):
        out[uid] = {"t": g["t"].to_numpy(float), "lat": g["lat"].to_numpy(), "lon": g["lon"].to_numpy(),
                    "prec": g["precision_m"].to_numpy()}
    del df, sucio
    gc.collect()
    return [out[e.uid] for e in eps]


@dataclass
class VentanasEp:
    t_fin: np.ndarray        # instante de evaluación
    dist_m: np.ndarray       # distancia (GPS ruidoso) al puesto
    modo_real: np.ndarray    # modo real en t_fin (índices en CLASES)
    probas: dict             # sistema -> (n, 3)


def _tiempos_evaluacion(t: np.ndarray) -> np.ndarray:
    """Como ClasificadorUsuario: cada 5 s, con >= 29 s de datos en el buffer."""
    if t.size < 2 or t[-1] - t[0] < VENTANA_S - 1:
        return np.empty(0)
    return np.arange(t[0] + VENTANA_S - 1, t[-1] + 1e-9, PASO_S)


def _umbral_lote(tn, lat, lon, te) -> np.ndarray:
    """Línea base del contrato §2: velocidad media de la ventana (posiciones con mediana móvil de 3,
    como `vel_media` de las características de S2), > 8 km/h vehiculo, < 0,5 km/h quieto."""
    from ia.inferencia import _mediana3

    ls, os_ = _mediana3(lat[None])[0], _mediana3(lon[None])[0]
    v = _haversine(ls[:-1], os_[:-1], ls[1:], os_[1:]) / np.maximum(np.diff(tn), 1e-6)
    cum = np.concatenate([[0.0], np.cumsum(v)])
    lo = np.searchsorted(tn, te - VENTANA_S, side="right")
    hi = np.searchsorted(tn, te, side="right")
    n = np.maximum(hi - 1 - lo, 1)
    vel = (cum[np.maximum(hi - 1, 0)] - cum[lo]) / n
    p = np.zeros((len(te), 3))
    p[vel > 8 / 3.6, IDX["vehiculo"]] = 1
    p[vel < 0.5 / 3.6, IDX["quieto"]] = 1
    p[p.sum(axis=1) == 0, IDX["a_pie"]] = 1
    return p


def clasificar_episodios(eps: list[Episodio], sucias: list[dict], tanda: int = 4000) -> list[VentanasEp]:
    """Clasifica todas las ventanas (umbral y RF) por tandas para acotar la memoria."""
    from ia.inferencia import clasificar_lote

    plan = []  # (episodio, te, lo, hi)
    for e, s in zip(eps, sucias):
        te = _tiempos_evaluacion(s["t"])
        if te.size:
            lo = np.searchsorted(s["t"], te - VENTANA_S, side="right")
            hi = np.searchsorted(s["t"], te, side="right")
            plan.append((e, s, te, lo, hi))
    salida = []
    cola_vent, cola_ref = [], []
    rf_por_ep: list[np.ndarray] = [np.zeros((len(te), 3)) for _, _, te, _, _ in plan]

    def vaciar():
        if not cola_vent:
            return
        _, probas = clasificar_lote(cola_vent, con_probas=True)
        for (i, j), pr, v in zip(cola_ref, probas, cola_vent):
            if pr is None:  # pocos puntos: umbral (el RF no se pudo usar); se usa one-hot
                pr = np.zeros(3)
                pr[IDX[_umbral_ventana(v)]] = 1
            rf_por_ep[i][j] = pr
        cola_vent.clear()
        cola_ref.clear()

    for i, (e, s, te, lo, hi) in enumerate(plan):
        t, la, lo_, pr = s["t"], s["lat"], s["lon"], s["prec"]
        for j in range(len(te)):
            a, b = int(lo[j]), int(hi[j])
            cola_vent.append([{"t": float(t[q]), "lat": float(la[q]), "lon": float(lo_[q]),
                               "precision_m": float(pr[q])} for q in range(a, b)])
            cola_ref.append((i, j))
            if len(cola_vent) >= tanda:
                vaciar()
    vaciar()

    for i, (e, s, te, lo, hi) in enumerate(plan):
        ult = hi - 1
        dist = _haversine(s["lat"][ult], s["lon"][ult], e.puesto[0], e.puesto[1])
        k = np.searchsorted(e.t, te, side="right") - 1
        real = np.array([IDX[m] for m in e.modo[np.clip(k, 0, len(e.modo) - 1)]])
        salida.append(VentanasEp(te, dist, real, {
            "umbral": _umbral_lote(s["t"], s["lat"], s["lon"], te), "rf": rf_por_ep[i]}))
    return salida


def _umbral_ventana(v: list[dict]) -> str:
    if len(v) < 2:
        return "quieto"
    la = np.array([p["lat"] for p in v]); lo = np.array([p["lon"] for p in v])
    dt = v[-1]["t"] - v[0]["t"]
    vel = _haversine(la[:-1], lo[:-1], la[1:], lo[1:]).sum() / dt if dt > 0 else 0.0
    return "vehiculo" if vel > 8 / 3.6 else ("quieto" if vel < 0.5 / 3.6 else "a_pie")


# ── Sesión y rejilla ───────────────────────────────────────────────────────


class MaquinaContrato(MaquinaSesion):
    """Máquina con las transiciones literales de la tabla del contrato §3: sin `REGRESANDO -> A_PIE`
    (esa regla la añadió la implementación de Freddy y no está en el contrato)."""

    def _siguiente(self, modo, distancia_m):
        if self.estado == "REGRESANDO" and not self._vehiculo_seguido >= self.ventanas_vehiculo:
            return None
        return super()._siguiente(modo, distancia_m)


MAQUINAS = {"freddy": lambda uid: MaquinaSesion(uid), "contrato": lambda uid: MaquinaContrato(uid)}


def simular_sesion(ep: Episodio, w: VentanasEp, sistema: str, metodo: str, k: int,
                   maquina: str = "freddy") -> tuple[int, float]:
    """Devuelve (resultado, retardo_s): resultado 1 = falsa liberación, 0 = cierre correcto,
    -1 = sin cierre. El retardo solo es válido con resultado 0."""
    maq = MAQUINAS[maquina](ep.uid)
    sv = Suavizador(k=k, metodo=metodo)
    probas = w.probas[sistema]
    for j in range(len(w.t_fin)):
        res = {"modo": CLASES[int(np.argmax(probas[j]))], "confianza": 1.0, "fuente": sistema}
        modo = sv.actualizar(res, probas[j])["modo"]
        for tr in maq.actualizar(modo, float(w.dist_m[j]), float(w.t_fin[j])):
            if tr.hacia == "CERRADA":
                if CLASES[w.modo_real[j]] != "vehiculo":
                    return 1, np.nan
                return 0, float(w.t_fin[j]) - ep.t_salida
    return -1, np.nan


_DATOS: dict = {}


def _tarea(args):
    sistema, metodo, k, maquina = args
    eps, por_sigma = _DATOS["eps"], _DATOS["ventanas"]
    res = np.full((len(SIGMAS), len(eps)), -1, dtype=np.int8)
    ret = np.full((len(SIGMAS), len(eps)), np.nan)
    for a, sg in enumerate(SIGMAS):
        for i, ep in enumerate(eps):
            res[a, i], ret[a, i] = simular_sesion(ep, por_sigma[sg][i], sistema, metodo, k, maquina)
    return (sistema, metodo, k, maquina), res, ret


def _ic(estad, n: int, semilla: int = 7) -> tuple[float, float]:
    from scipy.stats import bootstrap

    if n < 2:
        return (np.nan, np.nan)
    r = bootstrap((np.arange(n),), estad, n_resamples=N_BOOT, confidence_level=0.95,
                  method="percentile", vectorized=False, random_state=np.random.default_rng(semilla))
    return float(r.confidence_interval.low), float(r.confidence_interval.high)


def resumir(clave, res: np.ndarray, ret: np.ndarray) -> dict:
    sistema, metodo, k, maquina = clave
    n = res.shape[1]
    falsa_ses = (res == 1).mean(axis=0)  # por sesión: fracción de σ con falsa liberación

    def f_falsas(idx):
        return 100.0 * falsa_ses[np.asarray(idx, dtype=int)].mean()

    def f_retardo(idx):
        v = ret[:, np.asarray(idx, dtype=int)].ravel()
        v = v[~np.isnan(v)]
        return float(np.median(v)) if v.size else np.nan

    lo_f, hi_f = _ic(f_falsas, n)
    lo_r, hi_r = _ic(f_retardo, n)
    fila = {"sistema": sistema, "metodo": metodo, "k": k, "maquina": maquina, "n_sesiones": n,
            "falsas_100": f_falsas(np.arange(n)), "falsas_ic95_inf": lo_f, "falsas_ic95_sup": hi_f,
            "retardo_mediano_s": f_retardo(np.arange(n)), "retardo_ic95_inf": lo_r, "retardo_ic95_sup": hi_r,
            "cierre_correcto_pct": 100.0 * float((res == 0).mean()),
            "sin_cierre_pct": 100.0 * float((res == -1).mean())}
    for a, sg in enumerate(SIGMAS):
        fila[f"falsas_100_s{sg}"] = 100.0 * float((res[a] == 1).mean())
        v = ret[a][~np.isnan(ret[a])]
        fila[f"retardo_mediano_s{sg}"] = float(np.median(v)) if v.size else np.nan
    fila["cumple_retardo"] = bool(fila["retardo_mediano_s"] <= RETARDO_MAX_S)
    return fila


def recomendar(tabla: pd.DataFrame) -> pd.Series | None:
    """Mínimas falsas con retardo mediano <= 60 s; empates dentro del IC -> el menor k."""
    ok = tabla[tabla["cumple_retardo"]]
    if ok.empty:
        return None
    mejor = ok.sort_values(["falsas_100", "k"]).iloc[0]
    empatados = ok[ok["falsas_100"] <= mejor["falsas_ic95_sup"]]
    return empatados.sort_values(["k", "falsas_100"]).iloc[0]


def ejecutar(semillas=(101, 102, 103, 104, 105), max_sesiones=None, workers=3, salida=None) -> pd.DataFrame:
    t0 = time.time()
    eps = cargar_episodios(semillas, max_sesiones)
    if not eps:
        raise SystemExit("No hay episodios: corre ia/grabar_episodios.py en el contenedor (ver docstring).")
    print(f"{len(eps)} sesiones completas", flush=True)
    por_sigma = {}
    for sg in SIGMAS:
        sucias = ruido(eps, sg, semilla=1000 + sg)
        por_sigma[sg] = clasificar_episodios(eps, sucias)
        del sucias
        gc.collect()
        print(f"  sigma={sg}: clasificado ({time.time() - t0:.0f} s)", flush=True)

    # sesiones sin ventanas suficientes se descartan de todos los sigma por igual
    _DATOS["eps"], _DATOS["ventanas"] = eps, por_sigma
    combos = [(s, m, k, mq) for mq, s, m, k in product(MAQUINAS, SISTEMAS, METODOS, KS)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork")) as ex:
            resultados = list(ex.map(_tarea, combos))
    else:
        resultados = [_tarea(c) for c in combos]
    todas = pd.DataFrame([resumir(c, r, t) for c, r, t in resultados])
    REPORTES.mkdir(exist_ok=True)
    destino = Path(salida) if salida else REPORTES / "suavizado_k.csv"
    contrato = destino.with_name(destino.stem + "_contrato.csv")
    cols = ["sistema", "metodo", "k"]
    tabla = todas[todas["maquina"] == "freddy"].sort_values(cols).reset_index(drop=True)
    tabla.to_csv(destino, index=False, float_format="%.4f")
    todas[todas["maquina"] == "contrato"].sort_values(cols).reset_index(drop=True).to_csv(
        contrato, index=False, float_format="%.4f")
    for nombre, tb in (("maquina de Freddy", tabla), ("maquina del contrato", pd.read_csv(contrato))):
        print(f"--- {nombre}")
        print(tb[cols + ["falsas_100", "falsas_ic95_inf", "falsas_ic95_sup", "retardo_mediano_s",
                         "cierre_correcto_pct", "sin_cierre_pct"]].to_string(), flush=True)
    rec = recomendar(tabla)
    print("recomendado:", None if rec is None else dict(rec[["sistema", "metodo", "k"]]),
          f"({time.time() - t0:.0f} s)")
    return tabla


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--semillas", type=int, nargs="+", default=[101, 102, 103, 104, 105])
    ap.add_argument("--max-sesiones", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--salida", type=str, default=None)
    a = ap.parse_args()
    ejecutar(tuple(a.semillas), a.max_sesiones, a.workers, a.salida)


if __name__ == "__main__":
    main()
