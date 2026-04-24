import os

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# PostgreSQL: em produção (RDS) use variável DATABASE_URL — nunca commite senha no repositório.
# Exemplo RDS: postgresql+psycopg2://user:senha@nome-do-rds.xxx.sa-east-1.rds.amazonaws.com:5432/sigein
_default_local = "postgresql+psycopg2://postgres:1234@localhost:5432/sigein"
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", _default_local)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
