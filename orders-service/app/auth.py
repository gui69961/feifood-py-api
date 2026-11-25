"""Autenticação: lê e confere o token JWT emitido pelo Auth Service.

O token é conferido aqui mesmo, com a chave compartilhada (JWT_SECRET): este serviço
não precisa chamar o Auth Service a cada requisição.
"""
import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

JWT_SECRET = os.getenv("JWT_SECRET", "feifood-dev-secret-troque-em-producao-123")
JWT_ALGORITHM = "HS256"

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    id: int
    role: str  # CLIENTE ou LOJISTA
    name: str
    token: str


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return CurrentUser(
            id=int(payload["sub"]),
            role=payload["role"],
            name=payload.get("name", ""),
            token=credentials.credentials,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente")
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")


def require_owner(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "LOJISTA":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas donos de loja podem fazer isso")
    return user


def require_customer(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "CLIENTE":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Apenas clientes podem fazer pedidos")
    return user
