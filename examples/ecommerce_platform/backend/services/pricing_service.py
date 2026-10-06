from backend.models import OrderItem
from backend.strategies.discount_strategy import (
    IDiscountStrategy,
    TieredDiscountStrategy,
)


class PricingService:
    """Computes order subtotals and applies configured discount strategies."""

    def __init__(self, discount_strategy: IDiscountStrategy | None = None) -> None:
        self.discount_strategy = discount_strategy or TieredDiscountStrategy()

    def calculate_subtotal(self, items: list[OrderItem]) -> float:
        return sum(item.total_price for item in items)

    def calculate_order_pricing(
        self, items: list[OrderItem], customer_type: str
    ) -> tuple[float, float, float]:
        """
        Returns:
            (subtotal, discount_amount, final_total)
        """
        subtotal = self.calculate_subtotal(items)
        final_total = self.discount_strategy.calculate_discount(subtotal, customer_type)
        discount_amount = max(0.0, subtotal - final_total)
        return (round(subtotal, 2), round(discount_amount, 2), round(final_total, 2))
