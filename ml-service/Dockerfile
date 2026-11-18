# Contexto de construcción: la RAÍZ del repositorio (docker-compose.yml), para copiar las arquitecturas de
# ml/src/potato_blight/models: el servicio construye la red con el mismo código que la entrenó (D-51).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TORCH_HOME=/opt/torch \
    OMP_NUM_THREADS=2 \
    MODEL_CACHE_DIR=/tmp/papasana-modelos

WORKDIR /app
COPY ml-service/requirements.txt ml-service/requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

# Pesos ImageNet de torchvision (BSD-3-Clause) para el modelo DEMO: el contenedor no descarga nada al arrancar.
RUN python -c "from torchvision.models import resnet50, ResNet50_Weights; resnet50(weights=ResNet50_Weights.IMAGENET1K_V2)"

COPY ml/src/potato_blight/__init__.py potato_blight/__init__.py
COPY ml/src/potato_blight/models potato_blight/models
COPY ml-service/ .
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
