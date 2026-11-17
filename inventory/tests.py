from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, Inventory, InventoryMovement
from inventory import services


class InventoryServiceAndModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Sets")
        self.product = Product.objects.create(
            category=self.category,
            sku="SET-STAUNTON-5",
            name="German Knight Staunton Chess Set",
            selling_price=Decimal("120.00"),
            cost_price=Decimal("70.00"),
            low_stock_threshold=5
        )
        self.phys_store = Store.objects.create(name="Downtown Physical Store", store_type=Store.PHYSICAL)
        self.online_store = Store.objects.create(name="Online Webstore", store_type=Store.ONLINE)

    def test_stock_adjust_service_add(self):
        inv, mov = services.adjust_stock(
            product=self.product,
            store=self.phys_store,
            quantity_delta=10,
            movement_type=InventoryMovement.PURCHASE,
            reason="Supplier shipment"
        )
        self.assertEqual(inv.quantity, 10)
        self.assertEqual(mov.quantity, 10)
        self.assertEqual(mov.movement_type, InventoryMovement.PURCHASE)
        self.assertEqual(self.product.total_stock, 10)
        self.assertFalse(self.product.is_low_stock)

    def test_stock_adjust_service_deduct(self):
        # First add 10
        services.adjust_stock(self.product, self.phys_store, 10, InventoryMovement.PURCHASE)
        # Deduct 3
        inv, mov = services.adjust_stock(
            self.product, self.phys_store, -3, InventoryMovement.ADJUSTMENT, reason="Damaged pieces"
        )
        self.assertEqual(inv.quantity, 7)
        self.assertEqual(mov.quantity, -3)
        self.assertEqual(self.product.total_stock, 7)

    def test_stock_adjust_insufficient_stock_raises_error(self):
        # Current stock is 2; attempting to deduct 5 must fail and roll back
        inv = Inventory.objects.create(product=self.product, store=self.phys_store, quantity=2)
        with self.assertRaises(ValueError) as ctx:
            services.adjust_stock(self.product, self.phys_store, -5, InventoryMovement.ADJUSTMENT)
        self.assertIn("Insufficient stock", str(ctx.exception))
        # Ensure stock remained 2
        inv.refresh_from_db()
        self.assertEqual(inv.quantity, 2)

    def test_stock_adjust_zero_delta_raises_error(self):
        with self.assertRaises(ValueError):
            services.adjust_stock(self.product, self.phys_store, 0, InventoryMovement.ADJUSTMENT)

    def test_check_stock_availability(self):
        services.adjust_stock(self.product, self.phys_store, 8, InventoryMovement.PURCHASE)
        avail, qty = services.check_stock_availability(self.product, self.phys_store, 5)
        self.assertTrue(avail)
        self.assertEqual(qty, 8)

        avail_insufficient, _ = services.check_stock_availability(self.product, self.phys_store, 10)
        self.assertFalse(avail_insufficient)

    def test_get_low_stock_products(self):
        # Low stock threshold is 5. Adding 3 puts it in low stock.
        services.adjust_stock(self.product, self.phys_store, 3, InventoryMovement.PURCHASE)
        low_stock = services.get_low_stock_products()
        self.assertIn(self.product, low_stock)

        # Adding 10 more clears low-stock condition (total 13 > 5)
        services.adjust_stock(self.product, self.phys_store, 10, InventoryMovement.PURCHASE)
        low_stock_after = services.get_low_stock_products()
        self.assertNotIn(self.product, low_stock_after)


class InventoryViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Clocks")
        self.product = Product.objects.create(
            category=self.category,
            sku="CLK-DGT-2010",
            name="DGT 2010 Clock",
            selling_price=Decimal("79.99"),
            cost_price=Decimal("45.00"),
            low_stock_threshold=5
        )
        self.store = Store.objects.create(name="Physical Store", store_type=Store.PHYSICAL)

    def test_inventory_list_view(self):
        response = self.client.get(reverse('inventory:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DGT 2010 Clock")

    def test_stock_adjust_view_get(self):
        response = self.client.get(reverse('inventory:adjust'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock Adjustment")

    def test_stock_adjust_view_post_success(self):
        data = {
            'product': self.product.pk,
            'store': self.store.pk,
            'action': 'ADD',
            'quantity': 15,
            'reason': 'Supplier batch'
        }
        response = self.client.post(reverse('inventory:adjust'), data)
        self.assertRedirects(response, reverse('inventory:list'))
        inv = Inventory.objects.get(product=self.product, store=self.store)
        self.assertEqual(inv.quantity, 15)

    def test_stock_adjust_view_post_insufficient_stock(self):
        data = {
            'product': self.product.pk,
            'store': self.store.pk,
            'action': 'DEDUCT',
            'quantity': 100,  # Exceeds 0
            'reason': 'Excess reduction'
        }
        response = self.client.post(reverse('inventory:adjust'), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Insufficient stock")

    def test_movement_history_view(self):
        services.adjust_stock(self.product, self.store, 5, InventoryMovement.PURCHASE, reason="Initial stock")
        response = self.client.get(reverse('inventory:history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Initial stock")

    def test_low_stock_view(self):
        # Product has 0 stock which is <= threshold 5
        response = self.client.get(reverse('inventory:low_stock'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "DGT 2010 Clock")
