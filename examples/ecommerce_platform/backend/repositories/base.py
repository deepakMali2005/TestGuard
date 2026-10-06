from abc import ABC, abstractmethod
from typing import Optional

from backend.models import Customer, Order, Product


class ICustomerRepository(ABC):
    @abstractmethod
    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        pass

    @abstractmethod
    def save(self, customer: Customer) -> None:
        pass


class IProductRepository(ABC):
    @abstractmethod
    def get_by_id(self, product_id: str) -> Optional[Product]:
        pass

    @abstractmethod
    def list_all(self) -> list[Product]:
        pass

    @abstractmethod
    def save(self, product: Product) -> None:
        pass

    @abstractmethod
    def update_stock(self, product_id: str, new_stock: int) -> None:
        pass


class IOrderRepository(ABC):
    @abstractmethod
    def get_by_id(self, order_id: str) -> Optional[Order]:
        pass

    @abstractmethod
    def list_by_customer(self, customer_id: str) -> list[Order]:
        pass

    @abstractmethod
    def save(self, order: Order) -> None:
        pass
