"""Utilidades de MLflow: URI de seguimiento, artefactos JSON y etiquetas comunes de los runs."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import mlflow

import potato_blight

DEFAULT_TRACKING_URI = "http://127.0.0.1:5000"  # MLflow del docker-compose (puerto publicado solo en localhost)
MODEL_NAME_PREFIX = "papasana-"


def setup(experiment: str) -> str:
    uri = os.environ.get("MLFLOW_TRACKING_URI", DEFAULT_TRACKING_URI)
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(experiment)
    return uri


def git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5,
                             cwd=Path(__file__).parent)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def common_tags(run_type: str, architecture: str, *, smoke_test: bool, dataset_ids: list[str]) -> dict:
    return {
        "run_type": run_type,
        "architecture": architecture,
        "smoke_test": str(bool(smoke_test)).lower(),
        "dataset_ids": ",".join(dataset_ids),
        "label_scheme": "sintoma",
        "potato_blight_version": potato_blight.__version__,
        **({"git_commit": c} if (c := git_commit()) else {}),
    }


def log_json(data: dict | list, artifact_file: str) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / Path(artifact_file).name
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
        parent = str(Path(artifact_file).parent)
        mlflow.log_artifact(str(p), artifact_path=None if parent == "." else parent)


def registered_name(architecture: str) -> str:
    return f"{MODEL_NAME_PREFIX}{architecture.replace('_', '-')}"
