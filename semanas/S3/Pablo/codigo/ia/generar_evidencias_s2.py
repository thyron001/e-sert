"""
Genera las 3 evidencias PNG de S2-sesion 2:
  s2_matriz-confusion.png
  s2_importancia.png
  s2_suavizado.png
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DIR_EVIDENCIAS = Path(__file__).resolve().parent.parent.parent / "evidencias"
DIR_REPORTES = Path(__file__).resolve().parent / "reportes"
DIR_MODELOS = Path(__file__).resolve().parent / "modelos"


def generar_matriz_confusion():
    """Matriz de confusion normalizada: umbral vs rf_v1, lado a lado."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ruta = DIR_REPORTES / "cv_rf_v1.json"
    with open(ruta) as f:
        datos = json.load(f)

    metricas = datos["metricas"]
    CLASES = ["a_pie", "quieto", "vehiculo"]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metodo, titulo in [
        (axes[0], "umbral", "Umbral"),
        (axes[1], "rf", "Random Forest v1"),
    ]:
        cm = np.array(metricas[metodo]["confusion_matrix_media"])
        im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
        ax.set_xticks(range(3))
        ax.set_yticks(range(3))
        ax.set_xticklabels(CLASES, fontsize=9)
        ax.set_yticklabels(CLASES, fontsize=9)
        ax.set_xlabel("Predicho")
        ax.set_ylabel("Real")
        f1 = metricas[metodo]["macro_f1"]
        f1_std = metricas[metodo]["macro_f1_std"]
        ax.set_title(f"{titulo}\nmacro-F1 = {f1:.4f} ± {f1_std:.4f}", fontsize=11)
        for i in range(3):
            for j in range(3):
                color = "white" if cm[i, j] > 0.5 else "black"
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center",
                        fontsize=11, color=color)
    fig.colorbar(im, ax=axes, shrink=0.8)
    fig.suptitle("Matrices de confusion normalizadas — GroupKFold(5)", fontsize=13)
    plt.tight_layout()

    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_out = DIR_EVIDENCIAS / "s2_matriz-confusion.png"
    plt.savefig(ruta_out, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_out}")
    return ruta_out


def generar_importancia():
    """Importancia por permutacion con barras de error."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ruta = DIR_REPORTES / "cv_rf_v1.json"
    with open(ruta) as f:
        datos = json.load(f)

    importancia = datos["importancia"]
    features = importancia["features"]
    imp_media = np.array(importancia["importancia_media"])
    imp_std = np.array(importancia["importancia_std_entre_folds"])

    orden = np.argsort(imp_media)[::-1]

    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = np.arange(len(features))
    ax.barh(y_pos, imp_media[orden], xerr=imp_std[orden],
            color="#2E9E4F", alpha=0.8, capsize=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([features[i] for i in orden], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Importancia por permutacion (macro-F1)")
    ax.set_title("Importancia de features — RF v1 (5 folds, 5 repeats)", fontsize=12)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()

    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_out = DIR_EVIDENCIAS / "s2_importancia.png"
    plt.savefig(ruta_out, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_out}")
    return ruta_out


def generar_suavizado():
    """Secuencia de ejemplo: modo_real, crudo y suavizado con transicion vehiculo->quieto->a_pie."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    np.random.seed(42)
    n = 60
    modo_map = {"vehiculo": 2, "quieto": 1, "a_pie": 0}
    CLASES = ["a_pie", "quieto", "vehiculo"]

    modos_real = (["vehiculo"] * 20 + ["quieto"] * 15 + ["a_pie"] * 25)

    probas = []
    for m in modos_real:
        p = np.array([0.05, 0.05, 0.05])
        idx = CLASES.index(m)
        p[idx] = 0.85
        ruido = np.random.dirichlet([5, 1, 1]) * 0.15
        p = p + ruido
        p = p / p.sum()
        probas.append(p)
    probas = np.array(probas)

    for spike_idx in [18, 22, 40, 45]:
        if spike_idx < n:
            probas[spike_idx] = np.array([0.4, 0.1, 0.5]) if modos_real[spike_idx] != "vehiculo" else np.array([0.5, 0.1, 0.4])

    crudo = [CLASES[np.argmax(p)] for p in probas]

    from ia.suavizado import Suavizador
    ruta_json = DIR_MODELOS / "rf_v1.json"
    metodo, k = "media_movil", 3
    if ruta_json.exists():
        with open(ruta_json) as f:
            info = json.load(f)
        if info.get("suavizado"):
            metodo = info["suavizado"].get("metodo", metodo)
            k = info["suavizado"].get("k", k)

    suav = Suavizador(metodo=metodo, k=k)
    suavizado = suav.suavizar_secuencia(probas)

    fig, axes = plt.subplots(3, 1, figsize=(12, 6), sharex=True)
    t = np.arange(n) * 5

    for ax, modos, titulo, color in [
        (axes[0], modos_real, "Modo real", "#333333"),
        (axes[1], crudo, "Prediccion cruda (argmax)", "#E53935"),
        (axes[2], suavizado, f"Suavizado ({metodo}, k={k})", "#2E9E4F"),
    ]:
        valores = [modo_map[m] for m in modos]
        ax.step(t, valores, where="mid", color=color, linewidth=2)
        ax.set_yticks([0, 1, 2])
        ax.set_yticklabels(["a_pie", "quieto", "vehiculo"], fontsize=9)
        ax.set_title(titulo, fontsize=10, loc="left")
        ax.grid(axis="x", alpha=0.2)
        ax.set_ylim(-0.3, 2.3)

    axes[-1].set_xlabel("Tiempo (s)")
    fig.suptitle("Ejemplo de suavizado temporal — transicion vehiculo → quieto → a_pie",
                 fontsize=12)
    plt.tight_layout()

    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    ruta_out = DIR_EVIDENCIAS / "s2_suavizado.png"
    plt.savefig(ruta_out, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta_out}")
    return ruta_out


if __name__ == "__main__":
    print("Generando evidencias S2-sesion 2...")
    generar_matriz_confusion()
    generar_importancia()
    generar_suavizado()
    print("Listo.")
