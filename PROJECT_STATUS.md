# ChessMart Project Status & Handover Report

*Last Updated: Phase 2 Completion*

---

## 1. Project Overview
- **Project Name:** ChessMart
- **Objective:** Build a web-based retail operations and sales management system for chess equipment (boards, clocks, pieces, books, accessories) operating across both a physical store (POS) and an online channel.
- **Tech Stack:**
  - **Backend:** Python 3.13, Django 6.1
  - **Database:** PostgreSQL (with SQLite development fallback via `.env`), SQL
  - **Frontend:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons
  - **Tools:** Git, python-dotenv, psycopg (v3)
- **Architecture:** Modular Django design (`products`, `inventory`, `sales`, `customers`, `dashboard`). Business logic encapsulated in service layers with strict transactional atomicity (`@transaction.atomic`, `select_for_update()`).

---

## 2. Completed Work

### Phase 1: Project Setup and Database Architecture
- Virtual environment created and core dependencies installed (`Django`, `psycopg[binary]`, `python-dotenv`).
- Configured PostgreSQL connection in `settings.py` via `.env` (`USE_POSTGRES=False/True`).
- Normalized relational schema created and migrated across all 4 core apps:
  - `products`: `Category`, `Product` (with SKU uniqueness, profit properties, low-stock threshold).
  - `inventory`: `Store` (Physical vs Online), `Inventory` (`CheckConstraint(quantity >= 0)`, `unique_together(product, store)`), `InventoryMovement` (immutable audit log).
  - `customers`: `Customer` (Individual, Academy, Club).
  - `sales`: `Order`, `OrderItem` (freezing historical selling and cost prices), `OrderReturn`, `ReturnItem`.
- Django admin configured with customized list displays and inline relationships.
- Bootstrap 5 global responsive template layout (`templates/base.html`, `static/css/custom.css`).

### Phase 2: Product and Inventory Management
- **Product Management (`products` app)**:
  - Form validations in `products/forms.py` (`ProductForm`, `CategoryForm`) enforcing positive prices, SKU normalization, and unique checks.
  - CRUD views in `products/views.py`: Product catalog list (category filtering, search, status filter), Product details (financial margins and store distribution), Create/Update forms, Soft activation/deactivation toggle, Category management.
  - Templates created in `templates/products/`: `product_list.html`, `product_detail.html`, `product_form.html`, `category_list.html`.
- **Inventory Operations (`inventory` app)**:
  - Transactional service layer `inventory/services.py`:
    - `adjust_stock(...)`: Handles atomic additions/deductions with `select_for_update()`, blocks negative inventory, and records `InventoryMovement` audit entries.
    - `check_stock_availability(...)`: Verifies stock availability before order placements.
    - `get_low_stock_products(...)`: Real-time query for products reaching or below threshold.
  - Inventory views in `inventory/views.py`: Multi-channel inventory matrix, Stock Adjustment/Stock-In form, Audit movement history with filters, Low-stock alerts dashboard.
  - Templates created in `templates/inventory/`: `inventory_list.html`, `stock_adjust.html`, `movement_history.html`, `low_stock.html`.
  - Database seeding command `python manage.py seed_chessmart` populating physical and online stores, 5 product categories, and 10 realistic chess products with initial stock and movement records.

---

## 3. Current Status
- **Last Completed Phase:** Phase 2 (Product and Inventory Management).
- **Working Features:**
  - Product Catalog browsing, searching, and category filtering.
  - Product creation, editing, and soft deactivation.
  - Category creation and management.
  - Multi-store inventory tracking (Physical Store vs. Online Channel).
  - Transactional stock in and stock adjustment with movement audit logs.
  - Prevention of negative stock (atomic rollback on insufficient inventory).
  - Real-time low-stock alert monitoring.
- **Pending Features:**
  - **Phase 3:** Sales and Order Management (POS sale, online orders, order item calculation, inventory reservation/deduction on confirmation, cancellation stock restore, return restock workflows).
  - **Phase 4:** Customer Management (CRM customer profiles, order history aggregation, customer classification).
  - **Phase 5:** Sales Dashboard and Reporting (Revenue, profit calculations, channel comparison charts).
  - **Phase 6:** End-to-end testing and edge cases.
  - **Phase 7:** Documentation and deployment.

---

## 4. Database
- **Active Engine:** SQLite during active development (`USE_POSTGRES=False` in `.env`), with instant toggle to PostgreSQL (`USE_POSTGRES=True` using `psycopg3`).
- **Migrations Applied:**
  - `customers.0001_initial`
  - `products.0001_initial`
  - `inventory.0001_initial`
  - `inventory.0002_initial`
  - `sales.0001_initial`
- **Key Relationships:**
  - `Category` 1:N `Product`
  - `Product` 1:N `Inventory` (per `Store`)
  - `Product` 1:N `InventoryMovement`
  - `Store` 1:N `InventoryMovement`
  - `Customer` 1:N `Order`
  - `Order` 1:N `OrderItem`
  - `Order` 1:N `OrderReturn`

---

## 5. Testing
- **Test Suite:** Executed via `python manage.py test`.
- **Results:** **27 tests passed** (0 failures, 0 errors) in 0.209s.
  - Model and schema constraints: 11 tests.
  - Product forms, SKU uppercase normalization, CRUD views: 8 tests.
  - Inventory transactional services, stock rollback on insufficient inventory, availability check, low-stock query, views: 8 tests.
- **Untested Scenarios:** Order creation, status transitions, and returns (reserved for Phase 3).

---

## 6. Known Issues & Limitations
- **PostgreSQL Windows Service:** PostgreSQL 18 was partially downloaded earlier without binaries in PATH. App is currently running on SQLite for development speed, ready to switch to PostgreSQL whenever the user starts the PostgreSQL service.
- **No Unresolved Bugs:** All active features have passing unit tests.

---

## 7. Git Version Control
- **Current Branch:** `master`
- **Previous Commit:** `9073cd9` ("Phase 1: Project setup, database architecture, and initial models")
- **Pending Commit:** Phase 2 files and `PROJECT_STATUS.md` staged and committed.

---

## 8. Next Steps (Phase 3)
- **Task:** Implement **Phase 3: Sales and Order Management**.
- **Key Deliverables:**
  - Physical Store POS checkout view (fast in-store purchase).
  - Online Order creation and tracking.
  - Service functions for atomic order confirmation (stock deduction), cancellation (stock restock), and return processing.
  - Order status transition state machine enforcement.
- **Files to Inspect First:**
  - `sales/models.py`
  - `inventory/services.py`
  - `sales/views.py`
  - `sales/forms.py`
