from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
from products.models import Category, Product
from products.forms import ProductForm, CategoryForm
from inventory.models import Store, Inventory


class ProductModelAndFormTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Clocks", description="Timers")
        self.product = Product.objects.create(
            category=self.category,
            sku="CLK-DGT-001",
            name="DGT 2010 Digital Chess Clock",
            selling_price=Decimal("79.99"),
            cost_price=Decimal("45.00"),
            low_stock_threshold=5
        )
        self.store = Store.objects.create(name="Downtown Store", store_type=Store.PHYSICAL)

    def test_product_properties(self):
        self.assertEqual(str(self.product), "DGT 2010 Digital Chess Clock (CLK-DGT-001)")
        self.assertEqual(self.product.unit_profit, Decimal("34.99"))

    def test_sku_uniqueness(self):
        with self.assertRaises(Exception):
            Product.objects.create(
                category=self.category,
                sku="CLK-DGT-001",
                name="Duplicate Clock",
                selling_price=Decimal("50.00"),
                cost_price=Decimal("30.00"),
            )

    def test_negative_price_validation(self):
        p = Product(
            category=self.category,
            sku="CLK-NEG-001",
            name="Negative Price",
            selling_price=Decimal("-10.00"),
            cost_price=Decimal("20.00"),
        )
        with self.assertRaises(ValidationError):
            p.clean()

    def test_product_form_valid(self):
        form = ProductForm(data={
            'name': 'DGT 3000 FIDE Clock',
            'sku': 'clk-dgt-3000',
            'category': self.category.pk,
            'selling_price': '99.99',
            'cost_price': '60.00',
            'low_stock_threshold': 4,
            'is_active': True,
            'description': 'Flagship clock'
        })
        self.assertTrue(form.is_valid())
        saved = form.save()
        self.assertEqual(saved.sku, 'CLK-DGT-3000')  # SKU normalized to uppercase

    def test_product_form_duplicate_sku(self):
        form = ProductForm(data={
            'name': 'Another Clock',
            'sku': 'CLK-DGT-001',  # duplicate
            'category': self.category.pk,
            'selling_price': '50.00',
            'cost_price': '30.00',
            'low_stock_threshold': 5,
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('sku', form.errors)


class ProductViewTests(TestCase):
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
        self.store = Store.objects.create(name="Store A", store_type=Store.PHYSICAL)

    def test_product_list_view(self):
        response = self.client.get(reverse('products:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Staunton Chess Set")

    def test_product_detail_view(self):
        response = self.client.get(reverse('products:detail', args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SET-STAUNTON")

    def test_product_create_view_post(self):
        data = {
            'name': 'Folding Wooden Board',
            'sku': 'BRD-FLD-01',
            'category': self.category.pk,
            'selling_price': '45.00',
            'cost_price': '22.00',
            'low_stock_threshold': 5,
            'is_active': True,
            'description': 'Portable board'
        }
        response = self.client.post(reverse('products:create'), data)
        new_prod = Product.objects.get(sku='BRD-FLD-01')
        self.assertRedirects(response, reverse('products:detail', args=[new_prod.pk]))
        # Check that store inventory was initialized
        self.assertTrue(Inventory.objects.filter(product=new_prod, store=self.store).exists())

    def test_product_toggle_status_view(self):
        self.assertTrue(self.product.is_active)
        response = self.client.post(reverse('products:toggle_status', args=[self.product.pk]))
        self.assertRedirects(response, reverse('products:detail', args=[self.product.pk]))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_category_list_and_create_view(self):
        response = self.client.get(reverse('products:category_list'))
        self.assertEqual(response.status_code, 200)
        post_response = self.client.post(reverse('products:category_list'), {
            'name': 'Chess Clocks',
            'description': 'All timers',
            'is_active': True,
        })
        self.assertRedirects(post_response, reverse('products:category_list'))
        self.assertTrue(Category.objects.filter(name='Chess Clocks').exists())
