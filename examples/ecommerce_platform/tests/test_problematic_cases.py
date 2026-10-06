import random
import time
from backend.strategies.discount_strategy import discount


# 1. Ambiguous Test: Executes code but never validates behavior (No assertion)
def test_ambiguous_missing_assertion():
    """Ambiguous test smell: executes business logic without verifying anything."""
    result = discount(1500, "premium")


# 2. Redundant Test: Duplicates existing test target and identical input parameters
def test_redundant_discount_duplicate():
    """Redundant test smell: repeats test_premium_discount with exact same inputs."""
    assert discount(1200, "premium") == 960
    assert discount(1200, "premium") > 0


# 3. Out-of-Context Test: Disconnected from application targets and SRS
def test_out_of_context_unanchored():
    """Out-of-context smell: tautology with no target application call."""
    expected_sum = 42
    actual_sum = 40 + 2
    assert actual_sum == expected_sum


# 4. Flaky Test: Depends on non-deterministic state causing intermittent failures
def test_flaky_nondeterministic():
    """Flaky test smell: non-deterministic random condition prone to failure."""
    # Guarantees failure on test run to demonstrate TestGuard's execution guard
    assert random.random() > 0.99, "Flaky test failed due to non-deterministic random threshold"
