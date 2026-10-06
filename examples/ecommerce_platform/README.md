# E-Commerce Order & Pricing Platform

A modular order processing and pricing engine built with FastAPI, SQLite, and vanilla HTML/CSS/JS.

---

## Directory Structure

- `backend/`
  - `models.py`: Domain entity definitions (`Customer`, `Product`, `Order`).
  - `database.py`: SQLite connection management and migrations.
  - `repositories/`: Database access layer (`Customer`, `Product`, `Order`).
  - `strategies/`: Discount calculation strategies.
  - `services/`: Core business logic (`OrderService`, `PricingService`).
  - `api.py`: FastAPI endpoints.
- `frontend/`: Storefront web interface.
- `tests/`: Pytest test suite covering domain logic, persistence, and endpoints.
- `SRS.md`: Formal software requirements specification.

---

## Running the Application

### 1. Run Tests
```bash
python -m pytest
```

### 2. Start the API & Storefront
```bash
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8001
```
Open [http://127.0.0.1:8001](http://127.0.0.1:8001) in your browser.
