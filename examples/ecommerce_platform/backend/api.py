from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.database import Database
from backend.models import Customer, CustomerType, Product
from backend.repositories.sqlite_repository import (
    SQLiteCustomerRepository,
    SQLiteOrderRepository,
    SQLiteProductRepository,
)
from backend.services.order_service import OrderService
from backend.services.pricing_service import PricingService
from backend.strategies.discount_strategy import discount

app = FastAPI(
    title="E-Commerce Order & Pricing API",
    description="Real-world order processing and pricing engine backed by SQLite",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
db = Database()
customer_repo = SQLiteCustomerRepository(db)
product_repo = SQLiteProductRepository(db)
order_repo = SQLiteOrderRepository(db)
pricing_service = PricingService()
order_service = OrderService(
    customer_repo=customer_repo,
    product_repo=product_repo,
    order_repo=order_repo,
    pricing_service=pricing_service,
)


def seed_sample_data():
    """Populates initial customer tiers and catalog items if table is empty."""
    if not product_repo.list_all():
        product_repo.save(Product(id="P1", name="Mechanical Keyboard", price=1200.0, stock=20))
        product_repo.save(Product(id="P2", name="Ergonomic Mouse", price=600.0, stock=35))
        product_repo.save(Product(id="P3", name="USB-C Hub", price=400.0, stock=15))
        product_repo.save(Product(id="P4", name="27-inch 4K Monitor", price=15000.0, stock=8))

    if not customer_repo.get_by_id("C_PREMIUM"):
        customer_repo.save(
            Customer(
                id="C_PREMIUM",
                name="Alice Walker",
                customer_type=CustomerType.PREMIUM,
                email="alice@example.com",
            )
        )
    if not customer_repo.get_by_id("C_REGULAR"):
        customer_repo.save(
            Customer(
                id="C_REGULAR",
                name="Bob Smith",
                customer_type=CustomerType.REGULAR,
                email="bob@example.com",
            )
        )


seed_sample_data()


# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------
class CartItemInput(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class CreateOrderInput(BaseModel):
    customer_id: str
    items: list[CartItemInput]


class CalculateDiscountInput(BaseModel):
    amount: float = Field(ge=0)
    customer_type: str


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------
@app.get("/")
def get_frontend():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "E-Commerce API is running."}


@app.get("/api/products")
def list_products():
    return [
        {
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "stock": p.stock,
        }
        for p in product_repo.list_all()
    ]


@app.post("/api/calculate-discount")
def calculate_discount_endpoint(payload: CalculateDiscountInput):
    discounted = discount(payload.amount, payload.customer_type)
    return {
        "original_amount": payload.amount,
        "customer_type": payload.customer_type,
        "discounted_amount": discounted,
        "savings": round(payload.amount - discounted, 2),
    }


@app.post("/api/orders")
def place_order(payload: CreateOrderInput):
    try:
        cart_data = [
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in payload.items
        ]
        order = order_service.create_order(
            customer_id=payload.customer_id,
            cart_items=cart_data,
        )
        return {
            "order_id": order.id,
            "customer_id": order.customer_id,
            "customer_type": order.customer_type.value,
            "subtotal": order.subtotal,
            "discount_amount": order.discount_amount,
            "total": order.total,
            "status": order.status,
            "created_at": order.created_at,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Order failed: {str(exc)}")


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    order = order_repo.get_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order.id,
        "customer_id": order.customer_id,
        "customer_type": order.customer_type.value,
        "subtotal": order.subtotal,
        "discount_amount": order.discount_amount,
        "total": order.total,
        "status": order.status,
        "items": [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
            }
            for item in order.items
        ],
    }
