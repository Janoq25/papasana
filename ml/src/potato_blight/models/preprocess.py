"""Preprocesamiento de evaluación/inferencia, idéntico en `ml/` y en `ml-service` (solo PIL, numpy y torch).

Lado corto a `img_size / crop_pct` → recorte central `img_size` → [0, 1] → normalización con la media y la
desviación de ImageNet. El aumento de datos se aplica solo en el entrenamiento (potato_blight.data.transforms).
"""

import numpy as np
import torch
from PIL import Image

CROP_PCT = 0.875


def resize_center_crop(img: Image.Image, img_size: int, crop_pct: float = CROP_PCT) -> Image.Image:
    img = img.convert("RGB")
    short = round(img_size / crop_pct)
    w, h = img.size
    scale = short / min(w, h)
    img = img.resize((max(img_size, round(w * scale)), max(img_size, round(h * scale))), Image.Resampling.BILINEAR)
    w, h = img.size
    left, top = (w - img_size) // 2, (h - img_size) // 2
    return img.crop((left, top, left + img_size, top + img_size))


def to_tensor(img: Image.Image, mean, std) -> torch.Tensor:
    x = torch.from_numpy(np.asarray(img, dtype=np.float32) / 255.0).permute(2, 0, 1)
    m = torch.tensor(mean, dtype=torch.float32).view(3, 1, 1)
    s = torch.tensor(std, dtype=torch.float32).view(3, 1, 1)
    return (x - m) / s


def preprocess(img: Image.Image, config: dict) -> torch.Tensor:
    """Tensor (1, 3, S, S) listo para el modelo descrito en `model_config.json`."""
    size = int(config["img_size"])
    return to_tensor(resize_center_crop(img, size), config["mean"], config["std"]).unsqueeze(0)
