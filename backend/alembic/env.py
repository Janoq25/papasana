import os

from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registra los modelos en Base.metadata)
from app.db.base import SCHEMAS, Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    # Prioridad: -x url=... > MIGRATION_DATABASE_URL (usuario propietario)
    x_args = context.get_x_argument(as_dictionary=True)
    url = x_args.get("url") or config.attributes.get("url") or os.environ.get("MIGRATION_DATABASE_URL")
    if not url:
        raise RuntimeError("Defina MIGRATION_DATABASE_URL para ejecutar migraciones.")
    return url


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in SCHEMAS
    return True


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      include_schemas=True, include_name=include_name)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        engine = create_engine(_url(), poolclass=pool.NullPool)
        with engine.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
        render_item=alembic_helpers.render_item,  # tipos PostGIS (Geometry)
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
