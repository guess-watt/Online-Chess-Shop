from django.test import TestCase
from django.urls import reverse
from django.db import IntegrityError
from decimal import Decimal
from customers.models import Customer
from customers.forms import CustomerForm
from products.models import Category, Product
from inventory.models import Store, InventoryMovement
from inventory import services as inv_services
from sales import services as sales_services
from sales.models import Order


class CustomerModelAndFormTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Grandmaster Academy",
            email="info@gmacademy.com",
            phone="+1234567890",
            customer_type=Customer.ACADEMY,
            address="124 Chess Lane, New York"
        )
        self.category = Category.objects.create(name="Chess Clocks")
        self.product = Product.objects.create(
            category=self.category,
            sku="CLK-DGT-001",
            name="DGT Clock",
            selling_price=Decimal("100.00"),
            cost_price=Decimal("60.00")
        )
        self.store = Store.objects.create(name="Store A", store_type=Store.PHYSICAL)
        inv_services.adjust_stock(self.product, self.store, 20, InventoryMovement.PURCHASE)

    def test_customer_creation_and_str(self):
        self.assertEqual(str(self.customer), "Grandmaster Academy (Chess Academy)")
        self.assertEqual(self.customer.total_orders, 0)
        self.assertEqual(self.customer.total_spent, Decimal("0.00"))

    def test_email_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                name="Duplicate Customer",
                email="info@gmacademy.com",
                customer_type=Customer.INDIVIDUAL
            )

    def test_customer_order_aggregations(self):
        # Order 1: Confirmed sale of $200
        sales_services.create_order(
            customer=self.customer,
            store=self.store,
            items_data=[{'product': self.product, 'quantity': 2}],
            auto_confirm=True
        )
        # Order 2: Pending order of $100
        sales_services.create_order(
            customer=self.customer,
            store=self.store,
            items_data=[{'product': self.product, 'quantity': 1}],
            auto_confirm=False
        )
        # Order 3: Cancelled order
        o3 = sales_services.create_order(
            customer=self.customer,
            store=self.store,
            items_data=[{'product': self.product, 'quantity': 1}],
            auto_confirm=False
        )
        sales_services.cancel_order(o3)

        self.customer.refresh_from_db()
        # Non-cancelled count = 2 (Order 1 + Order 2)
        self.assertEqual(self.customer.total_orders, 2)
        # Total spent on confirmed/fulfilled orders = $200
        self.assertEqual(self.customer.total_spent, Decimal("200.00"))

    def test_customer_form_valid(self):
        form = CustomerForm(data={
            'name': 'Morphy Chess Club',
            'email': 'Contact@MorphyClub.org',
            'phone': '555-4321',
            'customer_type': Customer.CLUB,
            'address': 'New Orleans, LA'
        })
        self.assertTrue(form.is_valid())
        saved = form.save()
        self.assertEqual(saved.email, 'contact@morphyclub.org')  # Email normalized to lowercase

    def test_customer_form_duplicate_email(self):
        form = CustomerForm(data={
            'name': 'Duplicate Email Tester',
            'email': 'INFO@GMACADEMY.COM',  # Case-insensitive duplicate
            'customer_type': Customer.INDIVIDUAL,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)


class CustomerViewTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Alice Smith",
            email="alice@smith.org",
            phone="555-1234",
            customer_type=Customer.INDIVIDUAL,
            address="100 Main St"
        )
        self.category = Category.objects.create(name="Accessories")
        self.product = Product.objects.create(
            category=self.category,
            sku="ACC-BAG",
            name="Chess Bag",
            selling_price=Decimal("30.00"),
            cost_price=Decimal("15.00")
        )
        self.store = Store.objects.create(name="Main Store", store_type=Store.PHYSICAL)
        inv_services.adjust_stock(self.product, self.store, 10, InventoryMovement.PURCHASE)

    def test_customer_list_view(self):
        response = self.client.get(reverse('customers:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")

    def test_customer_list_search_and_filter(self):
        # Search by name
        res_search = self.client.get(reverse('customers:list') + '?q=Alice')
        self.assertContains(res_search, "Alice Smith")

        # Filter by customer type
        res_type = self.client.get(reverse('customers:list') + f'?type={Customer.INDIVIDUAL}')
        self.assertContains(res_type, "Alice Smith")

        res_club = self.client.get(reverse('customers:list') + f'?type={Customer.CLUB}')
        self.assertNotContains(res_club, "Alice Smith")

    def test_customer_detail_view_with_order_history(self):
        order = sales_services.create_order(
            customer=self.customer,
            store=self.store,
            items_data=[{'product': self.product, 'quantity': 2}],
            auto_confirm=True
        )
        response = self.client.get(reverse('customers:detail', args=[self.customer.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, order.order_number)
        self.assertContains(response, "$60.00")

    def test_customer_create_view_post(self):
        data = {
            'name': 'Bobby Fischer Club',
            'email': 'club@fischer.com',
            'phone': '555-9876',
            'customer_type': Customer.CLUB,
            'address': 'Brooklyn, NY'
        }
        response = self.client.post(reverse('customers:create'), data)
        new_cust = Customer.objects.get(email='club@fischer.com')
        self.assertRedirects(response, reverse('customers:detail', args=[new_cust.pk]))

    def test_customer_update_view_post(self):
        data = {
            'name': 'Alice Smith Updated',
            'email': 'alice@smith.org',
            'phone': '555-9999',
            'customer_type': Customer.INDIVIDUAL,
            'address': '200 Elm St'
        }
        response = self.client.post(reverse('customers:update', args=[self.customer.pk]), data)
        self.assertRedirects(response, reverse('customers:detail', args=[self.customer.pk]))
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, 'Alice Smith Updated')
        self.assertEqual(self.customer.phone, '555-9999')
