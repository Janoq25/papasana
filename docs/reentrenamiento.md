# Entrenamiento reproducible de PapaSana

Esta actualización del 18 de noviembre de 2026 prepara y ejecuta un piloto real en la GPU local. El objetivo es comprobar los datos, medir el entrenamiento y producir un candidato trazable antes de ejecutar la comparación científica completa. El piloto no demuestra superioridad entre arquitecturas ni sustituye la validación externa y prospectiva.

## Fuentes públicas seleccionadas

PlantVillage se mantiene como conjunto de desarrollo, limitado a las imágenes RGB de papa. Se descargaron 2152 imágenes: 152 sanas, 1000 etiquetadas como late blight y 1000 como early blight. Esta última etiqueta se conserva como otra enfermedad foliar, nunca como una etapa del tizón tardío. La publicación oficial del autor declara CC-BY-SA-3.0 en [README_HF.md](https://github.com/spMohanty/PlantVillage-Dataset/blob/7f7ecc7e1eaca78107e3affe7cb5abd9427e139a/README_HF.md). Se conserva atribución, licencia y la condición ShareAlike aplicable a la redistribución de datos adaptados. Su `leaf-map.json` proporciona grupos de hoja; `groups.csv` los conserva en la descarga local.

PlantDoc se mantiene para evaluación externa. Su [LICENSE.txt oficial](https://github.com/pratikkayal/PlantDoc-Dataset/blob/5467f6012d78d1c446145d5f582da6096f852ae8/LICENSE.txt) declara CC-BY-4.0. Se descargaron 222 imágenes de papa. Tras eliminar 5 copias exactas y apartar 9 imágenes de grupos perceptualmente similares con etiquetas contradictorias, quedaron 208: 98 compatibles con tizón tardío y 110 de otra enfermedad foliar. Este subconjunto no contiene hojas sanas. Por tanto, no permite estimar sensibilidad para sanos ni validar íntegramente el clasificador de tres clases en campo. Las coincidencias perceptuales requieren revisión visual antes de reincorporarse.

Ambas verificaciones son documentales y se registraron como realizadas por Codex el 18 de noviembre de 2026; no se atribuyen a una revisión humana. Sustituyen el estado pendiente del registro anterior. Las imágenes no requieren cuenta, tarjeta ni pago. La red solo se necesita para instalar y descargar; la preparación, el entrenamiento y la evaluación posteriores son locales. `source.json` conserva la revisión Git fijada, la ruta original y los hashes de cada imagen. Los nombres locales de PlantDoc evitan caracteres inválidos y colisiones de mayúsculas en Windows.

Los pesos iniciales son [timm/resnet50.a1_in1k](https://huggingface.co/timm/resnet50.a1_in1k), cuya tarjeta declara Apache-2.0. La ejecución guarda una caché local; no utiliza tokens ni una API de inferencia. Las figuras usan [Matplotlib](https://matplotlib.org/stable/project/license.html), con licencia propia basada en PSF y código compatible con BSD, ya usado como dependencia de MLflow y declarado ahora expresamente. No se incorporó ningún servicio de pago.

## Correcciones y configuración de GPU

Faltaba `ml/src/potato_blight/data/`: los scripts y las pruebas lo importaban, pero la regla `data/` de `ml/.gitignore` también ignoraba ese código. Se restauraron el registro, el índice, los hashes, la agrupación, las particiones, la carga de imágenes y los fixtures. La regla se limita ahora a `/data/`, donde siguen excluyéndose las imágenes y los pesos. También se corrigió la herencia recursiva de configuraciones, necesaria para cargar perfiles ajustados que heredan de otros perfiles.

El equipo comprobado tiene una NVIDIA GeForce RTX 3050 Laptop GPU de 4 GB, 12 procesadores lógicos y aproximadamente 23,4 GiB de RAM. La documentación anterior asumía 6 GB de VRAM. Se creó un entorno aislado Python 3.12 en `C:\Users\lener\.venvs\papasana312`, con PyTorch 2.7.1 y torchvision 0.22.1 para CUDA 12.8. No se necesita Docker para entrenar ni un MLflow remoto.

Los perfiles `*_laptop.yaml` reducen los lotes físicos: ResNet50, ConvNeXt y los híbridos usan 8 imágenes; EfficientNet-B3 usa 4. La acumulación de gradientes mantiene un lote nominal de 32. Se añade calentamiento del clasificador durante 2 épocas, ajuste posterior del backbone con una tasa menor, recorte de norma de gradientes, precisión mixta y comprobación explícita de CUDA. El perfil falla si CUDA no está disponible, en lugar de cambiar silenciosamente a CPU.

Se eligió el equipo local para este piloto por disponibilidad y continuidad. La [FAQ oficial de Colab](https://research.google.com/colaboratory/faq.html) indica que el tipo de GPU y los límites gratuitos son variables. No se ha ejecutado el mismo trabajo en una sesión de Colab; por tanto, no hay una comparación empírica de velocidad entre ambos. La duración y la memoria reales de cada entrenamiento quedan en MLflow.

## Repetir la preparación y el piloto

Desde PowerShell, en la carpeta `ml/`:

```powershell
$python = "$env:USERPROFILE\.venvs\papasana312\Scripts\python.exe"
$env:MLFLOW_TRACKING_URI = "sqlite:///" + ((Join-Path $PWD 'mlflow.db') -replace '\\','/')
$env:MLFLOW_ENABLE_TELEMETRY = 'false'
$env:MLFLOW_DISABLE_AGENT_HINT = '1'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:HF_HUB_DISABLE_XET = '1'
$env:HF_HOME = Join-Path $PWD 'data\cache\huggingface'
$env:OMP_NUM_THREADS = '4'
$env:MKL_NUM_THREADS = '4'

& $python -m potato_blight.download_public --destination data/raw
& $python -m potato_blight.prepare --config configs/base.yaml
& $python -m potato_blight.eda --manifest data/manifest.csv --output data/eda
& $python -m potato_blight.pilot --config configs/resnet50_laptop.yaml --output data/piloto-resnet50
& $python -m potato_blight.report_pilot
```

La descarga es idempotente y comprueba los blobs de la revisión fijada. El manifest valida además SHA-256 contra la procedencia guardada. Los grupos con etiquetas contradictorias quedan listados en `manifest.informe.json`. El EDA produce tablas CSV y figuras de 600 DPI con cantidades reales, incluido el flujo de preparación.

El piloto compara dos perfiles de ResNet50 sobre los mismos grupos: el ajuste de referencia y el progresivo. Selecciona únicamente por F1-macro de validación interna, sin consultar el test ni PlantDoc durante esa selección. Después entrena con todos los folds de desarrollo salvo el fold interno de validación y evalúa PlantDoc una vez. Guarda pesos, configuración y `resultados.json` en `data/piloto-resnet50`. El candidato no se promueve automáticamente a la aplicación.

## Comparación científica completa

El flujo previo buscaba hiperparámetros en el fold 0 y los reutilizaba en todos los folds. Esos hiperparámetros habían visto imágenes que después podían aparecer como prueba de otro fold. Para estimar el procedimiento de selección se incorpora `potato_blight.nested`: cinco folds externos y tres internos dentro de cada conjunto externo de desarrollo, con una búsqueda Optuna independiente por fold externo.

```powershell
foreach ($profile in 'resnet50_nested_laptop','efficientnet_b3_laptop','convnext_tiny_laptop','cnn_vit_laptop','effnet_att_bilstm_laptop') {
  & $python -m potato_blight.nested --config "configs/$profile.yaml"
}
& $python -m potato_blight.compare --experiment papasana-nested-gpu
```

Cada prueba externa del fold se evalúa una sola vez después de la selección interna. El reajuste reserva un fold interno para early stopping y calibración; no utiliza la prueba externa. PlantDoc queda fuera de toda esta búsqueda. Las configuraciones elegidas se guardan por fold junto con una huella del manifest y de la configuración. Los estudios persistidos no mezclan folds y no añaden intentos por encima del presupuesto configurado al reanudarse. No hay reanudación de una época interrumpida: se conserva el registro y se reinicia ese entrenamiento.

La comparación completa es un trabajo distinto y considerablemente mayor que el piloto. Está implementada y cubierta por pruebas de aislamiento, pero no debe describirse como ejecutada a partir de los resultados del piloto. No deben combinarse sus métricas con las de la validación convencional previa, otros manifests o pruebas sintéticas. Antes del artículo también se necesita revisar las unidades estadísticas, ampliar la evaluación externa con hojas sanas y obtener revisión agronómica. Las reglas climáticas y la app no se validan mediante este entrenamiento.

## Verificación

Se ejecutaron las 31 pruebas del módulo `ml/`, incluidas las cinco arquitecturas, serialización, Grad-CAM, datos, aislamiento anidado y el recorrido sintético de MLflow: todas pasaron. Ruff pasó sobre `src` y `tests`. Hay avisos de deprecación de dependencias, sin fallos. Las métricas sintéticas se mantienen separadas de los resultados reales. No hubo cambios de esquema ni se ejecutaron las pruebas de frontend, backend o servicios Docker, que no se modificaron.

## Comprobación explícita de CUDA

Desde la raíz de PapaSana se puede ejecutar `powershell -ExecutionPolicy Bypass -File scripts/train-gpu.ps1 -Mode check`. El comprobador ejecuta forward, backward y pasos de AdamW en `cuda:0`, y guarda dispositivo del modelo, entradas y pérdida en `ml/data/gpu-check.json`. El modo `pilot` repite esta comprobación antes de entrenar. Las operaciones de lectura y decodificación de imágenes siguen usando CPU.

La revisión final filtró los IDs de `leaf-map.json` por cultivo y clase: 79 nombres de archivo también existían en otras especies. Los primeros runs se marcaron como invalidados y no se usan como resultados. En el manifest corregido hay 538 IDs de hoja de papa, ninguno repartido entre folds.

Se corrigió también el F1 de una clase presente pero nunca predicha: debe contar como cero en la media y no omitirse. Se añadió una regresión contra scikit-learn y se reinició el piloto con esta corrección. Los runs anteriores no se usan como resultados definitivos.

## Resultados del piloto definitivo

La ejecución `papasana-piloto-gpu-20261118-v3` eligió el perfil de referencia: F1 interno 0,9688 frente a 0,8856 del progresivo. No se observó una mejora con el calentamiento propuesto dentro del presupuesto del piloto. El candidato se reentrenó con 1724 imágenes y validó con 428, siempre por hoja; su mejor checkpoint fue el de la época 4.

El candidato final obtuvo F1 interno 0,9793 y exactitud interna 0,9930. En las 208 imágenes externas de PlantDoc obtuvo exactitud 0,5769 y F1 0,5941, promediado sobre las dos clases con soporte. Estos F1 no deben presentarse como una comparación homogénea de tres clases: PlantDoc no aporta hojas sanas de papa. La sensibilidad para síntomas compatibles con tizón tardío fue 0,5510. La calibración ajustada en laboratorio tampoco se transfirió bien: ECE externo 0,2788 frente a 0,2314 sin escalado.

El resultado no demuestra que el modelo esté validado para campo. Se conserva como candidato experimental. Una siguiente investigación necesita datos de campo independientes para desarrollo, una prueba externa nueva reservada y validación agronómica; no debe seleccionar hiperparámetros mirando reiteradamente este mismo PlantDoc. La comparación anidada de cinco arquitecturas sigue pendiente de ejecución.

Los tres entrenamientos reales del piloto sumaron aproximadamente 405 segundos (6,75 minutos), sin incluir instalación, preparación ni descargas. El entrenamiento final consumió 175 segundos y unos 874 MB de memoria CUDA asignada por PyTorch. NVIDIA registró además uso activo de GPU y memoria total del proceso en `ml/data/gpu-usage.csv`. No se ha medido una sesión de Colab para afirmar cuál es más rápida.

Pesos, configuración, evaluación, curvas y verificación de recarga CUDA se guardaron en `ml/data/piloto-resnet50/`. El registro final de MLflow es `ee54f0fb37c84c558c1d91b364d2f124`. La app no se ha conectado a ese registro ni se ha promovido el candidato.
