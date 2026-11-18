"""Calidad de las explicaciones (docs/fase0_plan.md §6.3).

- Estabilidad: correlación entre el mapa de la imagen original y los mapas bajo perturbaciones pequeñas que no
  deberían cambiar la decisión (ruido, brillo, desplazamiento de pocos píxeles).
- Relevancia: fracción de la "energía" del mapa que cae dentro de la lesión anotada (máscara binaria).
"""

import numpy as np
import torch
from PIL import Image

from potato_blight.explain.gradcam import GradCAM


def _resize(cam: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    img = Image.fromarray((cam * 255).astype(np.uint8)).resize(size, Image.Resampling.BILINEAR)
    return np.asarray(img, dtype=np.float32) / 255.0


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.ravel() - a.mean(), b.ravel() - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / den) if den > 0 else 0.0


def perturbations(x: torch.Tensor, seed: int = 2026) -> dict[str, torch.Tensor]:
    g = torch.Generator().manual_seed(seed)
    return {
        "ruido": x + 0.05 * torch.randn(x.shape, generator=g),
        "brillo": x * 1.1,
        "desplazamiento": torch.roll(x, shifts=(4, 4), dims=(2, 3)),
    }


def stability(cam_fn: GradCAM, x: torch.Tensor, temperature: float = 1.0) -> dict:
    """Correlación de Pearson entre mapas (para la clase predicha en la imagen original)."""
    probs, base = cam_fn(x, temperature)
    cls = int(probs.argmax())
    out = {}
    for name, xp in perturbations(x).items():
        p2, cam = cam_fn(xp, temperature, class_idx=cls)
        out[name] = {"correlacion": pearson(base, cam), "misma_clase": int(p2.argmax()) == cls}
    out["media"] = float(np.mean([v["correlacion"] for v in out.values()]))
    return out


def relevance(cam: np.ndarray, mask: np.ndarray) -> float:
    """Fracción del mapa (normalizado) dentro de la máscara de la lesión, redimensionado al tamaño de la máscara."""
    m = (np.asarray(mask) > 0).astype(np.float32)
    c = _resize(cam, (m.shape[1], m.shape[0]))
    total = c.sum()
    return float((c * m).sum() / total) if total > 0 else 0.0
