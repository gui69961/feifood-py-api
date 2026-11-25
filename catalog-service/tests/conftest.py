import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from tests.helpers import make_headers


@pytest.fixture()
def client():
    """Cliente de teste com um banco SQLite em memória, novo a cada teste."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def owner():
    """Lojista com id 10."""
    return make_headers(10, "LOJISTA", "Dona Maria")


@pytest.fixture()
def other_owner():
    """Outro lojista, com id 11."""
    return make_headers(11, "LOJISTA", "Seu João")


@pytest.fixture()
def customer():
    """Cliente com id 1."""
    return make_headers(1, "CLIENTE", "Ana")
