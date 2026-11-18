"""Prepara lo que necesita el servidor de MLflow (lo ejecuta el servicio `migrate`, con el usuario propietario).

- Rol `mlflow` (contraseña MLFLOW_DB_PASSWORD) y base de datos `mlflow` de su propiedad: MLflow crea y migra sus
  propias tablas al arrancar, aislado de los datos de la aplicación.
- Bucket `mlflow` en MinIO para los artefactos (el servidor los sirve; los clientes no reciben credenciales).

Uso:  python -m app.seed.mlflow_init
"""

import logging
import os
import time

import psycopg
from psycopg import sql

log = logging.getLogger("papasana.seed")
ROLE = DB = "mlflow"
BUCKET = "mlflow"


def ensure_database(owner_url: str, password: str) -> dict:
    url = owner_url.replace("postgresql+psycopg://", "postgresql://")
    out = {}
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(ROLE), sql.Literal(password)))
        out["rol"] = "actualizado" if exists else "creado"
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB,)).fetchone():
            out["base"] = "existente"
        else:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DB), sql.Identifier(ROLE)))
            out["base"] = "creada"
    return out


def ensure_bucket(attempts: int = 10) -> bool:
    from app.services.storage_service import get_storage

    storage = get_storage()
    for i in range(attempts):
        try:
            storage.ensure_bucket(BUCKET)
            return True
        except Exception as e:  # MinIO puede tardar en aceptar conexiones
            log.info("MinIO aún no responde (%s); reintento %s/%s", type(e).__name__, i + 1, attempts)
            time.sleep(3)
    return False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    password = os.environ.get("MLFLOW_DB_PASSWORD", "")
    if not password:
        log.warning("MLFLOW_DB_PASSWORD no está definido: se omite la preparación de MLflow (ejecute scripts/init.ps1)")
        return
    log.info("Base de MLflow: %s", ensure_database(os.environ["MIGRATION_DATABASE_URL"], password))
    if not ensure_bucket():
        raise SystemExit("MinIO no responde: no se pudo crear el bucket de artefactos de MLflow")
    log.info("Bucket de artefactos de MLflow listo: %s", BUCKET)


if __name__ == "__main__":
    main()
