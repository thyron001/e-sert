"""Captura del visor con Playwright, medición de FPS y prueba de reconexión.

Uso (desde semanas/S2/Tyrone/codigo, con el entorno visor/.venv):
    python -m visor.captura --salida ../evidencias/s2_visor-leaflet.png [--reconexion]
    python -m visor.captura --url "http://localhost:8000/visor/?ws=..." --sin-servidor

Sin --url lanza `python -m visor.servidor_prueba` en un puerto libre, abre el visor a
1600x1000, espera a que lleguen snapshots y KPIs, mide los FPS durante 5 s
(requestAnimationFrame, `window.visorFps`) y guarda la captura. Con --reconexion, además, para
el servidor, comprueba que el visor queda desconectado, lo relanza y espera a que vuelva a
conectarse sin recargar la página.
"""
import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DIR_CODIGO = Path(__file__).resolve().parent.parent


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def lanzar_servidor(puerto, velocidad):
    proc = subprocess.Popen([sys.executable, "-m", "visor.servidor_prueba", "--puerto", str(puerto),
                             "--velocidad", str(velocidad), "--host", "127.0.0.1"],
                            cwd=DIR_CODIGO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=0.2).close()
            return proc
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise RuntimeError("El servidor de prueba no arrancó")


def medir_fps(pagina, segundos=5):
    muestras = []
    for _ in range(segundos):
        pagina.wait_for_timeout(1000)
        muestras.append(pagina.evaluate("window.visorFps || 0"))
    return sum(muestras) / len(muestras), min(muestras)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(DIR_CODIGO.parent / "evidencias" / "s2_visor-leaflet.png"))
    ap.add_argument("--url", default=None)
    ap.add_argument("--velocidad", type=int, default=1)
    ap.add_argument("--espera-s", type=float, default=35, help="tiempo para recibir snapshots y un kpi")
    ap.add_argument("--reconexion", action="store_true")
    args = ap.parse_args()

    puerto = puerto_libre()
    proc = None if args.url else lanzar_servidor(puerto, args.velocidad)
    url = args.url or f"http://127.0.0.1:{puerto}/visor/"
    try:
        with sync_playwright() as pw:
            nav = pw.chromium.launch()
            pagina = nav.new_page(viewport={"width": 1600, "height": 1000})
            errores = []
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            pagina.goto(url)
            pagina.wait_for_function("window.visorUltimoSnapshot !== undefined", timeout=30000)
            t_ini = pagina.evaluate("window.visorUltimoSnapshot")
            pagina.wait_for_timeout(args.espera_s * 1000)
            t_fin = pagina.evaluate("window.visorUltimoSnapshot")
            fps_medio, fps_min = medir_fps(pagina)
            n_veh = pagina.inner_text("#n-vehiculos")
            print(f"snapshots: t_sim {t_ini:.0f} -> {t_fin:.0f} s · vehículos {n_veh} · "
                  f"FPS medio {fps_medio:.1f} (mínimo {fps_min:.1f})")
            pagina.screenshot(path=args.salida)
            print(f"Captura -> {args.salida}")

            if args.reconexion and proc:
                proc.terminate()
                proc.wait()
                pagina.wait_for_function("window.visorConexion === 'desconectado'", timeout=15000)
                print("Servidor detenido: el visor muestra 'desconectado'")
                pagina.wait_for_timeout(3000)
                proc = lanzar_servidor(puerto, args.velocidad)
                antes = pagina.evaluate("window.visorUltimoSnapshot")
                pagina.wait_for_function("window.visorConexion === 'conectado'", timeout=40000)
                pagina.wait_for_function(f"window.visorUltimoSnapshot !== {antes}", timeout=15000)
                print("Servidor relanzado: el visor se reconectó sin recargar la página")
            if errores:
                print("Errores de JavaScript:", errores)
            nav.close()
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
