# Software Requirements Specification (SRS)
## E-Commerce Order & Pricing Management Engine

---

### 1. Purpose and Scope
This specification defines the functional, computational, and data consistency requirements for the Order and Pricing Engine. The system computes transaction totals, evaluates customer tier loyalty privileges, validates product inventory in real time, and persists transactional records to an SQLite database.

---

### 2. System Domain and Workflow
The system processes customer purchases through an automated verification pipeline:
1. **Catalog & Stock Verification**: Products are checked for available quantities before allocation.
2. **Pricing & Loyalty Evaluation**: Orders are evaluated based on account tier status and qualifying order subtotals.
3. **Transactional Persistence**: Inventory deductions and confirmed orders are committed atomically.

---

### 3. Functional Requirements

R1: Premium customers receive a 20% discount when the order amount is strictly greater than ₹1000. For orders where cumulative eligible cart items exceed the qualifying baseline, the discount rate applies across the full subtotal before local taxes, excluding canceled or refunded line items, and results in a 20% discount applied only when the verified cart value remains greater than ₹1000.

R2: Premium customers with an order amount equal to ₹1000 receive no discount. Boundary edge-cases where the cart subtotal evaluates to exactly the threshold baseline must be processed at full standard unit pricing without deductions, ensuring that accounts with verified premium status experiencing an exact match equal to ₹1000 receive no discount.

R3: Premium customers with an order amount less than ₹1000 receive no discount. Orders failing to reach the qualifying threshold baseline, including micro-transactions, fractional amounts, or carts whose active items sum to any value strictly below the tier threshold, do not qualify for promotional deductions and premium members with subtotal less than ₹1000 receive no discount.

R4: Non-premium customers receive no discount regardless of the order amount. All standard retail accounts, guest profiles, or unverified customer tiers must be billed at the full aggregate price across all purchase volumes and basket sizes, guaranteeing that any non-premium account receives no discount regardless of the order amount.

---

### 4. Data and Operational Integrity
- **Database Consistency**: All confirmed purchases and updated inventory levels must be committed to the database.
- **Precision**: Monetary calculations must maintain two decimal places of precision without floating-point drift.
- **Stock Guard**: Orders requesting quantities exceeding current inventory must be rejected immediately without partial deduction.
