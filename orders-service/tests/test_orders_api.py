import pytest

from tests.helpers import make_headers


def create_order(client, headers, items=None):
    items = items if items is not None else [{"product_id": 1, "quantity": 2}]
    return client.post("/orders", json={"items": items}, headers=headers)


def set_status(client, headers, order_id, new_status):
    return client.patch(f"/orders/{order_id}/status", json={"status": new_status}, headers=headers)


# ---------- saúde e CORS ----------
def test_health_is_public(client):
    assert client.get("/health").json() == {"status": "ok", "service": "orders"}


def test_cors_allows_browser_requests_and_preflight(client):
    response = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert response.headers["access-control-allow-origin"] == "*"

    preflight = client.options(
        "/orders/1/status",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type,authorization",
        },
    )
    assert preflight.status_code == 200
    assert "PATCH" in preflight.headers["access-control-allow-methods"]


# ---------- autenticação ----------
@pytest.mark.parametrize("method,path", [("get", "/orders"), ("get", "/orders/1")])
def test_endpoints_require_login(client, method, path):
    assert getattr(client, method)(path).status_code == 401


def test_create_order_requires_login(client):
    assert client.post("/orders", json={"items": [{"product_id": 1, "quantity": 1}]}).status_code == 401


def test_expired_token_returns_401(client):
    expired = make_headers(1, "CLIENTE", minutes=-5)
    assert client.get("/orders", headers=expired).status_code == 401


# ---------- criar pedido ----------
def test_customer_creates_order_and_total_is_calculated(client, customer):
    response = create_order(
        client, customer, [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}]
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "CRIADO"
    assert body["total"] == 52.0  # 2 x 22,50 + 1 x 7,00
    assert body["customer"] == "Ana"  # vem do token, não do corpo da requisição
    assert body["restaurant_name"] == "Burger Dev"
    assert len(body["items"]) == 2


def test_owner_cannot_create_orders(client, owner):
    assert create_order(client, owner).status_code == 403


def test_order_keeps_price_from_purchase_time(client, customer, catalog):
    order_id = create_order(client, customer).json()["id"]
    catalog.products[1]["price"] = 99.0  # o preço muda depois da compra
    assert client.get(f"/orders/{order_id}", headers=customer).json()["total"] == 45.0


def test_customer_token_is_forwarded_to_the_catalog(client, customer, catalog):
    create_order(client, customer)
    assert catalog.tokens_received
    assert customer["Authorization"] == f"Bearer {catalog.tokens_received[0]}"


def test_unknown_product_returns_404(client, customer):
    response = create_order(client, customer, [{"product_id": 999, "quantity": 1}])
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_items_from_different_restaurants_return_422(client, customer):
    response = create_order(client, customer, [{"product_id": 1, "quantity": 1}, {"product_id": 3, "quantity": 1}])
    assert response.status_code == 422
    assert "mesmo restaurante" in response.json()["detail"]


def test_catalog_down_returns_503(client, customer, catalog):
    catalog.down = True
    assert create_order(client, customer).status_code == 503


@pytest.mark.parametrize("payload", [
    {"items": []},
    {"items": [{"product_id": 1, "quantity": 0}]},
    {"items": [{"product_id": 1, "quantity": 51}]},
    {},
])
def test_invalid_order_returns_422(client, customer, payload):
    assert client.post("/orders", json=payload, headers=customer).status_code == 422


# ---------- quem vê o quê ----------
def test_customer_only_sees_own_orders(client, customer, other_customer):
    mine = create_order(client, customer).json()["id"]
    create_order(client, other_customer)

    listed = client.get("/orders", headers=customer).json()
    assert [o["id"] for o in listed] == [mine]


def test_owner_only_sees_orders_of_own_restaurant(client, customer, owner, other_owner):
    burger = create_order(client, customer, [{"product_id": 1, "quantity": 1}]).json()["id"]
    sushi = create_order(client, customer, [{"product_id": 3, "quantity": 1}]).json()["id"]

    assert [o["id"] for o in client.get("/orders", headers=owner).json()] == [burger]
    assert [o["id"] for o in client.get("/orders", headers=other_owner).json()] == [sushi]


def test_get_order_visible_to_its_customer_and_its_owner(client, customer, owner):
    order_id = create_order(client, customer).json()["id"]
    assert client.get(f"/orders/{order_id}", headers=customer).status_code == 200
    assert client.get(f"/orders/{order_id}", headers=owner).status_code == 200


def test_other_people_get_404_instead_of_403(client, customer, other_customer, other_owner):
    order_id = create_order(client, customer).json()["id"]
    assert client.get(f"/orders/{order_id}", headers=other_customer).status_code == 404
    assert client.get(f"/orders/{order_id}", headers=other_owner).status_code == 404
    assert client.get("/orders/999", headers=customer).status_code == 404


def test_list_orders_with_status_filter(client, customer, owner):
    first = create_order(client, customer).json()["id"]
    create_order(client, customer)
    set_status(client, owner, first, "PREPARANDO")

    assert len(client.get("/orders", headers=customer).json()) == 2
    preparing = client.get("/orders", params={"status": "PREPARANDO"}, headers=customer).json()
    assert [o["id"] for o in preparing] == [first]


def test_invalid_status_filter_returns_422(client, customer):
    assert client.get("/orders", params={"status": "VOANDO"}, headers=customer).status_code == 422


# ---------- mudança de status ----------
def test_owner_drives_the_full_delivery_flow(client, customer, owner):
    order_id = create_order(client, customer).json()["id"]
    for new_status in ["PREPARANDO", "A_CAMINHO", "ENTREGUE"]:
        response = set_status(client, owner, order_id, new_status)
        assert response.status_code == 200
        assert response.json()["status"] == new_status


def test_owner_cannot_skip_steps(client, customer, owner):
    order_id = create_order(client, customer).json()["id"]
    assert set_status(client, owner, order_id, "ENTREGUE").status_code == 409


def test_owner_cannot_cancel_delivered_order(client, customer, owner):
    order_id = create_order(client, customer).json()["id"]
    for new_status in ["PREPARANDO", "A_CAMINHO", "ENTREGUE"]:
        set_status(client, owner, order_id, new_status)
    assert set_status(client, owner, order_id, "CANCELADO").status_code == 409


def test_other_owner_cannot_change_the_order(client, customer, other_owner):
    order_id = create_order(client, customer).json()["id"]
    assert set_status(client, other_owner, order_id, "PREPARANDO").status_code == 404


def test_customer_cannot_advance_the_order(client, customer):
    order_id = create_order(client, customer).json()["id"]
    response = set_status(client, customer, order_id, "PREPARANDO")
    assert response.status_code == 403


def test_customer_can_cancel_before_the_restaurant_accepts(client, customer):
    order_id = create_order(client, customer).json()["id"]
    response = set_status(client, customer, order_id, "CANCELADO")
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADO"


def test_customer_cannot_cancel_after_the_restaurant_accepts(client, customer, owner):
    order_id = create_order(client, customer).json()["id"]
    set_status(client, owner, order_id, "PREPARANDO")
    assert set_status(client, customer, order_id, "CANCELADO").status_code == 403


def test_other_customer_cannot_cancel_someone_elses_order(client, customer, other_customer):
    order_id = create_order(client, customer).json()["id"]
    assert set_status(client, other_customer, order_id, "CANCELADO").status_code == 404


def test_update_status_of_missing_order_returns_404(client, owner):
    assert set_status(client, owner, 999, "PREPARANDO").status_code == 404


def test_garbage_token_returns_401(client):
    assert client.get("/orders", headers={"Authorization": "Bearer isso-nao-e-um-token"}).status_code == 401
