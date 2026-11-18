"""SHAP fuera de línea (D-13): costoso, se calcula en el laboratorio sobre una muestra, nunca en cada inferencia.

Requiere el extra opcional: `pip install -e ".[explain]"` (instala `shap`).
"""

import numpy as np
import torch
from torch import nn


def shap_values(model: nn.Module, background: torch.Tensor, samples: torch.Tensor, n_samples: int = 50):
    """Valores SHAP (GradientExplainer) por clase: lista de arreglos (N, C, H, W)."""
    try:
        import shap
    except ImportError as e:  # pragma: no cover - depende del extra opcional
        raise ImportError("Instale el extra opcional: pip install -e '.[explain]'") from e
    model.eval()
    explainer = shap.GradientExplainer(model, background)
    values = explainer.shap_values(samples, nsamples=n_samples)
    return [np.asarray(v) for v in values] if isinstance(values, list) else np.asarray(values)


def attention_map(model: nn.Module, x: torch.Tensor) -> np.ndarray | None:
    """Mapa de atención por parche del modelo H2 (EffNetAttBiLSTM), reorganizado a la grilla espacial."""
    grid = getattr(model, "grid", None)
    if grid is None:
        return None
    with torch.no_grad():
        model(x)
    alpha = model.last_attention[0].cpu().numpy()
    h, w = grid
    att = alpha.reshape(h, w)
    att = att - att.min()
    return att / att.max() if att.max() > 0 else att
