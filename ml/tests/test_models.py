import numpy as np
import pytest
import torch
from PIL import Image

from potato_blight import CLASSES
from potato_blight.explain.gradcam import GradCAM
from potato_blight.explain.quality import relevance, stability
from potato_blight.explain.shap_explain import attention_map
from potato_blight.models import ARCHITECTURES, build_model, load_model_dir, make_config, save_model_dir
from potato_blight.models.preprocess import preprocess, resize_center_crop

SIZE = 64  # pequeño para que las pruebas corran en CPU


@pytest.mark.parametrize("arch", ARCHITECTURES)
def test_cada_arquitectura_clasifica_y_explica(arch):
    torch.manual_seed(0)
    model = build_model(arch, len(CLASSES), img_size=SIZE, pretrained=False).eval()
    x = torch.randn(2, 3, SIZE, SIZE)
    assert model(x).shape == (2, 3)
    probs, cam = GradCAM(model, arch)(x[:1], temperature=1.5)
    assert probs.shape == (3,) and float(probs.sum()) == pytest.approx(1.0, abs=1e-5)
    assert cam.ndim == 2 and cam.min() >= 0 and cam.max() <= 1


def test_guardar_y_cargar_reproduce_las_salidas(tmp_path):
    model = build_model("cnn_vit", 3, img_size=SIZE, depth=1, d_model=128).eval()
    cfg = make_config("cnn_vit", CLASSES, img_size=SIZE, hparams={"depth": 1, "d_model": 128}, temperature=1.7,
                      smoke_test=True)
    save_model_dir(model, cfg, tmp_path / "model")
    loaded, cfg2 = load_model_dir(tmp_path / "model")
    x = torch.randn(1, 3, SIZE, SIZE)
    assert torch.allclose(model(x), loaded(x), atol=1e-5)
    assert cfg2["temperature"] == 1.7 and cfg2["smoke_test"] is True


def test_hiperparametros_no_admitidos():
    with pytest.raises(ValueError):
        build_model("resnet50", 3, depth=3)
    with pytest.raises(ValueError):
        build_model("vgg16", 3)


def test_preprocesamiento_recorta_al_centro():
    img = Image.new("RGB", (400, 200), (255, 0, 0))
    assert resize_center_crop(img, 64).size == (64, 64)
    x = preprocess(img, {"img_size": 64, "mean": [0.5] * 3, "std": [0.5] * 3})
    assert x.shape == (1, 3, 64, 64) and float(x[0, 0].mean()) == pytest.approx(1.0)


def test_calidad_de_explicaciones_y_atencion():
    model = build_model("effnet_att_bilstm", 3, img_size=SIZE).eval()
    cam = GradCAM(model, "effnet_att_bilstm")
    s = stability(cam, torch.randn(1, 3, SIZE, SIZE))
    assert set(s) == {"ruido", "brillo", "desplazamiento", "media"} and -1 <= s["media"] <= 1
    att = attention_map(model, torch.randn(1, 3, SIZE, SIZE))
    assert att is not None and att.shape == model.grid
    mapa = np.zeros((4, 4), dtype=np.float32)
    mapa[:2, :2] = 1
    mascara = np.zeros((8, 8))
    mascara[:4, :4] = 1
    assert relevance(mapa, mascara) > 0.6
