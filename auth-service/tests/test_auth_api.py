import pytest

CUSTOMER = {"name": "Ana Souza", "email": "ana@email.com", "password": "senha12345"}
OWNER = {
    "name": "Carlos Lima",
    "email": "carlos@burgerdev.com",
    "password": "senha12345",
    "company_name": "Burger Dev",
    "cnpj": "11.222.333/0001-81",
}


def register_customer(client, **overrides):
    return client.post("/auth/register/customer", json={**CUSTOMER, **overrides})


def register_owner(client, **overrides):
    return client.post("/auth/register/owner", json={**OWNER, **overrides})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "service": "auth"}


def test_register_customer_returns_token_and_user(client):
    response = register_customer(client)
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["role"] == "CLIENTE"
    assert body["user"]["email"] == "ana@email.com"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_email_is_normalized_to_lowercase(client):
    response = register_customer(client, email="  ANA@Email.COM ")
    assert response.json()["user"]["email"] == "ana@email.com"


def test_duplicate_email_returns_409(client):
    register_customer(client)
    assert register_customer(client).status_code == 409
    assert register_customer(client, email="ANA@EMAIL.COM").status_code == 409


@pytest.mark.parametrize("overrides", [
    {"password": "curta"},
    {"email": "email-invalido"},
    {"name": "A"},
    {"name": ""},
])
def test_invalid_customer_returns_422(client, overrides):
    assert register_customer(client, **overrides).status_code == 422


def test_register_owner_with_valid_cnpj(client):
    response = register_owner(client)
    assert response.status_code == 201
    user = response.json()["user"]
    assert user["role"] == "LOJISTA"
    assert user["company_name"] == "Burger Dev"
    assert user["cnpj"] == "11.222.333/0001-81"


def test_owner_cnpj_can_be_sent_without_mask(client):
    response = register_owner(client, cnpj="11222333000181")
    assert response.status_code == 201
    assert response.json()["user"]["cnpj"] == "11.222.333/0001-81"


@pytest.mark.parametrize("cnpj", ["11.222.333/0001-82", "00000000000000", "123", ""])
def test_owner_with_invalid_cnpj_returns_422(client, cnpj):
    response = register_owner(client, cnpj=cnpj)
    assert response.status_code == 422
    assert "CNPJ" in str(response.json())


def test_owner_without_cnpj_returns_422(client):
    payload = {k: v for k, v in OWNER.items() if k != "cnpj"}
    assert client.post("/auth/register/owner", json=payload).status_code == 422


def test_duplicate_cnpj_returns_409(client):
    register_owner(client)
    response = register_owner(client, email="outro@email.com")
    assert response.status_code == 409
    assert "CNPJ" in response.json()["detail"]


def test_login_success(client):
    register_customer(client)
    response = client.post("/auth/login", json={"email": "ana@email.com", "password": "senha12345"})
    assert response.status_code == 200
    assert response.json()["user"]["name"] == "Ana Souza"


def test_login_is_case_insensitive_on_email(client):
    register_customer(client)
    response = client.post("/auth/login", json={"email": "ANA@EMAIL.COM", "password": "senha12345"})
    assert response.status_code == 200


def test_login_wrong_password_and_unknown_email_look_the_same(client):
    register_customer(client)
    wrong = client.post("/auth/login", json={"email": "ana@email.com", "password": "errada123"})
    unknown = client.post("/auth/login", json={"email": "ninguem@email.com", "password": "senha12345"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_me_returns_the_logged_user(client):
    token = register_owner(client).json()["access_token"]
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "LOJISTA"


def test_me_without_token_returns_401(client):
    assert client.get("/auth/me").status_code == 401


def test_me_with_garbage_token_returns_401(client):
    response = client.get("/auth/me", headers={"Authorization": "Bearer isso-nao-e-um-token"})
    assert response.status_code == 401


def test_cors_allows_browser_requests(client):
    response = client.get("/health", headers={"Origin": "http://localhost:8080"})
    assert response.headers["access-control-allow-origin"] == "*"
