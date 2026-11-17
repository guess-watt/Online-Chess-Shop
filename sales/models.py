from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal
import uuid


class Order(models.Model):
    """
    Sales transaction header covering physical store (POS) and online orders.
    """
    PENDING = 'PENDING'
    CONFIRMED = 'CONFIRMED'
    PROCESSING = 'PROCESSING'
    SHIPPED = 'SHIPPED'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (PROCESSING, 'Processing'),
        (SHIPPED, 'Shipped'),
        (DELIVERED, 'Delivered'),
        (CANCELLED, 'Cancelled'),
    ]

    ALLOWED_TRANSITIONS = {
        PENDING: [CONFIRMED, CANCELLED],
        CONFIRMED: [PROCESSING, CANCELLED],
        PROCESSING: [SHIPPED, CANCELLED],
        SHIPPED: [DELIVERED],
        DELIVERED: [],
        CANCELLED: [],
    }

    order_number = models.CharField(max_length=32, unique=True, editable=False)
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.PROTECT,
        related_name='orders'
    )
    store = models.ForeignKey(
        'inventory.Store',
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Channel where the order originated (Physical POS or Online)"
    )
    order_status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=PENDING
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_number} - {self.customer.name} ({self.get_order_status_display()})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def can_transition_to(self, new_status):
        if self.order_status == new_status:
            return True
        return new_status in self.ALLOWED_TRANSITIONS.get(self.order_status, [])

    def calculate_total(self):
        total = sum(item.subtotal for item in self.items.all())
        self.total_amount = total
        return total


class OrderItem(models.Model):
    """
    Individual product line items belonging to an Order.
    Stores historical unit price and cost price to freeze margins at sale time.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.product.name} x {self.quantity} ({self.order.order_number})"

    def save(self, *args, **kwargs):
        self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)


class OrderReturn(models.Model):
    """
    Tracks returns and inventory restock decisions.
    """
    REQUESTED = 'REQUESTED'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    RESTOCKED = 'RESTOCKED'

    RETURN_STATUS_CHOICES = [
        (REQUESTED, 'Requested'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (RESTOCKED, 'Completed & Restocked'),
    ]

    return_number = models.CharField(max_length=32, unique=True, editable=False)
    order = models.ForeignKey(
        Order,
        on_delete=models.PROTECT,
        related_name='returns'
    )
    return_status = models.CharField(
        max_length=20,
        choices=RETURN_STATUS_CHOICES,
        default=REQUESTED
    )
    reason = models.TextField()
    restock_inventory = models.BooleanField(
        default=False,
        help_text="True if items are verified sellable and returned to stock"
    )
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.return_number} (Order: {self.order.order_number})"

    def save(self, *args, **kwargs):
        if not self.return_number:
            self.return_number = f"RET-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class ReturnItem(models.Model):
    """
    Specific line item being returned with condition inspection.
    """
    SELLABLE = 'SELLABLE'
    DAMAGED = 'DAMAGED'
    CONDITION_CHOICES = [
        (SELLABLE, 'Sellable / Like-New'),
        (DAMAGED, 'Damaged / Unsellable'),
    ]

    order_return = models.ForeignKey(
        OrderReturn,
        on_delete=models.CASCADE,
        related_name='items'
    )
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name='return_records'
    )
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default=SELLABLE)

    def __str__(self):
        return f"{self.order_item.product.name} x {self.quantity} ({self.get_condition_display()})"
