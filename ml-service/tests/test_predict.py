import base64
import io

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.model import CLASSES, _jet


def _leaf_png(size=(320, 240)) -> bytes:
    img = Image.new("RGB", size, (40, 130, 40))
    for x in range(120, 180):
        for y in range(90, 140):
            img.putpixel((x, y), (90, 60, 30))  # "lesión" marrón
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_prediccion_devuelve_probabilidades_calibradas_y_gradcam(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_TOKEN", raising=False)
    with TestClient(app) as c:
        r = c.post("/predict", files={"file": ("hoja.png", _leaf_png(), "image/png")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body["probabilities"]) == set(CLASSES)
        assert abs(sum(body["probabilities"].values()) - 1) < 1e-4
        assert body["predicted_class"] in CLASSES
        assert body["confidence"] == max(body["probabilities"].values())
        assert body["model"]["is_demo"] is True
        overlay = Image.open(io.BytesIO(base64.b64decode(body["gradcam_png_b64"])))
        assert overlay.format == "PNG" and overlay.size == (320, 240)


def test_prediccion_es_determinista(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_TOKEN", raising=False)
    with TestClient(app) as c:
        a = c.post("/predict", files={"file": ("a.png", _leaf_png(), "image/png")}).json()
        b = c.post("/predict", files={"file": ("a.png", _leaf_png(), "image/png")}).json()
        assert a["probabilities"] == b["probabilities"]


def test_token_interno_obligatorio(monkeypatch):
    monkeypatch.setenv("ML_SERVICE_TOKEN", "secreto")
    with TestClient(app) as c:
        assert c.post("/predict", files={"file": ("a.png", _leaf_png(), "image/png")}).status_code == 401
        ok = c.post("/predict", files={"file": ("a.png", _leaf_png(), "image/png")},
                    headers={"X-Internal-Token": "secreto"})
        assert ok.status_code == 200


def test_imagen_invalida(monkeypatch):
    monkeypatch.delenv("ML_SERVICE_TOKEN", raising=False)
    with TestClient(app) as c:
        assert c.post("/predict", files={"file": ("x.png", b"no es imagen", "image/png")}).status_code == 422


def test_mapa_de_color():
    rgb = _jet(np.array([0.0, 1.0]))
    assert rgb[0][2] > rgb[0][0]  # frío = azul
    assert rgb[1][0] > rgb[1][2]  # caliente = rojo
