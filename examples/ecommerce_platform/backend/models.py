from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class CustomerType(str, Enum):
    PREMIUM = "premium"
    REGULAR = "regular"


@dataclass
class Customer:
    id: str
    name: str
    customer_type: CustomerType
    email: str


@dataclass
class Product:
    id: str
    name: str
    price: float
    stock: int


@dataclass
class OrderItem:
    product_id: str
    quantity: int
    unit_price: float

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price


@dataclass
class Order:
    id: str
    customer_id: str
    customer_type: CustomerType
    items: list[OrderItem]
    subtotal: float
    discount_amount: float
    total: float
    status: str = "CONFIRMED"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
