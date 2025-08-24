"""add waitlist table and billing fields (existing users)

Revision ID: waitlist_fields
Revises: merge_otp
Create Date: 2025-08-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'waitlist_fields'
down_revision = 'merge_otp'
branch_labels = None
depends_on = None

def upgrade():
    # Billing fields (if not already present) - using batch_alter_table for SQLite compat
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('plan_tier', sa.String(), nullable=False, server_default='free'))
        batch_op.add_column(sa.Column('plan_status', sa.String(), nullable=False, server_default='inactive'))
        batch_op.add_column(sa.Column('billing_currency', sa.String(), nullable=False, server_default='PEN'))
        batch_op.add_column(sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('provider_customer_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('provider_subscription_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('last_payment_status', sa.String(), nullable=True))
    # Add index on plan_tier
    op.create_index('ix_users_plan_tier', 'users', ['plan_tier'])

    # Waitlist table
    op.create_table(
        'waitlist_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint('uq_waitlist_email', 'waitlist_entries', ['email'])
    op.create_index('ix_waitlist_entries_email', 'waitlist_entries', ['email'])

    # Remove server defaults (cleanup) so future inserts rely on model defaults
    with op.batch_alter_table('users') as batch_cleanup:
        batch_cleanup.alter_column('plan_tier', server_default=None)
        batch_cleanup.alter_column('plan_status', server_default=None)
        batch_cleanup.alter_column('billing_currency', server_default=None)
        batch_cleanup.alter_column('cancel_at_period_end', server_default=None)

def downgrade():
    op.drop_index('ix_waitlist_entries_email', table_name='waitlist_entries')
    op.drop_constraint('uq_waitlist_email', 'waitlist_entries', type_='unique')
    op.drop_table('waitlist_entries')

    op.drop_index('ix_users_plan_tier', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('plan_tier')
        batch_op.drop_column('plan_status')
        batch_op.drop_column('billing_currency')
        batch_op.drop_column('current_period_end')
        batch_op.drop_column('cancel_at_period_end')
        batch_op.drop_column('provider_customer_id')
        batch_op.drop_column('provider_subscription_id')
        batch_op.drop_column('last_payment_status')
