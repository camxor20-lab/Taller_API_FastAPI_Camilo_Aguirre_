"""usuarios

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 09:53:13.954566

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('usuarios',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('nombre', sa.String(length=100), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('rol', sa.Enum('admin', 'bibliotecario', 'socio', name='rolusuario'), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('intentos_fallidos', sa.Integer(), nullable=False),
    sa.Column('bloqueado_hasta', sa.DateTime(timezone=True), nullable=True),
    sa.Column('socio_id', sa.Integer(), nullable=True),
    sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['socio_id'], ['socios.id'], name=op.f('fk_usuarios_socio_id_socios')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuarios')),
    sa.UniqueConstraint('socio_id', name=op.f('uq_usuarios_socio_id'))
    )
    op.create_index(op.f('ix_usuarios_email'), 'usuarios', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_usuarios_email'), table_name='usuarios')
    op.drop_table('usuarios')
    # Borrar tipo ENUM rolusuario de PostgreSQL
    sa.Enum(name="rolusuario").drop(op.get_bind(), checkfirst=True)
