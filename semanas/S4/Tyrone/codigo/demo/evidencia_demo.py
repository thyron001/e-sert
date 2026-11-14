"""Evidencia de la demo en un comando (S4-1): `evidencias/s1_demo-un-comando.png`.

    demo/.venv/bin/python demo/evidencia_demo.py [--ruta kpis=...] [--ruta visor=...]

Arranca `demo.py --local --cronometro --sin-navegador` **con sumo-gui**, espera la captura de
sumo-gui que hace el controlador a los 60 s simulados (`traci.gui.screenshot`; `PIL.ImageGrab` no ve
la pantalla :99 del contenedor), captura el visor con Playwright *headless*, apaga con Ctrl+C
(SIGINT), comprueba que no quedan puertos ni `sumo-gui` vivos y compone 3 paneles: sumo-gui, visor
y el tiempo de arranque por componente.
"""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from demo import RAIZ, docker, leer_config, puerto_libre  # noqa: E402


def capturar_visor(url: str, destino: Path) -> dict:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:  # noqa: BLE001
            exe = sorted((Path.home() / ".cache" / "ms-playwright").glob("chromium-*/chrome-linux*/chrome"))[-1]
            b = p.chromium.launch(executable_path=str(exe))
        pg = b.new_page(viewport={"width": 1600, "height": 1000})
        pg.goto(url)
        pg.wait_for_function("(window.visorVehiculos || 0) > 20 && window.visorConexion === 'conectado'",
                             timeout=60000)
        pg.wait_for_timeout(3000)
        pg.screenshot(path=str(destino))
        info = pg.evaluate("({veh: window.visorVehiculos, espejos: window.visorEspejosVisibles})")
        b.close()
    return info


def componer(gui: Path, visor: Path, tiempos: dict, destino: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.image as mpimg
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(16, 5.6))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.45, 0.8])
    for i, (ruta, titulo) in enumerate([(gui, "sumo-gui en el contenedor (VNC :5901), t = 60 s"),
                                        (visor, "Visor Leaflet (localhost:8088) en el mismo instante")]):
        ax = fig.add_subplot(gs[0, i])
        if ruta and ruta.exists():
            ax.imshow(mpimg.imread(ruta))
        else:
            ax.text(0.5, 0.5, "sin captura", ha="center", va="center")
        ax.set_title(titulo, loc="left", fontsize=10)
        ax.axis("off")
    ax = fig.add_subplot(gs[0, 2])
    comp = ["backend", "controlador", "visor"]
    vals = [tiempos["arranque_s"].get(c, 0) for c in comp]
    barras = ax.barh(comp, vals, color=["#FF7043", "#1E63D6", "#2E9E4F"], edgecolor="white", linewidth=2)
    for b, v in zip(barras, vals):
        ax.text(v + 0.3, b.get_y() + b.get_height() / 2, f"{v:.1f} s".replace(".", ","), va="center", fontsize=9)
    ax.invert_yaxis()
    total = tiempos["arranque_s"].get("total", sum(vals))
    ax.set_xlabel("segundos")
    ax.set_title(f"Arranque: total {total:.1f} s".replace(".", ","), loc="left", fontsize=10)
    ax.axvline(60, color="#C62828", ls=":", lw=1, label="meta < 60 s")
    ax.legend(frameon=False, loc="lower right", fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(0.0, -0.22, f"Apagado con Ctrl+C: {tiempos.get('apagado_s', 0):.1f} s".replace(".", ","),
            transform=ax.transAxes, fontsize=9)
    fig.suptitle("S4-1 · Demo de e-sert en un comando: python demo/demo.py --local", x=0.01, ha="left",
                 fontweight="bold")
    fig.tight_layout()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=150)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ruta", action="append", default=[])
    ap.add_argument("--destino", default=str(AQUI.parent.parent / "evidencias" / "s1_demo-un-comando.png"))
    args = ap.parse_args(argv)
    cfg = leer_config(AQUI / "config_demo.yaml")
    cmd = [sys.executable, str(AQUI / "demo.py"), "--local", "--cronometro", "--sin-navegador"] + \
        sum((["--ruta", r] for r in args.ruta), [])
    demo = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    lineas, dir_logs = [], None
    for linea in demo.stdout:
        print(linea, end="")
        lineas.append(linea)
        if "Logs:" in linea:
            dir_logs = RAIZ / linea.split("Logs:")[1].strip()
        if "Ctrl+C para terminar" in linea or demo.poll() is not None:
            break
    if demo.poll() is not None or dir_logs is None:
        print("la demo no arrancó", file=sys.stderr)
        return 1
    gui = dir_logs / "sumo_gui.png"
    fin = time.time() + 180
    while time.time() < fin and not gui.exists():
        time.sleep(1)
    time.sleep(1)
    visor_png = dir_logs / "visor.png"
    url = f"http://localhost:{cfg['puertos']['visor']}/?ws=ws://127.0.0.1:{cfg['puertos']['backend']}/ws/estado"
    info = capturar_visor(url, visor_png)
    demo.send_signal(signal.SIGINT)
    resto, _ = demo.communicate(timeout=60)
    print(resto)
    time.sleep(1)
    tiempos = json.loads((dir_logs / "tiempos.json").read_text(encoding="utf-8"))
    limpieza = {
        "puertos_libres": {p: puerto_libre(p) for p in (cfg["puertos"]["backend"], cfg["puertos"]["visor"])},
        "sumo_gui_en_contenedor": docker("exec", cfg.get("contenedor", "van3twin"), "pgrep", "-l", "sumo-gui").stdout.split(),
        "sumo_en_contenedor": docker("exec", cfg.get("contenedor", "van3twin"), "pgrep", "-x", "sumo").stdout.split(),
    }
    componer(gui, visor_png, tiempos, Path(args.destino))
    resumen = {"tiempos": tiempos, "visor": info, "limpieza": limpieza, "captura_gui": gui.exists(),
               "evidencia": str(Path(args.destino))}
    (dir_logs / "evidencia.json").write_text(json.dumps(resumen, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(resumen, indent=1, ensure_ascii=False))
    ok = all(limpieza["puertos_libres"].values()) and not limpieza["sumo_gui_en_contenedor"] and gui.exists()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
