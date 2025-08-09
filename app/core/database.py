from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Single database engine (Postgres or any SQLAlchemy-supported URL provided via env)
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    use_insertmanyvalues=False,  # Avoid UUID sentinel mismatch with RETURNING
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
