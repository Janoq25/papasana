"""Fase 3: historial de reportes y notificaciones internas (módulo A4).

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10 15:00:00.000000+00:00
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

NEW_SCHEMAS = ["reportes", "notificaciones"]

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_user() -> str:
    return os.environ.get("APP_DB_USER", "papasana_app")


def upgrade() -> None:
    for schema in NEW_SCHEMAS:
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    op.create_table('report_jobs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('report_code', sa.String(length=10), nullable=False),
    sa.Column('format', sa.String(length=5), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('object_key', sa.String(length=255), nullable=True),
    sa.Column('file_name', sa.String(length=160), nullable=True),
    sa.Column('content_type', sa.String(length=120), nullable=True),
    sa.Column('size_bytes', sa.Integer(), nullable=True),
    sa.Column('row_count', sa.Integer(), nullable=True),
    sa.Column('error', sa.String(length=500), nullable=True),
    sa.Column('source', sa.String(length=12), nullable=False),
    sa.Column('requested_by', sa.UUID(), nullable=False),
    sa.Column('download_count', sa.Integer(), nullable=False),
    sa.Column('last_downloaded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['requested_by'], ['seguridad.users.id'], name=op.f('fk_report_jobs_requested_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_report_jobs')),
    schema='reportes'
    )
    op.create_index(op.f('ix_reportes_report_jobs_created_at'), 'report_jobs', ['created_at'], unique=False, schema='reportes')
    op.create_index(op.f('ix_reportes_report_jobs_report_code'), 'report_jobs', ['report_code'], unique=False, schema='reportes')
    op.create_index(op.f('ix_reportes_report_jobs_requested_by'), 'report_jobs', ['requested_by'], unique=False, schema='reportes')
    op.create_index(op.f('ix_reportes_report_jobs_status'), 'report_jobs', ['status'], unique=False, schema='reportes')

    op.create_table('notifications',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.String(length=30), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('link', sa.String(length=255), nullable=True),
    sa.Column('entity_type', sa.String(length=40), nullable=True),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['seguridad.users.id'], name=op.f('fk_notifications_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    schema='notificaciones'
    )
    op.create_index(op.f('ix_notificaciones_notifications_created_at'), 'notifications', ['created_at'], unique=False, schema='notificaciones')
    op.create_index(op.f('ix_notificaciones_notifications_user_id'), 'notifications', ['user_id'], unique=False, schema='notificaciones')

    app = _app_user()
    for schema in NEW_SCHEMAS:
        op.execute(f'GRANT USAGE ON SCHEMA {schema} TO "{app}"')
        op.execute(f'GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA {schema} TO "{app}"')
        op.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO "{app}"')
        op.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT SELECT, INSERT, UPDATE ON TABLES TO "{app}"')
        op.execute(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} GRANT USAGE, SELECT ON SEQUENCES TO "{app}"')


def downgrade() -> None:
    op.drop_index(op.f('ix_notificaciones_notifications_user_id'), table_name='notifications', schema='notificaciones')
    op.drop_index(op.f('ix_notificaciones_notifications_created_at'), table_name='notifications', schema='notificaciones')
    op.drop_table('notifications', schema='notificaciones')
    op.drop_index(op.f('ix_reportes_report_jobs_status'), table_name='report_jobs', schema='reportes')
    op.drop_index(op.f('ix_reportes_report_jobs_requested_by'), table_name='report_jobs', schema='reportes')
    op.drop_index(op.f('ix_reportes_report_jobs_report_code'), table_name='report_jobs', schema='reportes')
    op.drop_index(op.f('ix_reportes_report_jobs_created_at'), table_name='report_jobs', schema='reportes')
    op.drop_table('report_jobs', schema='reportes')
    for schema in reversed(NEW_SCHEMAS):
        op.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
