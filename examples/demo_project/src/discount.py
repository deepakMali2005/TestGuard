def discount(amount, customer_type):
    if customer_type == "premium" and amount > 1000:
        return amount * 0.8

    return amount