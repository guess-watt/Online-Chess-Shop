from django.test import TestCase
from django.urls import reverse
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, Inventory, InventoryMovement
from inventory import services as inv_services
from customers.models import Customer
from sales.models import Order, OrderItem, OrderReturn, ReturnItem
from sales import services as sales_services


class SalesServiceAndModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Clocks")
        self.clock = Product.objects.create(
            category=self.category,
            sku="CLK-DGT-2010",
            name="DGT 2010 Clock",
            selling_price=Decimal("80.00"),
            cost_price=Decimal("45.00"),
            low_stock_threshold=5
        )
        self.board = Product.objects.create(
            category=self.category,
            sku="BRD-WAL-21",
            name="Walnut Chessboard",
            selling_price=Decimal("150.00"),
            cost_price=Decimal("85.00"),
            low_stock_threshold=3
        )
        self.phys_store = Store.objects.create(name="Downtown Physical Store", store_type=Store.PHYSICAL)
        self.online_store = Store.objects.create(name="Online Webstore", store_type=Store.ONLINE)
        self.customer = Customer.objects.create(
            name="Magnus Club",
            email="magnus@club.org",
            customer_type=Customer.CLUB
        )

        # Seed physical store stock
        inv_services.adjust_stock(self.clock, self.phys_store, 10, InventoryMovement.PURCHASE)
        inv_services.adjust_stock(self.board, self.phys_store, 5, InventoryMovement.PURCHASE)

        # Seed online store stock
        inv_services.adjust_stock(self.clock, self.online_store, 8, InventoryMovement.PURCHASE)

    def test_pos_order_creation_auto_confirm_and_stock_deduction(self):
        # Physical store sale of 2 clocks and 1 board
        items_data = [
            {'product': self.clock, 'quantity': 2},
            {'product': self.board, 'quantity': 1},
        ]
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=items_data,
            notes="Cash Counter POS",
            auto_confirm=True
        )

        self.assertEqual(order.order_status, Order.CONFIRMED)
        self.assertEqual(order.total_amount, Decimal("310.00"))  # (2*80) + (1*150)

        # Check stock deduction
        clock_inv = Inventory.objects.get(product=self.clock, store=self.phys_store)
        board_inv = Inventory.objects.get(product=self.board, store=self.phys_store)
        self.assertEqual(clock_inv.quantity, 8)  # 10 - 2
        self.assertEqual(board_inv.quantity, 4)  # 5 - 1

        # Check inventory movements logged
        movements = InventoryMovement.objects.filter(reference_order=order)
        self.assertEqual(movements.count(), 2)
        self.assertTrue(all(m.movement_type == InventoryMovement.SALE for m in movements))

    def test_pos_order_insufficient_stock_fails_atomically(self):
        # Attempt to buy 15 clocks when only 10 available
        items_data = [{'product': self.clock, 'quantity': 15}]
        with self.assertRaises(ValueError) as ctx:
            sales_services.create_order(
                customer=self.customer,
                store=self.phys_store,
                items_data=items_data,
                auto_confirm=True
            )
        self.assertIn("Insufficient stock", str(ctx.exception))
        # Ensure clock inventory was NOT modified
        clock_inv = Inventory.objects.get(product=self.clock, store=self.phys_store)
        self.assertEqual(clock_inv.quantity, 10)
        # Ensure no order was created
        self.assertEqual(Order.objects.count(), 0)

    def test_online_order_creation_pending_and_confirmation(self):
        # Online order created in PENDING status
        items_data = [{'product': self.clock, 'quantity': 3}]
        order = sales_services.create_order(
            customer=self.customer,
            store=self.online_store,
            items_data=items_data,
            auto_confirm=False
        )
        self.assertEqual(order.order_status, Order.PENDING)

        # Stock is NOT yet deducted in pending state
        online_inv = Inventory.objects.get(product=self.clock, store=self.online_store)
        self.assertEqual(online_inv.quantity, 8)

        # Confirm order
        sales_services.confirm_order(order)
        self.assertEqual(order.order_status, Order.CONFIRMED)

        # Now stock is deducted
        online_inv.refresh_from_db()
        self.assertEqual(online_inv.quantity, 5)

    def test_order_status_transitions_and_cancellation_restock(self):
        # Create confirmed POS sale of 2 clocks
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 2}],
            auto_confirm=True
        )
        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.phys_store).quantity, 8)

        # Advance: CONFIRMED -> PROCESSING
        sales_services.transition_order_status(order, Order.PROCESSING)
        self.assertEqual(order.order_status, Order.PROCESSING)

        # Advance: PROCESSING -> SHIPPED
        sales_services.transition_order_status(order, Order.SHIPPED)
        self.assertEqual(order.order_status, Order.SHIPPED)

        # Invalid transition: SHIPPED -> PENDING must fail
        with self.assertRaises(ValueError):
            sales_services.transition_order_status(order, Order.PENDING)

        # Cancel shipped order: must restore stock to 10
        sales_services.cancel_order(order, reason="Customer cancelled before arrival")
        self.assertEqual(order.order_status, Order.CANCELLED)
        clock_inv = Inventory.objects.get(product=self.clock, store=self.phys_store)
        self.assertEqual(clock_inv.quantity, 10)

    def test_order_return_restock_sellable_vs_damaged(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.clock, 'quantity': 2}],
            auto_confirm=True
        )
        sales_services.transition_order_status(order, Order.PROCESSING)
        sales_services.transition_order_status(order, Order.SHIPPED)
        sales_services.transition_order_status(order, Order.DELIVERED)

        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.phys_store).quantity, 8)
        order_item = order.items.first()

        # Case 1: Return 1 unit in SELLABLE condition with restock=True
        ret1 = sales_services.process_order_return(
            order=order,
            return_items_data=[{'order_item': order_item, 'quantity': 1, 'condition': ReturnItem.SELLABLE}],
            reason="Unopened item",
            restock_inventory=True
        )
        self.assertEqual(ret1.refund_amount, Decimal("80.00"))
        # Inventory increased back from 8 to 9
        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.phys_store).quantity, 9)

        # Case 2: Return 1 unit in DAMAGED condition with restock=True -> must NOT be added to sellable stock
        ret2 = sales_services.process_order_return(
            order=order,
            return_items_data=[{'order_item': order_item, 'quantity': 1, 'condition': ReturnItem.DAMAGED}],
            reason="Cracked LCD",
            restock_inventory=True
        )
        self.assertEqual(ret2.refund_amount, Decimal("80.00"))
        # Inventory remains 9 because damaged item cannot be sold
        self.assertEqual(Inventory.objects.get(product=self.clock, store=self.phys_store).quantity, 9)


class SalesViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Sets")
        self.product = Product.objects.create(
            category=self.category,
            sku="SET-STAUNTON",
            name="Staunton Chess Set",
            selling_price=Decimal("120.00"),
            cost_price=Decimal("70.00"),
            low_stock_threshold=3
        )
        self.phys_store = Store.objects.create(name="Physical Store", store_type=Store.PHYSICAL)
        self.online_store = Store.objects.create(name="Online Webstore", store_type=Store.ONLINE)
        inv_services.adjust_stock(self.product, self.phys_store, 10, InventoryMovement.PURCHASE)
        inv_services.adjust_stock(self.product, self.online_store, 10, InventoryMovement.PURCHASE)

        self.customer = Customer.objects.create(
            name="Alice Walker",
            email="alice@walker.com",
            customer_type=Customer.INDIVIDUAL
        )

    def test_order_list_view(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.product, 'quantity': 1}],
            auto_confirm=True
        )
        response = self.client.get(reverse('sales:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)

    def test_order_detail_view(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.product, 'quantity': 1}],
            auto_confirm=True
        )
        response = self.client.get(reverse('sales:detail', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SET-STAUNTON")
        self.assertContains(response, "$120.00")

    def test_pos_checkout_view_post(self):
        data = {
            'customer': self.customer.pk,
            'notes': 'POS Test',
            'product_id[]': [self.product.pk],
            'quantity[]': [2],
        }
        response = self.client.post(reverse('sales:pos'), data)
        self.assertEqual(response.status_code, 302)
        # Check stock deducted
        self.assertEqual(Inventory.objects.get(product=self.product, store=self.phys_store).quantity, 8)

    def test_online_order_create_view_post(self):
        data = {
            'customer': self.customer.pk,
            'notes': 'Deliver to front desk',
            'product_id[]': [self.product.pk],
            'quantity[]': [1],
        }
        response = self.client.post(reverse('sales:online_create'), data)
        self.assertEqual(response.status_code, 302)
        new_order = Order.objects.filter(customer=self.customer, store=self.online_store).first()
        self.assertIsNotNone(new_order)
        self.assertEqual(new_order.order_status, Order.PENDING)

    def test_order_transition_view(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.online_store,
            items_data=[{'product': self.product, 'quantity': 1}],
            auto_confirm=False
        )
        response = self.client.post(
            reverse('sales:transition', args=[order.pk]),
            {'new_status': Order.CONFIRMED}
        )
        self.assertRedirects(response, reverse('sales:detail', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.CONFIRMED)

    def test_order_return_view_post(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.phys_store,
            items_data=[{'product': self.product, 'quantity': 2}],
            auto_confirm=True
        )
        sales_services.transition_order_status(order, Order.PROCESSING)
        sales_services.transition_order_status(order, Order.SHIPPED)
        sales_services.transition_order_status(order, Order.DELIVERED)

        order_item = order.items.first()
        data = {
            'reason': 'Customer requested refund',
            'restock_inventory': 'on',
            f'return_qty_{order_item.id}': '1',
            f'condition_{order_item.id}': 'SELLABLE',
        }
        response = self.client.post(reverse('sales:return_create', args=[order.pk]), data)
        self.assertRedirects(response, reverse('sales:detail', args=[order.pk]))
        self.assertTrue(order.returns.exists())
