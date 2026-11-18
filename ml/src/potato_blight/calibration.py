"""Calibración por temperatura (Guo et al., 2017) ajustada en la validación interna, ECE y diagrama de fiabilidad."""

import numpy as np
import torch
from torch import nn


def fit_temperature(logits, labels, max_iter: int = 200) -> float:
    """Temperatura T > 0 que minimiza la log-verosimilitud negativa de softmax(logits / T)."""
    z = torch.as_tensor(np.asarray(logits), dtype=torch.float64)
    y = torch.as_tensor(np.asarray(labels), dtype=torch.long)
    log_t = torch.zeros(1, dtype=torch.float64, requires_grad=True)
    opt = torch.optim.LBFGS([log_t], lr=0.1, max_iter=max_iter, line_search_fn="strong_wolfe")
    loss_fn = nn.CrossEntropyLoss()

    def closure():
        opt.zero_grad()
        loss = loss_fn(z / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    t = float(log_t.exp().item())
    return float(min(max(t, 0.05), 20.0))


def softmax(logits, temperature: float = 1.0) -> np.ndarray:
    z = np.asarray(logits, dtype=float) / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def nll(probs, labels) -> float:
    p = np.asarray(probs)[np.arange(len(labels)), np.asarray(labels)]
    return float(-np.log(np.clip(p, 1e-12, 1.0)).mean())


def reliability(probs, labels, n_bins: int = 15) -> dict:
    """Bins de confianza (máxima probabilidad) con su exactitud y el ECE ponderado."""
    probs = np.asarray(probs)
    labels = np.asarray(labels)
    conf = probs.max(axis=1)
    correct = (probs.argmax(axis=1) == labels).astype(float)
    edges = np.linspace(0, 1, n_bins + 1)
    bins, ece = [], 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        mask = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        n = int(mask.sum())
        if n:
            acc, avg = float(correct[mask].mean()), float(conf[mask].mean())
            ece += n / len(labels) * abs(acc - avg)
        else:
            acc = avg = None
        bins.append({"lower": float(lo), "upper": float(hi), "count": n, "accuracy": acc, "confidence": avg})
    return {"ece": float(ece), "bins": bins}


def ece(probs, labels, n_bins: int = 15) -> float:
    return reliability(probs, labels, n_bins)["ece"]
