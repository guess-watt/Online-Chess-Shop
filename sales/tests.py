from django.test import TestCase
from decimal import Decimal
from products.models import Category, Product
from inventory.models import Store
from customers.models import Customer
from sales.models import Order, OrderItem, OrderReturn


class SalesModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Chess Books")
        self.product = Product.objects.create(
            category=self.category,
            sku="BOK-ENDGM-01",
            name="100 Endgames You Must Know",
            selling_price=Decimal("25.00"),
            cost_price=Decimal("14.00")
        )
        self.store = Store.objects.create(
            name="Online Webstore",
            store_type=Store.ONLINE
        )
        self.customer = Customer.objects.create(
            name="Alice Smith",
            email="alice@example.com",
            customer_type=Customer.INDIVIDUAL
        )

    def test_order_creation_and_total_calculation(self):
        order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_status=Order.PENDING
        )
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            unit_price=self.product.selling_price,
            unit_cost=self.product.cost_price,
            subtotal=self.product.selling_price * 2
        )
        self.assertTrue(order.order_number.startswith("ORD-"))
        self.assertEqual(item.subtotal, Decimal("50.00"))
        order.calculate_total()
        self.assertEqual(order.total_amount, Decimal("50.00"))

    def test_allowed_status_transitions(self):
        order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_status=Order.PENDING
        )
        # PENDING -> CONFIRMED is allowed
        self.assertTrue(order.can_transition_to(Order.CONFIRMED))
        # PENDING -> CANCELLED is allowed
        self.assertTrue(order.can_transition_to(Order.CANCELLED))
        # PENDING -> DELIVERED is NOT allowed directly
        self.assertFalse(order.can_transition_to(Order.DELIVERED))

    def test_order_return_creation(self):
        order = Order.objects.create(
            customer=self.customer,
            store=self.store,
            order_status=Order.DELIVERED
        )
        ret = OrderReturn.objects.create(
            order=order,
            reason="Customer changed mind",
            refund_amount=Decimal("25.00")
        )
        self.assertTrue(ret.return_number.startswith("RET-"))
