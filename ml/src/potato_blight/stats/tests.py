"""Pruebas estadísticas para comparar los cinco modelos (docs/fase0_plan.md §6.3).

- Friedman sobre las métricas POR PARTICIÓN (bloques = particiones y escenarios externos), nunca sobre valores
  agregados de una sola partición.
- Wilcoxon pareado entre modelos con corrección de Holm.
- McNemar sobre las mismas imágenes de prueba (exacta si hay pocos desacuerdos).
- Intervalos de confianza por bootstrap (percentil).
- DeLong para comparar AUC correlacionadas (uno contra el resto), con la implementación rápida de Sun y Xu (2014).
"""

from collections.abc import Callable
from itertools import combinations

import numpy as np
from scipy import stats


def friedman(scores: dict[str, list[float]]) -> dict:
    """`scores[modelo]` = métrica en cada bloque (mismo orden de bloques para todos)."""
    names = list(scores)
    if len(names) < 3:
        return {"aplicable": False, "motivo": "Friedman requiere al menos 3 modelos."}
    lengths = {len(v) for v in scores.values()}
    if len(lengths) != 1 or lengths.pop() < 2:
        return {"aplicable": False, "motivo": "Todos los modelos necesitan los mismos bloques (≥ 2)."}
    mat = np.array([scores[n] for n in names], dtype=float)
    stat, p = stats.friedmanchisquare(*mat)
    ranks = stats.rankdata(-mat, axis=0).mean(axis=1)  # rango 1 = mejor
    return {"aplicable": True, "estadistico": float(stat), "p_valor": float(p), "bloques": int(mat.shape[1]),
            "rango_medio": {n: float(r) for n, r in zip(names, ranks, strict=True)}}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """p-valores ajustados por Holm-Bonferroni (monótonos, acotados en 1)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    adjusted, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[k] = running
    return adjusted


def wilcoxon_holm(scores: dict[str, list[float]]) -> list[dict]:
    raw, rows = {}, {}
    for a, b in combinations(scores, 2):
        x, y = np.asarray(scores[a], float), np.asarray(scores[b], float)
        key = f"{a} vs {b}"
        if np.allclose(x, y):
            p, stat = 1.0, 0.0
        else:
            res = stats.wilcoxon(x, y, zero_method="zsplit")
            p, stat = float(res.pvalue), float(res.statistic)
        raw[key] = p
        rows[key] = {"modelo_a": a, "modelo_b": b, "estadistico": stat, "p_valor": p,
                     "diferencia_media": float((x - y).mean())}
    adj = holm(raw)
    for key, r in rows.items():
        r["p_holm"] = adj[key]
    return list(rows.values())


def mcnemar(y_true, pred_a, pred_b) -> dict:
    y_true, pred_a, pred_b = map(np.asarray, (y_true, pred_a, pred_b))
    a_ok, b_ok = pred_a == y_true, pred_b == y_true
    n01 = int((a_ok & ~b_ok).sum())  # acierta A, falla B
    n10 = int((~a_ok & b_ok).sum())
    n = n01 + n10
    if n == 0:
        return {"n01": n01, "n10": n10, "p_valor": 1.0, "metodo": "sin desacuerdos"}
    if n < 25:
        p = float(stats.binomtest(n01, n, 0.5).pvalue)
        return {"n01": n01, "n10": n10, "p_valor": p, "metodo": "exacta (binomial)"}
    chi2 = (abs(n01 - n10) - 1) ** 2 / n
    return {"n01": n01, "n10": n10, "estadistico": float(chi2), "p_valor": float(stats.chi2.sf(chi2, 1)),
            "metodo": "chi cuadrado con corrección de continuidad"}


def bootstrap_ci(metric: Callable[[np.ndarray, np.ndarray], float], y_true, probs, *, n_boot: int = 1000,
                 alpha: float = 0.05, seed: int = 2026) -> dict:
    y_true, probs = np.asarray(y_true), np.asarray(probs)
    rng = np.random.default_rng(seed)
    n = len(y_true)
    values = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        try:
            v = metric(y_true[idx], probs[idx])
        except ValueError:
            continue
        if v is not None and np.isfinite(v):
            values.append(v)
    point = metric(y_true, probs)
    if not values:
        return {"valor": point, "ic_inferior": None, "ic_superior": None, "n_boot": 0}
    lo, hi = np.quantile(values, [alpha / 2, 1 - alpha / 2])
    return {"valor": float(point), "ic_inferior": float(lo), "ic_superior": float(hi), "n_boot": len(values)}


# --- DeLong ------------------------------------------------------------------------------------------

def _midrank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    xs = x[order]
    n = len(x)
    ranks = np.zeros(n)
    i = 0
    while i < n:
        j = i
        while j < n and xs[j] == xs[i]:
            j += 1
        ranks[i:j] = 0.5 * (i + j - 1) + 1
        i = j
    out = np.empty(n)
    out[order] = ranks
    return out


def _fast_delong(preds_sorted: np.ndarray, m: int) -> tuple[np.ndarray, np.ndarray]:
    """Sun & Xu (2014). `preds_sorted`: (k, n) con los m positivos primero."""
    n = preds_sorted.shape[1] - m
    pos, neg = preds_sorted[:, :m], preds_sorted[:, m:]
    k = preds_sorted.shape[0]
    tx, ty, tz = np.empty((k, m)), np.empty((k, n)), np.empty((k, m + n))
    for r in range(k):
        tx[r], ty[r], tz[r] = _midrank(pos[r]), _midrank(neg[r]), _midrank(preds_sorted[r])
    aucs = tz[:, :m].sum(axis=1) / m / n - (m + 1.0) / 2.0 / n
    v01 = (tz[:, :m] - tx) / n
    v10 = 1.0 - (tz[:, m:] - ty) / m
    cov = np.cov(v01) / m + np.cov(v10) / n
    return aucs, np.atleast_2d(cov)


def delong(y_binary, scores_a, scores_b) -> dict:
    """Compara dos AUC calculadas sobre los mismos casos (prueba bilateral)."""
    y = np.asarray(y_binary).astype(int)
    if y.min() == y.max():
        return {"aplicable": False, "motivo": "Se necesitan casos positivos y negativos."}
    order = np.argsort(-y, kind="mergesort")
    m = int(y.sum())
    preds = np.vstack([np.asarray(scores_a, float), np.asarray(scores_b, float)])[:, order]
    aucs, cov = _fast_delong(preds, m)
    var = cov[0, 0] + cov[1, 1] - 2 * cov[0, 1]
    diff = float(aucs[0] - aucs[1])
    if var <= 0:
        return {"aplicable": True, "auc_a": float(aucs[0]), "auc_b": float(aucs[1]), "z": 0.0,
                "p_valor": 1.0 if diff == 0 else 0.0}
    z = diff / np.sqrt(var)
    return {"aplicable": True, "auc_a": float(aucs[0]), "auc_b": float(aucs[1]), "z": float(z),
            "p_valor": float(2 * stats.norm.sf(abs(z)))}
