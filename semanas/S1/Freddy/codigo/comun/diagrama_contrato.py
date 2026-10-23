"""Diagrama de componentes y mensajes del contrato v1 de e-sert.

Dibuja con matplotlib (sin graphviz) las cajas de cada componente del proyecto,
coloreadas según su dueño, y las flechas con los mensajes del contrato v1
(HTTP, WebSocket y llamadas TraCI). Guarda el PNG en
``semanas/S1/Freddy/evidencias/s1_contrato-diagrama.png``.

Uso (desde ``semanas/S1/Freddy/codigo``)::

    python comun/diagrama_contrato.py

Compatible con Python 3.10.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin pantalla: solo generamos el archivo
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch

# Ruta de salida relativa a este archivo: comun/ -> codigo/ -> Freddy/evidencias/
SALIDA = Path(__file__).resolve().parent / ".." / ".." / "evidencias" / "s1_contrato-diagrama.png"

# Colores de cada dueño (borde) y su versión clara (relleno)
COLORES = {
    "Tyrone": ("#1E63D6", "#E3ECFB"),
    "Freddy": ("#FF7043", "#FFEDE6"),
    "Pablo": ("#2E9E4F", "#E3F4E8"),
    "Miguel": ("#C62828", "#F9E3E3"),
}

TAM_ETIQUETA = 7.5  # tamaño de letra de las etiquetas de flechas


def caja(ax, x, y, ancho, alto, texto, dueno, tam=10, subtitulo=None):
    """Dibuja una caja redondeada con el color del dueño y devuelve su rectángulo."""
    borde, relleno = COLORES[dueno]
    parche = FancyBboxPatch(
        (x, y), ancho, alto,
        boxstyle="round,pad=0.4,rounding_size=1.6",
        linewidth=2, edgecolor=borde, facecolor=relleno, zorder=2,
    )
    ax.add_patch(parche)
    cx, cy = x + ancho / 2, y + alto / 2
    if subtitulo:
        ax.text(cx, cy + 1.6, texto, ha="center", va="center", fontsize=tam,
                fontweight="bold", zorder=3)
        ax.text(cx, cy - 2.4, subtitulo, ha="center", va="center", fontsize=7.5,
                color="#444444", style="italic", zorder=3)
    else:
        ax.text(cx, cy, texto, ha="center", va="center", fontsize=tam,
                fontweight="bold", zorder=3)
    return (x, y, ancho, alto)


def flecha(ax, p0, p1, color="#333333", doble=False):
    """Flecha recta de p0 a p1 (doble punta si ``doble``)."""
    estilo = "<|-|>" if doble else "-|>"
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=estilo, mutation_scale=14,
                                 linewidth=1.6, color=color, zorder=4))


def etiqueta(ax, x, y, texto, ha="left", va="center", color="#222222"):
    """Texto pequeño de una flecha, con fondo blanco para que no se mezcle."""
    ax.text(x, y, texto, ha=ha, va=va, fontsize=TAM_ETIQUETA, color=color,
            family="DejaVu Sans Mono", linespacing=1.35, zorder=5,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="none", alpha=0.9))


def punteada(ax, puntos, color):
    """Línea punteada por varios puntos (para las dependencias de comun/)."""
    xs, ys = zip(*puntos)
    ax.plot(xs, ys, linestyle=(0, (3, 2.5)), color=color, linewidth=1.4, zorder=1)


def main():
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 160)
    ax.set_ylim(-4, 100)
    ax.axis("off")

    ax.text(80, 96, "e-sert · Contrato v1: componentes y mensajes", ha="center",
            va="center", fontsize=17, fontweight="bold")

    # --- Cajas de componentes ---
    caja(ax, 14, 74, 28, 12, "SUMO 1.12", "Tyrone", subtitulo="(contenedor van3twin)")
    caja(ax, 14, 44, 28, 16, "Controlador TraCI", "Freddy",
         subtitulo="+ emulador GPS + máquina de estados")
    caja(ax, 14, 10, 28, 14, "IA: clasificar(ventana)\n→ ResultadoModo", "Pablo", tam=9.5,
         subtitulo=None)
    ax.text(28, 7.2, "proyecto/ia/inferencia.py", ha="center", fontsize=7.5,
            color="#444444", style="italic")
    caja(ax, 80, 24, 28, 38, "Backend FastAPI\n/api/v1", "Freddy", tam=11)
    ax.text(94, 36, "billetera\nsesiones\nWS", ha="center", va="center", fontsize=8.5,
            color="#444444", style="italic", zorder=3)
    caja(ax, 132, 52, 26, 12, "Visor web Leaflet", "Tyrone")
    caja(ax, 132, 74, 26, 8, "KPIs (Tyrone)", "Tyrone", tam=9)
    caja(ax, 132, 20, 26, 20, "App Expo", "Miguel", subtitulo="(teléfono espejo)")
    caja(ax, 54, 4, 38, 10, "comun/", "Freddy", tam=9.5,
         subtitulo="esquemas.py · esquemas.ts · tarifa.json")

    # --- SUMO <-> TraCI ---
    flecha(ax, (28, 61), (28, 73), doble=True)
    etiqueta(ax, 26.5, 67, "TraCI: posiciones,\nisStoppedParking,\nsetParkingAreaStop",
             ha="right")

    # --- TraCI <-> IA ---
    flecha(ax, (20, 43), (20, 25))
    etiqueta(ax, 18.5, 34, "list[PuntoGPS]\n(ventana 30 s,\npaso 5 s)", ha="right")
    flecha(ax, (36, 25), (36, 43))
    etiqueta(ax, 37.5, 34, "ResultadoModo\n{modo, confianza,\nfuente}")

    # --- TraCI -> Backend ---
    flecha(ax, (42.8, 48), (79.2, 48))
    etiqueta(ax, 44, 50,
             "POST /sim/paso (1 Hz: vehiculos,\n"
             "     peatones, verdad)\n"
             "POST /eventos/ubicacion · /eventos/modo\n"
             "GET  /guia\n"
             "POST /sesiones · /sesiones/{id}/transicion\n"
             "     · /sesiones/{id}/cerrar\n"
             "POST /billetera/{id}/recarga", va="bottom")

    # --- Backend -> Visor y KPIs ---
    flecha(ax, (108.8, 56), (131.2, 56))
    etiqueta(ax, 110, 57.5, "WS /ws/estado?rol=visor:\nsnapshot, kpi, verdad", va="bottom")
    ax.plot([100, 100, 115], [62.8, 78, 78], color="#333333", linewidth=1.6, zorder=4)
    flecha(ax, (114, 78), (131.2, 78))
    etiqueta(ax, 102, 80, "kpi, verdad", va="bottom")

    # --- Backend <-> App ---
    flecha(ax, (108.8, 35), (131.2, 35))
    etiqueta(ax, 110, 36.5, "WS /ws/espejo/{veh_id}:\nespejo, espejo_fin", va="bottom")
    flecha(ax, (131.2, 27), (108.8, 27))
    etiqueta(ax, 110, 25.5,
             "GET /espejo/candidatos,\n    /puestos, /tarifa,\n    /billetera/{id}\n"
             "POST /billetera/{id}\n    /recarga", va="top")

    # --- comun/ importada por backend, TraCI, IA y app ---
    gris = "#FF7043"
    punteada(ax, [(54, 12), (42.5, 12)], gris)              # IA
    punteada(ax, [(62, 14.5), (62, 46), (42.5, 46)], gris)  # TraCI
    punteada(ax, [(86, 14.5), (86, 23.5)], gris)            # backend
    punteada(ax, [(92, 8), (145, 8), (145, 19.5)], gris)    # app
    ax.text(73, 15.8, "importan", ha="center", fontsize=8, style="italic", color=gris)

    # --- Leyenda de dueños ---
    manejadores = [Patch(facecolor=COLORES[n][1], edgecolor=COLORES[n][0], linewidth=2,
                         label=n) for n in COLORES]
    manejadores.append(Line2D([0], [0], color="#333333", lw=1.6, label="mensaje"))
    manejadores.append(Line2D([0], [0], color=gris, lw=1.4, linestyle=(0, (3, 2.5)),
                              label="importa comun/"))
    ax.legend(handles=manejadores, title="Dueños", loc="upper center",
              bbox_to_anchor=(0.43, 0.9), ncol=3, fontsize=9, title_fontsize=10,
              frameon=True)

    # --- Nota al pie ---
    ax.text(80, -2.5,
            'HTTP: header X-Contrato-Version: 1 · errores {"error": {"codigo", "mensaje"}}'
            " · 'verdad' nunca llega a la app",
            ha="center", va="center", fontsize=9, color="#333333")

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(SALIDA, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Diagrama guardado en {SALIDA.resolve()}")


if __name__ == "__main__":
    main()
