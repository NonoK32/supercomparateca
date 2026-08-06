"""verificacion de email

Añade `usuarios.email_verificado`. Sin verificar no se puede iniciar sesion.

Los usuarios que YA EXISTEN quedan marcados como verificados: se registraron
cuando no habia verificacion, asi que bloquearles la entrada por un requisito
que no existia cuando entraron seria echarles de su propia cuenta. Los nuevos
nacen sin verificar.

Por eso la columna se crea en tres pasos (nullable -> rellenar -> not null) en
vez de con un server_default: un default dejaria a los nuevos en el mismo valor
que a los antiguos, y aqui hacen falta valores distintos.

Revision ID: 6c76fab324c6
Revises: 01233e7e156c
Create Date: 2026-08-06 18:41:12.339820

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6c76fab324c6'
down_revision: str | Sequence[str] | None = '01233e7e156c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verificado', sa.Boolean(), nullable=True))

    # Los que ya estaban dentro, verificados.
    op.execute('UPDATE usuarios SET email_verificado = true')

    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.alter_column('email_verificado', nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_column('email_verificado')
