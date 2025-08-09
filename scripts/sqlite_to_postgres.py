"""
One-off data migration: copy data from existing SQLite DB into a fresh Postgres
DB whose schema was created by Alembic.

Usage:
  python scripts/sqlite_to_postgres.py \
    --sqlite sqlite:////absolute/path/to/personalcfo.db \
    --postgres postgresql+psycopg2://user:pass@host:5432/dbname \
    [--batch-size 1000] [--dry-run] [--truncate]

Notes:
- Run Alembic migrations against Postgres first (empty DB):
    ALEMBIC_CONFIG=alembic.ini DATABASE_URL=postgres://... alembic upgrade head
- This script only reads from SQLite and inserts into Postgres. It preserves IDs
  and timestamps so foreign keys remain valid.
- If Postgres already has rows, use --truncate to clear the target tables first
  (in dependency-safe order).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Iterable, List, Type

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

# Ensure we can import app models
BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.models import (  # type: ignore  # noqa: E402
    User,
    BankProvider,
    Category,
    CategoryKeyword,
    Card,
    Statement,
    Transaction,
    Budget,
    RecurringService,
    Alert,
    UserExcludedKeyword,
)
from app.models.user_keyword_rule import UserKeywordRule  # type: ignore  # noqa: E402

ModelType = Type

# Dependency order (parents before children)
INSERT_ORDER: List[ModelType] = [
    User,
    BankProvider,
    Category,
    CategoryKeyword,
    Card,
    Statement,
    Transaction,
    Budget,
    RecurringService,
    Alert,
    UserExcludedKeyword,
    UserKeywordRule,
]

TRUNCATE_ORDER: List[ModelType] = list(reversed(INSERT_ORDER))

# Timezone enum tokens expected by Postgres enum (and SQLAlchemy)
TZ_M8 = "UTC_MINUS_8"
TZ_M7 = "UTC_MINUS_7"
TZ_M6 = "UTC_MINUS_6"
TZ_M5 = "UTC_MINUS_5"
TZ_M3 = "UTC_MINUS_3"
TZ_P0 = "UTC_PLUS_0"
TZ_P1 = "UTC_PLUS_1"

# Allowed enum values in Postgres
ALLOWED_CURRENCIES = {"USD", "PEN", "EUR", "GBP"}
ALLOWED_TIMEZONES = {TZ_M8, TZ_M7, TZ_M6, TZ_M5, TZ_M3, TZ_P0, TZ_P1}

TIMEZONE_MAP = {
    # Already-correct tokens
    TZ_M8: TZ_M8,
    TZ_M7: TZ_M7,
    TZ_M6: TZ_M6,
    TZ_M5: TZ_M5,
    TZ_M3: TZ_M3,
    TZ_P0: TZ_P0,
    TZ_P1: TZ_P1,
    # Prefixed enum strings
    "TimezoneEnum.UTC_MINUS_8": TZ_M8,
    "TimezoneEnum.UTC_MINUS_7": TZ_M7,
    "TimezoneEnum.UTC_MINUS_6": TZ_M6,
    "TimezoneEnum.UTC_MINUS_5": TZ_M5,
    "TimezoneEnum.UTC_MINUS_3": TZ_M3,
    "TimezoneEnum.UTC_PLUS_0": TZ_P0,
    "TimezoneEnum.UTC_PLUS_1": TZ_P1,
    # Common variants and human labels
    "UTC-8": TZ_M8,
    "UTC-7": TZ_M7,
    "UTC-6": TZ_M6,
    "UTC-5": TZ_M5,
    "UTC-3": TZ_M3,
    "UTC+0": TZ_P0,
    "UTC+1": TZ_P1,
    "UTC-8 (Pacific Time)": TZ_M8,
    "UTC-7 (Mountain Time)": TZ_M7,
    "UTC-6 (Central Time)": TZ_M6,
    "UTC-5 (Eastern Time)": TZ_M5,
    "UTC-3 (Argentina Time)": TZ_M3,
    "UTC+0 (London Time)": TZ_P0,
    "UTC+1 (Central European Time)": TZ_P1,
}

# Allowed alert enums
ALERT_TYPES = {
    "spending_limit",
    "merchant_watch",
    "category_budget",
    "unusual_spending",
    "large_transaction",
    "new_merchant",
    "budget_exceeded",
}
ALERT_SEVERITIES = {"low", "medium", "high"}


def model_label(model: ModelType) -> str:
    return getattr(model, "__tablename__", model.__name__)


def _strip_enum_prefix(value):
    if value is None:
        return None
    # If value looks like 'TimezoneEnum.UTC_MINUS_8' or 'CurrencyEnum.USD'
    if isinstance(value, str) and "." in value and value.split(".", 1)[0].endswith("Enum"):
        return value.split(".", 1)[1]
    # If it's an actual Python Enum, use its value
    try:
        import enum
        if isinstance(value, enum.Enum):
            return value.value
    except Exception:
        pass
    return value


def _normalize_user_row(data: dict) -> dict:
    tz = _strip_enum_prefix(data.get("timezone"))
    if tz:
        mapped = TIMEZONE_MAP.get(tz, tz)
        if mapped in ALLOWED_TIMEZONES:
            data["timezone"] = mapped
        else:
            print(f"[WARN] Unknown timezone '{data.get('timezone')}', setting to NULL")
            data["timezone"] = None
    cur = _strip_enum_prefix(data.get("preferred_currency"))
    if cur and cur not in ALLOWED_CURRENCIES:
        print(f"[WARN] Unknown currency '{data.get('preferred_currency')}', setting to NULL")
        data["preferred_currency"] = None
    else:
        data["preferred_currency"] = cur
    return data


def _normalize_alert_row(data: dict) -> dict:
    at = data.get("alert_type")
    if at and at not in ALERT_TYPES:
        print(f"[WARN] Unknown alert_type '{at}', coercing to 'spending_limit'")
        data["alert_type"] = "spending_limit"
    sev = data.get("severity")
    if sev and sev not in ALERT_SEVERITIES:
        print(f"[WARN] Unknown severity '{sev}', coercing to 'low'")
        data["severity"] = "low"
    return data


def copy_rows(
    src: Session, dst: Session, model: ModelType, batch_size: int = 1000
) -> int:
    """Copy all rows of a model from src to dst. Returns number of inserted rows.

    We construct new ORM instances and explicitly set primary keys and columns
    to preserve identity. If a row with the same primary key already exists on
    the destination, it is skipped.
    """
    table = model.__table__
    pk_cols = [c.name for c in table.primary_key.columns]
    col_names = [c.name for c in table.columns]

    total_inserted = 0

    # Stream results to avoid loading entire table into memory
    query = src.query(model).yield_per(batch_size)
    batch: List[dict] = []
    for row in query:
        data = {col: getattr(row, col) for col in col_names}
        # Normalize legacy enum/text values to match Postgres enums
        if model.__tablename__ == "users":
            data = _normalize_user_row(data)
        elif model.__tablename__ == "alerts":
            data = _normalize_alert_row(data)
        batch.append(data)
        if len(batch) >= batch_size:
            total_inserted += _flush_batch(dst, model, batch, pk_cols)
            batch.clear()

    if batch:
        total_inserted += _flush_batch(dst, model, batch, pk_cols)

    return total_inserted


def _exists(dst: Session, model: ModelType, pk_cols: List[str], data: dict) -> bool:
    if len(pk_cols) != 1:
        # Composite PK not expected here; fall back to insert-try-except path
        return False
    pk = pk_cols[0]
    return dst.query(model).filter(getattr(model, pk) == data[pk]).first() is not None


def _create_obj(model: ModelType, data: dict):
    obj = model()
    for k, v in data.items():
        setattr(obj, k, v)
    return obj


def _insert_individually(dst: Session, model: ModelType, batch: List[dict], pk_cols: List[str]) -> int:
    inserted = 0
    for data in batch:
        try:
            if _exists(dst, model, pk_cols, data):
                continue
            obj = _create_obj(model, data)
            dst.add(obj)
            dst.commit()
            inserted += 1
        except IntegrityError:
            dst.rollback()
            # Skip conflicting row (likely already present due to unique constraint)
            continue
    return inserted


def _flush_batch(dst: Session, model: ModelType, batch: List[dict], pk_cols: List[str]) -> int:
    inserted = 0
    # Optimistic bulk commit first
    try:
        for data in batch:
            if _exists(dst, model, pk_cols, data):
                continue
            obj = _create_obj(model, data)
            dst.add(obj)
            inserted += 1
        dst.commit()
        return inserted
    except IntegrityError:
        dst.rollback()
        # Retry slower, per-row to skip duplicates
        return _insert_individually(dst, model, batch, pk_cols)


def truncate_tables(dst: Session, models: Iterable[ModelType]) -> None:
    for model in models:
        label = model_label(model)
        dst.execute(model.__table__.delete())
        dst.commit()
        print(f"Truncated {label}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate data SQLite -> Postgres")
    default_sqlite_path = os.path.join(BACKEND_ROOT, "personalcfo.db")

    parser.add_argument(
        "--sqlite",
        dest="sqlite_url",
        default=f"sqlite:///{default_sqlite_path}",
        help="SQLite SQLAlchemy URL (default: backend personalcfo.db)",
    )
    parser.add_argument(
        "--postgres",
        dest="postgres_url",
        default=os.environ.get("POSTGRES_URL")
        or os.environ.get("DATABASE_URL"),
        required=False,
        help="Postgres SQLAlchemy URL (postgresql+psycopg2://...). Reads POSTGRES_URL or DATABASE_URL if omitted.",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate destination tables before inserting",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Limit to specific tables by __tablename__ (space-separated)",
    )

    args = parser.parse_args()

    if not args.postgres_url:
        raise SystemExit("--postgres URL is required (or set POSTGRES_URL / DATABASE_URL)")

    print("Source (SQLite):", args.sqlite_url)
    print("Target (Postgres):", args.postgres_url)

    src_engine = create_engine(args.sqlite_url)
    dst_engine = create_engine(args.postgres_url)

    src_session_factory = sessionmaker(bind=src_engine)
    dst_session_factory = sessionmaker(bind=dst_engine)

    with src_session_factory() as src, dst_session_factory() as dst:
        # Discover available tables in both DBs
        src_tables = set(inspect(src_engine).get_table_names())
        dst_tables = set(inspect(dst_engine).get_table_names())

        # Sanity: ensure target has tables (Alembic applied)
        missing = {m.__tablename__ for m in INSERT_ORDER if m.__tablename__ not in dst_tables}
        if missing:
            raise SystemExit(
                f"Target DB is missing tables (did you run Alembic?): {sorted(missing)}"
            )

        # Select models
        if args.only:
            only = set(args.only)
            selected_models = [m for m in INSERT_ORDER if m.__tablename__ in only]
        else:
            selected_models = INSERT_ORDER

        # Skip models not present in source
        actually_missing_src = [m for m in selected_models if m.__tablename__ not in src_tables]
        for m in actually_missing_src:
            print(f"Skipping {model_label(m)}: not found in source")
        selected_models = [m for m in selected_models if m.__tablename__ in src_tables]

        if args.dry_run:
            for model in selected_models:
                count = src.query(model).count()
                print(f"{model_label(model)}: {count} rows to migrate")
            return

        if args.truncate:
            truncate_tables(dst, TRUNCATE_ORDER)

        total = 0
        for model in selected_models:
            label = model_label(model)
            count = src.query(model).count()
            print(f"Migrating {label} ({count} rows)...")
            inserted = copy_rows(src, dst, model, args.batch_size)
            total += inserted
            print(f"  -> inserted {inserted}")

        print(f"Done. Inserted ~{total} rows total.")


if __name__ == "__main__":
    main()
