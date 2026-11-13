"""Pruebas en navegador y capturas del visor final (S3-3), con Playwright *headless*.

Uso (desde semanas/S3/Tyrone/codigo, con el entorno visor/.venv):
    python -m visor.captura evidencias            # s3_visor-final.png y s3_visor-presentacion.png
    python -m visor.captura rendimiento --vehiculos 800
    python -m visor.captura reconexion
    python -m visor.captura teclas
    python -m visor.captura todo --informe visor/datos/prueba_navegador.json
    python -m visor.captura evidencias --url "http://localhost:8000/visor/" --sin-servidor   # backend real

Sin `--url`, lanza `python -m visor.servidor_prueba` en un puerto libre. Cada prueba devuelve un
dict con lo medido; `todo` las corre todas y escribe el informe JSON.
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DIR_CODIGO = Path(__file__).resolve().parent.parent
EVIDENCIAS = DIR_CODIGO.parent / "evidencias"


def puerto_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def esperar_puerto(puerto: int, abierto: bool = True, limite: float = 20) -> bool:
    fin = time.time() + limite
    while time.time() < fin:
        try:
            socket.create_connection(("127.0.0.1", puerto), timeout=0.2).close()
            if abierto:
                return True
        except OSError:
            if not abierto:
                return True
        time.sleep(0.2)
    return False


class Servidor:
    def __init__(self, puerto=None, velocidad=2, vehiculos=0, snapshots=None):
        self.puerto = puerto or puerto_libre()
        self.args = ["--puerto", str(self.puerto), "--velocidad", str(velocidad), "--host", "127.0.0.1",
                     "--vehiculos", str(vehiculos)] + (["--snapshots", str(snapshots)] if snapshots else [])
        self.proc = None

    def iniciar(self):
        self.proc = subprocess.Popen([sys.executable, "-m", "visor.servidor_prueba", *self.args], cwd=DIR_CODIGO,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not esperar_puerto(self.puerto):
            raise RuntimeError("el servidor de prueba no arrancó")
        return self

    def parar(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(10)
            self.proc = None
        esperar_puerto(self.puerto, abierto=False)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.puerto}/visor/"


def navegador(p):
    """Chromium de Playwright; si falta la versión exacta, el que haya en la caché."""
    try:
        return p.chromium.launch()
    except Exception:  # noqa: BLE001
        cache = Path.home() / ".cache" / "ms-playwright"
        for exe in sorted(cache.glob("chromium-*/chrome-linux*/chrome"), reverse=True):
            return p.chromium.launch(executable_path=str(exe))
        raise


def abrir(b, url, ancho=1600, alto=1000, escala=1):
    pg = b.new_page(viewport={"width": ancho, "height": alto}, device_scale_factor=escala)
    pg.errores = []
    pg.on("pageerror", lambda e: pg.errores.append(str(e)))
    pg.goto(url)
    return pg


def esperar(pg, expr, limite=30):
    pg.wait_for_function(expr, timeout=limite * 1000)


def candidato(url_base: str) -> str:
    import urllib.request

    api = url_base.split("/visor")[0] + "/api/v1/espejo/candidatos"
    with urllib.request.urlopen(api, timeout=5) as r:
        lista = json.loads(r.read())
    return lista[0]["id"] if lista else ""


# ----------------------------------------------------------------------------- pruebas

def prueba_evidencias(b, url, destino=EVIDENCIAS) -> dict:
    """Vista normal con un espejo seguido por WS (ruta y puesto) y modo presentación."""
    veh = candidato(url)
    pg = abrir(b, f"{url}?espejo={veh}" if veh else url)
    esperar(pg, "window.visorKpisRecibidos >= 1 && (window.visorEspejosVisibles || []).length >= 1", 40)
    if veh:
        esperar(pg, "window.visorEspejoPuesto", 20)
    pg.wait_for_timeout(2500)
    destino.mkdir(parents=True, exist_ok=True)
    normal = destino / "s3_visor-final.png"
    pg.screenshot(path=str(normal))
    r = pg.evaluate("({kpis: window.visorKpisRecibidos, espejos: window.visorEspejosVisibles,"
                    " ruta: window.visorEspejoRuta, puesto: window.visorEspejoPuesto,"
                    " redibujos: window.visorRedibujosPanel})")
    pg.close()
    pg = abrir(b, f"{url}?presentacion=1" + (f"&espejo={veh}" if veh else ""), 1920, 1080)
    esperar(pg, "window.visorKpisRecibidos >= 1 && (window.visorEspejosVisibles || []).length >= 1", 40)
    pg.wait_for_timeout(2500)
    pres = destino / "s3_visor-presentacion.png"
    pg.screenshot(path=str(pres))
    r["presentacion"] = pg.evaluate("window.visorPresentacion()")
    r["errores"] = pg.errores
    pg.close()
    r.update({"veh_espejo": veh, "png": [str(normal), str(pres)]})
    return r


def prueba_rendimiento(b, url, segundos=10) -> dict:
    pg = abrir(b, url, 1920, 1080)
    esperar(pg, "(window.visorVehiculos || 0) >= 790", 40)
    pg.keyboard.press("d")
    pg.wait_for_timeout(segundos * 1000)
    e = pg.evaluate("window.visorEstadisticaCuadros()")
    e["vehiculos"] = pg.evaluate("window.visorVehiculos")
    pg.close()
    e["cumple_33ms"] = e["cuadro_ms"]["p95"] is not None and e["cuadro_ms"]["p95"] < 33
    return e


def prueba_reconexion(b, srv: Servidor) -> dict:
    pg = abrir(b, srv.url)
    esperar(pg, "window.visorConexion === 'conectado'", 20)
    srv.parar()
    esperar(pg, "window.visorConexion !== 'conectado'", 20)
    apagado_s = 8
    pg.wait_for_timeout(apagado_s * 1000)  # el visor ya va por reintentos de 1, 2, 4 s
    t_sim_antes = pg.evaluate("window.visorUltimoSnapshot")
    srv.iniciar()
    t0 = time.time()
    esperar(pg, "window.visorConexion === 'conectado'", 35)
    tarda = time.time() - t0
    esperar(pg, f"window.visorUltimoSnapshot !== {json.dumps(t_sim_antes)}", 10)
    r = {"apagado_s": apagado_s, "reconexion_s": round(tarda, 1), "sin_recargar": True,
         "reconexiones": pg.evaluate("window.visorReconexiones"), "cumple_30s": tarda < 30, "errores": pg.errores}
    pg.close()
    return r


def prueba_teclas(b, url) -> dict:
    pg = abrir(b, url, 1920, 1080)
    esperar(pg, "(window.visorEspejosVisibles || []).length >= 1", 40)
    r = {}
    pg.keyboard.press("p")
    pg.wait_for_timeout(600)
    r["P"] = pg.evaluate("window.visorPresentacion().activa && document.body.classList.contains('presentacion')")
    r["fuente_x1_5"] = pg.evaluate("getComputedStyle(document.body).fontSize")
    pg.keyboard.press("h")
    r["H"] = pg.evaluate("window.visorPresentacion().ayuda")
    pg.keyboard.press("h")
    pg.keyboard.press("e")
    pg.wait_for_timeout(2500)
    centro = pg.evaluate("(() => { const c = window.visor.mapa.getCenter(); const p = window.visor.espejo.principal();"
                         " return p ? window.visor.mapa.distance(c, p) : null; })()")
    r["E"] = pg.evaluate("window.visorPresentacion().siguiendo") and centro is not None and centro < 150
    r["E_distancia_m"] = None if centro is None else round(centro, 1)
    pg.keyboard.press("e")
    pg.keyboard.press("t")
    vistas = [pg.evaluate("window.visorPresentacion().vista")]
    pg.wait_for_timeout(21500)
    vistas.append(pg.evaluate("window.visorPresentacion().vista"))
    r["T"] = pg.evaluate("window.visorPresentacion().recorrido") and vistas[0] != vistas[1]
    r["T_vistas"] = vistas
    pg.keyboard.press("t")
    pg.keyboard.press("p")
    r["P_sale"] = not pg.evaluate("window.visorPresentacion().activa")
    r["errores"] = pg.errores
    pg.close()
    return r


def prueba_retiro(b, url) -> dict:
    """Al dejar de seguir (sale de `espejos`), el halo se retira en ~5 s."""
    pg = abrir(b, url)
    esperar(pg, "(window.visorEspejosVisibles || []).length >= 1", 40)
    ids = pg.evaluate("window.visorEspejosVisibles")
    # simula que el backend deja de listar el espejo: se fuerza la lista vacía en los snapshots
    pg.evaluate("""(() => { const e = window.visor.espejo; const orig = e.onSnapshot.bind(e);
        e.onSnapshot = (m) => orig(Object.assign({}, m, {espejos: []})); window.__t0 = performance.now(); })()""")
    pg.wait_for_function("(window.visorEspejosVisibles || []).length === 0", timeout=15000)
    tarda = pg.evaluate("(performance.now() - window.__t0) / 1000")
    pg.close()
    return {"retirados": ids, "retiro_s": round(tarda, 1), "cumple": 4.0 <= tarda <= 7.5}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("prueba", choices=["evidencias", "rendimiento", "reconexion", "teclas", "retiro", "todo"])
    ap.add_argument("--url", default=None)
    ap.add_argument("--sin-servidor", action="store_true")
    ap.add_argument("--vehiculos", type=int, default=800)
    ap.add_argument("--destino", default=str(EVIDENCIAS))
    ap.add_argument("--informe", default=None)
    args = ap.parse_args(argv)
    res = {}
    with sync_playwright() as p:
        b = navegador(p)
        if args.sin_servidor:
            if args.prueba in ("evidencias", "todo"):
                res["evidencias"] = prueba_evidencias(b, args.url, Path(args.destino))
            if args.prueba in ("teclas",):
                res["teclas"] = prueba_teclas(b, args.url)
        else:
            if args.prueba in ("evidencias", "todo", "teclas", "retiro"):
                srv = Servidor(velocidad=2).iniciar()
                try:
                    if args.prueba in ("evidencias", "todo"):
                        res["evidencias"] = prueba_evidencias(b, srv.url, Path(args.destino))
                    if args.prueba in ("teclas", "todo"):
                        res["teclas"] = prueba_teclas(b, srv.url)
                    if args.prueba in ("retiro", "todo"):
                        res["retiro"] = prueba_retiro(b, srv.url)
                finally:
                    srv.parar()
            if args.prueba in ("rendimiento", "todo"):
                srv = Servidor(velocidad=1, vehiculos=args.vehiculos).iniciar()
                try:
                    res["rendimiento"] = prueba_rendimiento(b, srv.url)
                finally:
                    srv.parar()
            if args.prueba in ("reconexion", "todo"):
                srv = Servidor(velocidad=2).iniciar()
                try:
                    res["reconexion"] = prueba_reconexion(b, srv)
                finally:
                    srv.parar()
        b.close()
    texto = json.dumps(res, indent=1, ensure_ascii=False)
    print(texto)
    if args.informe:
        Path(args.informe).write_text(texto, encoding="utf-8")


if __name__ == "__main__":
    main()
