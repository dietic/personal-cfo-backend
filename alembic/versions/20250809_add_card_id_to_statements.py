"""add card_id to statements

Revision ID: card_id_stmt
Revises: init_base
Create Date: 2025-08-09 00:00:00.000000

"""
from typing import Sequence, Union
import sys
import os

# Ensure app is importable when running alembic
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from alembic import op
import sqlalchemy as sa
from app.core.types import GUID

# revision identifiers, used by Alembic.
revision: str = 'card_id_stmt'
down_revision: Union[str, None] = 'init_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('statements') as batch_op:
        batch_op.add_column(sa.Column('card_id', GUID(), nullable=True))
        batch_op.create_foreign_key('fk_statements_card', 'cards', ['card_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('statements') as batch_op:
        batch_op.drop_constraint('fk_statements_card', type_='foreignkey')
        batch_op.drop_column('card_id')
