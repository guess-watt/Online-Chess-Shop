from django.test import TestCase
from django.core.exceptions import ValidationError
from decimal import Decimal
from products.models import Category, Product


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Chess Clocks",
            description="Digital and analog clocks"
        )
        self.product = Product.objects.create(
            category=self.category,
            sku="CLK-DGT-001",
            name="DGT 2010 Digital Chess Clock",
            selling_price=Decimal("79.99"),
            cost_price=Decimal("45.00"),
            low_stock_threshold=5
        )

    def test_product_creation_and_str(self):
        self.assertEqual(str(self.product), "DGT 2010 Digital Chess Clock (CLK-DGT-001)")
        self.assertEqual(self.product.unit_profit, Decimal("34.99"))

    def test_sku_uniqueness(self):
        with self.assertRaises(Exception):
            Product.objects.create(
                category=self.category,
                sku="CLK-DGT-001",  # duplicate
                name="Duplicate Clock",
                selling_price=Decimal("50.00"),
                cost_price=Decimal("30.00"),
            )

    def test_negative_price_validation(self):
        invalid_product = Product(
            category=self.category,
            sku="CLK-NEG-001",
            name="Negative Price Clock",
            selling_price=Decimal("-10.00"),
            cost_price=Decimal("20.00"),
        )
        with self.assertRaises(ValidationError):
            invalid_product.clean()
