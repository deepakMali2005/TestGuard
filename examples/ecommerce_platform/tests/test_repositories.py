from backend.models import Customer, CustomerType, Product


def test_customer_repository_crud(repositories):
    cust_repo = repositories["customer"]

    new_cust = Customer(
        id="C_99",
        name="Charlie",
        customer_type=CustomerType.PREMIUM,
        email="charlie@test.com",
    )
    cust_repo.save(new_cust)

    fetched = cust_repo.get_by_id("C_99")
    assert fetched is not None
    assert fetched.name == "Charlie"
    assert fetched.customer_type == CustomerType.PREMIUM


def test_product_repository_stock_update(repositories):
    prod_repo = repositories["product"]

    prod_repo.update_stock("P1", 10)
    fetched = prod_repo.get_by_id("P1")
    assert fetched.stock == 10
