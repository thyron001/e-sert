"""
Suavizado temporal de predicciones para reducir cambios espurios de modo.

Metodos:
  - mayoria: voto de mayoria de los ultimos k modos (empate: gana el mas reciente).
  - prob_media (= media_movil): promedio de las ultimas k probabilidades y argmax.
  - histeresis: cambia de modo solo si el nuevo supera umbral_cambio
    durante k ventanas seguidas.

    from ia.suavizado import Suavizador, elegir_suavizado

La latencia anadida es k * 5 s (k ventanas de 5 s cada una).
"""
import numpy as np


CLASES = ["a_pie", "quieto", "vehiculo"]
METODOS = ("mayoria", "prob_media", "media_movil", "histeresis", "ninguno")


class Suavizador:
    """Suaviza una secuencia de probabilidades por ventana de un usuario."""

    def __init__(self, k: int = 3, metodo: str = "prob_media",
                 umbral_cambio: float = 0.6):
        if metodo not in METODOS:
            raise ValueError(f"Metodo no soportado: {metodo}")
        if k < 1:
            raise ValueError("k debe ser >= 1")
        self.metodo = metodo
        self.k = k
        self._historial_modos: list[str] = []
        self.umbral_cambio = umbral_cambio
        self._historial_probas: list[np.ndarray] = []
        self._modo_actual: str | None = None
        self._contador_cambio: int = 0
        self._modo_candidato: str | None = None

    def reset(self):
        self._historial_probas.clear()
        self._historial_modos.clear()
        self._modo_actual = None
        self._contador_cambio = 0
        self._modo_candidato = None

    def paso(self, probas: np.ndarray) -> str:
        """Procesa una ventana y devuelve el modo suavizado."""
        if self.metodo == "ninguno":
            return CLASES[int(np.argmax(probas))]
        elif self.metodo == "mayoria":
            return self._paso_mayoria(probas)
        elif self.metodo in ("media_movil", "prob_media"):
            return self._paso_media_movil(probas)
        else:
            return self._paso_histeresis(probas)

    def _paso_mayoria(self, probas: np.ndarray) -> str:
        self._historial_modos.append(CLASES[int(np.argmax(probas))])
        if len(self._historial_modos) > self.k:
            self._historial_modos.pop(0)
        votos = {c: self._historial_modos.count(c) for c in CLASES}
        mejor = max(votos.values())
        for modo in reversed(self._historial_modos):  # empate: gana el mas reciente
            if votos[modo] == mejor:
                return modo

    def actualizar(self, resultado: dict, probas: np.ndarray | None = None) -> dict:
        """
        Suaviza un `ResultadoModo` (contrato §2) y devuelve otro `ResultadoModo`.

        `probas` sigue el orden CLASES; si falta (fuente "umbral"), se usa un vector one-hot
        del modo. La confianza es la probabilidad media (o fraccion de votos) del modo elegido.
        """
        if probas is None:
            probas = np.zeros(len(CLASES))
            probas[CLASES.index(resultado["modo"])] = 1.0
        modo = self.paso(np.asarray(probas, dtype=float))
        if self.metodo == "mayoria":
            conf = self._historial_modos.count(modo) / len(self._historial_modos)
        elif self.metodo in ("media_movil", "prob_media") and self._historial_probas:
            conf = float(np.mean(self._historial_probas, axis=0)[CLASES.index(modo)])
        else:
            conf = float(resultado["confianza"])
        return {"modo": modo, "confianza": min(max(conf, 0.0), 1.0), "fuente": resultado["fuente"]}

    def _paso_media_movil(self, probas: np.ndarray) -> str:
        self._historial_probas.append(probas.copy())
        if len(self._historial_probas) > self.k:
            self._historial_probas.pop(0)
        media = np.mean(self._historial_probas, axis=0)
        return CLASES[int(np.argmax(media))]

    def _paso_histeresis(self, probas: np.ndarray) -> str:
        modo_crudo = CLASES[int(np.argmax(probas))]

        if self._modo_actual is None:
            self._modo_actual = modo_crudo
            return self._modo_actual

        if modo_crudo != self._modo_actual:
            if modo_crudo == self._modo_candidato:
                self._contador_cambio += 1
            else:
                self._modo_candidato = modo_crudo
                self._contador_cambio = 1

            max_proba = float(np.max(probas))
            if (self._contador_cambio >= self.k and
                    max_proba >= self.umbral_cambio):
                self._modo_actual = modo_crudo
                self._contador_cambio = 0
                self._modo_candidato = None
        else:
            self._contador_cambio = 0
            self._modo_candidato = None

        return self._modo_actual

    def suavizar_secuencia(self, secuencia_probas: np.ndarray) -> list[str]:
        """Suaviza una secuencia completa de probabilidades (n_ventanas, n_clases)."""
        self.reset()
        return [self.paso(p) for p in secuencia_probas]


def cambios_espurios_por_hora(modos_pred: list[str], modos_real: list[str],
                               dt_ventana_s: float = 5.0) -> float:
    """
    Cuenta cambios de modo en la prediccion que no existen en modo_real.

    Un cambio espurio es un cambio en modos_pred[i-1] -> modos_pred[i]
    que no corresponde a un cambio en modos_real[i-1] -> modos_real[i].
    """
    if len(modos_pred) < 2:
        return 0.0

    n_espurios = 0
    for i in range(1, len(modos_pred)):
        cambio_pred = modos_pred[i] != modos_pred[i - 1]
        cambio_real = modos_real[i] != modos_real[i - 1]
        if cambio_pred and not cambio_real:
            n_espurios += 1

    duracion_h = len(modos_pred) * dt_ventana_s / 3600.0
    if duracion_h < 1e-6:
        return 0.0
    return n_espurios / duracion_h


def evaluar_suavizado(secuencia_probas: np.ndarray, modos_real: list[str],
                       metodo: str, k: int, **kwargs) -> dict:
    """Evalua un metodo de suavizado sobre una secuencia."""
    from sklearn.metrics import f1_score

    suav = Suavizador(metodo=metodo, k=k, **kwargs)
    modos_suav = suav.suavizar_secuencia(secuencia_probas)

    modos_crudo = [CLASES[int(np.argmax(p))] for p in secuencia_probas]

    f1_suav = f1_score(modos_real, modos_suav, labels=CLASES, average="macro", zero_division=0)
    f1_crudo = f1_score(modos_real, modos_crudo, labels=CLASES, average="macro", zero_division=0)

    espurios_suav = cambios_espurios_por_hora(modos_suav, modos_real)
    espurios_crudo = cambios_espurios_por_hora(modos_crudo, modos_real)

    reduccion = 0.0
    if espurios_crudo > 0:
        reduccion = 1.0 - espurios_suav / espurios_crudo

    return {
        "metodo": metodo,
        "k": k,
        "f1_suavizado": float(f1_suav),
        "f1_crudo": float(f1_crudo),
        "delta_f1": float(f1_suav - f1_crudo),
        "espurios_h_suav": float(espurios_suav),
        "espurios_h_crudo": float(espurios_crudo),
        "reduccion_espurios": float(reduccion),
        "latencia_s": k * 5.0,
    }


def elegir_suavizado(df_train, pipe, verbose: bool = True) -> dict:
    """
    Evalua combinaciones metodo x k con validacion agrupada.
    Elige la que reduce >=30% cambios espurios sin bajar macro-F1 mas de 0.02.
    """
    from sklearn.metrics import f1_score
    from sklearn.model_selection import GroupKFold

    from ia.caracteristicas import NOMBRES_FEATURES as NF

    X = df_train[NF].to_numpy()
    y = np.array(df_train["modo_real"].tolist())
    grupos = np.array(df_train["grupo"].tolist())

    configuraciones = []
    for metodo in ["media_movil", "histeresis"]:
        for k in [1, 2, 3, 5]:
            configuraciones.append({"metodo": metodo, "k": k})

    gkf = GroupKFold(n_splits=3)
    resultados = []

    for config in configuraciones:
        f1s, reducciones, deltas = [], [], []

        for fold, (idx_train, idx_val) in enumerate(gkf.split(X, y, grupos)):
            X_tr, X_va = X[idx_train], X[idx_val]
            y_tr, y_va = y[idx_train], y[idx_val]
            g_va = grupos[idx_val]

            from sklearn.base import clone
            pipe_fold = clone(pipe)
            pipe_fold.fit(X_tr, y_tr)
            probas_va = pipe_fold.predict_proba(X_va)

            usuarios_val = g_va
            usuario_ids_unicos = np.unique(usuarios_val)

            fold_espurios_suav = []
            fold_espurios_crudo = []
            fold_modos_suav = []
            fold_modos_crudo = []
            fold_modos_real = []

            for uid in usuario_ids_unicos:
                mask = usuarios_val == uid
                probas_u = probas_va[mask]
                modos_real_u = list(y_va[mask])

                if len(probas_u) < 3:
                    continue

                res = evaluar_suavizado(probas_u, modos_real_u,
                                         config["metodo"], config["k"])
                fold_espurios_suav.append(res["espurios_h_suav"])
                fold_espurios_crudo.append(res["espurios_h_crudo"])
                fold_modos_suav.extend(
                    Suavizador(k=config["k"], metodo=config["metodo"]).suavizar_secuencia(probas_u))
                fold_modos_crudo.extend(
                    [CLASES[int(np.argmax(p))] for p in probas_u])
                fold_modos_real.extend(modos_real_u)

            if fold_modos_suav:
                f1_suav = f1_score(fold_modos_real, fold_modos_suav,
                                    labels=CLASES, average="macro", zero_division=0)
                f1_crudo = f1_score(fold_modos_real, fold_modos_crudo,
                                     labels=CLASES, average="macro", zero_division=0)
                esp_suav = np.mean(fold_espurios_suav) if fold_espurios_suav else 0
                esp_crudo = np.mean(fold_espurios_crudo) if fold_espurios_crudo else 0
                red = 1.0 - esp_suav / esp_crudo if esp_crudo > 0 else 0.0

                f1s.append(f1_suav)
                reducciones.append(red)
                deltas.append(f1_suav - f1_crudo)

        if f1s:
            resultado = {
                **config,
                "f1_media": float(np.mean(f1s)),
                "f1_std": float(np.std(f1s)),
                "reduccion_media": float(np.mean(reducciones)),
                "reduccion_std": float(np.std(reducciones)),
                "delta_f1_media": float(np.mean(deltas)),
                "delta_f1_std": float(np.std(deltas)),
            }
            resultados.append(resultado)
            if verbose:
                print(f"  {config['metodo']} k={config['k']}: "
                      f"F1={resultado['f1_media']:.4f}+/-{resultado['f1_std']:.4f}, "
                      f"reduccion={resultado['reduccion_media']:.1%}, "
                      f"delta_F1={resultado['delta_f1_media']:+.4f}", flush=True)

    candidatos = [r for r in resultados
                  if r["reduccion_media"] >= 0.30 and r["delta_f1_media"] >= -0.02]

    if candidatos:
        mejor = max(candidatos, key=lambda r: r["reduccion_media"])
    else:
        mejor = max(resultados, key=lambda r: r["reduccion_media"])
        if verbose:
            print("  AVISO: ningun candidato cumple reduccion>=30% sin perder >0.02 F1. "
                  "Se elige el de mayor reduccion.", flush=True)

    if verbose:
        print(f"\n  Elegido: {mejor['metodo']} k={mejor['k']} "
              f"(reduccion {mejor['reduccion_media']:.1%}, delta_F1 {mejor['delta_f1_media']:+.4f})",
              flush=True)

    return {
        "elegido": {"metodo": mejor["metodo"], "k": mejor["k"]},
        "todos": resultados,
    }
