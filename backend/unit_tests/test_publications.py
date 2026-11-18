"""API y snapshots del artículo: sin conexión a PostgreSQL ni servicios externos."""
import json
import os
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unit:unit@127.0.0.1:1/unit")
os.environ.setdefault("JWT_SECRET", "unit-tests-without-real-credentials")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import CurrentUser, get_current_user
from app.api.v1.routers.publications import router
from app.core.errors import NotFoundError, ServiceUnavailableError, register_error_handlers
from app.db.session import get_db
from app.services.publication_service import REPORT_ROOT, list_reports, read_report


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router, prefix="/api/v1")
    current = CurrentUser(user=SimpleNamespace(id="unit"), session=SimpleNamespace(id="unit"),
                          permissions={"laboratorio:ver"})
    app.dependency_overrides[get_current_user] = lambda: current
    app.dependency_overrides[get_db] = lambda: Mock()
    monkeypatch.setattr("app.api.deps.AuditService", Mock())
    with TestClient(app) as http:
        http.test_app = app
        http.test_current = current
        yield http


def test_los_cuatro_modelos_publicados_conservan_resultados_reales():
    index = list_reports()
    assert index and index[0]["model_count"] == 4
    report = read_report(index[0]["id"])
    assert len(report["models"]) == 4
    assert report["data"]["train"] == 1724 and report["data"]["validation"] == 428
    assert report["data"]["external"] == 208
    assert report["data"]["leaf_groups"] == 538
    data = report["data"]
    assert data["original"] - data["duplicates_removed"] - data["quarantined"] == data["accepted"]
    assert report["selection"]["external_used_for_selection"] is False
    for model in report["models"]:
        assert model["verification"]["reload_and_gradcam_passed"]
        assert len(model["history"]["val_macro_f1_epoch"]) >= model["best_epoch"]
        assert model["evaluation"]["external_plantdoc_papa"]["per_class"]["sano"]["support"] == 0
        assert len(model["checkpoint_sha256"]) == 64
    # No se publican rutas privadas, fotos, pesos ni tokens del entorno.
    text = json.dumps(report)
    assert "C:\\Users" not in text and "mlflow.db" not in text and "API_KEY" not in text


def test_endpoints_leen_snapshot_sin_mlflow(client):
    response = client.get("/api/v1/laboratorio/publicaciones")
    assert response.status_code == 200
    identifier = response.json()[0]["id"]
    detail = client.get(f"/api/v1/laboratorio/publicaciones/{identifier}")
    assert detail.status_code == 200 and len(detail.json()["models"]) == 4
    assert client.get("/api/v1/laboratorio/publicaciones/no-existe").status_code == 404


def test_sin_autenticacion_no_se_pueden_leer_informes(client):
    client.test_app.dependency_overrides.pop(get_current_user)
    assert client.get("/api/v1/laboratorio/publicaciones").status_code == 401


def test_permiso_del_laboratorio_tambien_se_exige_en_el_detalle(client):
    client.test_current.permissions.clear()
    assert client.get("/api/v1/laboratorio/publicaciones").status_code == 403
    identifier = list_reports()[0]["id"]
    assert client.get(f"/api/v1/laboratorio/publicaciones/{identifier}").status_code == 403


@pytest.mark.parametrize("identifier", ["../config", "..", "x/y", "x\\y", "A" * 130])
def test_identificadores_no_permiten_rutas_arbitrarias(identifier):
    with pytest.raises(NotFoundError):
        read_report(identifier)


@pytest.mark.parametrize("content", ["{", "[]", '{"schema_version":1,"id":"corrupto","models":[{}]}'])
def test_informe_corrupto_no_se_anuncia_como_valido(tmp_path, content):
    (tmp_path / "corrupto.json").write_text(content, encoding="utf-8")
    with pytest.raises(ServiceUnavailableError):
        read_report("corrupto", tmp_path)
    assert list_reports(tmp_path) == []
    assert REPORT_ROOT.is_dir()
