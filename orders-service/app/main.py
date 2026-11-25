"""Orders Service: criação e acompanhamento de pedidos do Feifood.

- CLIENTE: cria pedidos, vê os seus e pode cancelar enquanto o restaurante não aceitou.
- LOJISTA: vê os pedidos dos SEUS restaurantes e conduz cada pedido pelas etapas.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import CurrentUser, get_current_user, require_customer
from app.catalog_client import CatalogClient, CatalogUnavailable, get_catalog_client
from app.database import Base, engine, get_db
from app.rules import OrderStatus, calculate_total, can_actor_change, can_transition


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Feifood · Orders Service", version="2.0.0", lifespan=lifespan)

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
    return {"status": "ok", "service": "orders"}


def visible_to(user: CurrentUser, order: models.Order) -> bool:
    """O cliente só enxerga os próprios pedidos; o lojista, os dos seus restaurantes."""
    if user.role == "CLIENTE":
        return order.customer_id == user.id
    return order.owner_id == user.id


@app.post("/orders", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: schemas.OrderCreate,
    db: Session = Depends(get_db),
    catalog: CatalogClient = Depends(get_catalog_client),
    customer: CurrentUser = Depends(require_customer),
):
    items: list[models.OrderItem] = []
    restaurant: dict | None = None
    for item in data.items:
        try:
            product = catalog.get_product(item.product_id, customer.token)
        except CatalogUnavailable:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Catálogo indisponível no momento")
        if product is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, f"Produto {item.product_id} não encontrado no catálogo"
            )
        if restaurant is None:
            restaurant = product
        elif product["restaurant_id"] != restaurant["restaurant_id"]:
            raise HTTPException(
                422, "Todos os itens do pedido devem ser do mesmo restaurante"
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
    order = models.Order(
        customer=customer.name,
        customer_id=customer.id,
        restaurant_id=restaurant["restaurant_id"],
        restaurant_name=restaurant["restaurant_name"],
        owner_id=restaurant["owner_id"],
        total=total,
        items=items,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@app.get("/orders", response_model=list[schemas.OrderOut])
def list_orders(
    status_filter: OrderStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    query = select(models.Order).order_by(models.Order.id)
    if user.role == "CLIENTE":
        query = query.where(models.Order.customer_id == user.id)
    else:
        query = query.where(models.Order.owner_id == user.id)
    if status_filter:
        query = query.where(models.Order.status == status_filter.value)
    return db.scalars(query).all()


@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    order = db.get(models.Order, order_id)
    # 404 (e não 403) também para pedidos de outras pessoas: não revelamos que eles existem.
    if order is None or not visible_to(user, order):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")
    return order


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderOut)
def update_status(
    order_id: int,
    data: schemas.StatusUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    order = db.get(models.Order, order_id)
    if order is None or not visible_to(user, order):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pedido não encontrado")

    current = OrderStatus(order.status)
    if not can_transition(current, data.status):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Não é possível mudar de {current.value} para {data.status.value}",
        )
    if not can_actor_change(user.role, current, data.status):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Você não tem permissão para fazer essa mudança. Clientes só podem cancelar pedidos que o restaurante ainda não aceitou",
        )
    order.status = data.status.value
    db.commit()
    db.refresh(order)
    return order
