"""Evidencia S4-3: barras apiladas por fase de los dos ensayos frente al presupuesto de tiempo.

    demo/.venv/bin/python demo/presentacion/evidencia_ensayo.py

Lee `ensayos/ensayo_<n>.json` (que escribe `ensayo.py` con los tiempos de `tiempos.json` de la demo)
y deja `semanas/S4/Tyrone/evidencias/s3_ensayo-cronometro.png`. También arma `ensayo.md` desde
`ensayo.plantilla.md` con la tabla de tiempos y los eventos de cada ensayo (sin cifras a mano).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

AQUI = Path(__file__).resolve().parent
DESTINO = AQUI.parents[2] / "evidencias" / "s3_ensayo-cronometro.png"
FASES = [("arranque", "Arranque (demo.py → tabla)", "#1E63D6"),
         ("demo_guiada", "Demo guiada (espejo → recibo)", "#2E9E4F"),
         ("apagado", "Apagado (Ctrl+C → todo libre)", "#FF7043")]


def main(destino: Path = DESTINO) -> Path:
    ensayos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((AQUI / "ensayos").glob("ensayo_*.json"))]
    presupuesto = ensayos[0]["presupuesto_s"]
    filas = [("Presupuesto", presupuesto, True)] + [
        (f"Ensayo {e['vuelta']}" + (" (graba plan B)" if e.get("grabados_plan_b") else ""), e["fases_s"], False)
        for e in ensayos]
    fig, ax = plt.subplots(figsize=(9.5, 4))
    for y, (nombre, fases, es_pres) in enumerate(reversed(filas)):
        x = 0.0
        for clave, etiqueta, color in FASES:
            v = float(fases[clave])
            ax.barh(y, v, left=x, height=0.55, color="white" if es_pres else color,
                    edgecolor=color, hatch="//" if es_pres else None, linewidth=1.5,
                    label=etiqueta if y == len(filas) - 1 else None)
            if v >= 25:
                ax.text(x + v / 2, y, f"{v:.0f} s".replace(".", ","), ha="center", va="center", fontsize=9,
                        color="#0b2540" if es_pres else "white", fontweight="bold")
            x += v + 2  # 2 s de separación visual entre fases
        total = sum(float(fases[c]) for c, _, _ in FASES)
        detalle = f"total {total:.0f} s\narranque {float(fases['arranque']):.1f} s · apagado {float(fases['apagado']):.1f} s"
        ax.text(x + 4, y, detalle.replace(".", ","), va="center", fontsize=8.5, color="#3e4c59")
    ax.set_yticks(range(len(filas)), [f[0] for f in reversed(filas)])
    ax.set_xlabel("Segundos desde el arranque en frío")
    ax.set_xlim(0, sum(presupuesto.values()) * 1.5)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color="#DDDDDD", lw=0.6)
    ax.set_axisbelow(True)
    tropiezos = sum(len(e["tropiezos"]) for e in ensayos)
    ax.set_title(f"Ensayos de la demo con sumo-gui frente al presupuesto\n"
                 f"{len(ensayos)} ensayos desde arranque en frío, {tropiezos} tropiezos", loc="left", fontsize=11)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=3, frameon=False, fontsize=9)
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return destino


def _n(x, dec=1):
    return f"{float(x):.{dec}f}".replace(".", ",")


def escribir_ensayo_md() -> Path:
    ensayos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((AQUI / "ensayos").glob("ensayo_*.json"))]
    pres = ensayos[0]["presupuesto_s"]
    l = ["## Ensayos desde arranque en frío", "",
         "Cada ensayo corre `python demo/presentacion/ensayo.py --vuelta N`: lanza `demo.py --local --cronometro` "
         "(con `sumo-gui`, `--ritmo 10`), sigue por `/ws/espejo` a un auto como hace la app de Miguel en modo "
         "espejo, abre el visor con `?espejo=<veh>` en Chromium y comprueba el halo, espera una sesión `CERRADA` "
         "con recibo y apaga con Ctrl+C. Los datos están en `ensayos/ensayo_<n>.json`.", "",
         "| Ensayo | Fecha | Arranque (s) | Demo guiada (s) | Apagado (s) | Recibo | Halo en el visor | Tropiezos |",
         "|---|---|---:|---:|---:|---|---|---|",
         f"| Presupuesto | — | {pres['arranque']} | {pres['demo_guiada']} | {pres['apagado']} | — | — | — |"]
    for e in ensayos:
        r, v, f = e.get("recibo") or {}, e.get("visor") or {}, e["fases_s"]
        recibo = (f"`{r['veh']}`: {_n(r['minutos_reales'])} min, cobrado {_n(r['cobrado_usd'], 2)} USD "
                  f"(tarjeta SERT {_n(r['tarjeta_sert_usd'], 2)} USD)") if r else "no llegó"
        halo = f"sí ({v.get('ruta')} puntos de ruta, puesto `{v.get('puesto')}`)" if v.get("halo") else "no"
        l.append(f"| {e['vuelta']}{' (graba plan B)' if e.get('grabados_plan_b') else ''} | {e['fecha'][:16].replace('T', ' ')} | "
                 f"{_n(f['arranque'])} | {_n(f['demo_guiada'])} | {_n(f['apagado'])} | {recibo} | {halo} | "
                 f"{len(e['tropiezos'])} |")
    for e in ensayos:
        c = e.get("arranque_componentes_s") or {}
        l += ["", f"### Ensayo {e['vuelta']}", "",
              f"Arranque por componente: backend {_n(c.get('backend', 0))} s, controlador con `sumo-gui` "
              f"{_n(c.get('controlador', 0))} s, visor {_n(c.get('visor', 0))} s. Limpieza tras Ctrl+C: puertos "
              f"libres = {e['limpieza']['puertos_libres']}, `sumo-gui` vivos = {len(e['limpieza']['sumo_gui'])}.", ""]
        l += [f"- `{x['t']} s`: {x['evento']}" for x in e["eventos"]]
        if e.get("grabados_plan_b"):
            l.append(f"- Grabación del plan B: {e['grabados_plan_b']} mensajes WS → `demo/plan_b/snapshots_demo.jsonl.gz`.")
        l.append(f"- Tropiezos detectados por el script: {', '.join(e['tropiezos']) or 'ninguno'}.")
    bloque = "\n".join(l) + "\n\n" + (AQUI / "tropiezos_preparacion.md").read_text(encoding="utf-8").strip()
    destino = AQUI / "ensayo.md"
    destino.write_text((AQUI / "ensayo.plantilla.md").read_text(encoding="utf-8").replace("ENSAYOS", bloque),
                       encoding="utf-8")
    return destino


if __name__ == "__main__":
    print(main())
    print(escribir_ensayo_md())
