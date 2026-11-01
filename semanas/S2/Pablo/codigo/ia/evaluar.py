"""
Evaluación del clasificador: métricas por fold y agregadas.

Genera las evidencias PNG comparando umbral vs RF.
"""
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

CLASES = ["a_pie", "quieto", "vehiculo"]
DIR_EVIDENCIAS = Path(__file__).resolve().parent.parent.parent / "evidencias"


def metricas_fold(y_true, y_pred, fold: int, metodo: str) -> dict:
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, labels=CLASES, average="macro", zero_division=0)
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASES, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=CLASES, normalize="true")

    n_veh_real = np.sum(np.array(y_true) == "vehiculo")
    n_apie_real = np.sum(np.array(y_true) == "a_pie")
    y_true_arr = np.array(y_true)
    y_pred_arr = np.array(y_pred) if isinstance(y_pred, list) else y_pred

    tasa_veh_como_apie = (
        np.sum((y_true_arr == "vehiculo") & (y_pred_arr == "a_pie")) / n_veh_real
        if n_veh_real > 0 else 0.0
    )
    tasa_apie_como_veh = (
        np.sum((y_true_arr == "a_pie") & (y_pred_arr == "vehiculo")) / n_apie_real
        if n_apie_real > 0 else 0.0
    )

    return {
        "fold": fold,
        "metodo": metodo,
        "accuracy": float(acc),
        "macro_f1": float(macro_f1),
        "por_clase": {
            c: {"precision": float(precision[i]), "recall": float(recall[i]),
                "f1": float(f1[i]), "support": int(support[i])}
            for i, c in enumerate(CLASES)
        },
        "confusion_matrix": cm.tolist(),
        "tasa_veh_como_apie": float(tasa_veh_como_apie),
        "tasa_apie_como_veh": float(tasa_apie_como_veh),
    }


def agregar_folds(folds_rf: list[dict], folds_umbral: list[dict]) -> dict:
    def _agg(folds):
        macro_f1s = [f["macro_f1"] for f in folds]
        accs = [f["accuracy"] for f in folds]

        por_clase = {}
        for c in CLASES:
            f1s = [f["por_clase"][c]["f1"] for f in folds]
            recalls = [f["por_clase"][c]["recall"] for f in folds]
            por_clase[c] = {
                "f1_media": float(np.mean(f1s)),
                "f1_std": float(np.std(f1s)),
                "recall_media": float(np.mean(recalls)),
                "recall_std": float(np.std(recalls)),
            }

        cms = np.array([f["confusion_matrix"] for f in folds])
        cm_media = cms.mean(axis=0)

        tasas_veh_apie = [f["tasa_veh_como_apie"] for f in folds]
        tasas_apie_veh = [f["tasa_apie_como_veh"] for f in folds]

        return {
            "macro_f1": float(np.mean(macro_f1s)),
            "macro_f1_std": float(np.std(macro_f1s)),
            "accuracy": float(np.mean(accs)),
            "accuracy_std": float(np.std(accs)),
            "por_clase": por_clase,
            "confusion_matrix_media": cm_media.tolist(),
            "tasa_veh_como_apie": float(np.mean(tasas_veh_apie)),
            "tasa_apie_como_veh": float(np.mean(tasas_apie_veh)),
            "folds": folds,
        }

    return {"rf": _agg(folds_rf), "umbral": _agg(folds_umbral)}


def generar_evidencias(metricas: dict):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    DIR_EVIDENCIAS.mkdir(parents=True, exist_ok=True)

    # 1. Matrices de confusión lado a lado
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, metodo, titulo in [
        (axes[0], "umbral", "Umbral"),
        (axes[1], "rf", "Random Forest"),
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
        ax.set_title(f"{titulo}\nmacro-F1 = {f1:.4f}", fontsize=11)
        for i in range(3):
            for j in range(3):
                color = "white" if cm[i, j] > 0.5 else "black"
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center",
                        fontsize=11, color=color)
    fig.colorbar(im, ax=axes, shrink=0.8)
    fig.suptitle("Matrices de confusión normalizadas — GroupKFold(5)", fontsize=13)
    plt.tight_layout()
    ruta1 = DIR_EVIDENCIAS / "s3_matrices-umbral-vs-rf.png"
    plt.savefig(ruta1, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta1}")

    # 2. F1 por clase con barras de error
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(CLASES))
    ancho = 0.35

    for i, (metodo, label, color) in enumerate([
        ("umbral", "Umbral", "#FF7043"),
        ("rf", "Random Forest", "#2E9E4F"),
    ]):
        f1s = [metricas[metodo]["por_clase"][c]["f1_media"] for c in CLASES]
        stds = [metricas[metodo]["por_clase"][c]["f1_std"] for c in CLASES]
        ax.bar(x + i * ancho, f1s, ancho, yerr=stds, label=label,
               color=color, alpha=0.8, capsize=4)

    ax.set_xticks(x + ancho / 2)
    ax.set_xticklabels(CLASES)
    ax.set_ylabel("F1-score")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    rf_f1 = metricas["rf"]["macro_f1"]
    umb_f1 = metricas["umbral"]["macro_f1"]
    ax.set_title(f"F1 por clase — RF ({rf_f1:.4f}) vs Umbral ({umb_f1:.4f})", fontsize=12)

    plt.tight_layout()
    ruta2 = DIR_EVIDENCIAS / "s3_f1-por-clase.png"
    plt.savefig(ruta2, dpi=150)
    plt.close()
    print(f"Evidencia: {ruta2}")

    return ruta1, ruta2
