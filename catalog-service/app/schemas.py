"""Schemas (Pydantic): validam a entrada e definem o formato da saída da API."""
from pydantic import BaseModel, ConfigDict, Field


class RestaurantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    category: str = Field(min_length=1, max_length=50)


class RestaurantOut(RestaurantCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price: float = Field(gt=0, description="Preço em reais, maior que zero")


class ProductOut(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
