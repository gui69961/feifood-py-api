import pytest


def create_restaurant(client, name="Burger Dev", category="Lanches"):
    return client.post("/restaurants", json={"name": name, "category": category})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "catalog"}


def test_create_restaurant(client):
    response = create_restaurant(client)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Burger Dev"
    assert body["category"] == "Lanches"


def test_duplicate_restaurant_returns_409(client):
    create_restaurant(client)
    response = create_restaurant(client)
    assert response.status_code == 409


@pytest.mark.parametrize("payload", [
    {"name": "", "category": "Lanches"},
    {"name": "Sem categoria"},
    {},
])
def test_invalid_restaurant_returns_422(client, payload):
    assert client.post("/restaurants", json=payload).status_code == 422


def test_list_restaurants_is_sorted_by_name(client):
    create_restaurant(client, "Zé Pizzaria", "Pizza")
    create_restaurant(client, "Açaí Bom", "Sobremesa")
    names = [r["name"] for r in client.get("/restaurants").json()]
    assert names == sorted(names)
    assert len(names) == 2


def test_create_and_list_products(client):
    restaurant_id = create_restaurant(client).json()["id"]
    response = client.post(
        f"/restaurants/{restaurant_id}/products", json={"name": "X-Burguer", "price": 22.5}
    )
    assert response.status_code == 201
    assert response.json()["restaurant_id"] == restaurant_id

    products = client.get(f"/restaurants/{restaurant_id}/products").json()
    assert [p["name"] for p in products] == ["X-Burguer"]


@pytest.mark.parametrize("price", [0, -5])
def test_product_price_must_be_positive(client, price):
    restaurant_id = create_restaurant(client).json()["id"]
    response = client.post(
        f"/restaurants/{restaurant_id}/products", json={"name": "Grátis", "price": price}
    )
    assert response.status_code == 422


def test_product_for_missing_restaurant_returns_404(client):
    response = client.post("/restaurants/999/products", json={"name": "X", "price": 10})
    assert response.status_code == 404
    assert client.get("/restaurants/999/products").status_code == 404


def test_get_product_by_id(client):
    restaurant_id = create_restaurant(client).json()["id"]
    product = client.post(
        f"/restaurants/{restaurant_id}/products", json={"name": "Refrigerante", "price": 7}
    ).json()
    response = client.get(f"/products/{product['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Refrigerante"


def test_get_missing_product_returns_404(client):
    assert client.get("/products/999").status_code == 404
