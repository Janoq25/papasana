import numpy as np
import pandas as pd
import pytest
import torch

from potato_blight import CLASSES
from potato_blight.config import load_config
from potato_blight.four_models import choose_internal, development_parts
from potato_blight.models.architectures import QUICK_COMPARISON_ARCHITECTURES, build_model
from potato_blight.models.serialize import load_model_dir, make_config, save_model_dir

NEW_MODELS = ("efficientnetv2_b0", "mobilenetv4_conv_medium", "efficientvit_b1")


def test_la_comparacion_excluye_plantdoc_del_entrenamiento_y_validacion():
    cfg = load_config("configs/quick4_resnet50.yaml")
    rows = [{"dataset_id": "plantvillage_papa", "path": f"{label}-{fold}.png", "label": label,
             "group_id": f"{label}-{fold}", "fold": fold} for label in CLASSES for fold in (0, 1)]
    rows.append({"dataset_id": "plantdoc_papa", "path": "externa.png", "label": CLASSES[0],
                 "group_id": "externa", "fold": 1})
    parts = development_parts(pd.DataFrame(rows), cfg)
    assert all(set(part["dataset_id"]) == {"plantvillage_papa"} for part in parts.values())
    assert not set(parts["train"]["group_id"]) & set(parts["val"]["group_id"])
    assert len(QUICK_COMPARISON_ARCHITECTURES) == 4


def _row(arch, f1, seconds, external):
    return {"architecture": arch, "metrics": {"val_macro_f1": f1, "train_seconds": seconds,
                                              "external_plantdoc_papa_macro_f1": external}}


def test_la_seleccion_no_sacrifica_f1_interno_por_velocidad_ni_mira_plantdoc():
    rows = [_row("resnet50", 0.98, 100, 0.4), _row("efficientnetv2_b0", 0.99, 60, 0.2),
            _row("mobilenetv4_conv_medium", 0.97, 20, 1.0), _row("efficientvit_b1", 0.985, 45, 0.1)]
    choice = choose_internal(rows, previous_f1=0.979)
    assert choice["recommended_architecture"] == "efficientvit_b1"
    assert choice["best_internal_architecture"] == "efficientnetv2_b0"
    assert not choice["external_used_for_selection"]


def test_se_conserva_el_modelo_previo_si_todos_los_nuevos_bajan_f1():
    rows = [_row(arch, 0.96, 20, 1.0) for arch in QUICK_COMPARISON_ARCHITECTURES]
    choice = choose_internal(rows, previous_f1=0.98)
    assert choice["recommended_source"] == "previous_resnet50"


@pytest.mark.parametrize("arch", NEW_MODELS)
def test_los_nuevos_modelos_guardan_y_recargan_los_mismos_logits(tmp_path, arch):
    torch.set_num_threads(4)
    model = build_model(arch, 3, img_size=64, pretrained=False).eval()
    cfg = make_config(arch, CLASSES, img_size=64)
    save_model_dir(model, cfg, tmp_path / "model")
    loaded, _ = load_model_dir(tmp_path / "model")
    x = torch.randn(2, 3, 64, 64)
    with torch.no_grad():
        assert np.allclose(model(x).numpy(), loaded(x).numpy(), atol=1e-5)


@pytest.mark.skipif(not torch.cuda.is_available() or not torch.cuda.is_bf16_supported(), reason="Requiere CUDA BF16")
def test_bfloat16_preserva_logits_que_desbordan_float16():
    from torch.utils.data import DataLoader, TensorDataset

    from potato_blight.train import predict_logits

    model = torch.nn.Linear(2, 3, bias=False).cuda()
    with torch.no_grad():
        model.weight.fill_(20000)
    loader = DataLoader(TensorDataset(torch.full((2, 2), 2.0), torch.zeros(2, dtype=torch.long), torch.arange(2)))
    with pytest.raises(FloatingPointError, match="Logits no finitos"):
        predict_logits(model, loader, torch.device("cuda"), amp_dtype="float16")
    logits, labels = predict_logits(model, loader, torch.device("cuda"), amp_dtype="bfloat16")
    assert np.isfinite(logits).all()
    assert logits.shape == (2, 3) and labels.shape == (2,)
    assert logits.min() > torch.finfo(torch.float16).max
