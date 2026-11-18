"""Grad-CAM genérico para las cinco arquitecturas (capa objetivo: `gradcam_target`)."""

import numpy as np
import torch
from torch import nn

from potato_blight.models.architectures import gradcam_target


class GradCAM:
    """Registra hooks en la capa objetivo; `__call__` devuelve (probabilidades calibradas, mapa [0, 1])."""

    def __init__(self, model: nn.Module, arch: str):
        self.model = model
        self._acts: torch.Tensor | None = None
        self._grads: torch.Tensor | None = None
        self._handle = gradcam_target(model, arch).register_forward_hook(self._save)

    def _save(self, _module, _inp, out):
        if isinstance(out, (tuple, list)):
            out = out[0]
        self._acts = out
        if out.requires_grad:
            out.register_hook(self._save_grad)

    def _save_grad(self, grad):
        self._grads = grad

    def remove(self) -> None:
        self._handle.remove()

    def __call__(self, x: torch.Tensor, temperature: float = 1.0, class_idx: int | None = None):
        self.model.zero_grad(set_to_none=True)
        # cuDNN no permite el backward de una LSTM en modo evaluación (H2): se desactiva solo aquí.
        with torch.enable_grad(), torch.backends.cudnn.flags(enabled=False):
            x = x.requires_grad_(False)
            logits = self.model(x)
            probs = torch.softmax(logits.detach() / temperature, dim=1)[0]
            idx = int(probs.argmax()) if class_idx is None else class_idx
            logits[0, idx].backward()
        if self._acts is None or self._grads is None:
            raise RuntimeError("Grad-CAM no capturó activaciones o gradientes de la capa objetivo.")
        acts, grads = self._acts.detach()[0], self._grads.detach()[0]
        if acts.dim() != 3:
            raise RuntimeError(f"La capa objetivo debe producir un mapa (C, H, W); produjo {tuple(acts.shape)}")
        weights = grads.mean(dim=(1, 2))
        cam = torch.relu((weights[:, None, None] * acts).sum(0)).cpu().numpy()
        cam = cam - cam.min()
        cam = cam / cam.max() if cam.max() > 0 else cam
        return probs.cpu(), cam.astype(np.float32)


def jet(v: np.ndarray) -> np.ndarray:
    """Mapa de color 'jet' (0 = azul, 1 = rojo) sin matplotlib."""
    r = np.clip(1.5 - np.abs(4 * v - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * v - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * v - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)
