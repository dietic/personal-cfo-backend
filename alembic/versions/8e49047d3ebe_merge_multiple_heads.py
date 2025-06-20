"""merge_multiple_heads

Revision ID: 8e49047d3ebe
Revises: add_bank_providers_2025, cbc47a4a05fc, f8bc87e74a05
Create Date: 2025-06-19 20:34:23.782434

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e49047d3ebe'
down_revision: Union[str, None] = ('add_bank_providers_2025', 'cbc47a4a05fc', 'f8bc87e74a05')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
