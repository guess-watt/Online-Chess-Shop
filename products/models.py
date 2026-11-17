from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal


class Category(models.Model):
    """
    Represents a product category (e.g. Chess Boards, Chess Clocks, Chess Books, etc.).
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Represents an item sold by ChessMart with distinct retail and cost pricing.
    """
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )
    sku = models.CharField(
        max_length=50,
        unique=True,
        help_text="Stock Keeping Unit (e.g., CLK-DGT-001)"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        help_text="Alert threshold when total stock falls below this level"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.sku})"

    def clean(self):
        if self.selling_price is not None and self.selling_price < Decimal('0.00'):
            raise ValidationError({'selling_price': "Selling price cannot be negative."})
        if self.cost_price is not None and self.cost_price < Decimal('0.00'):
            raise ValidationError({'cost_price': "Cost price cannot be negative."})

    @property
    def unit_profit(self):
        return self.selling_price - self.cost_price

    @property
    def total_stock(self):
        return sum(inv.quantity for inv in self.inventory_records.all())

    @property
    def is_low_stock(self):
        return self.total_stock <= self.low_stock_threshold
