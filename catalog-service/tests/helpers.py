"""Gera tokens de teste, assinados com a mesma chave que o Auth Service usa."""
from datetime import datetime, timedelta, timezone

import jwt

from app.auth import JWT_ALGORITHM, JWT_SECRET


def make_headers(user_id: int, role: str, name: str = "Teste", minutes: int = 30) -> dict:
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return {"Authorization": f"Bearer {token}"}
