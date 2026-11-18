import pytest


@pytest.fixture(autouse=True)
def _sin_mlflow(monkeypatch, tmp_path):
    """Las pruebas no dependen de un servidor MLflow: por defecto se sirve el modelo DEMO."""
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr("app.model.CACHE_DIR", tmp_path / "cache")
