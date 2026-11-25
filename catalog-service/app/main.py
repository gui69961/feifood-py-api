"""Catalog Service: cadastro de restaurantes e produtos do Feifood."""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import Base, engine, get_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)  # cria as tabelas ao iniciar
    yield


app = FastAPI(title="Feifood · Catalog Service", version="1.0.0", lifespan=lifespan)

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
def create_restaurant(data: schemas.RestaurantCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(models.Restaurant).where(models.Restaurant.name == data.name))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe um restaurante com esse nome")
    restaurant = models.Restaurant(**data.model_dump())
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)
    return restaurant


@app.get("/restaurants", response_model=list[schemas.RestaurantOut])
def list_restaurants(db: Session = Depends(get_db)):
    return db.scalars(select(models.Restaurant).order_by(models.Restaurant.name)).all()


@app.post(
    "/restaurants/{restaurant_id}/products",
    response_model=schemas.ProductOut,
    status_code=status.HTTP_201_CREATED,
)
def create_product(restaurant_id: int, data: schemas.ProductCreate, db: Session = Depends(get_db)):
    if db.get(models.Restaurant, restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante não encontrado")
    product = models.Product(**data.model_dump(), restaurant_id=restaurant_id)
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@app.get("/restaurants/{restaurant_id}/products", response_model=list[schemas.ProductOut])
def list_products(restaurant_id: int, db: Session = Depends(get_db)):
    if db.get(models.Restaurant, restaurant_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Restaurante não encontrado")
    return db.scalars(
        select(models.Product).where(models.Product.restaurant_id == restaurant_id)
    ).all()


@app.get("/products/{product_id}", response_model=schemas.ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(models.Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Produto não encontrado")
    return product