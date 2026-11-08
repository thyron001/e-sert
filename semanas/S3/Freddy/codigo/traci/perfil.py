"""Perfil de rendimiento del controlador (S3-2): ms por paso por bloque y factor de tiempo real.

Envuelve, sin tocar el código de la corrida, las funciones de cada bloque con cronómetros
`time.perf_counter()` **exclusivos** (el tiempo de un bloque no incluye el de los bloques que
llama). Bloques: `simulationStep`, `suscripciones`, `gps`, `inferencia`, `maquina`, `nucleo`,
`guiado`, `peatones`, `kpis`, `ws` y `otros` (el resto del paso). Opcionalmente, `cProfile`.

Se ejecuta **dentro del contenedor** `van3twin`, desde `semanas/S3/Freddy/codigo`:

    python3 -m traci.perfil --id p80_rf_s1 --hasta 1800 --variante antes
    python3 -m traci.perfil --id p80_rf_s1 --hasta 1800 --variante despues
    python3 -m traci.perfil --id p80_rf_s1 --hasta 1800 --variante despues_libsumo --cprofile

Escribe `traci/salidas_kpi/perfil_<id>_<variante>.json`.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import json
import pstats
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .correr_kpis import SALIDAS_KPI, correr

BLOQUES = ("simulationStep", "suscripciones", "gps", "inferencia", "maquina", "nucleo", "guiado",
           "peatones", "kpis", "ws", "otros")

VARIANTES = {
    # antes de optimizar: todo el tráfico suscrito, inferencia usuario por usuario, socket TraCI
    "antes": {"solo_busca": False, "en_lote": False, "cache_parametros": False, "contar_eventos": False,
              "geo_local": False, "libsumo": False},
    "despues": {"solo_busca": True, "en_lote": True, "cache_parametros": True, "contar_eventos": True,
                "libsumo": False},
    "despues_libsumo": {"solo_busca": True, "en_lote": True, "cache_parametros": True, "contar_eventos": True,
                        "libsumo": True},
    # pruebas de opciones de SUMO (no cambian el escenario de Tyrone; van como argumentos)
    "libsumo_hilos4": {"solo_busca": True, "en_lote": True, "cache_parametros": True, "contar_eventos": True,
                       "libsumo": True, "args_sumo": ("--device.rerouting.threads", "4")},
    "libsumo_astar": {"solo_busca": True, "en_lote": True, "cache_parametros": True, "contar_eventos": True,
                      "libsumo": True, "args_sumo": ("--routing-algorithm", "astar")},
}


class Perfilador:
    """Cronómetros exclusivos por bloque (pila de bloques activos) y duración de cada paso."""

    def __init__(self):
        self.total: Dict[str, float] = defaultdict(float)
        self._pila: List[list] = []  # [bloque, t_inicio, tiempo_de_hijos]
        self.pasos: List[float] = []
        self.por_paso: List[Dict[str, float]] = []  # desglose de cada paso (para explicar el p95)
        self._actual: Dict[str, float] = defaultdict(float)

    def envolver(self, funcion, bloque: str):
        def envuelta(*args, **kwargs):
            t0 = time.perf_counter()
            self._pila.append([bloque, t0, 0.0])
            try:
                return funcion(*args, **kwargs)
            finally:
                _, inicio, hijos = self._pila.pop()
                dur = time.perf_counter() - inicio
                self.total[bloque] += dur - hijos
                self._actual[bloque] += dur - hijos
                if self._pila:
                    self._pila[-1][2] += dur
        return envuelta

    def envolver_paso(self, paso):
        def envuelta():
            t0 = time.perf_counter()
            self._pila.append(["otros", t0, 0.0])
            try:
                return paso()
            finally:
                _, inicio, hijos = self._pila.pop()
                dur = time.perf_counter() - inicio
                self.total["otros"] += dur - hijos
                self._actual["otros"] += dur - hijos
                self.pasos.append(dur)
                self.por_paso.append(dict(self._actual))
                self._actual = defaultdict(float)
        return envuelta

    def instalar(self, partes: dict) -> None:
        """Pone los cronómetros sobre los componentes de una corrida de `correr_kpis.correr`."""
        ctrl = partes["ctrl"]
        tr = ctrl.traci
        _parchear(tr, "simulationStep", self.envolver(tr.simulationStep, "simulationStep"))
        for dominio, metodos in ((tr.vehicle, ("getAllSubscriptionResults", "subscribe")),
                                 (tr.person, ("getAllSubscriptionResults", "subscribe")),
                                 (tr.simulation, ("getDepartedIDList", "getDepartedPersonIDList"))):
            for m in metodos:
                _parchear(dominio, m, self.envolver(getattr(dominio, m), "suscripciones"))
        ses, puente, clf = partes["sesiones"], partes["puente"], partes["clasificador"]
        ses._muestrear = self.envolver(ses._muestrear, "gps")
        clf.evaluar = self.envolver(clf.evaluar, "inferencia")
        clf.evaluar_lote = self.envolver(clf.evaluar_lote, "inferencia")
        for m in ("iniciar", "transicion", "cerrar", "registrar"):
            setattr(puente, m, self.envolver(getattr(puente, m), "nucleo"))
        nombres = {partes["peatones"].on_paso: "peatones", partes["guia"].on_paso: "guiado",
                   ses.on_paso: "maquina", partes["registro"].on_paso: "guiado", partes["progreso"]: "otros"}
        kpis = partes["kpis"]
        if kpis is not None:
            nombres[kpis.on_paso] = "kpis"
            nombres[kpis.verdad.on_paso] = "kpis"
            puente.al_cerrar[:] = [self.envolver(h, "kpis") for h in puente.al_cerrar]
        ctrl.hooks[:] = [self.envolver(h, nombres.get(getattr(h, "__wrapped__", h), "ws")) for h in ctrl.hooks]
        ctrl.paso = self.envolver_paso(ctrl.paso)

    def informe(self, t_sim: float, tiempo_real: float) -> dict:
        n = max(1, len(self.pasos))
        ms = sorted(1000 * p for p in self.pasos)
        p95 = ms[min(len(ms) - 1, int(round(0.95 * (len(ms) - 1))))] if ms else float("nan")
        umbral = p95 / 1000
        lentos = [d for d, dur in zip(self.por_paso, self.pasos) if dur >= umbral]
        p95_bloque = {}
        for b in BLOQUES:
            xs = sorted(1000 * d.get(b, 0.0) for d in self.por_paso)
            p95_bloque[b] = round(xs[int(0.95 * (len(xs) - 1))], 3) if xs else None
        propio = sorted(1000 * (dur - d.get("simulationStep", 0.0)) for d, dur in zip(self.por_paso, self.pasos))
        sumo = sorted(1000 * d.get("simulationStep", 0.0) for d in self.por_paso)
        return {
            "pasos": len(self.pasos),
            # el paso separado en lo que tarda SUMO y lo que tarda el controlador (todo lo demás)
            "ms_controlador_medio": round(statistics.fmean(propio), 3) if propio else None,
            "ms_controlador_p95": round(propio[int(0.95 * (len(propio) - 1))], 3) if propio else None,
            "ms_simulationStep_p95": round(sumo[int(0.95 * (len(sumo) - 1))], 3) if sumo else None,
            "ms_p95_por_bloque": p95_bloque,
            "ms_medio_por_bloque_en_pasos_lentos": {
                b: round(1000 * statistics.fmean(d.get(b, 0.0) for d in lentos), 3) for b in BLOQUES} if lentos else {},
            "ms_por_paso_serie": [round(1000 * x, 2) for x in self.pasos],
            "ms_por_paso_medio": round(statistics.fmean(ms), 3) if ms else None,
            "ms_por_paso_p95": round(p95, 3),
            "ms_por_paso_max": round(ms[-1], 3) if ms else None,
            "factor_tiempo_real": round(t_sim / tiempo_real, 3) if tiempo_real else None,
            "ms_por_paso_por_bloque": {b: round(1000 * self.total.get(b, 0.0) / n, 3) for b in BLOQUES},
        }


def _parchear(objeto, nombre: str, valor) -> None:
    """`setattr` que funciona con los dominios de traci (instancias) y de libsumo (clases)."""
    setattr(objeto, nombre, valor)


def perfilar(id_corrida: str, hasta: float, variante: str, usar_cprofile: bool = False) -> dict:
    perf = Perfilador()
    perfilador_c = cProfile.Profile() if usar_cprofile else None
    if perfilador_c:
        perfilador_c.enable()
    inicio = time.perf_counter()
    salida = correr(id_corrida, hasta, sufijo=f"_perfil_{variante}", ws_nulo=True, guardar_csv=False,
                    instrumentar=perf.instalar, **VARIANTES[variante])
    tiempo_real = time.perf_counter() - inicio
    if perfilador_c:
        perfilador_c.disable()
    informe = {"id": id_corrida, "variante": variante, "opciones": VARIANTES[variante],
               "t_sim": salida["t_sim_final"], "tiempo_real_s": round(tiempo_real, 2),
               **perf.informe(salida["t_sim_final"], tiempo_real),
               "metas": {"factor_min": 10, "p95_max_ms": 100},
               "sesiones": salida["sesiones_maquina"]["sesiones"],
               "ventanas_por_fuente": salida["ventanas_por_fuente"],
               "kpis": {k: salida["kpis"][k] for k in ("falsas_lib_100", "n_sesiones", "n_falsas", "sin_cierre",
                                                        "precision_mapa_app")}}
    if perfilador_c:
        texto = io.StringIO()
        pstats.Stats(perfilador_c, stream=texto).sort_stats("tottime").print_stats(25)
        (SALIDAS_KPI / f"cprofile_{id_corrida}_{variante}.txt").write_text(texto.getvalue(), encoding="utf-8")
    return informe


def main(argv: Optional[Sequence[str]] = None) -> dict:
    ap = argparse.ArgumentParser(description="Perfil por bloque del controlador (S3-2)")
    ap.add_argument("--id", default="p80_rf_s1")
    ap.add_argument("--hasta", type=float, default=1800)
    ap.add_argument("--variante", choices=sorted(VARIANTES), default="despues")
    ap.add_argument("--cprofile", action="store_true")
    args = ap.parse_args(argv)
    SALIDAS_KPI.mkdir(parents=True, exist_ok=True)
    informe = perfilar(args.id, args.hasta, args.variante, args.cprofile)
    ruta = SALIDAS_KPI / f"perfil_{args.id}_{args.variante}.json"
    ruta.write_text(json.dumps(informe, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(informe, indent=2, ensure_ascii=False))
    return informe


if __name__ == "__main__":
    main()
