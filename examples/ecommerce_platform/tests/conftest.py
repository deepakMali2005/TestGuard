import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.database import Database
from backend.models import Customer, CustomerType, Product
from backend.repositories.sqlite_repository import (
    SQLiteCustomerRepository,
    SQLiteOrderRepository,
    SQLiteProductRepository,
)
from backend.services.order_service import OrderService
from backend.services.pricing_service import PricingService
from backend.strategies.discount_strategy import TieredDiscountStrategy


@pytest.fixture
def in_memory_db(tmp_path):
    """Provides a fresh isolated SQLite database file per test session."""
    db_file = tmp_path / "test_ecommerce.db"
    return Database(db_file)


@pytest.fixture
def repositories(in_memory_db):
    cust_repo = SQLiteCustomerRepository(in_memory_db)
    prod_repo = SQLiteProductRepository(in_memory_db)
    ord_repo = SQLiteOrderRepository(in_memory_db)

    # Seed baseline fixtures
    cust_repo.save(
        Customer(
            id="C_PREM",
            name="Alice",
            customer_type=CustomerType.PREMIUM,
            email="alice@test.com",
        )
    )
    cust_repo.save(
        Customer(
            id="C_REG",
            name="Bob",
            customer_type=CustomerType.REGULAR,
            email="bob@test.com",
        )
    )

    prod_repo.save(Product(id="P1", name="Laptop", price=1200.0, stock=5))
    prod_repo.save(Product(id="P2", name="Mouse", price=50.0, stock=20))

    return {
        "customer": cust_repo,
        "product": prod_repo,
        "order": ord_repo,
    }


@pytest.fixture
def order_service(repositories):
    pricing_svc = PricingService(TieredDiscountStrategy())
    return OrderService(
        customer_repo=repositories["customer"],
        product_repo=repositories["product"],
        order_repo=repositories["order"],
        pricing_service=pricing_svc,
    )
