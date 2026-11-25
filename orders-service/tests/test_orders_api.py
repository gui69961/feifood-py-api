import pytest


def create_order(client, items=None, customer="Guilherme"):
    items = items if items is not None else [{"product_id": 1, "quantity": 2}]
    return client.post("/orders", json={"customer": customer, "items": items})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "orders"}


def test_create_order_calculates_total(client):
    response = create_order(
        client, [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}]
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "CRIADO"
    assert body["total"] == 52.0  # 2 x 22,50 + 1 x 7,00
    assert len(body["items"]) == 2
    assert body["items"][0]["product_name"] == "X-Burguer"


def test_order_keeps_price_from_purchase_time(client, catalog):
    order_id = create_order(client).json()["id"]
    catalog.products[1]["price"] = 99.0  # o preço muda depois da compra
    assert client.get(f"/orders/{order_id}").json()["total"] == 45.0


def test_unknown_product_returns_404(client):
    response = create_order(client, [{"product_id": 999, "quantity": 1}])
    assert response.status_code == 404
    assert "999" in response.json()["detail"]


def test_catalog_down_returns_503(client, catalog):
    catalog.down = True
    assert create_order(client).status_code == 503


@pytest.mark.parametrize("payload", [
    {"customer": "Ana", "items": []},
    {"customer": "", "items": [{"product_id": 1, "quantity": 1}]},
    {"customer": "Ana", "items": [{"product_id": 1, "quantity": 0}]},
    {"customer": "Ana", "items": [{"product_id": 1, "quantity": 51}]},
    {"customer": "Ana"},
])
def test_invalid_order_returns_422(client, payload):
    assert client.post("/orders", json=payload).status_code == 422


def test_get_order_and_not_found(client):
    order_id = create_order(client).json()["id"]
    assert client.get(f"/orders/{order_id}").status_code == 200
    assert client.get("/orders/999").status_code == 404


def test_list_orders_with_status_filter(client):
    first = create_order(client).json()["id"]
    create_order(client, customer="Ana")
    client.patch(f"/orders/{first}/status", json={"status": "PREPARANDO"})

    assert len(client.get("/orders").json()) == 2
    preparing = client.get("/orders", params={"status": "PREPARANDO"}).json()
    assert [o["id"] for o in preparing] == [first]


def test_invalid_status_filter_returns_422(client):
    assert client.get("/orders", params={"status": "VOANDO"}).status_code == 422


def test_full_delivery_flow(client):
    order_id = create_order(client).json()["id"]
    for new_status in ["PREPARANDO", "A_CAMINHO", "ENTREGUE"]:
        response = client.patch(f"/orders/{order_id}/status", json={"status": new_status})
        assert response.status_code == 200
        assert response.json()["status"] == new_status


def test_cannot_skip_steps(client):
    order_id = create_order(client).json()["id"]
    response = client.patch(f"/orders/{order_id}/status", json={"status": "ENTREGUE"})
    assert response.status_code == 409


def test_cannot_cancel_delivered_order(client):
    order_id = create_order(client).json()["id"]
    for new_status in ["PREPARANDO", "A_CAMINHO", "ENTREGUE"]:
        client.patch(f"/orders/{order_id}/status", json={"status": new_status})
    response = client.patch(f"/orders/{order_id}/status", json={"status": "CANCELADO"})
    assert response.status_code == 409


def test_update_status_of_missing_order_returns_404(client):
    assert client.patch("/orders/999/status", json={"status": "PREPARANDO"}).status_code == 404



def test_cors_allows_browser_requests_and_preflight(client):
    response = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert response.headers["access-control-allow-origin"] == "*"

    preflight = client.options(
        "/orders/1/status",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert "PATCH" in preflight.headers["access-control-allow-methods"]