import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.catalog_client import CatalogUnavailable, get_catalog_client
from app.database import Base, get_db
from app.main import app


class FakeCatalog:
    """Catálogo falso: os testes do Orders Service não dependem do outro serviço."""

    def __init__(self):
        self.products = {
            1: {"id": 1, "name": "X-Burguer", "price": 22.5, "restaurant_id": 1},
            2: {"id": 2, "name": "Refrigerante", "price": 7.0, "restaurant_id": 1},
        }
        self.down = False

    def get_product(self, product_id):
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
