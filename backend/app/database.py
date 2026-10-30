import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Uses SQLite locally by default; switches to PostgreSQL automatically when deployed
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://neondb_owner:npg_iJ2INYMOa9HL@ep-cool-dawn-b40sbu41-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require")

# SQLite requires a thread check flag; PostgreSQL does not
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# ADDED pool_pre_ping and pool_recycle here to fix the Neon database drops
engine = create_engine(
    DATABASE_URL, 
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """FastAPI dependency that provides a clean DB session per request and closes it after."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()