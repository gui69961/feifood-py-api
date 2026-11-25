import pytest

from app.rules import OrderStatus, calculate_total, can_actor_change, can_transition


@pytest.mark.parametrize("current,new", [
    (OrderStatus.CRIADO, OrderStatus.PREPARANDO),
    (OrderStatus.CRIADO, OrderStatus.CANCELADO),
    (OrderStatus.PREPARANDO, OrderStatus.A_CAMINHO),
    (OrderStatus.PREPARANDO, OrderStatus.CANCELADO),
    (OrderStatus.A_CAMINHO, OrderStatus.ENTREGUE),
])
def test_valid_transitions(current, new):
    assert can_transition(current, new)


@pytest.mark.parametrize("current,new", [
    (OrderStatus.CRIADO, OrderStatus.ENTREGUE),
    (OrderStatus.PREPARANDO, OrderStatus.CRIADO),
    (OrderStatus.A_CAMINHO, OrderStatus.CANCELADO),
    (OrderStatus.ENTREGUE, OrderStatus.CANCELADO),
    (OrderStatus.CANCELADO, OrderStatus.PREPARANDO),
])
def test_invalid_transitions(current, new):
    assert not can_transition(current, new)


def test_calculate_total():
    assert calculate_total([(22.5, 2), (7.0, 1)]) == 52.0


def test_calculate_total_rounds_to_two_decimals():
    assert calculate_total([(0.1, 3)]) == 0.3


def test_calculate_total_of_empty_list_is_zero():
    assert calculate_total([]) == 0


# ---------- quem pode fazer cada mudança ----------
@pytest.mark.parametrize("current,new", [
    (OrderStatus.CRIADO, OrderStatus.PREPARANDO),
    (OrderStatus.PREPARANDO, OrderStatus.A_CAMINHO),
    (OrderStatus.A_CAMINHO, OrderStatus.ENTREGUE),
    (OrderStatus.CRIADO, OrderStatus.CANCELADO),
    (OrderStatus.PREPARANDO, OrderStatus.CANCELADO),
])
def test_owner_can_drive_the_order(current, new):
    assert can_actor_change("LOJISTA", current, new)


def test_customer_can_only_cancel_before_the_restaurant_accepts():
    assert can_actor_change("CLIENTE", OrderStatus.CRIADO, OrderStatus.CANCELADO)
    assert not can_actor_change("CLIENTE", OrderStatus.PREPARANDO, OrderStatus.CANCELADO)
    assert not can_actor_change("CLIENTE", OrderStatus.CRIADO, OrderStatus.PREPARANDO)
    assert not can_actor_change("CLIENTE", OrderStatus.A_CAMINHO, OrderStatus.ENTREGUE)


def test_unknown_role_can_do_nothing():
    assert not can_actor_change("VISITANTE", OrderStatus.CRIADO, OrderStatus.CANCELADO)
