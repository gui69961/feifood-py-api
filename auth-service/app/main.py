"""Auth Service: contas de clientes e donos de loja, login e emissão de tokens JWT."""
import os
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import Base, engine, get_db
from app.security import create_access_token, decode_access_token, hash_password, verify_password


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Feifood · Auth Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer(auto_error=False)
_DUMMY_HASH = hash_password("senha-falsa-para-igualar-o-tempo")


def token_response(user: models.User) -> schemas.TokenOut:
    token = create_access_token(user.id, user.role, user.name)
    return schemas.TokenOut(access_token=token, user=schemas.UserOut.model_validate(user))


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar")
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Entre novamente")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")
    user = db.get(models.User, int(payload["sub"]))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Conta não encontrada")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/auth/register/customer", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register_customer(data: schemas.CustomerRegister, db: Session = Depends(get_db)):
    if db.scalar(select(models.User).where(models.User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com esse e-mail")
    user = models.User(
        name=data.name, email=data.email, password_hash=hash_password(data.password), role="CLIENTE"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


@app.post("/auth/register/owner", response_model=schemas.TokenOut, status_code=status.HTTP_201_CREATED)
def register_owner(data: schemas.OwnerRegister, db: Session = Depends(get_db)):
    if db.scalar(select(models.User).where(models.User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com esse e-mail")
    if db.scalar(select(models.User).where(models.User.cnpj == data.cnpj)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta de lojista com esse CNPJ")
    user = models.User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role="LOJISTA",
        company_name=data.company_name,
        cnpj=data.cnpj,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return token_response(user)


@app.post("/auth/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == data.email.strip().lower()))
    # Mesmo sem conta, calculamos um hash: o tempo de resposta não revela se o e-mail existe.
    password_ok = verify_password(data.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos")
    return token_response(user)


@app.get("/auth/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(current_user)):
    return user
