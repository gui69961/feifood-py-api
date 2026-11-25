"""Senhas (scrypt) e tokens JWT."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

JWT_SECRET = os.getenv("JWT_SECRET", "feifood-dev-secret-troque-em-producao-123")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

_N, _R, _P = 2**14, 8, 1


def hash_password(password: str) -> str:
    """Gera um hash com sal aleatório. A senha original nunca é guardada."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)  # comparação em tempo constante


def create_access_token(user_id: int, role: str, name: str, minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES if minutes is None else minutes)
    payload = {"sub": str(user_id), "role": role, "name": name, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Levanta jwt.InvalidTokenError se o token for inválido ou estiver expirado."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
