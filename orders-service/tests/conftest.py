import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.catalog_client import CatalogUnavailable, get_catalog_client
from app.database import Base, get_db
from app.main import app
from tests.helpers import make_headers


class FakeCatalog:
    """Catálogo falso: os testes do Orders Service não dependem do outro serviço."""

    def __init__(self):
        self.products = {
            1: {"id": 1, "name": "X-Burguer", "price": 22.5, "restaurant_id": 1,
                "restaurant_name": "Burger Dev", "owner_id": 10},
            2: {"id": 2, "name": "Refrigerante", "price": 7.0, "restaurant_id": 1,
                "restaurant_name": "Burger Dev", "owner_id": 10},
            3: {"id": 3, "name": "Combo 20 peças", "price": 59.9, "restaurant_id": 2,
                "restaurant_name": "Sushi Byte", "owner_id": 11},
        }
        self.down = False
        self.tokens_received = []

    def get_product(self, product_id, token):
        self.tokens_received.append(token)
        if self.down:
            raise CatalogUnavailable("catálogo fora do ar")
        return self.products.get(product_id)


@pytest.fixture()
def catalog():
    return FakeCatalog()


@pytest.fixture()
def client(catalog):
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
    app.dependency_overrides[get_catalog_client] = lambda: catalog
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def customer():
    """Cliente com id 1."""
    return make_headers(1, "CLIENTE", "Ana")


@pytest.fixture()
def other_customer():
    return make_headers(2, "CLIENTE", "Bruno")


@pytest.fixture()
def owner():
    """Dono do restaurante Burger Dev (id 10)."""
    return make_headers(10, "LOJISTA", "Dona Maria")


@pytest.fixture()
def other_owner():
    """Dono do restaurante Sushi Byte (id 11)."""
    return make_headers(11, "LOJISTA", "Seu João")
