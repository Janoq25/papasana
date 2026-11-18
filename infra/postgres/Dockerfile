# PostgreSQL 16 oficial (Debian bookworm) + PostGIS 3 + pgvector desde el repositorio PGDG.
# Las imágenes postgis/postgis:16-3.x se basan en bullseye, cuyo repositorio PGDG ya fue archivado.
FROM postgres:16-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-16-postgis-3 \
       postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

COPY initdb/20_papasana.sh /docker-entrypoint-initdb.d/20_papasana.sh
