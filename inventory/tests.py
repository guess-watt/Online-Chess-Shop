from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store, Inventory, InventoryMovement


class InventoryModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Sets")
        self.product = Product.objects.create(
            category=self.category,
            sku="SET-STAUNTON-5",
            name="German Knight Staunton Chess Set",
            selling_price=Decimal("120.00"),
            cost_price=Decimal("70.00"),
            low_stock_threshold=3
        )
        self.store = Store.objects.create(
            name="Downtown Physical Store",
            store_type=Store.PHYSICAL
        )

    def test_inventory_creation_and_clean(self):
        inv = Inventory.objects.create(
            product=self.product,
            store=self.store,
            quantity=10
        )
        self.assertEqual(inv.quantity, 10)
        self.assertEqual(self.product.total_stock, 10)
        self.assertFalse(self.product.is_low_stock)

    def test_duplicate_store_product_constraint(self):
        Inventory.objects.create(
            product=self.product,
            store=self.store,
            quantity=5
        )
        with self.assertRaises(IntegrityError):
            Inventory.objects.create(
                product=self.product,
                store=self.store,
                quantity=15
            )

    def test_inventory_movement_logging(self):
        movement = InventoryMovement.objects.create(
            product=self.product,
            store=self.store,
            quantity=10,
            movement_type=InventoryMovement.PURCHASE,
            reason="Initial supplier batch"
        )
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.movement_type, InventoryMovement.PURCHASE)
