from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# SQLite-specific configuration
if settings.DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False}  # Allow SQLite to work with FastAPI
    )

    # Apply performance PRAGMAs per connection
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        # Better concurrency and read performance
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA temp_store=MEMORY;")
        cursor.execute("PRAGMA cache_size=-20000;")  # ~20MB page cache
        cursor.execute("PRAGMA mmap_size=134217728;")  # 128MB if supported
        cursor.close()

    # Ensure helpful indexes exist (no-op if already present)
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_card ON transactions(card_id);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_cards_user ON cards(user_id);"))
        # New: indexes for excluded keywords feature (only if table already exists)
        try:
            # Use PRAGMA table_info to check existence reliably
            exists_rows = conn.execute(text("SELECT COUNT(*) FROM pragma_table_info('user_excluded_keywords');")).scalar()
            if exists_rows and int(exists_rows) > 0:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_excl_keywords_user ON user_excluded_keywords(user_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_excl_keywords_norm ON user_excluded_keywords(keyword_normalized);"))
        except Exception:
            # Table may not exist yet; ExcludedKeywordsService will create it on demand
            pass
        conn.commit()
else:
    # Postgres or others
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        use_insertmanyvalues=False  # Avoid UUID sentinel mismatch with RETURNING
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
