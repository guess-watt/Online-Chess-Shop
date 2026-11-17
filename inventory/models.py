from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Store(models.Model):
    """
    Represents a retail fulfillment channel: physical store or online channel.
    Extensible for multiple stores in future phases.
    """
    PHYSICAL = 'PHYSICAL'
    ONLINE = 'ONLINE'
    STORE_TYPE_CHOICES = [
        (PHYSICAL, 'Physical Store'),
        (ONLINE, 'Online Channel'),
    ]

    name = models.CharField(max_length=100, unique=True)
    store_type = models.CharField(max_length=20, choices=STORE_TYPE_CHOICES, default=PHYSICAL)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_store_type_display()})"


class Inventory(models.Model):
    """
    Tracks on-hand inventory quantity per product per store location.
    """
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='inventory_records'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='inventory_records'
    )
    quantity = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Inventories"
        unique_together = ('product', 'store')
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name='inventory_quantity_non_negative'
            )
        ]

    def __str__(self):
        return f"{self.product.name} @ {self.store.name}: {self.quantity}"

    def clean(self):
        if self.quantity < 0:
            raise ValidationError({'quantity': "Inventory quantity cannot be negative."})


class InventoryMovement(models.Model):
    """
    Audit log of every stock addition or reduction for accountability.
    """
    PURCHASE = 'PURCHASE'
    SALE = 'SALE'
    RETURN = 'RETURN'
    ADJUSTMENT = 'ADJUSTMENT'
    DAMAGE = 'DAMAGE'

    MOVEMENT_TYPES = [
        (PURCHASE, 'Purchase / Stock In'),
        (SALE, 'Sale Deduction'),
        (RETURN, 'Return Restock'),
        (ADJUSTMENT, 'Manual Inventory Adjustment'),
        (DAMAGE, 'Damaged / Write-Off'),
    ]

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='inventory_movements'
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.PROTECT,
        related_name='inventory_movements'
    )
    quantity = models.IntegerField(
        help_text="Stock delta: positive for additions (+), negative for reductions (-)"
    )
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    reference_order = models.ForeignKey(
        'sales.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='inventory_movements'
    )
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logged_movements'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        delta = f"+{self.quantity}" if self.quantity > 0 else str(self.quantity)
        return f"{self.created_at.strftime('%Y-%m-%d %H:%M')} | {self.product.sku} | {delta} ({self.get_movement_type_display()})"
