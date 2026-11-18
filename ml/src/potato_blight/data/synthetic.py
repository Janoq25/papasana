"""Fixtures sintéticos reproducibles, exclusivamente para comprobar el pipeline."""

import csv
import random
from pathlib import Path

from PIL import Image, ImageDraw

from potato_blight import CLASSES


def generate(root: str | Path, plants_per_class: int = 6, views_per_plant: int = 2, size: int = 128) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for label_index, label in enumerate(CLASSES):
        folder = root / label
        folder.mkdir(exist_ok=True)
        for plant in range(plants_per_class):
            for view in range(views_per_plant):
                rng = random.Random(2026 + label_index * 10000 + plant * 100 + view)
                image = Image.new("RGB", (size, size))
                # Textura distinta por imagen: el grupo conocido une las vistas, no un hash accidental.
                image.putdata([tuple(rng.randrange(20, 200) for _ in range(3)) for _ in range(size * size)])
                draw = ImageDraw.Draw(image)
                colors = [(30, 180, 50), (130, 100, 35), (220, 80, 35)]
                draw.ellipse((size // 4, size // 4, 3 * size // 4, 3 * size // 4), fill=colors[label_index])
                relative = f"{label}/plant{plant}_view{view}.png"
                image.save(root / relative)
                records.append({"path": relative, "group": f"{label}-plant{plant}"})
    with (root / "groups.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["path", "group"])
        writer.writeheader()
        writer.writerows(records)
    return root
