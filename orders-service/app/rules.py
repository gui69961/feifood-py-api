"""Regras de negócio puras (sem banco nem HTTP), fáceis de testar."""
from enum import Enum


class OrderStatus(str, Enum):
    CRIADO = "CRIADO"
    PREPARANDO = "PREPARANDO"
    A_CAMINHO = "A_CAMINHO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


# Para quais status cada status pode avançar.
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CRIADO: {OrderStatus.PREPARANDO, OrderStatus.CANCELADO},
    OrderStatus.PREPARANDO: {OrderStatus.A_CAMINHO, OrderStatus.CANCELADO},
    OrderStatus.A_CAMINHO: {OrderStatus.ENTREGUE},
    OrderStatus.ENTREGUE: set(),
    OrderStatus.CANCELADO: set(),
}


def can_transition(current: OrderStatus, new: OrderStatus) -> bool:
    return new in ALLOWED_TRANSITIONS[current]


def calculate_total(lines: list[tuple[float, int]]) -> float:
    """Soma (preço unitário x quantidade) de cada item, arredondando em 2 casas."""
    return round(sum(price * quantity for price, quantity in lines), 2)
