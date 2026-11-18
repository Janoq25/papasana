import numpy as np
import pytest
from scipy import stats
from sklearn.metrics import f1_score, matthews_corrcoef, roc_auc_score

from potato_blight import CLASSES
from potato_blight.calibration import ece, fit_temperature, nll, softmax
from potato_blight.metrics import compute_metrics, scalar_metrics
from potato_blight.stats.tests import bootstrap_ci, delong, friedman, holm, mcnemar, wilcoxon_holm


def _data(n=300, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.integers(0, 3, n)
    logits = rng.normal(0, 1, (n, 3))
    logits[np.arange(n), y] += 1.5
    return y, logits


def test_metricas_coinciden_con_sklearn():
    y, logits = _data()
    p = softmax(logits)
    m = compute_metrics(y, p, CLASSES)
    assert m["macro_f1"] == pytest.approx(f1_score(y, p.argmax(1), average="macro"))
    assert m["mcc"] == pytest.approx(matthews_corrcoef(y, p.argmax(1)))
    assert m["per_class"]["sano"]["auc_roc"] == pytest.approx(roc_auc_score(y == 0, p[:, 0]))
    assert np.array(m["confusion_matrix"]).sum() == len(y)
    assert set(m["roc_curves"]) == set(CLASSES) and len(m["roc_curves"]["sano"]["fpr"]) <= 101
    s = scalar_metrics(m, "test")
    assert "test_macro_f1" in s and "test_sensitivity_sano" in s


def test_clase_ausente_no_inventa_auc():
    y = np.array([0, 0, 1, 1])
    p = softmax(np.array([[2, 0, 0], [1, 0, 0], [0, 2, 0], [0, 1, 0]], dtype=float))
    m = compute_metrics(y, p, CLASSES)
    assert m["per_class"]["otra_enfermedad_foliar"]["auc_roc"] is None
    assert m["per_class"]["otra_enfermedad_foliar"]["support"] == 0


def test_calibracion_por_temperatura_mejora_la_nll():
    y, logits = _data(2000, 1)
    over = logits * 4  # modelo sobreconfiado
    t = fit_temperature(over, y)
    assert t > 1.5
    assert nll(softmax(over, t), y) < nll(softmax(over), y)
    assert ece(softmax(over, t), y) < ece(softmax(over), y)


def test_holm():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj == pytest.approx({"a": 0.03, "c": 0.06, "b": 0.06})


def test_friedman_y_wilcoxon():
    scores = {"m1": [0.9, 0.91, 0.89, 0.92, 0.9, 0.88], "m2": [0.8, 0.82, 0.81, 0.79, 0.8, 0.83],
              "m3": [0.85, 0.86, 0.84, 0.86, 0.85, 0.84]}
    f = friedman(scores)
    ref = stats.friedmanchisquare(*scores.values())
    assert f["aplicable"] and f["p_valor"] == pytest.approx(ref.pvalue)
    assert f["rango_medio"]["m1"] == 1.0
    w = wilcoxon_holm(scores)
    assert len(w) == 3 and all(r["p_holm"] >= r["p_valor"] for r in w)
    assert not friedman({"a": [1, 2], "b": [1, 2]})["aplicable"]


def test_mcnemar():
    y = np.zeros(40, dtype=int)
    a = np.zeros(40, dtype=int)
    b = np.zeros(40, dtype=int)
    b[:10] = 1  # B falla 10 casos que A acierta
    r = mcnemar(y, a, b)
    assert r["n01"] == 10 and r["n10"] == 0 and r["metodo"].startswith("exacta")
    assert r["p_valor"] == pytest.approx(stats.binomtest(10, 10, 0.5).pvalue)


def test_delong_contra_auc_y_simetria():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 400)
    a = y + rng.normal(0, 0.8, 400)
    b = y + rng.normal(0, 1.6, 400)
    r = delong(y, a, b)
    assert r["auc_a"] == pytest.approx(roc_auc_score(y, a))
    assert r["auc_b"] == pytest.approx(roc_auc_score(y, b))
    assert r["p_valor"] < 0.05
    assert delong(y, a, a)["p_valor"] == 1.0
    assert not delong(np.ones(10), a[:10], b[:10])["aplicable"]


def test_bootstrap_contiene_el_valor():
    y, logits = _data(500, 4)
    p = softmax(logits)
    r = bootstrap_ci(lambda yt, pp: f1_score(yt, pp.argmax(1), average="macro"), y, p, n_boot=200)
    assert r["ic_inferior"] <= r["valor"] <= r["ic_superior"]
