from fastapi.testclient import TestClient
from backend.api import app

client = TestClient(app)


def test_api_list_products():
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_api_calculate_discount_endpoint():
    # Premium customer with amount 1200 > 1000 -> 20% discount
    res = client.post(
        "/api/calculate-discount",
        json={"amount": 1200.0, "customer_type": "premium"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["discounted_amount"] == 960.0
    assert body["savings"] == 240.0


def test_api_place_order_endpoint():
    res = client.post(
        "/api/orders",
        json={
            "customer_id": "C_PREMIUM",
            "items": [{"product_id": "P1", "quantity": 1}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "CONFIRMED"
    assert body["customer_type"] == "premium"
    assert "order_id" in body
