import httpx
import pytest

from app.catalog_client import CatalogClient, CatalogUnavailable


def client_with(handler):
    return CatalogClient(base_url="http://catalog", transport=httpx.MockTransport(handler))


def test_returns_product_when_found():
    def handler(request):
        assert request.url.path == "/products/1"
        return httpx.Response(200, json={"id": 1, "name": "X-Burguer", "price": 22.5})

    assert client_with(handler).get_product(1)["name"] == "X-Burguer"


def test_returns_none_when_not_found():
    client = client_with(lambda request: httpx.Response(404, json={"detail": "x"}))
    assert client.get_product(99) is None


def test_raises_when_catalog_returns_server_error():
    client = client_with(lambda request: httpx.Response(500))
    with pytest.raises(CatalogUnavailable):
        client.get_product(1)


def test_raises_when_catalog_is_unreachable():
    def handler(request):
        raise httpx.ConnectError("sem conexão")

    with pytest.raises(CatalogUnavailable):
        client_with(handler).get_product(1)
