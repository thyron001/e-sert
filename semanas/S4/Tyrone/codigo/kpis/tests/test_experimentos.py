"""Tests del ejecutor de experimentos (S3-1).

Los que corren SUMO van **dentro del contenedor** (`SUMO_HOME`), desde `semanas/S3/Tyrone/codigo`:

    python3 -m pytest -q kpis/tests/test_experimentos.py

Usan corridas cortas (modo rápido: 300–600 s de simulación) en carpetas temporales.
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

CODIGO = Path(__file__).resolve().parents[2]
ESC = CODIGO / "sumo" / "escenarios"
con_sumo = pytest.mark.skipif(not os.environ.get("SUMO_HOME"), reason="requiere SUMO (contenedor van3twin)")
NO_COMPARABLES = {"id", "clasificador", "duracion_real_s"}


def _cfg(pen, clf, sem, tmp, dur=300, warm=60):
    from kpis.correr_una import id_corrida

    rel = os.path.relpath(tmp, CODIGO)
    return {"id": id_corrida(pen, clf, sem), "penetracion": pen, "clasificador": clf, "semilla": sem,
            "duracion_s": float(dur), "warmup_s": float(warm), "modelo_rf": "kpis/externo/rf_final.plano.npz",
            "dir_resultados": rel, "subdir_salidas": f"test_{tmp.name}"}


def _correr_en_proceso(cfg):
    """Cada corrida en su propio intérprete, como en el ejecutor (TraCI guarda estado global)."""
    codigo = ("import json,sys; from kpis.correr_una import correr; "
              f"print('RES'+json.dumps(correr(json.loads(sys.argv[1]))))")
    out = subprocess.run([sys.executable, "-c", codigo, json.dumps(cfg)], cwd=CODIGO, capture_output=True,
                         text=True, timeout=900)
    assert out.returncode == 0, out.stderr[-2000:]
    linea = [l for l in out.stdout.splitlines() if l.startswith("RES")][-1]
    return json.loads(linea[3:])


def _con_app(ruta):
    ids, actual = set(), None
    patron = re.compile(r'<(?:trip|vehicle) id="([^"]+)"')
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        m = patron.search(linea)
        if m:
            actual = m.group(1)
        elif '<param key="con_app" value="1"/>' in linea and actual:
            ids.add(actual)
    return ids


@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_con_app_anidados(semilla):
    """20 % ⊂ 50 % ⊂ 80 % (números aleatorios comunes) y el 0 % sin usuarios con app."""
    rutas = [ESC / f"{n}_s{semilla}.rou.xml" for n in ("base", "app20", "app50", "app80")]
    if not all(r.exists() for r in rutas):
        pytest.skip("faltan demandas: corre sumo/escenarios/generar_escenarios.py")
    base, a20, a50, a80 = (_con_app(r) for r in rutas)
    assert not base
    assert a20 < a50 < a80
    assert len(a20) > 0


def test_hash_ignora_carpetas_y_modelo_sin_usuarios():
    from kpis.experimentos import hash_config

    h = {"red": "a", "parqueos": "b", "modelo_rf": "m1"}
    c = {"id": "p00_rf_s1", "penetracion": 0, "clasificador": "rf", "semilla": 1, "duracion_s": 600.0,
         "warmup_s": 120.0, "modelo_rf": "x.npz", "dir_resultados": "a", "subdir_salidas": ""}
    otra = dict(c, dir_resultados="b", subdir_salidas="z")
    assert hash_config(c, h) == hash_config(otra, h)
    assert hash_config(c, h) == hash_config(c, dict(h, modelo_rf="m2"))  # 0 %: el modelo no influye
    c50 = dict(c, penetracion=50, id="p50_rf_s1")
    assert hash_config(c50, h) != hash_config(c50, dict(h, modelo_rf="m2"))


@con_sumo
def test_penetracion_0_umbral_igual_a_rf(tmp_path):
    """Sin usuarios con app no hay nada que clasificar: umbral y rf dan los mismos KPIs."""
    u = _correr_en_proceso(_cfg(0, "umbral", 1, tmp_path))["fila"]
    r = _correr_en_proceso(_cfg(0, "rf", 1, tmp_path))["fila"]
    assert {k: v for k, v in u.items() if k not in NO_COMPARABLES} == \
           {k: v for k, v in r.items() if k not in NO_COMPARABLES}


@con_sumo
def test_repetir_da_el_mismo_json(tmp_path):
    """Determinismo: la misma corrida dos veces da el mismo resultado (salvo el tiempo real)."""
    a = _correr_en_proceso(_cfg(50, "rf", 1, tmp_path))
    b = _correr_en_proceso(_cfg(50, "rf", 1, tmp_path))
    for x in (a, b):
        x["fila"].pop("duracion_real_s")
        x["extra"].pop("ms_por_paso")
    assert a == b


@con_sumo
def test_relanzar_tras_interrupcion_no_repite(tmp_path):
    """Se mata el ejecutor cuando ya escribió una corrida; al relanzar, esa no se repite."""
    rel = os.path.relpath(tmp_path, CODIGO)
    cmd = [sys.executable, "-m", "kpis.experimentos", "--rapida", "--procesos", "1", "--resultados", str(tmp_path)]
    proc = subprocess.Popen(cmd, cwd=CODIGO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    corridas = tmp_path / "corridas"
    limite = time.time() + 600
    while time.time() < limite and not list(corridas.glob("*.json")):
        time.sleep(1)
    hechas = [p for p in corridas.glob("*.json") if not p.name.endswith(".error.json")]
    os.killpg(proc.pid, signal.SIGKILL)  # muere a mitad de la segunda corrida
    proc.wait()
    subprocess.run(["pkill", "-f", "kpis_p50_rf_s1"], check=False)  # el SUMO huérfano
    assert len(hechas) == 1, f"se esperaba 1 corrida escrita, hay {hechas} ({rel})"
    escrita = hechas[0]
    antes = (escrita.stat().st_mtime_ns, escrita.read_text())
    dry = subprocess.run(cmd + ["--dry-run"], cwd=CODIGO, capture_output=True, text=True, timeout=120)
    assert "1 ya hechas, 1 pendientes" in dry.stdout, dry.stdout
    assert escrita.stem not in dry.stdout.split("pendientes")[-1]
    fin = subprocess.run(cmd, cwd=CODIGO, capture_output=True, text=True, timeout=900)
    assert fin.returncode == 0, fin.stdout[-2000:] + fin.stderr[-2000:]
    assert (escrita.stat().st_mtime_ns, escrita.read_text()) == antes
    log = (tmp_path / "progreso.log").read_text()
    assert log.count(f"fin {escrita.stem}") == 1
    assert (tmp_path / "experimentos.csv").read_text().count("\n") == 3  # cabecera + 2 corridas
