from src.discount import discount


def test_premium_discount():
    assert discount(1200, "premium") == 960

def test_r2_exact_threshold():
    assert discount(1000, "premium") == 1000


def test_r3_below_threshold():
    assert discount(999, "premium") == 999


def test_r4_non_premium():
    assert discount(1200, "regular") == 1200
