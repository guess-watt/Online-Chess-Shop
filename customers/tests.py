from django.test import TestCase
from django.db import IntegrityError
from customers.models import Customer


class CustomerModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(
            name="Grandmaster Academy",
            email="info@gmacademy.com",
            phone="+1234567890",
            customer_type=Customer.ACADEMY,
            address="124 Chess Lane, New York"
        )

    def test_customer_creation(self):
        self.assertEqual(str(self.customer), "Grandmaster Academy (Chess Academy)")
        self.assertEqual(self.customer.total_orders, 0)

    def test_email_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Customer.objects.create(
                name="Duplicate Email Customer",
                email="info@gmacademy.com",
                customer_type=Customer.INDIVIDUAL
            )
