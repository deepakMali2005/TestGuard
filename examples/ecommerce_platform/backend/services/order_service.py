import uuid
from typing import Optional

from backend.models import Customer, Order, OrderItem, Product
from backend.repositories.base import (
    ICustomerRepository,
    IOrderRepository,
    IProductRepository,
)
from backend.services.pricing_service import PricingService


class OrderService:
    """
    Coordinates multi-entity order processing with inventory checks
    and transactional persistence.
    """

    def __init__(
        self,
        customer_repo: ICustomerRepository,
        product_repo: IProductRepository,
        order_repo: IOrderRepository,
        pricing_service: Optional[PricingService] = None,
    ) -> None:
        self.customer_repo = customer_repo
        self.product_repo = product_repo
        self.order_repo = order_repo
        self.pricing_service = pricing_service or PricingService()

    def create_order(
        self,
        customer_id: str,
        cart_items: list[dict],
    ) -> Order:
        """
        Creates an order after validating customer exists, checking stock,
        deducting inventory, and persisting the order record.
        """
        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer with ID '{customer_id}' not found.")

        if not cart_items:
            raise ValueError("Cannot create an empty order.")

        order_items: list[OrderItem] = []

        # Validate stock and assemble items
        for entry in cart_items:
            prod_id = entry["product_id"]
            qty = entry["quantity"]
            if qty <= 0:
                raise ValueError("Quantity must be greater than zero.")

            product = self.product_repo.get_by_id(prod_id)
            if not product:
                raise ValueError(f"Product '{prod_id}' not found.")

            if product.stock < qty:
                raise ValueError(
                    f"Insufficient stock for '{product.name}'. Available: {product.stock}, Requested: {qty}"
                )

            order_items.append(
                OrderItem(
                    product_id=product.id,
                    quantity=qty,
                    unit_price=product.price,
                )
            )

        # Calculate pricing with customer tier discount
        subtotal, discount_amount, total = self.pricing_service.calculate_order_pricing(
            items=order_items,
            customer_type=customer.customer_type.value,
        )

        # Deduct stock
        for item in order_items:
            prod = self.product_repo.get_by_id(item.product_id)
            if prod:
                self.product_repo.update_stock(prod.id, prod.stock - item.quantity)

        # Assemble and persist order
        order = Order(
            id=str(uuid.uuid4()),
            customer_id=customer.id,
            customer_type=customer.customer_type,
            items=order_items,
            subtotal=subtotal,
            discount_amount=discount_amount,
            total=total,
            status="CONFIRMED",
        )

        self.order_repo.save(order)
        return order
