"""Cifras de la sección de Freddy del informe (S4-3): mide y deja todo en `informe/datos/freddy/`.

    python informe/freddy_cifras.py corridas     # SUMO en van3twin: p00/p20/p50/p80, 1 800 s, semilla 1
    python informe/freddy_cifras.py pruebas      # conteo y duración de tests, cobertura del núcleo
    python informe/freddy_cifras.py cierre       # escenario mínimo de cierre con σ = 5 y 2 m (SUMO)
    python informe/freddy_cifras.py cobro        # ejemplo de cobro de 47 min frente a la tarjeta SERT
    python informe/freddy_cifras.py todo

Se corre desde la carpeta con `backend/`, `comun/`, `traci/` e `informe/`, con `backend/.venv`.

- `corridas.json`: por penetración, `ms_por_paso`, sesiones y los KPIs de `KPIsSistema.resumen()`.
- `pruebas.json`: tests unitarios y e2e (pasan, omitidos, segundos) y cobertura de `backend/nucleo`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

CODIGO = Path(__file__).resolve().parents[1]
DATOS = CODIGO / "informe" / "datos" / "freddy"
PY = sys.executable
PENETRACIONES = (0, 20, 50, 80)
HASTA_S = 1800
SEMILLA = 1


def raiz_repo() -> Path:
    return next(p for p in CODIGO.parents if (p / ".git").exists())


def en_contenedor(ruta: Path) -> str:
    return "/home/vanet/results/e-sert/" + ruta.resolve().relative_to(raiz_repo()).as_posix()


def corrida(pen: int) -> dict:
    ident = f"p{pen:02d}_rf_s{SEMILLA}"
    sufijo = "_informe"
    cmd = ["docker", "exec", "-w", en_contenedor(CODIGO), "van3twin", "bash", "-lc",
           f"python3 -m traci.correr_kpis --id {ident} --hasta {HASTA_S} --sufijo {sufijo}"]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError(r.stdout[-2000:] + r.stderr[-2000:])
    (CODIGO / "traci" / "salidas_kpi" / f"ejemplo_{ident}{sufijo}.json").unlink(missing_ok=True)
    d = json.loads(r.stdout[r.stdout.index("{\n"):])
    return {"id": ident, "penetracion": pen, "hasta_s": HASTA_S, "ms_por_paso": d["ms_por_paso"],
            "pasos": d["pasos"], "tiempo_real_s": d["tiempo_real_s"], "pared_s": round(time.perf_counter() - t0, 1),
            "clasificador_usado": d["clasificador_usado"], "sesiones_maquina": d["sesiones_maquina"],
            "kpis": d.get("kpis"), "costo_kpis": d.get("costo_kpis")}


def corridas() -> dict:
    salida = {"semilla": SEMILLA, "hasta_s": HASTA_S, "fecha": time.strftime("%Y-%m-%d %H:%M"), "corridas": []}
    for pen in PENETRACIONES:
        print(f"corriendo p{pen:02d} ({HASTA_S} s)…", flush=True)
        c = corrida(pen)
        salida["corridas"].append(c)
        print(f"  {c['ms_por_paso']} ms/paso, {c['sesiones_maquina']['sesiones']} sesiones", flush=True)
    escribir("corridas.json", salida)
    return salida


def derivar() -> dict:
    """Añade a `corridas.json` los conteos que el informe necesita (n de cada indicador)."""
    d = json.loads((DATOS / "corridas.json").read_text(encoding="utf-8"))
    for c in d["corridas"]:
        k = c.get("kpis") or {}
        n = k.get("n_sesiones", 0)
        c["derivados"] = {
            "cierres_correctos": n - k.get("n_falsas", 0),
            "sesiones_con_estadia_real": n - k.get("n_sin_estadia_real", 0),
            "abiertas_al_final": c["sesiones_maquina"]["abiertas_al_final"],
            "ventanas_retenidas_datos_pobres": c["sesiones_maquina"]["ventanas_retenidas"],
            "puestos": 610,
            "pct_fantasma_total": round(100 * (k.get("libres_fantasma_medio") or 0) / 610, 1),
        }
    escribir("corridas.json", d)
    return d


def pytest(args: list) -> dict:
    t0 = time.perf_counter()
    r = subprocess.run([PY, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider"], cwd=CODIGO,
                       capture_output=True, text=True)
    pared = round(time.perf_counter() - t0, 1)
    ultima = [l for l in r.stdout.splitlines() if re.search(r"\d+ (passed|failed|skipped)", l)][-1]
    cuenta = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|deselected)", ultima)}
    fallos = [l.strip() for l in r.stdout.splitlines() if l.startswith("FAILED")]
    motivos = [l.strip()[:300] for l in r.stdout.splitlines() if l.startswith("E   ") and "Error" in l][:6]
    return {"args": " ".join(args), "pasan": cuenta.get("passed", 0), "fallan": cuenta.get("failed", 0),
            "omitidos": cuenta.get("skipped", 0), "segundos": pared, "resumen": ultima.strip("= "),
            "fallos": fallos, "motivos": motivos}, r.stdout


def pruebas() -> dict:
    salida = {"fecha": time.strftime("%Y-%m-%d %H:%M")}
    salida["unit_backend"], _ = pytest(["backend/tests"])
    salida["unit_traci"], _ = pytest(["traci/tests"])
    salida["unit_comun"], _ = pytest(["comun/tests"])
    salida["e2e"], _ = pytest(["-c", "backend/pytest.ini", "backend/tests", "traci/tests", "-m", "e2e"])
    cov, texto = pytest(["backend/tests", "--cov=backend/nucleo", "--cov-report=term"])
    m = re.search(r"^TOTAL\s+(\d+)\s+(\d+)\s+(\d+)%", texto, re.M)
    salida["cobertura_nucleo"] = {"lineas": int(m.group(1)), "sin_cubrir": int(m.group(2)),
                                  "porcentaje": int(m.group(3))} if m else None
    unit = [salida[k] for k in ("unit_backend", "unit_traci", "unit_comun")]
    salida["total_unitarios"] = {"pasan": sum(u["pasan"] for u in unit), "omitidos": sum(u["omitidos"] for u in unit),
                                 "fallan": sum(u["fallan"] for u in unit), "segundos": round(sum(u["segundos"] for u in unit), 1)}
    escribir("pruebas.json", salida)
    return salida


def cierre() -> dict:
    """Escenario mínimo de cierre (5 autos con peatones de diligencia) con GPS σ = 5 m y σ = 2 m."""
    salida = {"escenario": "traci/tests/e2e/escenario_cierre.py (5 autos de búsqueda, estadías 4-8 min)",
              "fecha": time.strftime("%Y-%m-%d %H:%M"), "por_sigma": {}}
    for sigma in (5, 2):
        rel = f"traci/salidas/informe_cierre_s{sigma}.json"
        dir_csv = CODIGO / "traci" / "salidas" / f"informe_cierre_s{sigma}"
        cmd = ["docker", "exec", "-w", en_contenedor(CODIGO), "van3twin", "python3", "-m",
               "traci.tests.e2e.escenario_cierre", "--salida", rel, "--sigma", str(sigma),
               "--guardar", f"traci/salidas/informe_cierre_s{sigma}"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            raise RuntimeError(r.stderr[-2000:])
        d = json.loads((CODIGO / rel).read_text(encoding="utf-8"))
        (CODIGO / rel).unlink()
        cierres = d["cierres"]
        # Ventanas de 30 s en que la persona caminaba (modo_real a_pie): ¿cuántas salieron `vehiculo`?
        import csv as _csv
        ventanas = list(_csv.DictReader((dir_csv / "ventanas_e2e_cierre.csv").open(encoding="utf-8")))
        a_pie = [v for v in ventanas if v["modo_real"] == "a_pie"]
        confusion = {"ventanas_a_pie": len(a_pie),
                     "a_pie_como_vehiculo": sum(v["modo_clasificado"] == "vehiculo" for v in a_pie)}
        confusion["frac_a_pie_como_vehiculo"] = round(confusion["a_pie_como_vehiculo"] / max(1, len(a_pie)), 3)
        import shutil as _sh
        _sh.rmtree(dir_csv, ignore_errors=True)
        retardos = sorted(c["retardo_cierre_s"] for c in cierres if c["retardo_cierre_s"] is not None)
        salida["por_sigma"][str(sigma)] = {
            "sesiones": len(cierres), "falsas": sum(c["falsa"] for c in cierres),
            "retardos_s": retardos, "retardo_mediana_s": retardos[len(retardos) // 2] if retardos else None,
            "ventanas_por_fuente": d["sesiones_maquina"]["ventanas_por_fuente"], **confusion}
        print(f"  σ={sigma}: {salida['por_sigma'][str(sigma)]}", flush=True)
    escribir("cierre_sigma.json", salida)
    return salida


def cobro(minutos: float = 47.0) -> dict:
    """Ejemplo numérico de cobro con `comun/tarifa.json` frente a la tarjeta SERT de papel."""
    sys.path.insert(0, str(CODIGO))
    from comun.tarifa import cargar_tarifa, costo_usd, minutos_cobrados, monto_debito, monto_retencion, tarjeta_sert_usd

    t = cargar_tarifa()
    cobrados = minutos_cobrados(minutos, t)
    salida = {"minutos_reales": minutos, "tarifa": t.model_dump(), "retencion_usd": monto_retencion(t),
              "minutos_cobrados": cobrados, "fracciones": cobrados // t.fraccion_min,
              "debito_usd": monto_debito(minutos, t), "costo_tiempo_exacto_usd": costo_usd(minutos, t),
              "tarjeta_sert_usd": tarjeta_sert_usd(minutos, t),
              "ahorro_usd": round(tarjeta_sert_usd(minutos, t) - monto_debito(minutos, t), 2),
              "saldo_tras_recarga_5_usd": round(5 - monto_debito(minutos, t), 2),
              "disponible_durante_sesion_usd": round(5 - monto_retencion(t), 2)}
    escribir("cobro_47min.json", salida)
    return salida


def escribir(nombre: str, datos: dict) -> None:
    DATOS.mkdir(parents=True, exist_ok=True)
    (DATOS / nombre).write_text(json.dumps(datos, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(f"→ {DATOS / nombre}")


if __name__ == "__main__":
    que = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if que in ("corridas", "todo"):
        corridas()
    if que in ("corridas", "derivar", "todo"):
        derivar()
    if que in ("pruebas", "todo"):
        pruebas()
    if que in ("cierre", "todo"):
        cierre()
    if que in ("cobro", "todo"):
        cobro()
