from django.db import transaction
from decimal import Decimal
from sales.models import Order, OrderItem, OrderReturn, ReturnItem
from inventory.models import Inventory, InventoryMovement
from inventory import services as inv_services


@transaction.atomic
def create_order(customer, store, items_data, notes="", auto_confirm=False, user=None):
    """
    Creates an order with line items.
    items_data: list of dicts [{'product': Product, 'quantity': int}]
    If auto_confirm=True (e.g. POS sale), stock is checked and deducted immediately.
    """
    if not items_data:
        raise ValueError("An order must contain at least one item.")

    # 1. If auto_confirm, check stock availability upfront for all items
    if auto_confirm:
        for item in items_data:
            product = item['product']
            qty = item['quantity']
            if qty <= 0:
                raise ValueError(f"Quantity for '{product.name}' must be at least 1.")
            is_avail, current_stock = inv_services.check_stock_availability(product, store, qty)
            if not is_avail:
                raise ValueError(
                    f"Insufficient stock for '{product.name}' at '{store.name}'. "
                    f"Available: {current_stock}, Requested: {qty}."
                )

    initial_status = Order.CONFIRMED if auto_confirm else Order.PENDING

    # 2. Create Order Header
    order = Order.objects.create(
        customer=customer,
        store=store,
        order_status=initial_status,
        notes=notes,
        total_amount=Decimal('0.00')
    )

    total_amount = Decimal('0.00')

    # 3. Create Order Items & deduct stock if auto_confirm
    for item in items_data:
        product = item['product']
        qty = item['quantity']
        unit_price = product.selling_price
        unit_cost = product.cost_price
        subtotal = unit_price * qty
        total_amount += subtotal

        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=qty,
            unit_price=unit_price,
            unit_cost=unit_cost,
            subtotal=subtotal
        )

        if auto_confirm:
            inv_services.adjust_stock(
                product=product,
                store=store,
                quantity_delta=-qty,
                movement_type=InventoryMovement.SALE,
                reason=f"POS Sale: {order.order_number}",
                user=user,
                reference_order=order
            )

    order.total_amount = total_amount
    order.save(update_fields=['total_amount'])
    return order


@transaction.atomic
def confirm_order(order, user=None):
    """
    Confirms a PENDING order: verifies stock and deducts inventory.
    """
    if order.order_status != Order.PENDING:
        raise ValueError(f"Cannot confirm order {order.order_number} in status '{order.order_status}'.")

    # Verify all items have enough stock before making deductions
    for item in order.items.all():
        is_avail, current_stock = inv_services.check_stock_availability(item.product, order.store, item.quantity)
        if not is_avail:
            raise ValueError(
                f"Cannot confirm order: Insufficient stock for '{item.product.name}' at '{order.store.name}'. "
                f"Available: {current_stock}, Required: {item.quantity}."
            )

    # Deduct stock for each line item
    for item in order.items.all():
        inv_services.adjust_stock(
            product=item.product,
            store=order.store,
            quantity_delta=-item.quantity,
            movement_type=InventoryMovement.SALE,
            reason=f"Order Confirmed: {order.order_number}",
            user=user,
            reference_order=order
        )

    order.order_status = Order.CONFIRMED
    order.save(update_fields=['order_status', 'updated_at'])
    return order


@transaction.atomic
def cancel_order(order, reason="Order cancelled by admin/customer", user=None):
    """
    Cancels an order and restores deducted stock if the order was confirmed/in-progress.
    """
    if order.order_status in [Order.CANCELLED, Order.DELIVERED]:
        raise ValueError(f"Cannot cancel order {order.order_number} with status '{order.order_status}'.")

    previous_status = order.order_status

    # If the order was confirmed, processing, or shipped, stock was deducted -> restore it
    if previous_status in [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED]:
        for item in order.items.all():
            inv_services.adjust_stock(
                product=item.product,
                store=order.store,
                quantity_delta=item.quantity,
                movement_type=InventoryMovement.RETURN,
                reason=f"Cancellation Restock: {order.order_number} ({reason})",
                user=user,
                reference_order=order
            )

    order.order_status = Order.CANCELLED
    order.notes = f"{order.notes}\n[Cancelled]: {reason}".strip()
    order.save(update_fields=['order_status', 'notes', 'updated_at'])
    return order


def transition_order_status(order, new_status, user=None):
    """
    Advances or changes an order status adhering strictly to allowed transitions.
    """
    if not order.can_transition_to(new_status):
        raise ValueError(
            f"Invalid status transition from '{order.order_status}' to '{new_status}' for order {order.order_number}."
        )

    if new_status == Order.CANCELLED:
        return cancel_order(order, reason="Status changed to Cancelled", user=user)

    if new_status == Order.CONFIRMED and order.order_status == Order.PENDING:
        return confirm_order(order, user=user)

    order.order_status = new_status
    order.save(update_fields=['order_status', 'updated_at'])
    return order


@transaction.atomic
def process_order_return(order, return_items_data, reason, restock_inventory=False, user=None):
    """
    Processes a return for an order.
    return_items_data: list of dicts [{'order_item': OrderItem, 'quantity': int, 'condition': 'SELLABLE'|'DAMAGED'}]
    Only restocks if restock_inventory=True AND item condition is 'SELLABLE'.
    """
    if not return_items_data:
        raise ValueError("Return must include at least one item.")

    if order.order_status not in [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]:
        raise ValueError(f"Cannot return an unfulfilled or cancelled order ({order.order_status}).")

    total_refund = Decimal('0.00')

    # Validate return quantities against original order items
    for entry in return_items_data:
        order_item = entry['order_item']
        ret_qty = entry['quantity']
        if ret_qty <= 0 or ret_qty > order_item.quantity:
            raise ValueError(f"Invalid return quantity {ret_qty} for '{order_item.product.name}' (Ordered: {order_item.quantity}).")
        total_refund += order_item.unit_price * ret_qty

    return_record = OrderReturn.objects.create(
        order=order,
        return_status=OrderReturn.RESTOCKED if restock_inventory else OrderReturn.APPROVED,
        reason=reason,
        restock_inventory=restock_inventory,
        refund_amount=total_refund
    )

    for entry in return_items_data:
        order_item = entry['order_item']
        ret_qty = entry['quantity']
        condition = entry.get('condition', ReturnItem.SELLABLE)

        ReturnItem.objects.create(
            order_return=return_record,
            order_item=order_item,
            quantity=ret_qty,
            condition=condition
        )

        # Restock ONLY if requested AND item is sellable
        if restock_inventory and condition == ReturnItem.SELLABLE:
            inv_services.adjust_stock(
                product=order_item.product,
                store=order.store,
                quantity_delta=ret_qty,
                movement_type=InventoryMovement.RETURN,
                reason=f"Customer Return Restock: {return_record.return_number}",
                user=user,
                reference_order=order
            )

    return return_record
