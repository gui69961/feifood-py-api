from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.rules import OrderStatus


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=50)


class OrderCreate(BaseModel):
    # O cliente vem do token de login: não é mais enviado no corpo da requisição.
    items: list[OrderItemIn] = Field(min_length=1)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    product_id: int
    product_name: str
    unit_price: float
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    customer: str
    restaurant_id: int
    restaurant_name: str
    status: OrderStatus
    total: float
    created_at: datetime
    items: list[OrderItemOut]


class StatusUpdate(BaseModel):
    status: OrderStatus
