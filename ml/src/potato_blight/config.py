"""Configuración de experimentos (YAML en `ml/configs/`), validada con Pydantic."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from potato_blight.models.architectures import ARCHITECTURES


class TrainCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    epochs: int = Field(20, ge=1)
    batch_size: int = Field(32, ge=1)
    lr: float = Field(3e-4, gt=0)
    weight_decay: float = Field(1e-4, ge=0)
    label_smoothing: float = Field(0.0, ge=0, lt=1)
    patience: int = Field(5, ge=1)
    amp: bool = True
    amp_dtype: Literal["float16", "bfloat16"] = "float16"
    num_workers: int = Field(2, ge=0)
    seed: int = 2026
    max_minutes: float | None = Field(None, gt=0)
    accumulation_steps: int = Field(1, ge=1)
    freeze_epochs: int = Field(0, ge=0)
    backbone_lr_factor: float = Field(1.0, gt=0, le=1)
    require_cuda: bool = False


class DataCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: str
    roots: dict[str, str]
    train_datasets: list[str]
    external_datasets: list[str] = []
    n_splits: int = Field(5, ge=3)
    near_duplicate_distance: int = Field(4, ge=0, le=16)


class TuneCfg(BaseModel):
    """Mismo presupuesto para los cinco modelos (comparación justa)."""

    model_config = ConfigDict(extra="forbid")
    n_trials: int = Field(30, ge=1)
    max_epochs: int = Field(15, ge=1)
    timeout_hours: float = Field(4.0, gt=0)
    fold: int = 0
    seed: int = 2026
    inner_splits: int = Field(3, ge=3)


class ExperimentCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment: str = "papasana-ap01"
    architecture: str
    pretrained: bool = True
    img_size: int | None = None
    hparams: dict = {}
    train: TrainCfg = TrainCfg()
    data: DataCfg
    tuning: TuneCfg = TuneCfg()
    smoke_test: bool = False

    @field_validator("architecture")
    @classmethod
    def _known_arch(cls, v: str) -> str:
        if v not in ARCHITECTURES:
            raise ValueError(f"Arquitectura desconocida: {v}. Opciones: {', '.join(ARCHITECTURES)}")
        return v


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _load_yaml(path: Path, seen: set[Path] | None = None) -> dict:
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        raise ValueError(f"Herencia circular de configuración: {path}")
    seen.add(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "base" in data:
        data = _merge(_load_yaml(path.parent / data.pop("base"), seen), data)
    return data


def load_config(path: str | Path, overrides: dict | None = None) -> ExperimentCfg:
    """Lee un YAML; si declara `base: otro.yaml`, lo combina (las claves del archivo hijo ganan)."""
    path = Path(path)
    data = _load_yaml(path)
    if overrides:
        data = _merge(data, overrides)
    return ExperimentCfg.model_validate(data)
