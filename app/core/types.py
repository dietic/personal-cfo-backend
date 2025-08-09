from sqlalchemy import String, TypeDecorator
from sqlalchemy.dialects import sqlite, postgresql
import uuid


class GUID(TypeDecorator):
    """
    Platform-independent GUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses
    String(36) to store string representation of UUID.
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            # Use native UUID that returns/accepts uuid.UUID objects
            return dialect.type_descriptor(postgresql.UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            # Ensure we bind uuid.UUID objects for Postgres UUID
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        else:
            # Store as string in SQLite and others
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if dialect.name == 'postgresql':
            # Already a uuid.UUID when as_uuid=True
            return value
        else:
            # Convert back to uuid.UUID from string
            return value if isinstance(value, uuid.UUID) else uuid.UUID(value)
