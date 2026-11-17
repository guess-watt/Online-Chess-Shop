from django.db import models


class Customer(models.Model):
    """
    Customer profile supporting retail categories: Individual, Academy, Club.
    """
    INDIVIDUAL = 'INDIVIDUAL'
    ACADEMY = 'ACADEMY'
    CLUB = 'CLUB'

    CUSTOMER_TYPES = [
        (INDIVIDUAL, 'Individual Customer'),
        (ACADEMY, 'Chess Academy'),
        (CLUB, 'Chess Club'),
    ]

    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPES, default=INDIVIDUAL)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_customer_type_display()})"

    @property
    def total_orders(self):
        return self.orders.exclude(order_status='CANCELLED').count()

    @property
    def total_spent(self):
        from decimal import Decimal
        spent = sum(
            order.total_amount for order in self.orders.filter(
                order_status__in=['CONFIRMED', 'PROCESSING', 'SHIPPED', 'DELIVERED']
            )
        )
        return spent if spent else Decimal('0.00')
