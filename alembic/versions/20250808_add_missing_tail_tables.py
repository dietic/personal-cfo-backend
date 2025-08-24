"""add missing tail tables

Revision ID: tail_tables
Revises: init_base
Create Date: 2025-08-08 01:10:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.types import GUID

# revision identifiers, used by Alembic.
revision: str = "tail_tables"
down_revision: Union[str, None] = "init_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_NOW = sa.text("now()")


def upgrade() -> None:
    # user_excluded_keywords
    op.create_table(
        "user_excluded_keywords",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("keyword_normalized", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "keyword_normalized", name="uq_user_excluded_keyword_normalized"),
    )

    # budgets
    op.create_table(
        "budgets",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # recurring_services
    op.create_table(
        "recurring_services",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("reminder_days", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # user_keyword_rules
    op.create_table(
        "user_keyword_rules",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("category_id", GUID(), nullable=True),
        sa.Column("include_keywords", sa.Text(), nullable=True),
        sa.Column("exclude_keywords", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("user_keyword_rules")
    op.drop_table("recurring_services")
    op.drop_table("budgets")
    op.drop_table("user_excluded_keywords")
