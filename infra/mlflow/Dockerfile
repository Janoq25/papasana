# Servidor de MLflow (tracking + Model Registry). Metadatos en PostgreSQL (base `mlflow`, rol propio) y
# artefactos en MinIO (bucket `mlflow`), servidos por el propio servidor: los clientes no necesitan credenciales
# de MinIO (D-51).
FROM python:3.12-slim
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONUNBUFFERED=1
RUN pip install "mlflow==3.18.*" "psycopg2-binary>=2.9" "psycopg[binary]>=3.2" "boto3>=1.34"
RUN useradd --create-home --uid 1000 mlflow
USER mlflow
WORKDIR /home/mlflow
EXPOSE 5000
