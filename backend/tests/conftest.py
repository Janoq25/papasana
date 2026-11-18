"""Infraestructura de pruebas.

Las pruebas corren contra la base `papasana_test` (PostgreSQL real: los triggers y permisos de la
bitácora no se pueden simular con SQLite). Cada prueba se ejecuta en una transacción que se revierte.

Ejecutar:  docker compose run --rm backend pytest
"""

import os

# Debe configurarse antes de importar la aplicación (settings y engine se crean al importar).
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["MIGRATION_DATABASE_URL"] = os.environ["TEST_MIGRATION_DATABASE_URL"]
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["APP_ENV"] = "development"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.seed import seed  # noqa: E402
from app.services.settings_service import clear_settings_cache  # noqa: E402
from app.services.storage_service import get_storage  # noqa: E402

TEST_PASSWORD = "Prueba-Segura-2026"
DEMO = {
    "ADMINISTRADOR": "admin@demo.papasana.pe",
    "INVESTIGADOR": "investigador@demo.papasana.pe",
    "AGRONOMO": "agronomo@demo.papasana.pe",
    "TECNICO": "tecnico@demo.papasana.pe",
    "AUDITOR": "auditor@demo.papasana.pe",
}


@pytest.fixture(scope="session")
def owner_engine():
    return create_engine(os.environ["TEST_MIGRATION_DATABASE_URL"], connect_args={"options": "-c timezone=UTC"})


@pytest.fixture(scope="session", autouse=True)
def _database(owner_engine):
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "alembic"))
    cfg.attributes["url"] = os.environ["TEST_MIGRATION_DATABASE_URL"]
    command.upgrade(cfg, "head")
    with Session(owner_engine) as s:
        seed(s, demo_password=TEST_PASSWORD, development=True)
    yield


class FakeStorage:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def ensure_bucket(self, bucket):
        pass

    def put_bytes(self, bucket, key, data, content_type):
        self.objects[(bucket, key)] = data

    def get_bytes(self, bucket, key):
        return self.objects[(bucket, key)]

    def remove(self, bucket, key):
        self.objects.pop((bucket, key), None)


@pytest.fixture
def db():
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False,
                      autoflush=False)
    clear_settings_cache()
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        connection.close()
        clear_settings_cache()


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def emails(monkeypatch):
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr("app.services.auth_service.enqueue_email", lambda to, s, b: sent.append((to, s, b)))
    return sent


@pytest.fixture
def client(db, storage, emails):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_storage] = lambda: storage
    c = TestClient(app)  # sin "with": no se ejecuta el lifespan (no se necesita MinIO)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


def login(client: TestClient, role: str = "ADMINISTRADOR", password: str = TEST_PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": DEMO[role], "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return login(client, "ADMINISTRADOR")


# --- Fase 2: inferencia simulada -------------------------------------------------------------------

class FakeML:
    """Sustituye a ml-service: la clase y la confianza se configuran en cada prueba."""

    def __init__(self):
        self.predicted = "sintomas_compatibles_tizon_tardio"
        self.confidence = 0.91
        self.fail = False
        self.calls = 0

    def predict(self, raw, filename):
        from app.core.errors import ServiceUnavailableError

        self.calls += 1
        if self.fail:
            raise ServiceUnavailableError("El servicio de inferencia no está disponible. Intente más tarde.")
        rest = (1 - self.confidence) / 2
        probs = {c: rest for c in ("sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar")}
        probs[self.predicted] = self.confidence
        import base64
        import io

        from PIL import Image as PILImage

        buf = io.BytesIO()
        PILImage.new("RGB", (8, 8), (255, 0, 0)).save(buf, format="PNG")
        return {"model": self.model_info(), "predicted_class": self.predicted, "confidence": self.confidence,
                "probabilities": probs, "gradcam_png_b64": base64.b64encode(buf.getvalue()).decode(),
                "inference_ms": 12}

    def model_info(self):
        return {"key": "demo-resnet50-imagenet-v1", "architecture": "resnet50", "display_name": "DEMO",
                "is_demo": True, "classes": ["sano", "sintomas_compatibles_tizon_tardio", "otra_enfermedad_foliar"],
                "temperature": 1.0}


@pytest.fixture
def fake_ml():
    return FakeML()


@pytest.fixture
def ml_client(client, fake_ml, monkeypatch):
    """Cliente HTTP con ml-service simulado y la cola de Celery interceptada."""
    from app.services.ml_client import get_ml_client

    app.dependency_overrides[get_ml_client] = lambda: fake_ml
    queued: list[str] = []
    monkeypatch.setattr("app.api.v1.routers.diagnoses.process_image.delay", lambda image_id: queued.append(image_id))
    client.queued = queued
    return client
