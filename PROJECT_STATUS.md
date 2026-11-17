# ChessMart Project Status & Handover Report

*Last Updated: Phase 3 Completion*

---

## 1. Project Overview
- **Project Name:** ChessMart
- **Objective:** Build a web-based retail operations and sales management system for chess equipment (boards, clocks, pieces, books, accessories) operating across both a physical store (POS) and an online channel.
- **Tech Stack:**
  - **Backend:** Python 3.13, Django 6.1
  - **Database:** PostgreSQL (with SQLite development fallback via `.env`), SQL
  - **Frontend:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons, JavaScript (vanilla)
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

### Phase 3: Sales and Order Management
- **Sales and Order Service Layer (`sales/services.py`)**:
  - `create_order(...)`: Atomically creates orders with multiple line items, calculates totals, checks stock availability, freezes historical selling & cost prices, and supports instant POS confirmation (`auto_confirm=True`).
  - `confirm_order(...)`: Validates available stock, transitions status from `PENDING` to `CONFIRMED`, and atomically deducts store inventory.
  - `transition_order_status(...)`: Enforces valid status transitions (`PENDING -> CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED` or `CANCELLED`).
  - `cancel_order(...)`: Atomically restores previously deducted stock if the order was confirmed/in-progress and records a `RETURN` inventory movement.
  - `process_order_return(...)`: Records return items, calculates refund, inspects condition (`SELLABLE` vs `DAMAGED`), and restocks inventory **only** when items are verified sellable.
- **Sales Forms & UI (`sales/forms.py`, `sales/views.py`)**:
  - `pos_checkout`: Interactive counter checkout terminal for the physical store with dynamic product catalog search, live cart calculation, automatic walk-in customer fallback, and immediate stock deduction.
  - `online_order_create`: Webstore order placement interface generating pending orders with warehouse stock checks.
  - `order_list`: Multi-channel order list with status badges, channel filters, search, and totals.
  - `order_detail`: Complete invoice and tracking view with line-item breakdown, gross profit calculations, status progression actions, and returns history.
  - `order_return_create`: Formal return processing with line-by-line quantity selection, condition inspection, and restock options.
  - Templates created in `templates/sales/`: `order_list.html`, `order_detail.html`, `pos_checkout.html`, `online_order_form.html`, `order_return_form.html`.

---

## 3. Current Status
- **Last Completed Phase:** Phase 3 (Sales and Order Management).
- **Working Features:**
  - Product Catalog browsing, searching, and category filtering.
  - Product creation, editing, and soft deactivation.
  - Category creation and management.
  - Multi-store inventory tracking (Physical Store vs. Online Channel).
  - Transactional stock in and stock adjustment with movement audit logs.
  - Prevention of negative stock (atomic rollback on insufficient inventory).
  - Real-time low-stock alert monitoring.
  - Physical store Point-of-Sale (POS) counter checkout with instant stock deduction.
  - Online channel order creation in PENDING state.
  - Order confirmation with stock verification and atomic deduction.
  - Order status progression state machine.
  - Order cancellation with automatic inventory restoration.
  - Customer return filing with sellable vs. damaged item inspection and conditional restocking.
- **Pending Features:**
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
  - `OrderReturn` 1:N `ReturnItem`

---

## 5. Testing
- **Test Suite:** Executed via `python manage.py test`.
- **Results:** **35 tests passed** (0 failures, 0 errors) in 0.334s.
  - Model and schema constraints: 11 tests.
  - Product forms, SKU uppercase normalization, CRUD views: 8 tests.
  - Inventory transactional services, stock rollback on insufficient inventory, availability check, low-stock query, views: 8 tests.
  - Sales service operations (POS sale deduction, online order pending, status transitions, cancellation restock, return sellable vs damaged restock) and views (order list, detail, pos checkout, online order, transition, returns): 8 tests.
- **Untested Scenarios:** Customer CRM detail views (Phase 4) and Analytics aggregation queries (Phase 5).

---

## 6. Known Issues & Limitations
- **PostgreSQL Windows Service:** PostgreSQL 18 was partially downloaded earlier without binaries in PATH. App is currently running on SQLite for development speed, ready to switch to PostgreSQL whenever the user starts the PostgreSQL service.
- **No Unresolved Bugs:** All active features have passing unit tests.

---

## 7. Git Version Control
- **Current Branch:** `master`
- **Previous Commit:** `7e0a988` ("Phase 2: Complete Product and Inventory Management with transactional services and seed data")
- **Pending Commit:** Phase 3 files and updated `PROJECT_STATUS.md` ready to be committed.

---

## 8. Next Steps (Phase 4)
- **Task:** Implement **Phase 4: Customer Management**.
- **Key Deliverables:**
  - Customer directory view (search by name, email, phone, filter by type: Individual, Chess Academy, Chess Club).
  - Customer profile page with full purchase history, total lifetime spend, and non-cancelled order counts.
  - Customer registration and edit forms with email uniqueness and input validation.
  - Customer segment tags (Individual, Academy, Club).
- **Files to Inspect First:**
  - `customers/models.py`
  - `customers/views.py`
  - `customers/forms.py`
  - `customers/urls.py`
