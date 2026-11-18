# Comparación de cuatro modelos en GPU

El usuario solicitó cuatro arquitecturas en total, priorizando tiempos cortos sin rebajar la calidad observada. Esta comparación del 18 de noviembre de 2026 conserva ResNet50 y añade EfficientNetV2-B0, MobileNetV4 Conv Medium y EfficientViT-B1. Sustituye el alcance de cinco modelos para esta ejecución concreta; las arquitecturas anteriores siguen disponibles y sus pesos no se eliminan.

## Selección y coste

Se eligieron variantes intermedias o ligeras con pesos ImageNet y soporte en la instalación existente de timm. No se añadieron dependencias ni cuentas externas. Todas las fichas oficiales declaran Apache-2.0; se conservan la revisión fijada, la ficha y su SHA-256 en `ml/data/comparacion-cuatro/model_sources.json` y `sources/`.

- [ResNet50 A1](https://huggingface.co/timm/resnet50.a1_in1k): referencia existente; revisión `767268603ca0cb0bfe326fa87277f19c419566ef`.
- [EfficientNetV2-B0](https://huggingface.co/timm/tf_efficientnetv2_b0.in1k): bloques fused-MBConv y MBConv; revisión `30b1df5883752d711e047538d9b01db797782818`.
- [MobileNetV4 Conv Medium](https://huggingface.co/timm/mobilenetv4_conv_medium.e500_r224_in1k): CNN móvil de capacidad intermedia; revisión `02a09fbfb82b289e871ba8255f9da58c056fb13b`.
- [EfficientViT-B1](https://huggingface.co/timm/efficientvit_b1.r224_in1k): atención lineal multiescala; revisión `cebc58510738e196c3cce3c3077dc8737973b7ba`.

Las tres alternativas tienen menor cálculo publicado que ResNet50, pero eso no garantiza menor tiempo en esta GPU. El programa mide pasos sintéticos, tiempo de entrenamiento real, memoria y tamaño de los pesos. Los parámetros registrados corresponden a un clasificador de tres clases; son menores que los de las fichas ImageNet de mil clases. Las descargas son públicas y gratuitas, sin tokens ni tarjetas. El cálculo se ejecuta en la RTX 3050 local. No hay inferencia mediante API de pago.

## Protocolo común

Todos usan el mismo manifest SHA-256 `3ef95f9563afbf7f8584d7735ae232f1c565224b2b7a1c1fb853b3b7ba3e7924`, con 1724 imágenes de entrenamiento y 428 de validación interna. La separación se mantiene por hoja: ninguna hoja cruza los conjuntos. Solo PlantVillage participa en el desarrollo.

Se vuelve a entrenar ResNet50 con este presupuesto común para poder comparar con las alternativas, conservando su checkpoint previo. Los cuatro perfiles usan resolución de 224 píxeles, transformaciones comunes, AdamW con tasa inicial 0,0003, precisión mixta, lote físico 16 y acumulación de dos pasos (lote nominal 32). El máximo son 16 épocas, con parada tras cuatro sin mejora y un límite adicional de 15 minutos por entrenamiento. Se conservan los pesos del mejor F1 de validación. El código exige CUDA y registra el dispositivo; no cambia silenciosamente a CPU. Los trabajos se ejecutan uno a uno para compartir los 4 GB de VRAM.

No se replica el entrenamiento ImageNet original de cada publicación. Es fine-tuning sobre hojas de papa con un protocolo común. Tampoco es la validación anidada completa ni una demostración estadística de no inferioridad: es un holdout agrupado para comparar candidatos de forma rápida.

## Precisión numérica y recuperación

ResNet50 y EfficientNetV2-B0 terminaron con FP16. El primer intento de MobileNetV4 con FP16 generó logits no finitos; se descartó y no aporta métricas a la comparación. La RTX 3050 admite BF16 y se configuró BF16 para MobileNetV4 y EfficientViT. Cambia el rango numérico de AMP; los pesos guardados siguen en float32. Los perfiles registran `train.amp_dtype`, y la evaluación usa la misma precisión que el entrenamiento. No se interpretan estas ejecuciones como una comparación con precisión idéntica.

Antes de la corrección se guardaron el código, contrato y resultados originales en `provenance_fp16/`. Para conservar los dos trabajos válidos se verificaron el SHA-256 del manifest, la equivalencia de sus configuraciones FP16 y el SHA-256 de ambos checkpoints. La migración explícita está en `precision_migration.json`; cada resultado conserva `training_fingerprint` y la huella de reanudación. No se modificaron los pesos ni métricas ya obtenidos. Las reanudaciones ordinarias siguen exigiendo una huella idéntica.

## Selección sin usar PlantDoc

Antes de evaluar PlantDoc se guarda `selection_before_external.json`. La regla busca el candidato más rápido cuyo F1 interno no sea menor que el máximo entre la referencia ResNet50 de esta ejecución y el candidato ResNet50 previo. Si ninguno lo cumple, se conserva el candidato previo. También se informa por separado el de mayor F1 y el de menor tiempo.

Esta regla protege el F1 observado en ese conjunto; no garantiza calidad equivalente en toda la población ni en campo. PlantDoc ya se observó en el piloto anterior y no contiene hojas sanas de papa. Sus 208 imágenes se usan después, una vez por candidato, para evaluación descriptiva de las dos clases presentes. No se elige arquitectura ni hiperparámetros mirando ese resultado. Antes de una afirmación de calidad de campo hacen falta evaluación independiente nueva y revisión agronómica.

## Archivos y repetición

Desde la raíz de PapaSana puede usar `powershell -ExecutionPolicy Bypass -File scripts/train-gpu.ps1 -Mode four`. También, desde la carpeta `ml/`, con el entorno CUDA configurado como se indica en `docs/reentrenamiento.md`:

```powershell
& "$env:USERPROFILE\.venvs\papasana312\Scripts\python.exe" -m potato_blight.four_models
```

Cada arquitectura produce en `data/comparacion-cuatro/<arquitectura>/` los pesos, configuración, métricas, evaluación externa, predicciones y verificación de recarga y Grad-CAM en CUDA. El fichero `training.json` permite reutilizar candidatos terminados si código, configuración y manifest mantienen la misma huella. Una época interrumpida se reinicia; no se presenta como reanudación del optimizador. Si cambia la huella se exige otro directorio de salida para evitar mezclar experimentos.

El resumen está en `results.json` y `comparison.csv`; las figuras de 600 DPI son `comparison.png` y `learning_curves.png`. Para regenerarlas sin entrenar:

```powershell
& "$env:USERPROFILE\.venvs\papasana312\Scripts\python.exe" -m potato_blight.four_models --report-only
```

Los cuatro candidatos quedan en MLflow local (`papasana-cuatro-gpu-20261118`), sin promoción automática ni cambios de esquema. La selección y los resultados reales deben revisarse antes de conectarlos a la aplicación.

## Verificación previa

Pasaron las 41 pruebas del módulo ML, incluyendo las ocho arquitecturas admitidas, la serialización de las tres nuevas, Grad-CAM y las regresiones que excluyen PlantDoc de la selección y evitan elegir un modelo más rápido con F1 interno inferior. La regresión CUDA comprueba que BF16 conserva salidas finitas cuando FP16 desborda, y que no se calculan métricas con logits inválidos. Ruff pasó. Los avisos de deprecación de dependencias existentes no produjeron fallos. Las pruebas sintéticas no se usan como resultados agronómicos.

## Resultados ejecutados (18 de noviembre de 2026)

Los cuatro trabajos terminaron en la NVIDIA GeForce RTX 3050 Laptop GPU de 4 GB. F1 es macro: tres clases en validación interna y solo las dos clases presentes en PlantDoc. Los tiempos son los registrados por el entrenador para cada ajuste exitoso.

- **ResNet50**: F1 interno 0.993108; PlantDoc 0.579046; 2 min 40 s; mejor época 4; pico de memoria asignada por PyTorch 1216 MB; run `6056304c051f4e7f9fd5e85e6ace85e9`.
- **EfficientNetV2-B0**: F1 interno 0.993317; PlantDoc 0.504314; 2 min 58 s; mejor época 7; pico de memoria asignada por PyTorch 629 MB; run `09cbc33324d349c2894d880e89a19170`.
- **MobileNetV4 Conv Medium**: F1 interno 0.986667; PlantDoc 0.584878; 2 min 30 s; mejor época 5; pico de memoria asignada por PyTorch 575 MB; run `6e2e1bbdf4cd435bb12917736359432c`.
- **EfficientViT-B1**: F1 interno 1.000000; PlantDoc 0.573069; 4 min 30 s; mejor época 11; pico de memoria asignada por PyTorch 783 MB; run `d6c5da9c6baa4d378d501cb8e89afc52`.

La regla fijada antes de observar estos resultados externos seleccionó **ResNet50**: es el de menor tiempo entre los candidatos con F1 interno al menos igual a la referencia observada (0,993108). MobileNetV4 fue el más rápido en total, pero su F1 interno fue menor. EfficientViT obtuvo el mayor F1 interno y requiere unos 4,5 minutos con este perfil.

El F1 1,000 de EfficientViT corresponde a 428 imágenes internas y no demuestra generalización perfecta. La caída de los cuatro modelos en PlantDoc (F1 0,504–0,585) sigue siendo el hallazgo principal: cambiar la arquitectura no resolvió el salto de fotografías de laboratorio a fotografías de campo. La comparación requiere validación anidada y un conjunto independiente de campo con hojas sanas antes de afirmar calidad agronómica. PlantDoc ya fue observado y no debe reutilizarse para ajustar modelos y presentarse después como prueba independiente.

La suma de tiempos de los cuatro ajustes exitosos fue 12.64 minutos. Descargas, pruebas, pasos sintéticos, evaluación posterior y el intento FP16 fallido se contabilizan aparte. Se conservaron los pesos previos; no se cambió el modelo activo de la aplicación ni el esquema de base de datos.

La recarga de los cuatro checkpoints y Grad-CAM 7×7 pasaron en CUDA. `real_checkpoint_validation.json` registra además la reproducción de 16 predicciones externas ya guardadas por cada checkpoint: es una comprobación de serialización, sin una nueva elección de modelos. Las figuras `comparison.png` y `learning_curves.png` se revisaron visualmente.
