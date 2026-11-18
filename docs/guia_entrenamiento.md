# Guía de entrenamiento y registro de modelos

> Actualización del 18 de noviembre de 2026: consulte [Entrenamiento reproducible](reentrenamiento.md) para
> las fuentes oficiales verificadas, la GPU local de 4 GB, el EDA ejecutable y la validación agrupada anidada.
> El flujo `tune` seguido de `train --mode cv` descrito abajo corresponde al procedimiento convencional previo;
> no equivale a una búsqueda independiente dentro de cada fold externo. No debe presentarse como CV anidada.

Cómo pasar de los datos a un modelo en producción en AP-01. El código está en `ml/` (paquete `potato_blight`), separado de la aplicación.

## 0. Flujo completo

```
datasets.yaml (licencias verificadas)
   → prepare (índice, deduplicación, particiones agrupadas)
   → tune (Optuna, mismo presupuesto para los 5 modelos)
   → train --mode cv (validación cruzada agrupada, 5 particiones)
   → compare (pruebas estadísticas)
   → train --mode final
   → register (Model Registry de MLflow, sin alias)
   → aplicación: Sincronizar → Promover (Investigador) → Aprobar (Administrador)
   → ml-service carga el modelo
```

Todos los runs quedan en MLflow (http://127.0.0.1:5000 con la aplicación levantada).

## 1. Instalación

```powershell
cd ml
python -m venv .venv
.venv\Scripts\activate
pip install --extra-index-url https://download.pytorch.org/whl/cu124 -e ".[dev]"   # GPU (RTX 3050)
# o, solo CPU:  pip install --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"
$env:MLFLOW_TRACKING_URI = "http://127.0.0.1:5000"
python -m pytest           # 25 pruebas, incluida una prueba de humo de punta a punta
```

> En Windows, si `pip` falla con "No such file or directory" en archivos de PyTorch, el problema es el límite de 260 caracteres de las rutas: cree el entorno en una ruta corta (p. ej., `C:\pbv`) o active las rutas largas de Windows.

## 2. Prueba de humo (antes de gastar horas de GPU)

```powershell
python -m potato_blight.smoke --arch resnet50 --register
```

Este comando:

1. genera imágenes **sintéticas**;
2. entrena 1 época sin pesos preentrenados (no descarga nada);
3. calibra y evalúa;
4. registra el run y el modelo en MLflow con la etiqueta `smoke_test=true`.

En la aplicación, el modelo de humo aparece como "SMOKE TEST / no validado": se sirve marcado como DEMO y sus métricas nunca se reportan.

## 3. Datos y licencias

1. Registre el dataset en **Datasets y licencias** (aplicación) o en `ml/datasets.yaml`, con el `class_map` hacia las clases por síntoma. *Early blight* va a `otra_enfermedad_foliar`, **nunca** a tizón tardío (D-01).
2. Revise la licencia **en la fuente oficial** (el repositorio o la página de los autores, no una copia de terceros) y regístrela en **Datasets y licencias → Licencia**. Quedan registrados su nombre y la fecha.
3. Exporte el registro (**Exportar datasets.yaml**) y reemplace `ml/datasets.yaml`.
4. Descargue las imágenes en `ml/data/raw/<id>/<etiqueta de la fuente>/…`.
   - Si la fuente publica IDs de planta o parcela, agregue `groups.csv` (columnas `path,group`).

`prepare` y `build_manifest` **se niegan** a indexar un dataset cuya licencia no esté verificada.

```powershell
python -m potato_blight.prepare --config configs/base.yaml
```

Escribe dos archivos:

- `data/manifest.csv`;
- `data/manifest.informe.json`, con los duplicados eliminados, los grupos, las imágenes compartidas entre datasets (que se excluyen de la validación externa) y el conteo por partición y por clase.

## 4. Búsqueda de hiperparámetros (mismo presupuesto)

```powershell
foreach ($a in "resnet50","efficientnet_b3","convnext_tiny","cnn_vit","effnet_att_bilstm") {
  python -m potato_blight.tune --config configs/$a.yaml
}
```

- **Algoritmos:** TPE con semilla fija y `MedianPruner`.
- **Presupuesto común:** `tuning.n_trials`, `max_epochs` y `timeout_hours` se definen en `configs/base.yaml` y valen para los cinco modelos. **No lo cambie para un solo modelo**: invalidaría la comparación.
- **Datos usados:** solo el entrenamiento y la validación interna de la partición 0. La prueba no se mira durante la búsqueda.
- **Resultado:** queda en `configs/tuned/<arquitectura>.yaml`, que hereda de la configuración base.
- **Reanudar:** se puede retomar con el mismo `--storage` (`optuna.db`).

## 5. Validación cruzada, comparación y modelo final

```powershell
python -m potato_blight.train --config configs/tuned/resnet50.yaml --mode cv      # 5 particiones agrupadas
python -m potato_blight.compare --metric macro_f1                                 # tras correr los 5 modelos
python -m potato_blight.train --config configs/tuned/resnet50.yaml --mode final --cv-parent-run-id <run padre>
python -m potato_blight.register --run-id <run del modelo final>
```

**En cada partición:**

- **Prueba:** la partición k.
- **Validación interna:** la partición k + 1. Sirve para el early stopping (por macro-F1) y para calibrar la temperatura.
- **Entrenamiento:** el resto de las particiones.
- **Validación externa:** cada dataset con rol `validacion_externa`, sin los grupos compartidos con el entrenamiento.

**Lo que se registra:**

- métricas por partición y por clase;
- calibración (ECE antes y después);
- curvas ROC y precisión-exhaustividad;
- `evaluation.json` y `predictions.csv`;
- el modelo (`model/model.pt` y `model/model_config.json`).

**`compare`:**

- aplica Friedman y Wilcoxon con corrección de Holm sobre los bloques (partición × escenario);
- aplica McNemar, DeLong y bootstrap sobre las predicciones fuera de partición;
- deja el resultado en un run `comparison`, que muestra la pestaña **Comparación estadística** del laboratorio.

## 6. Google Colab (búsquedas largas)

Use `notebooks/02_entrenamiento_colab.ipynb`, que guarda el MLflow en Google Drive. Al terminar, en el equipo donde corre la aplicación:

```powershell
python -m potato_blight.sync_runs --origen sqlite:///G:/MiUnidad/papasana/mlflow.db --destino http://127.0.0.1:5000
python -m potato_blight.register --run-id <run final copiado>
```

`sync_runs` copia lo siguiente y no duplica lo que ya existe:

- parámetros;
- el historial completo de métricas;
- etiquetas;
- artefactos;
- la jerarquía de validación cruzada.

## 7. Poner un modelo en producción (cuatro ojos)

1. **Investigador**, en Laboratorio de modelos:
   - **Sincronizar con MLflow**;
   - revisar el **Detalle** (métricas, curvas, calibración) y la **Comparación estadística**;
   - pulsar **Promover** y escribir el motivo.
2. **Administrador** (otra persona): **Promociones → Aprobar**. La aplicación:
   - mueve el alias `production` en MLflow;
   - pide a ml-service que recargue el modelo;
   - comprueba que cargó la versión correcta.

   Si algo falla, restaura el alias anterior y la solicitud queda **Fallida**.
3. **Rollback:** el botón **Rollback** de una versión que estuvo en producción, o del modelo DEMO para retirar el entrenado, sigue el mismo circuito de solicitud y aprobación.

Todo queda en la bitácora: quién solicitó, quién aprobó, el modelo anterior y el nuevo, y el motivo.

## 8. Explicabilidad fuera de línea

`notebooks/04_explicabilidad.ipynb` calcula, para el modelo de un run:

- **Grad-CAM;**
- **estabilidad:** correlación del mapa ante ruido, cambios de brillo y desplazamientos;
- **relevancia:** fracción del mapa dentro de la lesión anotada;
- **atención del modelo H2;**
- **SHAP:** requiere `pip install -e ".[explain]"`. Es costoso, así que use una muestra pequeña.

## 9. Formato del modelo

`model/model_config.json` contiene:

- la arquitectura;
- las clases;
- `img_size`, `mean` y `std`;
- los hiperparámetros;
- la `temperature`;
- `label_scheme` = `sintoma` y la marca `smoke_test`.

ml-service reconstruye la red con el mismo código (`potato_blight.models`, copiado al construir su imagen) y carga `model.pt` con `weights_only=True`, sin pickles arbitrarios. El preprocesamiento de evaluación (lado corto a `img_size / 0.875` y recorte central) es el mismo en el entrenamiento y en la producción.
