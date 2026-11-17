from django.db import transaction
from django.db.models import Sum, F, Q
from django.core.exceptions import ValidationError
from products.models import Product
from .models import Store, Inventory, InventoryMovement


def get_or_create_inventory(product, store):
    """
    Retrieves or initializes an inventory record for a product at a given store.
    """
    inventory, _ = Inventory.objects.get_or_create(
        product=product,
        store=store,
        defaults={'quantity': 0}
    )
    return inventory


@transaction.atomic
def adjust_stock(product, store, quantity_delta, movement_type, reason="", user=None, reference_order=None):
    """
    Atomically updates stock for a product at a store and records an audit movement log.
    quantity_delta: positive for addition, negative for reduction.
    Raises ValueError if reduction would lead to negative inventory.
    """
    if quantity_delta == 0:
        raise ValueError("Stock adjustment quantity delta cannot be zero.")

    # Lock row for update to prevent concurrent race conditions
    inventory, _ = Inventory.objects.select_for_update().get_or_create(
        product=product,
        store=store,
        defaults={'quantity': 0}
    )

    new_quantity = inventory.quantity + quantity_delta
    if new_quantity < 0:
        raise ValueError(
            f"Insufficient stock for '{product.name}' at '{store.name}'. "
            f"Current: {inventory.quantity}, requested deduction: {abs(quantity_delta)}."
        )

    inventory.quantity = new_quantity
    inventory.save(update_fields=['quantity', 'updated_at'])

    # Create immutable movement audit log
    movement = InventoryMovement.objects.create(
        product=product,
        store=store,
        quantity=quantity_delta,
        movement_type=movement_type,
        reference_order=reference_order,
        reason=reason,
        created_by=user
    )

    return inventory, movement


def check_stock_availability(product, store, requested_quantity):
    """
    Checks whether a specific store has sufficient stock for an order item.
    Returns (is_available: bool, current_stock: int).
    """
    try:
        inv = Inventory.objects.get(product=product, store=store)
        current_stock = inv.quantity
    except Inventory.DoesNotExist:
        current_stock = 0

    return (current_stock >= requested_quantity), current_stock


def get_low_stock_products():
    """
    Returns active products where total stock across all active stores
    is less than or equal to their low-stock threshold.
    """
    products = Product.objects.filter(is_active=True).prefetch_related('inventory_records', 'category')
    low_stock_list = []
    for prod in products:
        if prod.is_low_stock:
            low_stock_list.append(prod)
    return low_stock_list
