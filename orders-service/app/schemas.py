from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.rules import OrderStatus


class OrderItemIn(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, le=50)


class OrderCreate(BaseModel):
    customer: str = Field(min_length=1, max_length=100)
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
    status: OrderStatus
    total: float
    created_at: datetime
    items: list[OrderItemOut]


class StatusUpdate(BaseModel):
    status: OrderStatus
