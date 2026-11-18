"""Snapshots científicos publicados por el entrenador. Lectura local, sin MLflow ni GPU."""
import json
import logging
import re
from pathlib import Path

from app.core.errors import NotFoundError, ServiceUnavailableError

REPORT_ROOT = Path(__file__).resolve().parents[1] / "data" / "training_reports"
log = logging.getLogger("papasana")


def read_report(identifier: str, root: Path = REPORT_ROOT) -> dict:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,119}", identifier):
        raise NotFoundError("Informe no encontrado.")
    path = root / f"{identifier}.json"
    if not path.is_file():
        raise NotFoundError("Informe no encontrado.")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(report, dict) or report.get("schema_version") != 1
                or report.get("id") != identifier or not isinstance(report.get("models"), list)
                or not report["models"]
                or not all(isinstance(report.get(key), str) for key in ("title", "trained_on"))):
            raise ValueError("Versión o identificador no válido")
        return report
    except (ValueError, KeyError, OSError) as error:
        log.warning("Informe científico ilegible: %s", identifier)
        raise ServiceUnavailableError("No se pudo leer el informe. Regenérelo desde el entrenamiento.") from error


def list_reports(root: Path = REPORT_ROOT) -> list[dict]:
    reports = []
    for path in sorted(root.glob("*.json")):
        try:
            report = read_report(path.stem, root)
        except (NotFoundError, ServiceUnavailableError):
            continue
        reports.append({"id": report["id"], "title": report["title"], "trained_on": report["trained_on"],
                        "model_count": len(report["models"])})
    return sorted(reports, key=lambda r: r["trained_on"], reverse=True)
