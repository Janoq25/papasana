"""Descarga únicamente hojas de papa desde las fuentes oficiales, con revisión y hashes fijados.

Uso: python -m potato_blight.download_public --destination data/raw
No requiere cuentas, claves ni la descarga de todos los cultivos.
"""

import argparse
import csv
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SOURCES = {
    "plantvillage_papa": {
        "repo": "spMohanty/PlantVillage-Dataset",
        "revision": "7f7ecc7e1eaca78107e3affe7cb5abd9427e139a",
        "license": "CC-BY-SA-3.0",
        "license_path": "README_HF.md",
        "labels": ["Potato___healthy", "Potato___Late_blight", "Potato___Early_blight"],
    },
    "plantdoc_papa": {
        "repo": "pratikkayal/PlantDoc-Dataset",
        "revision": "5467f6012d78d1c446145d5f582da6096f852ae8",
        "license": "CC-BY-4.0",
        "license_path": "LICENSE.txt",
        "labels": ["Potato leaf", "Potato leaf late blight", "Potato leaf early blight"],
    },
}


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "PapaSana-academic-research"})
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read()
        except OSError:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("Descarga incompleta")


def tree(repo: str, ref: str, recursive: bool = False) -> dict:
    suffix = "?recursive=1" if recursive else ""
    result = json.loads(fetch(f"https://api.github.com/repos/{repo}/git/trees/{ref}{suffix}"))
    if result.get("truncated"):
        raise RuntimeError("GitHub devolvió un árbol incompleto; no se acepta como inventario.")
    return result


def raw_url(source: dict, path: str) -> str:
    safe = urllib.parse.quote(path, safe="/")
    return f"https://raw.githubusercontent.com/{source['repo']}/{source['revision']}/{safe}"


def potato_leaf_group(leaf_map: dict, path: str) -> str:
    relative = Path(path)
    name = relative.stem.split("___", 1)[-1].lower()
    label = relative.parts[0]
    groups = [group for group in leaf_map.get(name, []) if group.split(":::", 1)[0] == label]
    if len(groups) != 1:
        raise ValueError(f"ID de hoja ausente o ambiguo dentro de la clase {label}: {path}")
    return groups[0]


def selected_files(ds_id: str, source: dict) -> list[dict]:
    if ds_id == "plantvillage_papa":
        current = source["revision"]
        for component in ("raw", "color"):
            current = next(e["sha"] for e in tree(source["repo"], current)["tree"] if e["path"] == component)
        classes = {e["path"]: e["sha"] for e in tree(source["repo"], current)["tree"]}
        entries = []
        for label in source["labels"]:
            for item in tree(source["repo"], classes[label])["tree"]:
                entries.append({**item, "source_path": f"raw/color/{label}/{item['path']}",
                                "local_path": f"{label}/{item['path']}"})
    else:
        entries = []
        for item in tree(source["repo"], source["revision"], recursive=True)["tree"]:
            parts = item["path"].split("/")
            if len(parts) >= 3 and parts[0] in ("train", "test") and parts[1] in source["labels"]:
                # Conserva el split de origen en el nombre para impedir colisiones.
                # Nombres únicos también en Windows (la fuente contiene diferencias solo de mayúsculas).
                name = hashlib.sha256(item["path"].encode()).hexdigest()[:24] + Path(item["path"]).suffix.lower()
                entries.append({**item, "source_path": item["path"],
                                "local_path": f"{parts[1]}/{parts[0]}__{name}"})
    return sorted((e for e in entries if e["type"] == "blob" and
                   Path(e["path"]).suffix.lower() in {".jpg", ".jpeg", ".png"}),
                  key=lambda e: e["local_path"])


def download(ds_id: str, destination: Path, workers: int = 8) -> dict:
    source = SOURCES[ds_id]
    root = destination / ds_id
    root.mkdir(parents=True, exist_ok=True)
    evidence = fetch(raw_url(source, source["license_path"]))
    (root / "license-source.txt").write_bytes(evidence)
    if ds_id == "plantvillage_papa" and b"license: cc-by-sa-3.0" not in evidence:
        raise RuntimeError("La fuente fijada ya no declara la licencia verificada.")
    files = selected_files(ds_id, source)
    if not files:
        raise RuntimeError(f"La fuente no tiene clases de papa reconocidas: {ds_id}")
    leaf_map = json.loads(fetch(raw_url(source, "leaf-map.json"))) if ds_id == "plantvillage_papa" else {}

    def one(entry: dict) -> dict:
        rel = Path(entry["local_path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError("Ruta de origen no permitida")
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = dest.read_bytes() if dest.exists() else fetch(raw_url(source, entry["source_path"]))
        git_hash = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if git_hash != entry["sha"]:
            raise RuntimeError(f"El contenido no coincide con el blob publicado: {rel}")
        if not dest.exists():
            partial = dest.with_suffix(dest.suffix + ".part")
            partial.write_bytes(data)
            partial.replace(dest)
        # Un mismo nombre puede existir en varias especies. Selecciona la clase exacta de papa.
        group = potato_leaf_group(leaf_map, rel.as_posix()) if leaf_map else None
        return {"path": rel.as_posix(), "source_path": entry["source_path"], "git_blob": git_hash,
                "sha256": hashlib.sha256(data).hexdigest(), "group": group}

    records = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, e) for e in files]
        for future in as_completed(futures):
            records.append(future.result())
            if len(records) % 200 == 0:
                print(f"{ds_id}: {len(records)}/{len(files)} imágenes verificadas", flush=True)
    records.sort(key=lambda r: r["path"])
    if leaf_map:
        missing = [r["path"] for r in records if not r["group"]]
        if missing:
            raise RuntimeError(f"Faltan IDs de hoja en {len(missing)} imágenes: {missing[:3]}")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=["path", "group"])
        writer.writeheader()
        writer.writerows({"path": r["path"], "group": r["group"]} for r in records)
        (root / "groups.csv").write_text(stream.getvalue(), encoding="utf-8")
    result = {"dataset_id": ds_id, **source, "checked_on": "2026-11-18", "image_count": len(records),
              "license_source_sha256": hashlib.sha256(evidence).hexdigest(), "files": records}
    (root / "source.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{ds_id}: COMPLETO, {len(records)} imágenes", flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("data/raw"))
    parser.add_argument("--dataset", choices=list(SOURCES), action="append")
    parser.add_argument("--workers", type=int, default=8, choices=range(1, 17))
    args = parser.parse_args()
    for ds_id in args.dataset or SOURCES:
        download(ds_id, args.destination, args.workers)


if __name__ == "__main__":
    main()
