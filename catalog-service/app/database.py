"""Conexão com o banco de dados (SQLAlchemy)."""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./catalog.db")

# O SQLite exige esta opção quando usado com FastAPI (várias threads).
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Abre uma sessão por requisição e garante que ela seja fechada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
