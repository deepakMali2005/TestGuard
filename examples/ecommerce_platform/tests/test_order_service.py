import pytest
from backend.models import CustomerType


def test_create_order_successful(order_service, repositories):
    cart = [
        {"product_id": "P1", "quantity": 1},  # Laptop 1200
        {"product_id": "P2", "quantity": 2},  # Mouse 50 * 2 = 100
    ]

    order = order_service.create_order(
        customer_id="C_PREM",
        cart_items=cart,
    )

    assert order.status == "CONFIRMED"
    assert order.subtotal == 1300.0
    # Premium customer with subtotal > 1000 gets 20% discount
    assert order.discount_amount == 260.0
    assert order.total == 1040.0

    # Stock should be decremented
    updated_laptop = repositories["product"].get_by_id("P1")
    assert updated_laptop.stock == 4  # was 5


def test_create_order_insufficient_stock(order_service):
    cart = [
        {"product_id": "P1", "quantity": 99},  # exceeds stock 5
    ]

    with pytest.raises(ValueError) as exc_info:
        order_service.create_order(
            customer_id="C_PREM",
            cart_items=cart,
        )
    assert "Insufficient stock" in str(exc_info.value)


def test_create_order_unknown_customer(order_service):
    with pytest.raises(ValueError) as exc_info:
        order_service.create_order(
            customer_id="NON_EXISTENT",
            cart_items=[{"product_id": "P1", "quantity": 1}],
        )
    assert "not found" in str(exc_info.value)


def test_create_order_empty_cart(order_service):
    with pytest.raises(ValueError) as exc_info:
        order_service.create_order(
            customer_id="C_PREM",
            cart_items=[],
        )
    assert "empty order" in str(exc_info.value)
