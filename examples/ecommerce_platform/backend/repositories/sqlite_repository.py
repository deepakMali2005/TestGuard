from typing import Optional

from backend.database import Database
from backend.models import Customer, CustomerType, Order, OrderItem, Product
from backend.repositories.base import (
    ICustomerRepository,
    IOrderRepository,
    IProductRepository,
)


class SQLiteCustomerRepository(ICustomerRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_by_id(self, customer_id: str) -> Optional[Customer]:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "SELECT id, name, customer_type, email FROM customers WHERE id = ?",
                (customer_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return Customer(
                id=row["id"],
                name=row["name"],
                customer_type=CustomerType(row["customer_type"]),
                email=row["email"],
            )

    def save(self, customer: Customer) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO customers (id, name, customer_type, email)
                VALUES (?, ?, ?, ?)
                """,
                (
                    customer.id,
                    customer.name,
                    customer.customer_type.value,
                    customer.email,
                ),
            )


class SQLiteProductRepository(IProductRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_by_id(self, product_id: str) -> Optional[Product]:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "SELECT id, name, price, stock FROM products WHERE id = ?",
                (product_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return Product(
                id=row["id"],
                name=row["name"],
                price=float(row["price"]),
                stock=int(row["stock"]),
            )

    def list_all(self) -> list[Product]:
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "SELECT id, name, price, stock FROM products ORDER BY name ASC"
            )
            return [
                Product(
                    id=row["id"],
                    name=row["name"],
                    price=float(row["price"]),
                    stock=int(row["stock"]),
                )
                for row in cursor.fetchall()
            ]

    def save(self, product: Product) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO products (id, name, price, stock)
                VALUES (?, ?, ?, ?)
                """,
                (product.id, product.name, product.price, product.stock),
            )

    def update_stock(self, product_id: str, new_stock: int) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE products SET stock = ? WHERE id = ?",
                (new_stock, product_id),
            )


class SQLiteOrderRepository(IOrderRepository):
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_by_id(self, order_id: str) -> Optional[Order]:
        with self.db.transaction() as conn:
            order_row = conn.execute(
                """
                SELECT id, customer_id, customer_type, subtotal, discount_amount, total, status, created_at
                FROM orders WHERE id = ?
                """,
                (order_id,),
            ).fetchone()

            if not order_row:
                return None

            items_cursor = conn.execute(
                """
                SELECT product_id, quantity, unit_price
                FROM order_items WHERE order_id = ?
                """,
                (order_id,),
            )

            items = [
                OrderItem(
                    product_id=row["product_id"],
                    quantity=int(row["quantity"]),
                    unit_price=float(row["unit_price"]),
                )
                for row in items_cursor.fetchall()
            ]

            return Order(
                id=order_row["id"],
                customer_id=order_row["customer_id"],
                customer_type=CustomerType(order_row["customer_type"]),
                items=items,
                subtotal=float(order_row["subtotal"]),
                discount_amount=float(order_row["discount_amount"]),
                total=float(order_row["total"]),
                status=order_row["status"],
                created_at=order_row["created_at"],
            )

    def list_by_customer(self, customer_id: str) -> list[Order]:
        with self.db.transaction() as conn:
            orders_rows = conn.execute(
                "SELECT id FROM orders WHERE customer_id = ? ORDER BY created_at DESC",
                (customer_id,),
            ).fetchall()

        orders: list[Order] = []
        for row in orders_rows:
            order = self.get_by_id(row["id"])
            if order:
                orders.append(order)
        return orders

    def save(self, order: Order) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO orders (
                    id, customer_id, customer_type, subtotal, discount_amount, total, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    order.id,
                    order.customer_id,
                    order.customer_type.value,
                    order.subtotal,
                    order.discount_amount,
                    order.total,
                    order.status,
                    order.created_at,
                ),
            )

            conn.execute("DELETE FROM order_items WHERE order_id = ?", (order.id,))
            for item in order.items:
                conn.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (order.id, item.product_id, item.quantity, item.unit_price),
                )
