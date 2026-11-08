"""
Random Forest compilado a arrays planos de numpy.

Recorre los T árboles a la vez (un paso por nivel de profundidad) con indexación
vectorizada. Da las mismas probabilidades que sklearn pero sin su sobrecarga por
árbol: ~0.3 ms por ventana en vez de ~20 ms con 200 árboles.
"""
from __future__ import annotations

import numpy as np


class BosquePlano:
    def __init__(self, pipeline):
        pasos = dict(pipeline.steps) if hasattr(pipeline, "steps") else {}
        rf = pasos.get("rf", pipeline)
        imputer = pasos.get("imputer")
        self.classes_ = np.asarray(rf.classes_)
        self._medianas = None
        if imputer is not None:
            self._medianas = np.asarray(imputer.statistics_, dtype=np.float64)

        arboles = [e.tree_ for e in rf.estimators_]
        self.n_arboles = len(arboles)
        tam = np.array([t.node_count for t in arboles], dtype=np.int64)
        base = np.concatenate([[0], np.cumsum(tam)[:-1]])
        total = int(tam.sum())
        k = len(self.classes_)

        self._izq = np.empty(total, dtype=np.int32)
        self._der = np.empty(total, dtype=np.int32)
        self._feat = np.empty(total, dtype=np.int32)
        self._umbral = np.empty(total, dtype=np.float64)
        self._valor = np.empty((total, k), dtype=np.float32)

        for t, b, n in zip(arboles, base, tam):
            sl = slice(int(b), int(b + n))
            idx = np.arange(b, b + n, dtype=np.int32)
            hoja = t.children_left == -1
            self._izq[sl] = np.where(hoja, idx, t.children_left + b)
            self._der[sl] = np.where(hoja, idx, t.children_right + b)
            self._feat[sl] = np.where(hoja, 0, t.feature)
            self._umbral[sl] = np.where(hoja, np.inf, t.threshold)
            v = t.value[:, 0, :]
            self._valor[sl] = v / v.sum(axis=1, keepdims=True)

        self._raices = base.astype(np.int32)
        self._prof = int(max(t.max_depth for t in arboles))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float64)
        if self._medianas is not None:
            X = np.where(np.isnan(X), self._medianas, X)
        X = X.astype(np.float32)
        n = X.shape[0]
        nodo = np.broadcast_to(self._raices, (n, self.n_arboles)).copy()
        filas = np.arange(n)[:, None]
        for _ in range(self._prof):
            xv = X[filas, self._feat[nodo]]
            nodo = np.where(xv <= self._umbral[nodo], self._izq[nodo], self._der[nodo])
        return self._valor[nodo].mean(axis=1, dtype=np.float64)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(X), axis=1)]
