"""Fase 4: enlace con MLflow, promociones con cuatro ojos y registro de datasets y licencias (A1).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-12 18:00:00.000000+00:00
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_user() -> str:
    return os.environ.get("APP_DB_USER", "papasana_app")


def upgrade() -> None:
    op.add_column('model_versions', sa.Column('mlflow_run_id', sa.String(length=64), nullable=True), schema='ml')
    op.add_column('model_versions', sa.Column('source', sa.String(length=10), server_default='demo', nullable=False),
                  schema='ml')
    op.add_column('model_versions', sa.Column('smoke_test', sa.Boolean(), server_default='false', nullable=False),
                  schema='ml')
    op.add_column('model_versions', sa.Column('train_dataset_ids', postgresql.JSONB(astext_type=sa.Text()),
                                              server_default='[]', nullable=False), schema='ml')
    op.add_column('model_versions', sa.Column('registered_at', sa.DateTime(timezone=True), nullable=True), schema='ml')
    op.add_column('model_versions', sa.Column('synced_at', sa.DateTime(timezone=True), nullable=True), schema='ml')

    op.create_table('model_promotions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('model_version_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('from_stage', sa.String(length=15), nullable=True),
    sa.Column('to_stage', sa.String(length=15), nullable=False),
    sa.Column('previous_model_version_id', sa.Integer(), nullable=True),
    sa.Column('requested_by', sa.UUID(), nullable=False),
    sa.Column('request_reason', sa.Text(), nullable=False),
    sa.Column('decided_by', sa.UUID(), nullable=True),
    sa.Column('decision_reason', sa.Text(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['decided_by'], ['seguridad.users.id'], name=op.f('fk_model_promotions_decided_by_users')),
    sa.ForeignKeyConstraint(['model_version_id'], ['ml.model_versions.id'],
                            name=op.f('fk_model_promotions_model_version_id_model_versions')),
    sa.ForeignKeyConstraint(['previous_model_version_id'], ['ml.model_versions.id'],
                            name=op.f('fk_model_promotions_previous_model_version_id_model_versions')),
    sa.ForeignKeyConstraint(['requested_by'], ['seguridad.users.id'],
                            name=op.f('fk_model_promotions_requested_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_promotions')),
    schema='ml'
    )
    op.create_index(op.f('ix_ml_model_promotions_model_version_id'), 'model_promotions', ['model_version_id'],
                    unique=False, schema='ml')
    op.create_index(op.f('ix_ml_model_promotions_status'), 'model_promotions', ['status'], unique=False, schema='ml')

    op.create_table('datasets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('version', sa.String(length=40), nullable=True),
    sa.Column('source_url', sa.String(length=500), nullable=True),
    sa.Column('license', sa.String(length=200), nullable=True),
    sa.Column('license_url', sa.String(length=500), nullable=True),
    sa.Column('license_status', sa.String(length=15), nullable=False),
    sa.Column('license_notes', sa.Text(), nullable=True),
    sa.Column('license_verified_by', sa.UUID(), nullable=True),
    sa.Column('license_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('citation', sa.Text(), nullable=True),
    sa.Column('conditions', sa.String(length=20), nullable=False),
    sa.Column('label_scheme', sa.String(length=15), nullable=False),
    sa.Column('etiological_confirmation', sa.String(length=10), nullable=False),
    sa.Column('has_group_ids', sa.Boolean(), nullable=False),
    sa.Column('role', sa.String(length=30), nullable=False),
    sa.Column('class_map', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('n_images', sa.Integer(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['seguridad.users.id'], name=op.f('fk_datasets_created_by_users')),
    sa.ForeignKeyConstraint(['license_verified_by'], ['seguridad.users.id'],
                            name=op.f('fk_datasets_license_verified_by_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_datasets')),
    sa.UniqueConstraint('code', name=op.f('uq_datasets_code')),
    schema='ml'
    )
    op.create_index(op.f('ix_ml_datasets_license_status'), 'datasets', ['license_status'], unique=False, schema='ml')

    app = _app_user()
    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ml.datasets TO "{app}"')
    op.execute(f'GRANT SELECT, INSERT, UPDATE ON ml.model_promotions TO "{app}"')
    op.execute(f'REVOKE DELETE, TRUNCATE ON ml.model_promotions FROM "{app}"')
    op.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ml TO "{app}"')


def downgrade() -> None:
    op.drop_index(op.f('ix_ml_datasets_license_status'), table_name='datasets', schema='ml')
    op.drop_table('datasets', schema='ml')
    op.drop_index(op.f('ix_ml_model_promotions_status'), table_name='model_promotions', schema='ml')
    op.drop_index(op.f('ix_ml_model_promotions_model_version_id'), table_name='model_promotions', schema='ml')
    op.drop_table('model_promotions', schema='ml')
    for col in ('synced_at', 'registered_at', 'train_dataset_ids', 'smoke_test', 'source', 'mlflow_run_id'):
        op.drop_column('model_versions', col, schema='ml')
