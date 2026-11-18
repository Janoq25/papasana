"""Configuración de experimentos (YAML en `ml/configs/`), validada con Pydantic."""

from pathlib import Path

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
    num_workers: int = Field(2, ge=0)
    seed: int = 2026
    max_minutes: float | None = Field(None, gt=0)


class DataCfg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: str
    roots: dict[str, str]
    train_datasets: list[str]
    external_datasets: list[str] = []
    n_splits: int = Field(5, ge=2)
    near_duplicate_distance: int = Field(4, ge=0, le=16)


class TuneCfg(BaseModel):
    """Mismo presupuesto para los cinco modelos (comparación justa)."""

    model_config = ConfigDict(extra="forbid")
    n_trials: int = Field(30, ge=1)
    max_epochs: int = Field(15, ge=1)
    timeout_hours: float = Field(4.0, gt=0)
    fold: int = 0
    seed: int = 2026


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


def load_config(path: str | Path, overrides: dict | None = None) -> ExperimentCfg:
    """Lee un YAML; si declara `base: otro.yaml`, lo combina (las claves del archivo hijo ganan)."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "base" in data:
        base = yaml.safe_load((path.parent / data.pop("base")).read_text(encoding="utf-8")) or {}
        data = _merge(base, data)
    if overrides:
        data = _merge(data, overrides)
    return ExperimentCfg.model_validate(data)
