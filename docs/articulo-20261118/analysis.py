"""Análisis descriptivo del artículo sobre pesos y temperaturas congelados."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy.special import logsumexp
from torch.utils.data import DataLoader

from potato_blight import CLASSES
from potato_blight.config import load_config
from potato_blight.data.dataset import ManifestDataset, eval_transform
from potato_blight.four_models import development_parts
from potato_blight.models.serialize import load_model_dir
from potato_blight.train import predict_logits

OUTPUT = Path('../docs/articulo-20261118')
SOURCE = Path('data/comparacion-cuatro')
report = json.loads((SOURCE / 'results.json').read_text(encoding='utf-8'))
manifest = pd.read_csv('data/manifest.csv')
assert hashlib.sha256(Path('data/manifest.csv').read_bytes()).hexdigest() == report['contract']['manifest_sha256']
torch.set_num_threads(4)
assert torch.cuda.is_available()
rows = []
all_predictions = []
for row in report['models']:
    arch = row['architecture']
    cfg = load_config(f'configs/quick4_{arch}.yaml')
    folder = SOURCE / arch
    original_hash = hashlib.sha256((folder / 'model/model.pt').read_bytes()).hexdigest()
    assert original_hash == row['verification']['checkpoint_sha256']
    model, mc = load_model_dir(folder / 'model')
    model = model.cuda().eval()
    val = development_parts(manifest, cfg)['val']
    external = pd.read_csv(folder / 'predictions_plantdoc_papa.csv')
    # Conserva exactamente el orden y el lote de la evaluación archivada.
    ext = manifest[manifest.dataset_id == 'plantdoc_papa'].set_index('path').loc[external.path].reset_index()
    diagnostics = {}
    for split, subset in [('val', val), ('external_plantdoc_papa', ext)]:
        loader = DataLoader(ManifestDataset(subset, cfg.data.roots, eval_transform(224)), batch_size=16)
        logits, labels = predict_logits(model, loader, torch.device('cuda'), amp=True, amp_dtype=cfg.train.amp_dtype)
        pred = logits.argmax(1)
        cm = np.zeros((3, 3), dtype=int)
        np.add.at(cm, (labels, pred), 1)
        assert cm.tolist() == row['evaluation'][split]['confusion_matrix']
        nlls = {}
        for label, temperature in [('before', 1.0), ('after', mc['temperature'])]:
            z = logits.astype(np.float64) / temperature
            logp = z - logsumexp(z, axis=1, keepdims=True)
            nlls[label] = float(-logp[np.arange(len(labels)), labels].mean())
        diagnostics[split] = {'stable_nll': nlls, 'n': len(labels), 'cm_reproduced': True}
    cm = np.array(row['evaluation']['val']['confusion_matrix'])
    cm[0] = 0  # Análisis secundario: solo imágenes cuya referencia es una de las dos enfermedades.
    tp = cm.diagonal().astype(float)
    denom = cm.sum(0) + cm.sum(1)
    conditional_f1 = float((2 * tp[1:] / denom[1:]).mean())
    entry = {'architecture': arch, 'run_id': row['run_id'], 'val_f1_three': row['metrics']['val_macro_f1'],
             'val_disease_only_n': int(cm.sum()), 'val_f1_disease_only': conditional_f1,
             'external_f1_two': row['metrics']['external_plantdoc_papa_macro_f1'],
             'diagnostics': diagnostics, 'checkpoint_sha256': original_hash}
    all_predictions.append(external)
    assert hashlib.sha256((folder / 'model/model.pt').read_bytes()).hexdigest() == original_hash
    del model
    torch.cuda.empty_cache()
    rows.append(entry)
    print(arch, diagnostics, 'F1 interno condicionado:', conditional_f1, flush=True)

# Remuestreo de grupos perceptuales ya definidos. No estima variación entre reentrenamientos.
base = all_predictions[0]
for pred in all_predictions[1:]:
    assert pred[['path', 'group_id', 'y_true']].equals(base[['path', 'group_id', 'y_true']])
groups = sorted(base.group_id.unique())
matrices = []
for pred in all_predictions:
    pred_labels = pred[[f'p_{c}' for c in CLASSES]].to_numpy().argmax(1)
    group_matrix = np.zeros((len(groups), 3, 3), dtype=np.int64)
    mapping = {g: i for i, g in enumerate(groups)}
    for g, y, yp in zip(pred.group_id, pred.y_true, pred_labels, strict=True):
        group_matrix[mapping[g], int(y), int(yp)] += 1
    matrices.append(group_matrix)
matrices = np.array(matrices)
rng = np.random.default_rng(20261118)
replicates = 5000
weights = rng.multinomial(len(groups), np.repeat(1 / len(groups), len(groups)), size=replicates)
bootstrap = np.einsum('bg,mgij->bmij', weights, matrices)
tp = np.diagonal(bootstrap, axis1=2, axis2=3)
denominator = bootstrap.sum(2) + bootstrap.sum(3)
f1 = (2 * tp[:, :, 1:] / denominator[:, :, 1:]).mean(2)
for i, row in enumerate(rows):
    row['external_cluster_bootstrap_f1_ci95'] = np.quantile(f1[:, i], [0.025, 0.975]).tolist()
    row['matched_class_gap'] = row['val_f1_disease_only'] - row['external_f1_two']
result = {'source_fingerprint': report['fingerprint'], 'manifest_sha256': report['contract']['manifest_sha256'],
          'external_n': len(base), 'external_groups': len(groups), 'bootstrap_replicates': replicates,
          'bootstrap_seed': 20261118, 'ci_method': 'Percentil de remuestreo de grupos perceptuales con reemplazo',
          'notes': ['Análisis posterior descriptivo de modelos congelados; no se reentrenó ni cambió temperatura.',
                    'IC condicionales al conjunto observado y grupos disponibles; no incorporan variación de entrenamiento.',
                    'NLL estable calculada en log-espacio sin recortar probabilidades a 1e-12.'], 'models': rows}
(OUTPUT / 'analisis_derivado.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
print('ANALISIS', json.dumps(result, ensure_ascii=False, indent=2))
