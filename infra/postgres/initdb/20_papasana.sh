#!/bin/bash
# Inicialización de PostgreSQL (solo en el primer arranque del volumen).
# - Crea el usuario de aplicación con privilegios mínimos.
# - Crea la base de pruebas.
# - Instala extensiones en ambas bases.
set -euo pipefail

: "${APP_DB_USER:?Falta APP_DB_USER}"
: "${APP_DB_PASSWORD:?Falta APP_DB_PASSWORD}"
TEST_DB="${POSTGRES_TEST_DB:-papasana_test}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE "${APP_DB_USER}" LOGIN PASSWORD '${APP_DB_PASSWORD}';
    CREATE DATABASE "${TEST_DB}" OWNER "${POSTGRES_USER}";
EOSQL

for db in "$POSTGRES_DB" "$TEST_DB"; do
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$db" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    REVOKE CREATE ON SCHEMA public FROM PUBLIC;
    REVOKE ALL ON DATABASE "${db}" FROM PUBLIC;
    GRANT CONNECT, TEMPORARY ON DATABASE "${db}" TO "${APP_DB_USER}";
    GRANT USAGE ON SCHEMA public TO "${APP_DB_USER}";
EOSQL
done

echo "PapaSana: base de datos inicializada (${POSTGRES_DB}, ${TEST_DB})."
