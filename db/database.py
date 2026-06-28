"""
Database engine + session factory — NourishBot pattern, verbatim.
"""
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

logger = logging.getLogger(__name__)

# ponytail: replace scheme so psycopg2 driver is used (Neon requires it)
_url = os.environ["POSTGRES_URL"].replace("postgresql://", "postgresql+psycopg2://")
engine = create_engine(_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
