"""Modelo en uso, preprocesamiento, calibración por temperatura y Grad-CAM.

Orden de carga (docs/decisiones.md D-51):
1. Si hay MLflow (`MLFLOW_TRACKING_URI`), la versión con alias `production` de algún modelo `papasana-*`.
   Arquitectura, clases, tamaño de entrada y temperatura salen de su `model_config.json`; la red se construye
   con el mismo paquete `potato_blight.models` que se usó para entrenarla.
2. Si no hay modelo en producción, MLflow no responde o el modelo no es válido: el modelo DEMO (D-16), un
   ResNet50 con pesos ImageNet y una cabeza de 3 clases SIN ENTRENAR. Sus predicciones no tienen valor diagnóstico.
Un modelo de prueba de humo (`smoke_test`) se sirve, pero marcado como DEMO / no validado.
"""

import base64
import io
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from potato_blight.models.architectures import SPECS, gradcam_target
from potato_blight.models.preprocess import preprocess
from potato_blight.models.serialize import load_model_dir
from torch import nn
from torchvision.models import ResNet50_Weights, resnet50

from app.registry import RegistryClient

log = logging.getLogger("ml-service")
CLASSES = ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"]
DEMO_KEY = "demo-resnet50-imagenet-v1"
DEMO_CONFIG = {"img_size": 224, "mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
OVERLAY_MAX_SIDE = 768
CACHE_DIR = Path(os.environ.get("MODEL_CACHE_DIR", "/tmp/papasana-modelos"))


@dataclass(frozen=True)
class ModelInfo:
    key: str
    architecture: str
    display_name: str
    is_demo: bool
    classes: list[str]
    temperature: float
    source: str = "demo"  # demo | mlflow
    mlflow: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"key": self.key, "architecture": self.architecture, "display_name": self.display_name,
                "is_demo": self.is_demo, "classes": self.classes, "temperature": self.temperature,
                "source": self.source, "mlflow": self.mlflow}


def build_demo_model(seed: int = 2026) -> nn.Module:
    model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)
    generator = torch.Generator().manual_seed(seed)
    head = nn.Linear(model.fc.in_features, len(CLASSES))
    with torch.no_grad():
        head.weight.copy_(torch.randn(head.weight.shape, generator=generator) * 0.02)
        head.bias.zero_()
    model.fc = head
    return model.eval()


def _jet(v: np.ndarray) -> np.ndarray:
    """Mapa de color 'jet' (0 = azul, 1 = rojo) sin depender de matplotlib."""
    r = np.clip(1.5 - np.abs(4 * v - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * v - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * v - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


class GradCAM:
    """Grad-CAM sobre la capa objetivo de cada arquitectura (última capa con mapa espacial)."""

    def __init__(self, model: nn.Module, layer: nn.Module):
        self.model = model
        self._acts: torch.Tensor | None = None
        self._grads: torch.Tensor | None = None
        layer.register_forward_hook(self._save_acts)

    def _save_acts(self, _module, _inp, out):
        if isinstance(out, (tuple, list)):
            out = out[0]
        self._acts = out
        if out.requires_grad:
            out.register_hook(self._save_grads)

    def _save_grads(self, grad):
        self._grads = grad

    def __call__(self, x: torch.Tensor, temperature: float) -> tuple[torch.Tensor, np.ndarray]:
        self.model.zero_grad(set_to_none=True)
        with torch.backends.cudnn.flags(enabled=False):  # backward de la LSTM (H2) en modo evaluación
            logits = self.model(x)
            probs = torch.softmax(logits.detach() / temperature, dim=1)[0]
            idx = int(probs.argmax())
            logits[0, idx].backward()
        if self._acts is None or self._grads is None:
            raise RuntimeError("Grad-CAM no capturó la capa objetivo")
        acts, grads = self._acts.detach()[0], self._grads.detach()[0]
        weights = grads.mean(dim=(1, 2))
        cam = torch.relu((weights[:, None, None] * acts).sum(0)).numpy()
        cam = cam - cam.min()
        cam = cam / cam.max() if cam.max() > 0 else cam
        return probs, cam


class Predictor:
    def __init__(self, model: nn.Module, info: ModelInfo, target: nn.Module, config: dict):
        self.model = model
        self.info = info
        self.config = config
        self.cam = GradCAM(model, target)
        self._lock = threading.Lock()  # los hooks guardan estado: una inferencia a la vez

    def predict(self, raw: bytes) -> dict:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        x = preprocess(img, self.config)
        t0 = time.perf_counter()
        with self._lock, torch.enable_grad():
            probs, cam = self.cam(x, self.info.temperature)
        elapsed = int((time.perf_counter() - t0) * 1000)
        probabilities = {c: round(float(p), 6) for c, p in zip(self.info.classes, probs, strict=True)}
        predicted = max(probabilities, key=probabilities.get)
        return {
            "model": self.info.as_dict(),
            "predicted_class": predicted,
            "confidence": probabilities[predicted],
            "probabilities": probabilities,
            "gradcam_png_b64": base64.b64encode(self._overlay(img, cam)).decode(),
            "inference_ms": elapsed,
        }

    @staticmethod
    def _overlay(img: Image.Image, cam: np.ndarray) -> bytes:
        base = img.copy()
        base.thumbnail((OVERLAY_MAX_SIDE, OVERLAY_MAX_SIDE))
        heat = Image.fromarray((cam * 255).astype(np.uint8)).resize(base.size, Image.Resampling.BILINEAR)
        colored = Image.fromarray(_jet(np.asarray(heat, dtype=np.float32) / 255.0))
        out = Image.blend(base, colored, alpha=0.45)
        buf = io.BytesIO()
        out.save(buf, format="PNG", optimize=True)
        return buf.getvalue()


def demo_predictor() -> Predictor:
    model = build_demo_model()
    info = ModelInfo(key=DEMO_KEY, architecture="resnet50",
                     display_name="DEMO / no validado · ResNet50 (ImageNet) con cabeza sin entrenar",
                     is_demo=True, classes=CLASSES, temperature=1.0)
    return Predictor(model, info, model.layer4, DEMO_CONFIG)


def predictor_from_dir(model_dir: Path, *, name: str, version: str, run_id: str) -> Predictor:
    model, cfg = load_model_dir(model_dir)
    if cfg["classes"] != CLASSES or cfg.get("label_scheme") != "sintoma":
        raise ValueError(f"Clases no compatibles con la aplicación (D-01): {cfg['classes']}")
    arch = cfg["architecture"]
    smoke = bool(cfg.get("smoke_test"))
    label = f"{SPECS[arch].display_name} · {name} v{version}"
    info = ModelInfo(key=f"{name}:v{version}", architecture=arch,
                     display_name=("SMOKE TEST / no validado · " + label) if smoke else label,
                     is_demo=smoke, classes=list(cfg["classes"]), temperature=float(cfg["temperature"]),
                     source="mlflow", mlflow={"name": name, "version": version, "run_id": run_id,
                                              "smoke_test": smoke})
    return Predictor(model, info, gradcam_target(model, arch), cfg)


@dataclass
class LoadResult:
    predictor: Predictor
    status: str          # produccion | demo_sin_produccion | demo_sin_mlflow | error_produccion
    detail: str | None = None


def load_predictor(tracking_uri: str | None = None, *, fallback_to_demo: bool = True) -> LoadResult:
    torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))
    uri = tracking_uri if tracking_uri is not None else os.environ.get("MLFLOW_TRACKING_URI", "")
    if not uri:
        return LoadResult(demo_predictor(), "demo_sin_mlflow", "MLFLOW_TRACKING_URI no está configurado")
    try:
        client = RegistryClient(uri)
        pm = client.production_model()
        if pm is None:
            return LoadResult(demo_predictor(), "demo_sin_produccion", "Ningún modelo tiene el alias production")
        dest = CACHE_DIR / pm.name / pm.version
        if not (dest / "model.pt").exists():
            client.download_model_dir(pm, dest)
        p = predictor_from_dir(dest, name=pm.name, version=pm.version, run_id=pm.run_id)
        log.info("Modelo en producción cargado: %s", p.info.key)
        return LoadResult(p, "produccion")
    except Exception as e:  # noqa: BLE001 - cualquier fallo deja el servicio con un modelo válido
        log.exception("No se pudo cargar el modelo de producción")
        if not fallback_to_demo:
            raise
        return LoadResult(demo_predictor(), "error_produccion", f"{type(e).__name__}: {e}"[:500])
