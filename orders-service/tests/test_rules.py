import pytest

from app.rules import OrderStatus, calculate_total, can_transition


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
