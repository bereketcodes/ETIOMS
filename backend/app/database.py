import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Uses SQLite locally by default; switches to PostgreSQL automatically when deployed
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./etioms.db")

# SQLite requires a thread check flag; PostgreSQL does not
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """FastAPI dependency that provides a clean DB session per request and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()