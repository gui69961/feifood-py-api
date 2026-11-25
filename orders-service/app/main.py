"""Orders Service: criação e acompanhamento de pedidos do Feifood."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.catalog_client import CatalogClient, CatalogUnavailable, get_catalog_client
from app.database import Base, engine, get_db
from app.rules import OrderStatus, calculate_total, can_transition


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Feifood · Orders Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "orders"}


@app.post("/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    catalog: CatalogClient = Depends(get_catalog_client),
):
    items: list[models.OrderItem] = []
    for item in data.items:
        try:
            product = catalog.get_product(item.product_id)
        except CatalogUnavailable:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Catálogo indisponível no momento")
        if product is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Produto {item.product_id} não encontrado no catálogo"
            )
        items.append(
            models.OrderItem(
                product_id=product["id"],
                product_name=product["name"],
                unit_price=product["price"],
                quantity=item.quantity,
            )
        )

    total = calculate_total([(i.unit_price, i.quantity) for i in items])
    order = models.Order(customer=data.customer, total=total, items=items)
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[schemas.OrderOut])
def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
):
    query = select(models.Order).order_by(models.Order.id)
    if status_filter:
        query = query.where(models.Order.status == status_filter.value)
    return db.scalars(query).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(models.Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    return order


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderOut)
def update_status(order_id: int, data: schemas.StatusUpdate, db: Session = Depends(get_db)):
    order = db.get(models.Order, order_id)
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")

    current = OrderStatus(order.status)
    if not can_transition(current, data.status):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Não é possível mudar de {current.value} para {data.status.value}",
        )
    order.status = data.status.value
    db.commit()
    db.refresh(order)
    return order
