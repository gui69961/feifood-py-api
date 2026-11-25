import pytest

from tests.helpers import make_headers


def create_restaurant(client, headers, name="Burger Dev", category="Lanches"):
    return client.post("/restaurants", json={"name": name, "category": category}, headers=headers)


def create_product(client, headers, restaurant_id, name="X-Burguer", price=22.5):
    return client.post(
        f"/restaurants/{restaurant_id}/products", json={"name": name, "price": price}, headers=headers
    )


# ---------- saúde e CORS ----------
def test_health_is_public(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "catalog"}


def test_cors_allows_browser_requests(client):
    response = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert response.headers["access-control-allow-origin"] == "*"


# ---------- autenticação ----------
@pytest.mark.parametrize("method,path", [
    ("get", "/restaurants"),
    ("get", "/restaurants/mine"),
    ("get", "/restaurants/1/products"),
    ("get", "/products/1"),
])
def test_endpoints_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_post_requires_login(client):
    assert client.post("/restaurants", json={"name": "X", "category": "Y"}).status_code == 401


def test_invalid_token_returns_401(client):
    response = client.get("/restaurants", headers={"Authorization": "Bearer lixo"})
    assert response.status_code == 401


def test_expired_token_returns_401(client):
    expired = make_headers(10, "LOJISTA", minutes=-5)
    response = client.get("/restaurants", headers=expired)
    assert response.status_code == 401
    assert "expirada" in response.json()["detail"].lower()


# ---------- permissões ----------
def test_customer_cannot_create_restaurant(client, customer):
    assert create_restaurant(client, customer).status_code == 403


def test_customer_cannot_list_my_restaurants(client, customer):
    assert client.get("/restaurants/mine", headers=customer).status_code == 403


def test_customer_cannot_create_product(client, owner, customer):
    restaurant_id = create_restaurant(client, owner).json()["id"]
    assert create_product(client, customer, restaurant_id).status_code == 403


def test_owner_cannot_add_product_to_someone_elses_restaurant(client, owner, other_owner):
    restaurant_id = create_restaurant(client, owner).json()["id"]
    response = create_product(client, other_owner, restaurant_id)
    assert response.status_code == 403


# ---------- restaurantes ----------
def test_owner_creates_restaurant_and_becomes_its_owner(client, owner):
    response = create_restaurant(client, owner)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Burger Dev"
    assert body["owner_id"] == 10


def test_duplicate_restaurant_returns_409(client, owner, other_owner):
    create_restaurant(client, owner)
    assert create_restaurant(client, other_owner).status_code == 409


@pytest.mark.parametrize("payload", [
    {"name": "", "category": "Lanches"},
    {"name": "Sem categoria"},
    {},
])
def test_invalid_restaurant_returns_422(client, owner, payload):
    assert client.post("/restaurants", json=payload, headers=owner).status_code == 422


def test_customer_sees_all_restaurants_sorted_by_name(client, owner, other_owner, customer):
    create_restaurant(client, owner, "Zé Pizzaria", "Pizza")
    create_restaurant(client, other_owner, "Açaí Bom", "Sobremesa")
    names = [r["name"] for r in client.get("/restaurants", headers=customer).json()]
    assert names == sorted(names)
    assert len(names) == 2


def test_my_restaurants_only_returns_the_owners_own(client, owner, other_owner):
    create_restaurant(client, owner, "Burger Dev")
    create_restaurant(client, other_owner, "Sushi Byte", "Japonesa")
    mine = client.get("/restaurants/mine", headers=owner).json()
    assert [r["name"] for r in mine] == ["Burger Dev"]


# ---------- produtos ----------
def test_owner_creates_and_customer_lists_products(client, owner, customer):
    restaurant_id = create_restaurant(client, owner).json()["id"]
    response = create_product(client, owner, restaurant_id)
    assert response.status_code == 201
    body = response.json()
    assert body["restaurant_id"] == restaurant_id
    assert body["restaurant_name"] == "Burger Dev"
    assert body["owner_id"] == 10

    products = client.get(f"/restaurants/{restaurant_id}/products", headers=customer).json()
    assert [p["name"] for p in products] == ["X-Burguer"]


@pytest.mark.parametrize("price", [0, -5])
def test_product_price_must_be_positive(client, owner, price):
    restaurant_id = create_restaurant(client, owner).json()["id"]
    assert create_product(client, owner, restaurant_id, price=price).status_code == 422


def test_product_for_missing_restaurant_returns_404(client, owner, customer):
    assert create_product(client, owner, 999).status_code == 404
    assert client.get("/restaurants/999/products", headers=customer).status_code == 404


def test_get_product_by_id(client, owner, customer):
    restaurant_id = create_restaurant(client, owner).json()["id"]
    product = create_product(client, owner, restaurant_id, "Refrigerante", 7).json()
    response = client.get(f"/products/{product['id']}", headers=customer)
    assert response.status_code == 200
    assert response.json()["name"] == "Refrigerante"


def test_get_missing_product_returns_404(client, customer):
    assert client.get("/products/999", headers=customer).status_code == 404
