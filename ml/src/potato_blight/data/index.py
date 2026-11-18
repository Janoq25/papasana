"""Índice verificable de imágenes locales y sus grupos publicados."""

import hashlib
import json
from pathlib import Path

import pandas as pd
from PIL import Image

from potato_blight.data.imagehash import dhash
from potato_blight.data.registry import DatasetEntry, LicenseNotVerified

COLUMNS = ["path", "dataset_id", "source_label", "label", "sha256", "dhash", "width", "height", "source_group"]


def build_manifest(entry: DatasetEntry, root: str | Path, *, allow_unverified: bool = False) -> pd.DataFrame:
    if not entry.usable and not allow_unverified:
        raise LicenseNotVerified(f"Licencia sin verificar para {entry.id}: revise datasets.yaml")
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"No existe el dataset local {entry.id}: {root}")
    groups_file = root / "groups.csv"
    source_file = root / "source.json"
    published = None
    if source_file.exists():
        provenance = json.loads(source_file.read_text(encoding="utf-8"))
        published = {item["path"]: item["sha256"] for item in provenance["files"]}
    groups = {}
    if groups_file.exists():
        table = pd.read_csv(groups_file, dtype=str)
        if table["path"].duplicated().any() or table["group"].isna().any():
            raise ValueError(f"Grupos duplicados o vacíos: {groups_file}")
        groups = dict(zip(table["path"], table["group"], strict=True))
    records = []
    for source_label, label in entry.class_map.items():
        folder = root / source_label
        if not folder.is_dir():
            continue  # PlantDoc puede carecer de una clase; el EDA debe mostrarlo.
        for image_path in sorted(folder.rglob("*")):
            if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
                continue
            if not image_path.resolve().is_relative_to(root):
                raise ValueError(f"Imagen fuera del dataset: {image_path}")
            relative = image_path.relative_to(root).as_posix()
            if published is not None and relative not in published:
                continue
            sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if published is not None and sha != published[relative]:
                raise ValueError(f"Imagen alterada desde la descarga verificada: {relative}")
            group = groups.get(relative)
            if entry.has_group_ids and group is None:
                raise ValueError(f"Falta el ID de hoja/planta publicado: {relative}")
            with Image.open(image_path) as image:
                image.load()  # Falla explícitamente ante imágenes dañadas.
                width, height = image.size
                perceptual = dhash(image)
            records.append({"path": relative, "dataset_id": entry.id, "source_label": source_label,
                            "label": label, "sha256": sha,
                            "dhash": perceptual, "width": width, "height": height, "source_group": group})
    if not records:
        raise ValueError(f"El dataset no contiene imágenes con etiquetas reconocidas: {entry.id}")
    return pd.DataFrame(records, columns=COLUMNS)
