"""Métricas de clasificación (docs/fase0_plan.md §6.3), por clase y macro, con curvas ROC y PR.

Accuracy, sensibilidad (recall), especificidad, precisión, F1, MCC, AUC-ROC y AUC-PR (uno contra el resto) y
matriz de confusión. Si una clase no aparece en `y_true`, sus AUC quedan en None (no se inventan).
"""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    matthews_corrcoef,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

MAX_CURVE_POINTS = 101


def _downsample(x: np.ndarray, y: np.ndarray, n: int = MAX_CURVE_POINTS) -> tuple[list[float], list[float]]:
    if len(x) <= n:
        return [float(v) for v in x], [float(v) for v in y]
    idx = np.unique(np.linspace(0, len(x) - 1, n).round().astype(int))
    return [float(v) for v in x[idx]], [float(v) for v in y[idx]]


def _safe_div(a: float, b: float) -> float | None:
    return float(a / b) if b else None


def compute_metrics(y_true, probs, classes: list[str], *, curves: bool = True) -> dict:
    y_true = np.asarray(y_true, dtype=int)
    probs = np.asarray(probs, dtype=float)
    k = len(classes)
    y_pred = probs.argmax(axis=1)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(k)))
    total = cm.sum()
    per_class, roc, pr = {}, {}, {}
    for i, c in enumerate(classes):
        tp = cm[i, i]
        fn = cm[i].sum() - tp
        fp = cm[:, i].sum() - tp
        tn = total - tp - fn - fp
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        # Una clase presente pero nunca predicha tiene F1=0; excluirla inflaría la macro.
        f1 = _safe_div(2 * tp, 2 * tp + fp + fn)
        binary = (y_true == i).astype(int)
        has_both = 0 < binary.sum() < len(binary)
        auc_roc = float(roc_auc_score(binary, probs[:, i])) if has_both else None
        auc_pr = float(average_precision_score(binary, probs[:, i])) if has_both else None
        per_class[c] = {"support": int(cm[i].sum()), "precision": precision, "sensitivity": recall,
                        "specificity": _safe_div(tn, tn + fp), "f1": f1, "auc_roc": auc_roc, "auc_pr": auc_pr}
        if curves and has_both:
            fpr, tpr, _ = roc_curve(binary, probs[:, i])
            prec, rec, _ = precision_recall_curve(binary, probs[:, i])
            roc[c] = dict(zip(("fpr", "tpr"), _downsample(fpr, tpr), strict=True))
            pr[c] = dict(zip(("recall", "precision"), _downsample(rec[::-1], prec[::-1]), strict=True))

    def macro(key):
        vals = [m[key] for m in per_class.values() if m[key] is not None and m["support"] > 0]
        return float(np.mean(vals)) if vals else None

    out = {
        "n": int(total),
        "accuracy": _safe_div(np.trace(cm), total),
        "macro_precision": macro("precision"),
        "macro_sensitivity": macro("sensitivity"),
        "macro_specificity": macro("specificity"),
        "macro_f1": macro("f1"),
        "mcc": float(matthews_corrcoef(y_true, y_pred)) if total else None,
        "macro_auc_roc": macro("auc_roc"),
        "macro_auc_pr": macro("auc_pr"),
        "per_class": per_class,
        "confusion_matrix": cm.tolist(),
        "classes": list(classes),
    }
    if curves:
        out["roc_curves"] = roc
        out["pr_curves"] = pr
    return out


SCALAR_KEYS = ("accuracy", "macro_precision", "macro_sensitivity", "macro_specificity", "macro_f1", "mcc",
               "macro_auc_roc", "macro_auc_pr")


def scalar_metrics(m: dict, prefix: str) -> dict[str, float]:
    """Métricas escalares para MLflow (`<prefijo>_<métrica>`), sin los valores indefinidos."""
    out = {f"{prefix}_{k}": float(m[k]) for k in SCALAR_KEYS if m.get(k) is not None}
    for c, pc in m["per_class"].items():
        for key in ("sensitivity", "specificity", "f1"):
            if pc[key] is not None:
                out[f"{prefix}_{key}_{c}"] = float(pc[key])
    return out
