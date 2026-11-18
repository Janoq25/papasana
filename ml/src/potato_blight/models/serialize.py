"""Formato del modelo entregado a ml-service: una carpeta con `model.pt` (state_dict) y `model_config.json`.

Se registra en MLflow como artefactos simples del run (`model/`), no con `mlflow.pytorch.log_model`, para que
ml-service no necesite instalar MLflow ni pickles: solo torch, timm y este paquete de arquitecturas.
"""

import json
from pathlib import Path

import torch
from torch import nn

from potato_blight.models.architectures import IMAGENET_MEAN, IMAGENET_STD, SPECS, build_model

CONFIG_FILE = "model_config.json"
WEIGHTS_FILE = "model.pt"
FORMAT_VERSION = 1
REQUIRED = ("architecture", "classes", "img_size")


def make_config(arch: str, classes: list[str], *, img_size: int | None = None, hparams: dict | None = None,
                temperature: float = 1.0, label_scheme: str = "sintoma", smoke_test: bool = False,
                extra: dict | None = None) -> dict:
    return {
        "format_version": FORMAT_VERSION,
        "architecture": arch,
        "classes": list(classes),
        "img_size": int(img_size or SPECS[arch].default_img_size),
        "mean": list(IMAGENET_MEAN),
        "std": list(IMAGENET_STD),
        "hparams": dict(hparams or {}),
        "temperature": float(temperature),
        "label_scheme": label_scheme,
        "smoke_test": bool(smoke_test),
        **(extra or {}),
    }


def save_model_dir(model: nn.Module, config: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / WEIGHTS_FILE)
    (out / CONFIG_FILE).write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def read_config(model_dir: str | Path) -> dict:
    cfg = json.loads((Path(model_dir) / CONFIG_FILE).read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise ValueError(f"model_config.json incompleto: faltan {missing}")
    if cfg.get("format_version", 1) > FORMAT_VERSION:
        raise ValueError("model_config.json fue generado por una versión más nueva de potato_blight")
    return cfg


def load_model_dir(model_dir: str | Path, device: str = "cpu") -> tuple[nn.Module, dict]:
    """Reconstruye la red sin pesos preentrenados y carga el state_dict (weights_only: sin pickles arbitrarios)."""
    cfg = read_config(model_dir)
    model = build_model(cfg["architecture"], len(cfg["classes"]), img_size=cfg["img_size"], pretrained=False,
                        **cfg.get("hparams", {}))
    state = torch.load(Path(model_dir) / WEIGHTS_FILE, map_location=device, weights_only=True)
    model.load_state_dict(state)
    return model.eval(), cfg
