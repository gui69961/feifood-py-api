"""Catalog Service: restaurantes e produtos do Feifood.

- Qualquer usuário logado (cliente ou lojista) pode VER restaurantes e produtos.
- Apenas LOJISTAS podem criar restaurantes, e só mexem nos que são deles.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import CurrentUser, get_current_user, require_owner
from app.database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # cria as tabelas ao iniciar
    yield


app = FastAPI(title="Feifood · Catalog Service", version="2.0.0", lifespan=lifespan)

# CORS: permite que a interface web (outra porta) converse com a API pelo navegador.
# Em produção, defina CORS_ORIGINS com os endereços permitidos, separados por vírgula.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "catalog"}


@app.post("/restaurants", response_model=schemas.RestaurantOut, status_code=status.HTTP_201_CREATED)
def create_restaurant(
    data: schemas.RestaurantCreate,
    db: Session = Depends(get_db),
    owner: CurrentUser = Depends(require_owner),
):
    exists = db.scalar(select(models.Restaurant).where(models.Restaurant.name == data.name))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um restaurante com esse nome")
    restaurant = models.Restaurant(**data.model_dump(), owner_id=owner.id)
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@app.get("/restaurants", response_model=list[schemas.RestaurantOut])
def list_restaurants(db: Session = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    return db.scalars(select(models.Restaurant).order_by(models.Restaurant.name)).all()


@app.get("/restaurants/mine", response_model=list[schemas.RestaurantOut])
def list_my_restaurants(db: Session = Depends(get_db), owner: CurrentUser = Depends(require_owner)):
    return db.scalars(
        select(models.Restaurant).where(models.Restaurant.owner_id == owner.id).order_by(models.Restaurant.name)
    ).all()


@app.post(
    "/restaurants/{restaurant_id}/products",
    response_model=schemas.ProductOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    restaurant_id: int,
    data: schemas.ProductCreate,
    db: Session = Depends(get_db),
    owner: CurrentUser = Depends(require_owner),
):
    restaurant = db.get(models.Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante não encontrado")
    if restaurant.owner_id != owner.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Esse restaurante pertence a outro lojista")
    product = models.Product(**data.model_dump(), restaurant_id=restaurant_id)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.get("/restaurants/{restaurant_id}/products", response_model=list[schemas.ProductOut])
def list_products(
    restaurant_id: int, db: Session = Depends(get_db), _user: CurrentUser = Depends(get_current_user)
):
    if db.get(models.Restaurant, restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante não encontrado")
    return db.scalars(
        select(models.Product).where(models.Product.restaurant_id == restaurant_id)
    ).all()


@app.get("/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), _user: CurrentUser = Depends(get_current_user)):
    product = db.get(models.Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    return product
