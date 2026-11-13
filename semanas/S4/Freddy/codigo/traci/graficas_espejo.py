"""Evidencia de S3-3 (Freddy): el modo espejo en vivo.

Lee `traci/salidas_kpi/espejo_local.json` (lo escribe `python3 -m backend.espejo.seguir`) y la
captura del visor `traci/salidas_kpi/visor_espejo_local.png`, y deja
`evidencias/s3_espejo-en-vivo.png`:

- (a) línea de tiempo del auto seguido: estado, distancia al puesto y costo en vivo, con el
  instante del recibo;
- (b) latencia snapshot → pantalla (p50 y p95) de todos los mensajes espejo;
- (c) el visor con los autos seguidos resaltados.

    python3 -m traci.graficas_espejo
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
SALIDAS_KPI = AQUI / "salidas_kpi"
EVIDENCIAS = AQUI.parents[1] / "evidencias"
ESTADOS = ["BUSCANDO", "GUIADO", "ESTACIONADO", "A_PIE", "REGRESANDO", "SALIENDO", "CERRADA"]
COLORES = {"BUSCANDO": "#F5A623", "GUIADO": "#7B3FBF", "ESTACIONADO": "#1E63D6", "A_PIE": "#00A3A3",
           "REGRESANDO": "#D63FD6", "SALIENDO": "#7A4A2A", "CERRADA": "#8C8C8C"}


def espejo_en_vivo(datos: Path = SALIDAS_KPI / "espejo_local.json",
                   visor: Path = SALIDAS_KPI / "visor_espejo_local.png",
                   salida: Path = EVIDENCIAS / "s3_espejo-en-vivo.png") -> Path:
    r = json.loads(datos.read_text(encoding="utf-8"))
    veh = r["principal"]
    linea = r["lineas"][veh]
    fig = plt.figure(figsize=(16, 9))
    rejilla = fig.add_gridspec(3, 2, width_ratios=[1, 1.15], height_ratios=[0.7, 1.2, 1])
    a_est = fig.add_subplot(rejilla[0, 0])
    a_dist = fig.add_subplot(rejilla[1, 0], sharex=a_est)
    a_lat = fig.add_subplot(rejilla[2, 0])
    a_vis = fig.add_subplot(rejilla[:, 1])

    t = [p["t_sim"] for p in linea]
    # (a) estado como escalones de color
    for p, q in zip(linea, linea[1:] + [None]):
        fin = q["t_sim"] if q else p["t_sim"] + 1
        if p["estado"]:
            a_est.barh(0, fin - p["t_sim"], left=p["t_sim"], color=COLORES[p["estado"]], height=0.6)
    vistos = [s for s in ESTADOS if any(p["estado"] == s for p in linea)]
    a_est.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=COLORES[s]) for s in vistos], labels=vistos,
                 ncol=len(vistos), fontsize=8, loc="center right", framealpha=0.9)
    a_est.set_yticks([])
    a_est.set_title(f"(a) Pantalla de {veh}: estado, distancia al puesto y costo en vivo", loc="left")

    dist = [(p["t_sim"], p["distancia_m"]) for p in linea if p["distancia_m"] is not None]
    if dist:
        a_dist.plot(*zip(*dist), color="#7B3FBF", lw=1.5, label="distancia al puesto (m)")
    a_dist.set_ylabel("distancia (m)")
    a_cost = a_dist.twinx()
    costo = [(p["t_sim"], p["costo_usd"]) for p in linea if p["costo_usd"] is not None]
    if costo:
        a_cost.plot(*zip(*costo), color="#2E9E4F", lw=1.5, marker=".", label="costo en vivo (USD)")
    a_cost.set_ylabel("costo en vivo (USD)", color="#2E9E4F")
    recibos = [p for p in linea if p["recibo"]]
    for ax in (a_est, a_dist):
        for p in recibos:
            ax.axvline(p["t_sim"], color="#C62828", ls="--", lw=1.2)
    if recibos:
        rc = recibos[0]["recibo"]
        a_dist.annotate(f"recibo: {rc['minutos_reales']:.1f} min reales → {rc['minutos_cobrados']} cobrados\n"
                        f"cobrado {rc['cobrado_usd']:.2f} USD · tarjeta SERT {rc['tarjeta_sert_usd']:.2f} "
                        f"· ahorro {rc['ahorro_usd']:.2f}",
                        (recibos[0]["t_sim"] + 15, max(d for _, d in dist) * 0.75 if dist else 0), fontsize=8,
                        ha="left", color="#C62828")
    a_dist.set_xlabel("t_sim (s)")
    fin = r["fin"].get(veh)
    if fin:
        a_dist.set_title(f"espejo_fin: {fin['motivo']} (t_sim {fin['t_sim']})", fontsize=9, loc="right")
    a_dist.set_xlim(min(t), max(t) + 1)

    # (b) latencia
    lat = [p["lat_total_ms"] for l in r["lineas"].values() for p in l if p.get("lat_total_ms") is not None]
    resumen = r["latencia_total_ms"]
    dentro = [x for x in lat if 0 <= x <= 1000]
    a_lat.hist(dentro, bins=40, range=(0, 1000), color="#1E63D6", alpha=0.8)
    for q, est in (("p50", "-"), ("p95", "--")):
        a_lat.axvline(resumen[q], color="black", ls=est, lw=1, label=f"{q} = {resumen[q]:.0f} ms")
    a_lat.axvline(1500, color="#C62828", lw=1, label="meta p95 < 1 500 ms")
    a_lat.set_xlabel("latencia: ts del snapshot en el controlador → llegada del mensaje espejo a la pantalla (ms)")
    a_lat.set_ylabel("mensajes")
    a_lat.legend(fontsize=8)
    a_lat.set_xlim(0, 1600)
    fuera = len(lat) - len(dentro)
    a_lat.set_title(f"(b) {resumen['n']} mensajes espejo con dato nuevo, {len(r['lineas'])} pantallas"
                    + (f"\n({fuera} negativas, de origen sin aislar (¿reloj de pared?); no se dibujan)" if fuera else ""),
                    loc="left", fontsize=10)

    # (c) visor
    if visor.exists():
        a_vis.imshow(mpimg.imread(visor))
    a_vis.set_axis_off()
    a_vis.set_title("(c) Visor (/visor): los autos seguidos llevan halo amarillo (campo `espejos`)", loc="left")

    fig.suptitle("S3-3 · Modo espejo en vivo (local: uvicorn + p50_umbral_s1 a 10× + cliente websockets)",
                 fontsize=13)
    fig.tight_layout()
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(salida, dpi=150)
    plt.close(fig)
    return salida


if __name__ == "__main__":
    print(espejo_en_vivo())
