from abc import ABC, abstractmethod


class IDiscountStrategy(ABC):
    """Abstract discount calculation strategy."""

    @abstractmethod
    def calculate_discount(self, amount: float, customer_type: str) -> float:
        """Returns the final discounted total for an order."""
        pass


def discount(amount: float, customer_type: str) -> float:
    """
    Core business rule calculation fulfilling SRS requirements R1-R4:
    - R1: Premium customers receive a 20% discount when order amount > 1000.
    - R2: Premium customers with order amount == 1000 receive no discount.
    - R3: Premium customers with order amount < 1000 receive no discount.
    - R4: Non-premium customers receive no discount regardless of amount.
    """
    normalized_type = str(customer_type).strip().lower()

    if normalized_type == "premium" and amount > 1000:
        return amount * 0.8

    return float(amount)


class TieredDiscountStrategy(IDiscountStrategy):
    """Default tiered strategy conforming to IDiscountStrategy interface."""

    def calculate_discount(self, amount: float, customer_type: str) -> float:
        return discount(amount, customer_type)


class NoDiscountStrategy(IDiscountStrategy):
    """Plug-and-play strategy where no discounts are applied."""

    def calculate_discount(self, amount: float, customer_type: str) -> float:
        return float(amount)
