from django.test import TestCase
from django.urls import reverse
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, InventoryMovement
from inventory import services as inv_services
from customers.models import Customer
from sales import services as sales_services
from sales.models import Order, ReturnItem
from dashboard import services as dash_services


class DashboardAnalyticsTests(TestCase):
    def setUp(self):
        # 1. Categories
        self.cat_clocks = Category.objects.create(name="Chess Clocks")
        self.cat_boards = Category.objects.create(name="Chess Boards")

        # 2. Products
        self.clock = Product.objects.create(
            category=self.cat_clocks,
            sku="CLK-TEST-01",
            name="DGT Digital Clock",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00"),
            low_stock_threshold=5
        )
        self.board = Product.objects.create(
            category=self.cat_boards,
            sku="BRD-TEST-01",
            name="Tournament Board",
            selling_price=Decimal("50.00"),
            cost_price=Decimal("20.00"),
            low_stock_threshold=2
        )

        # 3. Stores
        self.phys_store = Store.objects.create(name="Downtown Physical Store", store_type=Store.PHYSICAL)
        self.online_store = Store.objects.create(name="Online Webstore", store_type=Store.ONLINE)

        # 4. Inventory
        inv_services.adjust_stock(self.clock, self.phys_store, 10, InventoryMovement.PURCHASE)
        inv_services.adjust_stock(self.clock, self.online_store, 10, InventoryMovement.PURCHASE)
        inv_services.adjust_stock(self.board, self.phys_store, 10, InventoryMovement.PURCHASE)
        inv_services.adjust_stock(self.board, self.online_store, 15, InventoryMovement.PURCHASE)

        # 5. Customer
        self.customer = Customer.objects.create(
            name="Chess Master",
            email="master@chess.org",
            customer_type=Customer.INDIVIDUAL
        )

    def test_kpi_calculations_with_sales_and_returns(self):
        # Order 1: POS sale of 2 clocks ($200 rev, $120 cost, $80 profit)
        sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 2}],
            auto_confirm=True
        )

        # Order 2: Online sale of 2 boards ($100 rev, $40 cost, $60 profit)
        order2 = sales_services.create_order(
            customer=self.customer,
            store=self.online_store,
            items_data=[{'product': self.board, 'quantity': 2}],
            auto_confirm=False
        )
        sales_services.confirm_order(order2)

        # Total gross revenue = $200 + $100 = $300
        # Total cost = $120 + $40 = $160
        # Net profit = $300 - $160 = $140
        kpis = dash_services.get_dashboard_kpis()
        self.assertEqual(kpis['total_orders'], 2)
        self.assertEqual(kpis['gross_revenue'], Decimal("300.00"))
        self.assertEqual(kpis['net_revenue'], Decimal("300.00"))
        self.assertEqual(kpis['cogs'], Decimal("160.00"))
        self.assertEqual(kpis['net_profit'], Decimal("140.00"))

        # Process a return on Order 2 (1 board returned and restocked)
        # Advance through valid transition path: CONFIRMED -> PROCESSING -> SHIPPED -> DELIVERED
        sales_services.transition_order_status(order2, Order.PROCESSING)
        sales_services.transition_order_status(order2, Order.SHIPPED)
        sales_services.transition_order_status(order2, Order.DELIVERED)
        order2_item = order2.items.first()
        sales_services.process_order_return(
            order=order2,
            return_items_data=[{'order_item': order2_item, 'quantity': 1, 'condition': ReturnItem.SELLABLE}],
            reason="Unwanted gift",
            restock_inventory=True
        )

        # After return:
        # Net revenue = $300 - $50 = $250
        # Adjusted COGS = $160 - $20 = $140
        # Net profit = $250 - $140 = $110
        kpis_after = dash_services.get_dashboard_kpis()
        self.assertEqual(kpis_after['total_refunds'], Decimal("50.00"))
        self.assertEqual(kpis_after['net_revenue'], Decimal("250.00"))
        self.assertEqual(kpis_after['cogs'], Decimal("140.00"))
        self.assertEqual(kpis_after['net_profit'], Decimal("110.00"))

    def test_channel_comparison(self):
        # POS sale $100
        sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 1}],
            auto_confirm=True
        )
        # Online sale $150 (3 boards)
        o_online = sales_services.create_order(
            customer=self.customer,
            store=self.online_store,
            items_data=[{'product': self.board, 'quantity': 3}],
            auto_confirm=False
        )
        sales_services.confirm_order(o_online)

        comparison = dash_services.get_channel_comparison()
        self.assertEqual(len(comparison), 2)
        phys = next(c for c in comparison if c['store_type'] == Store.PHYSICAL)
        online = next(c for c in comparison if c['store_type'] == Store.ONLINE)

        self.assertEqual(phys['revenue'], 100.0)
        self.assertEqual(online['revenue'], 150.0)
        self.assertEqual(phys['share_percent'], 40.0)   # 100 / 250 = 40%
        self.assertEqual(online['share_percent'], 60.0) # 150 / 250 = 60%

    def test_best_selling_products(self):
        # Sell 4 boards and 1 clock
        sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[
                {'product': self.board, 'quantity': 4},
                {'product': self.clock, 'quantity': 1},
            ],
            auto_confirm=True
        )

        best_sellers = dash_services.get_best_selling_products(limit=5)
        self.assertEqual(len(best_sellers), 2)
        # Top product should be the board (4 units sold)
        self.assertEqual(best_sellers[0]['name'], "Tournament Board")
        self.assertEqual(best_sellers[0]['units_sold'], 4)
        self.assertEqual(best_sellers[0]['total_revenue'], Decimal("200.00"))
        self.assertEqual(best_sellers[0]['profit'], Decimal("120.00"))

    def test_dashboard_view_renders_successfully(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Retail Dashboard")
        self.assertContains(response, "Net Revenue")
        self.assertContains(response, "Net Profit")
        self.assertContains(response, "Sales Channels Comparison")
