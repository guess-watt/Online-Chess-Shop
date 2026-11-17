from django.test import TestCase
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, Inventory, InventoryMovement
from inventory import services as inv_services
from customers.models import Customer
from sales.models import Order, OrderItem, OrderReturn, ReturnItem
from sales import services as sales_services
from dashboard import services as dash_services


class BusinessScenariosAndEdgeCasesTests(TestCase):
    def setUp(self):
        # 1. Categories
        self.cat_clocks = Category.objects.create(name="Chess Clocks")
        self.cat_boards = Category.objects.create(name="Chess Boards")
        self.cat_pieces = Category.objects.create(name="Chess Pieces")

        # 2. Products
        self.clock = Product.objects.create(
            category=self.cat_clocks,
            sku="CLK-DGT-2010",
            name="DGT 2010 Digital Chess Clock",
            selling_price=Decimal("80.00"),
            cost_price=Decimal("45.00"),
            low_stock_threshold=5
        )
        self.board = Product.objects.create(
            category=self.cat_boards,
            sku="BRD-WAL-21",
            name="Deluxe Walnut Board (21\")",
            selling_price=Decimal("150.00"),
            cost_price=Decimal("85.00"),
            low_stock_threshold=4
        )
        self.pieces = Product.objects.create(
            category=self.cat_pieces,
            sku="PCS-GER-375",
            name="German Knight Staunton Pieces",
            selling_price=Decimal("120.00"),
            cost_price=Decimal("65.00"),
            low_stock_threshold=3
        )

        # 3. Stores
        self.phys_store = Store.objects.create(name="Downtown Physical Store", store_type=Store.PHYSICAL)
        self.online_store = Store.objects.create(name="Online Webstore", store_type=Store.ONLINE)

        # 4. Customers
        self.walkin_cust = Customer.objects.create(
            name="Walk-in Store Customer",
            email="walkin@chessmart.local",
            customer_type=Customer.INDIVIDUAL
        )
        self.academy_cust = Customer.objects.create(
            name="Metropolitan Chess Academy",
            email="contact@metropolitanchess.org",
            customer_type=Customer.ACADEMY
        )

        # 5. Initial Inventory Inflow
        inv_services.adjust_stock(self.clock, self.phys_store, 10, InventoryMovement.PURCHASE, "Initial physical stock")
        inv_services.adjust_stock(self.clock, self.online_store, 15, InventoryMovement.PURCHASE, "Initial online stock")

        inv_services.adjust_stock(self.board, self.phys_store, 6, InventoryMovement.PURCHASE, "Initial physical stock")
        inv_services.adjust_stock(self.board, self.online_store, 10, InventoryMovement.PURCHASE, "Initial online stock")

        inv_services.adjust_stock(self.pieces, self.phys_store, 5, InventoryMovement.PURCHASE, "Initial physical stock")
        inv_services.adjust_stock(self.pieces, self.online_store, 8, InventoryMovement.PURCHASE, "Initial online stock")

    # =========================================================================
    # Scenario A: Physical store purchase
    # =========================================================================
    def test_scenario_a_physical_store_purchase(self):
        """
        Customer buys a chess clock from the physical store:
        - Sales record created
        - Product & quantity recorded
        - Total calculated accurately ($80.00)
        - Physical inventory reduced from 10 to 9
        - Transaction reflected in sales reports
        """
        order = sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 1}],
            notes="Counter POS purchase",
            auto_confirm=True
        )

        self.assertEqual(order.order_status, Order.CONFIRMED)
        self.assertEqual(order.total_amount, Decimal("80.00"))
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product, self.clock)

        # Inventory check
        phys_inv = Inventory.objects.get(product=self.clock, store=self.phys_store)
        self.assertEqual(phys_inv.quantity, 9)

        # Sales reports check
        kpis = dash_services.get_dashboard_kpis()
        self.assertEqual(kpis['gross_revenue'], Decimal("80.00"))
        self.assertEqual(kpis['net_profit'], Decimal("35.00"))  # 80 - 45

    # =========================================================================
    # Scenario B: Online order
    # =========================================================================
    def test_scenario_b_online_order_lifecycle(self):
        """
        Customer places an online order:
        - Created in PENDING status
        - Stock checked before confirmation
        - Confirmed order deducts stock exactly once
        - Tracking through statuses
        """
        order = sales_services.create_order(
            customer=self.academy_cust,
            store=self.online_store,
            items_data=[
                {'product': self.board, 'quantity': 2},
                {'product': self.pieces, 'quantity': 2},
            ],
            notes="Academy tournament order",
            auto_confirm=False
        )

        self.assertEqual(order.order_status, Order.PENDING)
        # Total = (2 * 150) + (2 * 120) = $540.00
        self.assertEqual(order.total_amount, Decimal("540.00"))

        # Stock must NOT be deducted yet
        self.assertEqual(Inventory.objects.get(product=self.board, store=self.online_store).quantity, 10)

        # Confirm order: verifies stock and deducts
        sales_services.confirm_order(order)
        self.assertEqual(order.order_status, Order.CONFIRMED)
        self.assertEqual(Inventory.objects.get(product=self.board, store=self.online_store).quantity, 8)
        self.assertEqual(Inventory.objects.get(product=self.pieces, store=self.online_store).quantity, 6)

        # Order tracking progression
        sales_services.transition_order_status(order, Order.PROCESSING)
        self.assertEqual(order.order_status, Order.PROCESSING)
        sales_services.transition_order_status(order, Order.SHIPPED)
        self.assertEqual(order.order_status, Order.SHIPPED)
        sales_services.transition_order_status(order, Order.DELIVERED)
        self.assertEqual(order.order_status, Order.DELIVERED)

    # =========================================================================
    # Scenario C: Inventory synchronization
    # =========================================================================
    def test_scenario_c_inventory_synchronization(self):
        """
        A product is sold in the physical store:
        - Updates centralized stock quantity
        - Directly updates global total availability visible across channels
        """
        initial_total = self.clock.total_stock  # 10 (phys) + 15 (online) = 25
        self.assertEqual(initial_total, 25)

        # Sell 4 clocks at physical store
        sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 4}],
            auto_confirm=True
        )

        # Physical store stock is 6, online remains 15, centralized total is 21
        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.phys_store).quantity, 6)
        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.online_store).quantity, 15)
        self.assertEqual(self.clock.total_stock, 21)

    # =========================================================================
    # Scenario D: Low-stock detection
    # =========================================================================
    def test_scenario_d_low_stock_detection(self):
        """
        Product stock drops to or below minimum threshold:
        - Product threshold is 4. Currently 16 total (6 phys + 10 online).
        - Sale reduces stock to 4 (or below).
        - Low stock alert triggered and reported.
        """
        self.assertFalse(self.board.is_low_stock)

        # Sell 6 boards at physical store (leaving 0 at phys)
        sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.board, 'quantity': 6}],
            auto_confirm=True
        )

        # Sell 7 boards online (leaving 3 at online)
        o_online = sales_services.create_order(
            customer=self.academy_cust,
            store=self.online_store,
            items_data=[{'product': self.board, 'quantity': 7}],
            auto_confirm=False
        )
        sales_services.confirm_order(o_online)

        # Total stock is now 0 + 3 = 3 <= threshold 4!
        self.assertEqual(self.board.total_stock, 3)
        self.assertTrue(self.board.is_low_stock)

        # Detected in low stock service
        low_stock_list = inv_services.get_low_stock_products()
        self.assertIn(self.board, low_stock_list)

    # =========================================================================
    # Scenario E: Business reporting & product revenue ranking
    # =========================================================================
    def test_scenario_e_business_reporting_aggregation(self):
        """
        Retrieve sales records, aggregate by product, calculate revenue,
        and rank best-selling chess products.
        """
        # Sell 2 clocks ($160)
        sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 2}],
            auto_confirm=True
        )

        # Sell 3 boards ($450)
        sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.board, 'quantity': 3}],
            auto_confirm=True
        )

        best_sellers = dash_services.get_best_selling_products(limit=5)
        # Top volume and revenue is the Walnut Board ($450, 3 units)
        self.assertEqual(best_sellers[0]['sku'], "BRD-WAL-21")
        self.assertEqual(best_sellers[0]['units_sold'], 3)
        self.assertEqual(best_sellers[0]['total_revenue'], Decimal("450.00"))

        # Second is the Clock ($160, 2 units)
        self.assertEqual(best_sellers[1]['sku'], "CLK-DGT-2010")
        self.assertEqual(best_sellers[1]['units_sold'], 2)
        self.assertEqual(best_sellers[1]['total_revenue'], Decimal("160.00"))

    # =========================================================================
    # Edge Cases & Hardening
    # =========================================================================
    def test_multi_item_atomic_rollback_on_partial_stockout(self):
        """
        Multi-item order where item A has stock, but item B does not:
        Must abort atomically and NOT deduct stock for item A!
        """
        # Clock has 10 units at physical store
        # Board has only 6 units at physical store
        items_data = [
            {'product': self.clock, 'quantity': 5},   # Sufficient
            {'product': self.board, 'quantity': 10},  # Insufficient (only 6 exist)
        ]

        with self.assertRaises(ValueError) as ctx:
            sales_services.create_order(
                customer=self.walkin_cust,
                store=self.phys_store,
                items_data=items_data,
                auto_confirm=True
            )
        self.assertIn("Insufficient stock for 'Deluxe Walnut Board (21\")'", str(ctx.exception))

        # Check that Clock stock was NOT deducted (must still be 10)
        clock_inv = Inventory.objects.get(product=self.clock, store=self.phys_store)
        self.assertEqual(clock_inv.quantity, 10)

        # No order created
        self.assertEqual(Order.objects.count(), 0)

    def test_return_quantity_bounds_validation(self):
        """
        Cannot return more items than were originally ordered.
        """
        order = sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 2}],
            auto_confirm=True
        )
        sales_services.transition_order_status(order, Order.PROCESSING)
        sales_services.transition_order_status(order, Order.SHIPPED)
        sales_services.transition_order_status(order, Order.DELIVERED)

        order_item = order.items.first()

        # Attempting to return 3 units when only 2 were ordered must fail
        with self.assertRaises(ValueError) as ctx:
            sales_services.process_order_return(
                order=order,
                return_items_data=[{'order_item': order_item, 'quantity': 3, 'condition': ReturnItem.SELLABLE}],
                reason="Excess return attempt"
            )
        self.assertIn("Invalid return quantity 3", str(ctx.exception))

    def test_financial_accuracy_decimal_precision(self):
        """
        Validates cent-accurate ($0.01) calculations across selling prices, COGS,
        and multiple returns.
        """
        # Product with cent pricing
        book = Product.objects.create(
            category=self.cat_clocks,
            sku="BOK-TEST-01",
            name="Endgame Study Book",
            selling_price=Decimal("24.95"),
            cost_price=Decimal("13.40"),
            low_stock_threshold=5
        )
        inv_services.adjust_stock(book, self.phys_store, 20, InventoryMovement.PURCHASE)

        # Buy 7 books: total = 7 * 24.95 = 174.65, cost = 7 * 13.40 = 93.80, profit = 80.85
        order = sales_services.create_order(
            customer=self.walkin_cust,
            store=self.phys_store,
            items_data=[{'product': book, 'quantity': 7}],
            auto_confirm=True
        )
        self.assertEqual(order.total_amount, Decimal("174.65"))

        kpis = dash_services.get_dashboard_kpis()
        self.assertEqual(kpis['net_revenue'], Decimal("174.65"))
        self.assertEqual(kpis['cogs'], Decimal("93.80"))
        self.assertEqual(kpis['net_profit'], Decimal("80.85"))

        # Return 2 books: refund = 2 * 24.95 = 49.90, COGS recovery = 2 * 13.40 = 26.80
        # Expected new net revenue: 174.65 - 49.90 = 124.75
        # Expected new adjusted COGS: 93.80 - 26.80 = 67.00
        # Expected new net profit: 124.75 - 67.00 = 57.75
        sales_services.transition_order_status(order, Order.PROCESSING)
        sales_services.transition_order_status(order, Order.SHIPPED)
        sales_services.transition_order_status(order, Order.DELIVERED)

        sales_services.process_order_return(
            order=order,
            return_items_data=[{'order_item': order.items.first(), 'quantity': 2, 'condition': ReturnItem.SELLABLE}],
            reason="Two duplicate copies",
            restock_inventory=True
        )

        kpis_after = dash_services.get_dashboard_kpis()
        self.assertEqual(kpis_after['total_refunds'], Decimal("49.90"))
        self.assertEqual(kpis_after['net_revenue'], Decimal("124.75"))
        self.assertEqual(kpis_after['cogs'], Decimal("67.00"))
        self.assertEqual(kpis_after['net_profit'], Decimal("57.75"))
