import jwt
import pytest

from app.security import (
    JWT_ALGORITHM,
    JWT_SECRET,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_is_not_the_plain_password():
    hashed = hash_password("minhasenha123")
    assert "minhasenha123" not in hashed
    assert hashed.startswith("scrypt$")


def test_same_password_generates_different_hashes():
    assert hash_password("minhasenha123") != hash_password("minhasenha123")


def test_verify_password():
    hashed = hash_password("minhasenha123")
    assert verify_password("minhasenha123", hashed)
    assert not verify_password("outra-senha", hashed)


def test_verify_password_with_corrupted_hash_returns_false():
    assert not verify_password("qualquer", "isto-nao-e-um-hash")


def test_token_roundtrip():
    token = create_access_token(7, "LOJISTA", "Dona Maria")
    payload = decode_access_token(token)
    assert payload["sub"] == "7"
    assert payload["role"] == "LOJISTA"
    assert payload["name"] == "Dona Maria"


def test_expired_token_is_rejected():
    token = create_access_token(1, "CLIENTE", "Ana", minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode({"sub": "1", "role": "LOJISTA"}, "outra-chave-qualquer-com-32-caracteres!", algorithm=JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(forged)


def test_token_without_signature_is_rejected():
    unsigned = jwt.encode({"sub": "1", "role": "LOJISTA"}, None, algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(unsigned)
