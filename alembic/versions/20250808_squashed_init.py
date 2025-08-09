"""squashed_init baseline

Revision ID: 20250808_squashed_init
Revises:
Create Date: 2025-08-08 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.core.types import GUID

# revision identifiers, used by Alembic.
revision: str = "20250808_squashed_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reusable defaults
DEFAULT_NOW = sa.text("now()")


def upgrade() -> None:
    # Pre-create enums idempotently using DO blocks to avoid duplicate errors
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currencyenum') THEN
                CREATE TYPE currencyenum AS ENUM ('USD','PEN','EUR','GBP');
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'timezoneenum') THEN
                CREATE TYPE timezoneenum AS ENUM (
                    'UTC-8 (Pacific Time)',
                    'UTC-7 (Mountain Time)',
                    'UTC-6 (Central Time)',
                    'UTC-5 (Eastern Time)',
                    'UTC-3 (Argentina Time)',
                    'UTC+0 (London Time)',
                    'UTC+1 (Central European Time)'
                );
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alerttype') THEN
                CREATE TYPE alerttype AS ENUM (
                    'spending_limit',
                    'merchant_watch',
                    'category_budget',
                    'unusual_spending',
                    'large_transaction',
                    'new_merchant',
                    'budget_exceeded'
                );
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'alertseverity') THEN
                CREATE TYPE alertseverity AS ENUM ('low','medium','high');
            END IF;
        END $$;
        """
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("first_name", sa.String(), nullable=True),
        sa.Column("last_name", sa.String(), nullable=True),
        sa.Column("phone_number", sa.String(), nullable=True),
        sa.Column("profile_picture_url", sa.String(), nullable=True),
        # Use plain String at creation time to avoid implicit ENUM CREATE TYPE
        sa.Column("preferred_currency", sa.String(length=3), nullable=True),
        sa.Column("timezone", sa.String(), nullable=True),
        sa.Column("budget_alerts_enabled", sa.Boolean(), nullable=True),
        sa.Column("payment_reminders_enabled", sa.Boolean(), nullable=True),
        sa.Column("transaction_alerts_enabled", sa.Boolean(), nullable=True),
        sa.Column("weekly_summary_enabled", sa.Boolean(), nullable=True),
        sa.Column("monthly_reports_enabled", sa.Boolean(), nullable=True),
        sa.Column("email_notifications_enabled", sa.Boolean(), nullable=True),
        sa.Column("push_notifications_enabled", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    # bank_providers
    op.create_table(
        "bank_providers",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=False),
        sa.Column("country_name", sa.String(), nullable=False),
        sa.Column("logo_url", sa.String(), nullable=True),
        sa.Column("website", sa.String(), nullable=True),
        sa.Column("color_primary", sa.String(), nullable=True),
        sa.Column("color_secondary", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_popular", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # cards
    op.create_table(
        "cards",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("card_name", sa.String(), nullable=False),
        sa.Column("payment_due_date", sa.Date(), nullable=True),
        sa.Column("bank_provider_id", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["bank_provider_id"], ["bank_providers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # statements
    op.create_table(
        "statements",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("statement_month", sa.Date(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("processing_message", sa.String(), nullable=True),
        sa.Column("transactions_count", sa.Integer(), nullable=True),
        sa.Column("extraction_method", sa.String(), nullable=True),
        sa.Column("extraction_status", sa.String(), nullable=True),
        sa.Column("categorization_status", sa.String(), nullable=True),
        sa.Column("extraction_retries", sa.Integer(), nullable=True),
        sa.Column("categorization_retries", sa.Integer(), nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=True),
        sa.Column("processed_transactions", sa.Text(), nullable=True),
        sa.Column("ai_insights", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # transactions
    op.create_table(
        "transactions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("card_id", GUID(), nullable=False),
        sa.Column("statement_id", GUID(), nullable=True),
        sa.Column("merchant", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("tags", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("ai_confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["card_id"], ["cards.id"]),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # categories
    op.create_table(
        "categories",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # category_keywords
    op.create_table(
        "category_keywords",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("category_id", GUID(), nullable=False),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        sa.Column("statement_id", GUID(), nullable=True),
        # Use String initially; convert to ENUM after table creation
        sa.Column("alert_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=DEFAULT_NOW, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["statement_id"], ["statements.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # After creating tables, alter relevant columns to use the pre-created ENUM types.
    op.execute("ALTER TABLE users ALTER COLUMN preferred_currency TYPE currencyenum USING preferred_currency::currencyenum")
    op.execute("ALTER TABLE users ALTER COLUMN timezone TYPE timezoneenum USING timezone::timezoneenum")
    op.execute("ALTER TABLE alerts ALTER COLUMN alert_type TYPE alerttype USING alert_type::alerttype")
    op.execute("ALTER TABLE alerts ALTER COLUMN severity TYPE alertseverity USING severity::alertseverity")



def downgrade() -> None:
    # drop in reverse FK order
    op.drop_table("recurring_services")
    op.drop_table("budgets")
    op.drop_table("user_excluded_keywords")
    op.drop_table("alerts")
    op.drop_table("category_keywords")
    op.drop_table("categories")
    op.drop_table("transactions")
    op.drop_table("statements")
    op.drop_table("cards")
    op.drop_table("bank_providers")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    # Drop enums if they exist
    op.execute("DROP TYPE IF EXISTS alertseverity CASCADE;")
    op.execute("DROP TYPE IF EXISTS alerttype CASCADE;")
    op.execute("DROP TYPE IF EXISTS timezoneenum CASCADE;")
    op.execute("DROP TYPE IF EXISTS currencyenum CASCADE;")
