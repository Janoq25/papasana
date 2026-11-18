"""Registro de datasets y verificación documental de licencias."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, field_validator

from potato_blight import CLASSES


class LicenseNotVerified(ValueError):
    """El registro no documenta permiso de uso del dataset."""


class DatasetEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    conditions: str
    role: str
    class_map: dict[str, str]
    version: str = ""
    source_url: str | None = None
    license: str | None = None
    license_url: str | None = None
    license_status: Literal["por_verificar", "verificada", "rechazada"] = "por_verificar"
    license_verified_by: str | None = None
    license_verified_at: str | None = None
    license_notes: str = ""
    citation: str | None = None
    label_scheme: str = "sintoma"
    etiological_confirmation: bool | str = False
    has_group_ids: bool = False
    notes: str = ""

    @field_validator("class_map")
    @classmethod
    def known_labels(cls, values: dict[str, str]) -> dict[str, str]:
        unknown = set(values.values()) - set(CLASSES)
        if unknown:
            raise ValueError(f"Clases no reconocidas: {sorted(unknown)}")
        return values

    @property
    def usable(self) -> bool:
        return bool(self.license_status == "verificada" and self.license and
                    self.license_verified_by and self.license_verified_at)


class Registry(BaseModel):
    datasets: list[DatasetEntry]

    def get(self, ds_id: str) -> DatasetEntry:
        for entry in self.datasets:
            if entry.id == ds_id:
                return entry
        raise KeyError(f"Dataset no registrado: {ds_id}")


def load_registry(path: str | Path | None = None) -> Registry:
    path = Path(path) if path is not None else Path(__file__).resolve().parents[3] / "datasets.yaml"
    return Registry.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
