"""Análisis del ensayo de la demo de e-sert (S4).

Lee las latencias exportadas por la app (`latencias/*.csv`), los eventos anotados a mano
(`eventos_ensayo.json`, opcional) y la tarifa del contrato (`../src/contrato/tarifa.json`), y
produce:

- `resultados_ensayo.json`: estadísticas de latencia por modo, reconexiones, tomas y recibos.
- `semanas/S4/Miguel/evidencias/s2_latencias-ensayo.png`: diagrama de cajas de lat_total_ms
  por modo (VPS frente a local).

Uso (desde cualquier carpeta):

    python analizar_ensayo.py
    python analizar_ensayo.py --entrada <carpeta> --salida <json> --png <png>

Si falta un dato, el campo queda en null con una nota; el script no falla.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin pantalla: solo se guarda el PNG
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

AQUI = Path(__file__).resolve().parent
TARIFA_POR_DEFECTO = AQUI.parent / "src" / "contrato" / "tarifa.json"
PNG_POR_DEFECTO = AQUI.parent.parent.parent / "evidencias" / "s2_latencias-ensayo.png"

COLUMNAS = ["modo", "t_sim", "lat_total_ms", "lat_cliente_ms"]
TOLERANCIA_USD = 0.01
MARGEN_TOMAS_S = 30
EPS = 1e-9


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def normalizar_modo(modo: str) -> str:
    """`remoto` y `vps` son el mismo modo; todo en minúsculas."""
    m = str(modo).strip().lower()
    return "vps" if m in ("vps", "remoto") else m


def leer_json(ruta: Path, notas: list[str]) -> dict | None:
    if not ruta.exists():
        notas.append(f"No existe {ruta.name}.")
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        notas.append(f"No se pudo leer {ruta.name}: {exc}")
        return None


def redondear(x: float | None, nd: int = 1) -> float | None:
    return None if x is None else round(float(x), nd)


# ---------------------------------------------------------------------------
# Latencias
# ---------------------------------------------------------------------------

def cargar_latencias(carpeta: Path, notas: list[str]) -> pd.DataFrame:
    """Une todos los CSV de `latencias/`; ignora los que no tengan la cabecera esperada."""
    archivos = sorted(carpeta.glob("*.csv")) if carpeta.is_dir() else []
    if not archivos:
        notas.append(f"No hay CSV de latencias en {carpeta.name}/.")
        return pd.DataFrame(columns=COLUMNAS)
    partes = []
    for ruta in archivos:
        try:
            df = pd.read_csv(ruta)
        except Exception as exc:  # noqa: BLE001 - cualquier CSV roto se anota y se salta
            notas.append(f"{ruta.name}: no se pudo leer ({exc}).")
            continue
        faltan = [c for c in COLUMNAS if c not in df.columns]
        if faltan:
            notas.append(f"{ruta.name}: faltan columnas {faltan}; se ignora.")
            continue
        df = df[COLUMNAS].copy()
        df["archivo"] = ruta.name
        partes.append(df)
    if not partes:
        return pd.DataFrame(columns=COLUMNAS)
    datos = pd.concat(partes, ignore_index=True)
    datos["modo"] = datos["modo"].map(normalizar_modo)
    for col in ("lat_total_ms", "lat_cliente_ms"):
        datos[col] = pd.to_numeric(datos[col], errors="coerce")
    return datos


def estadisticas(serie: pd.Series) -> dict:
    s = serie.dropna()
    if s.empty:
        return {"n": 0, "p50": None, "p95": None, "max": None}
    return {
        "n": int(s.size),
        "p50": redondear(s.quantile(0.50)),
        "p95": redondear(s.quantile(0.95)),
        "max": redondear(s.max()),
    }


def resumen_latencias(datos: pd.DataFrame) -> dict:
    res = {}
    for modo in ("local", "vps"):
        sub = datos[datos["modo"] == modo] if not datos.empty else datos
        if sub.empty:
            res[modo] = {"n": 0, "lat_total_ms": None, "lat_cliente_ms": None,
                         "nota": f"Sin datos del modo {modo}."}
            continue
        res[modo] = {
            "n": int(len(sub)),
            "lat_total_ms": estadisticas(sub["lat_total_ms"]),
            "lat_cliente_ms": estadisticas(sub["lat_cliente_ms"]),
        }
    # Modos inesperados (por si la app exporta otro nombre)
    for modo in sorted(set(datos["modo"]) - {"local", "vps"}) if not datos.empty else []:
        sub = datos[datos["modo"] == modo]
        res[modo] = {"n": int(len(sub)),
                     "lat_total_ms": estadisticas(sub["lat_total_ms"]),
                     "lat_cliente_ms": estadisticas(sub["lat_cliente_ms"]),
                     "nota": "Modo no reconocido (se esperaba local o vps)."}
    return res


def graficar(datos: pd.DataFrame, ruta_png: Path) -> None:
    etiquetas, series = [], []
    for modo, nombre in (("vps", "VPS"), ("local", "Local")):
        s = datos.loc[datos["modo"] == modo, "lat_total_ms"].dropna() if not datos.empty else []
        if len(s):
            etiquetas.append(f"{nombre}\n(n={len(s)})")
            series.append(list(s))
    faltan = [n for m, n in (("vps", "VPS"), ("local", "Local"))
              if datos.empty or datos.loc[datos["modo"] == m, "lat_total_ms"].dropna().empty]

    fig, ax = plt.subplots(figsize=(7, 5))
    if series:
        ax.boxplot(series, tick_labels=etiquetas, showfliers=True)
    else:
        ax.text(0.5, 0.5, "Sin datos de latencia", ha="center", va="center",
                transform=ax.transAxes)
    titulo = "Latencia extremo a extremo del espejo (lat_total_ms)"
    if faltan:
        titulo += "\n" + ", ".join(f"{n}: sin datos" for n in faltan)
    ax.set_title(titulo)
    ax.set_xlabel("Modo de conexión")
    ax.set_ylabel("Latencia total (ms)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta_png, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Eventos: reconexiones, tomas y recibos
# ---------------------------------------------------------------------------

def segundos_entre(corte: str, recuperado: str) -> float:
    """Diferencia en s entre dos horas HH:MM:SS (si cruza medianoche, suma un día)."""
    t0 = datetime.strptime(corte.strip(), "%H:%M:%S")
    t1 = datetime.strptime(recuperado.strip(), "%H:%M:%S")
    if t1 < t0:
        t1 += timedelta(days=1)
    return (t1 - t0).total_seconds()


def resumen_reconexiones(eventos: dict | None) -> dict:
    if eventos is None or "reconexiones" not in eventos:
        return {"numero": None, "detalle": [], "max_recuperacion_s": None,
                "nota": "Sin datos de reconexiones."}
    detalle = []
    for r in eventos.get("reconexiones") or []:
        item = {"modo": normalizar_modo(r.get("modo", "")), "corte": r.get("corte"),
                "recuperado": r.get("recuperado"), "recuperacion_s": None}
        try:
            item["recuperacion_s"] = segundos_entre(r["corte"], r["recuperado"])
        except (KeyError, TypeError, ValueError, AttributeError):
            item["nota"] = "Hora de corte o de recuperación ausente o mal escrita."
        detalle.append(item)
    tiempos = [d["recuperacion_s"] for d in detalle if d["recuperacion_s"] is not None]
    return {"numero": len(detalle), "detalle": detalle,
            "max_recuperacion_s": max(tiempos) if tiempos else None}


def resumen_tomas(eventos: dict | None) -> dict:
    if eventos is None or "tomas" not in eventos:
        return {"detalle": [], "total_previsto_s": None, "total_real_s": None,
                "diferencia_s": None, "dentro_de_30s": None, "nota": "Sin datos de tomas."}
    detalle = []
    for t in eventos.get("tomas") or []:
        prev, real = t.get("previsto_s"), t.get("real_s")
        item = {"toma": t.get("toma"), "nombre": t.get("nombre"),
                "previsto_s": prev, "real_s": real, "diferencia_s": None}
        if isinstance(prev, (int, float)) and isinstance(real, (int, float)):
            item["diferencia_s"] = real - prev
        else:
            item["nota"] = "Falta el tiempo previsto o el real."
        detalle.append(item)
    completas = [d for d in detalle if d["diferencia_s"] is not None]
    res = {"detalle": detalle, "total_previsto_s": None, "total_real_s": None,
           "diferencia_s": None, "dentro_de_30s": None}
    if completas:
        prev = sum(d["previsto_s"] for d in completas)
        real = sum(d["real_s"] for d in completas)
        res.update(total_previsto_s=prev, total_real_s=real, diferencia_s=real - prev,
                   dentro_de_30s=abs(real - prev) <= MARGEN_TOMAS_S)
        if len(completas) < len(detalle):
            res["nota"] = "El total solo suma las tomas con previsto y real."
    else:
        res["nota"] = "Ninguna toma tiene previsto y real."
    return res


def minutos_cobrados(minutos_reales: float, tarifa: dict) -> float:
    """Fracciones de `fraccion_min` hacia arriba, con mínimo `cobro_minimo_min` (como la app)."""
    fracciones = math.ceil(max(0.0, minutos_reales) / tarifa["fraccion_min"] - EPS)
    return max(tarifa["cobro_minimo_min"], fracciones * tarifa["fraccion_min"])


def costo_usd(minutos_reales: float, tarifa: dict) -> float:
    """Minutos cobrados × valor_hora / 60, al centavo con mitad hacia arriba."""
    minutos = minutos_cobrados(minutos_reales, tarifa)
    bruto = Decimal(str(minutos)) * Decimal(str(tarifa["valor_hora_usd"])) / Decimal(60)
    return float(bruto.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def resumen_recibos(eventos: dict | None, tarifa: dict | None) -> dict:
    if eventos is None or "recibos" not in eventos:
        return {"detalle": [], "todos_cuadran": None, "nota": "Sin datos de recibos."}
    detalle = []
    for r in eventos.get("recibos") or []:
        mins, deb = r.get("minutos_reales"), r.get("debitado")
        item = {"veh_id": r.get("veh_id"), "minutos_reales": mins, "minutos_cobrados": None,
                "esperado_usd": None, "debitado_usd": deb, "diferencia_usd": None, "cuadra": None}
        if tarifa is None:
            item["nota"] = "Sin tarifa.json: no se puede calcular el cobro esperado."
        elif not isinstance(mins, (int, float)):
            item["nota"] = "Faltan los minutos reales."
        else:
            item["minutos_cobrados"] = minutos_cobrados(mins, tarifa)
            item["esperado_usd"] = costo_usd(mins, tarifa)
            if isinstance(deb, (int, float)):
                dif = round(deb - item["esperado_usd"], 4)
                item["diferencia_usd"] = dif
                item["cuadra"] = abs(dif) <= TOLERANCIA_USD + EPS
            else:
                item["nota"] = "Falta el monto debitado."
        detalle.append(item)
    valores = [d["cuadra"] for d in detalle if d["cuadra"] is not None]
    return {"detalle": detalle, "todos_cuadran": all(valores) if valores else None}


# ---------------------------------------------------------------------------
# Principal
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analiza el ensayo de la demo de e-sert.")
    ap.add_argument("--entrada", type=Path, default=AQUI,
                    help="Carpeta con latencias/ y eventos_ensayo.json (por defecto, la del script).")
    ap.add_argument("--tarifa", type=Path, default=TARIFA_POR_DEFECTO)
    ap.add_argument("--salida", type=Path, default=None,
                    help="JSON de resultados (por defecto, <entrada>/resultados_ensayo.json).")
    ap.add_argument("--png", type=Path, default=PNG_POR_DEFECTO)
    args = ap.parse_args(argv)

    notas: list[str] = []
    entrada = args.entrada.resolve()
    salida = args.salida or entrada / "resultados_ensayo.json"

    datos = cargar_latencias(entrada / "latencias", notas)
    eventos = leer_json(entrada / "eventos_ensayo.json", notas)
    tarifa = leer_json(args.tarifa, notas)
    if tarifa is not None:
        faltan = [k for k in ("valor_hora_usd", "fraccion_min", "cobro_minimo_min") if k not in tarifa]
        if faltan:
            notas.append(f"tarifa.json no trae {faltan}.")
            tarifa = None

    resultados = {
        "generado": datetime.now().isoformat(timespec="seconds"),
        "tarifa": {k: tarifa[k] for k in ("valor_hora_usd", "fraccion_min", "cobro_minimo_min")}
        if tarifa else None,
        "latencias": resumen_latencias(datos),
        "reconexiones": resumen_reconexiones(eventos),
        "tomas": resumen_tomas(eventos),
        "recibos": resumen_recibos(eventos, tarifa),
        "notas": notas,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    graficar(datos, args.png)

    print(f"Resultados: {salida}")
    print(f"Gráfica:    {args.png}")
    for n in notas:
        print(f"Nota: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
