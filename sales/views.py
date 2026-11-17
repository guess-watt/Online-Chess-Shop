from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from decimal import Decimal
from .models import Order, OrderItem, OrderReturn, ReturnItem
from .forms import POSSaleForm, OnlineOrderForm, OrderReturnForm
from . import services
from products.models import Product
from inventory.models import Store, Inventory
from customers.models import Customer


def order_list(request):
    """
    Lists orders with filters by status, channel/store, and search query.
    """
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    store_id = request.GET.get('store', '').strip()

    orders = Order.objects.select_related('customer', 'store').prefetch_related('items').order_by('-created_at')

    if query:
        orders = orders.filter(
            Q(order_number__icontains=query) |
            Q(customer__name__icontains=query) |
            Q(customer__email__icontains=query)
        )
    if status_filter:
        orders = orders.filter(order_status=status_filter)
    if store_id:
        orders = orders.filter(store_id=store_id)

    stores = Store.objects.filter(is_active=True)

    context = {
        'orders': orders,
        'stores': stores,
        'status_choices': Order.STATUS_CHOICES,
        'selected_status': status_filter,
        'selected_store': store_id,
        'search_query': query,
    }
    return render(request, 'sales/order_list.html', context)


def order_detail(request, pk):
    """
    Shows detailed order information, line items, status workflow actions, and return logs.
    """
    order = get_object_or_404(
        Order.objects.select_related('customer', 'store').prefetch_related('items__product', 'returns__items__order_item__product'),
        pk=pk
    )

    # Next valid transitions
    allowed_next = Order.ALLOWED_TRANSITIONS.get(order.order_status, [])

    # Calculate gross profit for this order
    total_cost = sum(item.unit_cost * item.quantity for item in order.items.all())
    gross_profit = order.total_amount - total_cost

    can_return = order.order_status in [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]

    context = {
        'order': order,
        'allowed_next': allowed_next,
        'total_cost': total_cost,
        'gross_profit': gross_profit,
        'can_return': can_return,
    }
    return render(request, 'sales/order_detail.html', context)


def pos_checkout(request):
    """
    Physical Store POS (Point of Sale) counter terminal.
    Atomically creates confirmed sale, deducts physical inventory, and issues receipt.
    """
    physical_store = Store.objects.filter(store_type=Store.PHYSICAL, is_active=True).first()
    if not physical_store:
        messages.error(request, "Physical Store is not configured. Please initialize store first.")
        return redirect('inventory:list')

    # Get active products with their current physical store stock
    products = Product.objects.filter(is_active=True).order_by('category__name', 'name')
    products_with_stock = []
    for prod in products:
        inv = prod.inventory_records.filter(store=physical_store).first()
        qty = inv.quantity if inv else 0
        products_with_stock.append({
            'product': prod,
            'current_stock': qty
        })

    # Ensure a default walk-in customer exists if none selected
    default_customer = Customer.objects.filter(email='walkin@chessmart.local').first()
    if not default_customer:
        default_customer = Customer.objects.create(
            name="Walk-in Store Customer",
            email="walkin@chessmart.local",
            phone="N/A",
            customer_type=Customer.INDIVIDUAL,
            address="Physical Store Counter"
        )

    if request.method == 'POST':
        form = POSSaleForm(request.POST)
        if form.is_valid():
            customer = form.cleaned_data['customer']
            notes = form.cleaned_data['reason'] if 'reason' in form.cleaned_data else form.cleaned_data.get('notes', '')

            # Parse line items from POST
            items_data = []
            product_ids = request.POST.getlist('product_id[]')
            quantities = request.POST.getlist('quantity[]')

            for pid, qty_str in zip(product_ids, quantities):
                try:
                    qty = int(qty_str)
                    if qty > 0:
                        prod = Product.objects.get(pk=pid, is_active=True)
                        items_data.append({'product': prod, 'quantity': qty})
                except (ValueError, Product.DoesNotExist):
                    continue

            if not items_data:
                messages.error(request, "Please add at least one product with quantity > 0 to the sale.")
            else:
                try:
                    user = request.user if request.user.is_authenticated else None
                    order = services.create_order(
                        customer=customer,
                        store=physical_store,
                        items_data=items_data,
                        notes=notes,
                        auto_confirm=True,  # Instant POS deduction
                        user=user
                    )
                    messages.success(request, f"POS Sale {order.order_number} completed successfully! Stock deducted.")
                    return redirect('sales:detail', pk=order.pk)
                except ValueError as err:
                    messages.error(request, str(err))
    else:
        form = POSSaleForm(initial={'customer': default_customer})

    context = {
        'store': physical_store,
        'form': form,
        'products_with_stock': products_with_stock,
    }
    return render(request, 'sales/pos_checkout.html', context)


def online_order_create(request):
    """
    Creates an Online Customer Order through the online channel.
    Starts in PENDING status for fulfillment review.
    """
    online_store = Store.objects.filter(store_type=Store.ONLINE, is_active=True).first()
    if not online_store:
        messages.error(request, "Online Store is not configured. Please initialize store first.")
        return redirect('inventory:list')

    products = Product.objects.filter(is_active=True).order_by('category__name', 'name')
    products_with_stock = []
    for prod in products:
        inv = prod.inventory_records.filter(store=online_store).first()
        qty = inv.quantity if inv else 0
        products_with_stock.append({
            'product': prod,
            'current_stock': qty
        })

    if request.method == 'POST':
        form = OnlineOrderForm(request.POST)
        if form.is_valid():
            customer = form.cleaned_data['customer']
            notes = form.cleaned_data['notes']

            items_data = []
            product_ids = request.POST.getlist('product_id[]')
            quantities = request.POST.getlist('quantity[]')

            for pid, qty_str in zip(product_ids, quantities):
                try:
                    qty = int(qty_str)
                    if qty > 0:
                        prod = Product.objects.get(pk=pid, is_active=True)
                        items_data.append({'product': prod, 'quantity': qty})
                except (ValueError, Product.DoesNotExist):
                    continue

            if not items_data:
                messages.error(request, "Please add at least one product with quantity > 0.")
            else:
                try:
                    user = request.user if request.user.is_authenticated else None
                    order = services.create_order(
                        customer=customer,
                        store=online_store,
                        items_data=items_data,
                        notes=notes,
                        auto_confirm=False,  # Online starts PENDING
                        user=user
                    )
                    messages.success(request, f"Online Order {order.order_number} created in Pending status.")
                    return redirect('sales:detail', pk=order.pk)
                except ValueError as err:
                    messages.error(request, str(err))
    else:
        form = OnlineOrderForm()

    context = {
        'store': online_store,
        'form': form,
        'products_with_stock': products_with_stock,
    }
    return render(request, 'sales/online_order_form.html', context)


def order_transition_status(request, pk):
    """
    Processes status transitions (e.g. Confirm, Process, Ship, Deliver, Cancel).
    """
    if request.method == 'POST':
        order = get_object_or_404(Order, pk=pk)
        new_status = request.POST.get('new_status', '').strip()
        user = request.user if request.user.is_authenticated else None

        try:
            services.transition_order_status(order, new_status, user=user)
            messages.success(request, f"Order status successfully updated to '{order.get_order_status_display()}'.")
        except ValueError as err:
            messages.error(request, str(err))

    return redirect('sales:detail', pk=pk)


def order_return_create(request, pk):
    """
    Filing a return for an order with condition checking and restock options.
    """
    order = get_object_or_404(Order.objects.prefetch_related('items__product'), pk=pk)

    if order.order_status not in [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]:
        messages.error(request, "Returns cannot be processed for unfulfilled or cancelled orders.")
        return redirect('sales:detail', pk=order.pk)

    if request.method == 'POST':
        form = OrderReturnForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            restock_inventory = form.cleaned_data['restock_inventory']

            return_items_data = []
            for item in order.items.all():
                qty_field = f"return_qty_{item.id}"
                condition_field = f"condition_{item.id}"
                qty_str = request.POST.get(qty_field, '0')
                condition = request.POST.get(condition_field, ReturnItem.SELLABLE)

                try:
                    qty = int(qty_str)
                    if qty > 0:
                        return_items_data.append({
                            'order_item': item,
                            'quantity': qty,
                            'condition': condition
                        })
                except ValueError:
                    continue

            if not return_items_data:
                messages.error(request, "Please enter a return quantity > 0 for at least one item.")
            else:
                try:
                    user = request.user if request.user.is_authenticated else None
                    ret = services.process_order_return(
                        order=order,
                        return_items_data=return_items_data,
                        reason=reason,
                        restock_inventory=restock_inventory,
                        user=user
                    )
                    restock_msg = "Items inspected and returned to stock." if restock_inventory else "Return logged without restocking."
                    messages.success(request, f"Return {ret.return_number} recorded! Refund: ${ret.refund_amount}. {restock_msg}")
                    return redirect('sales:detail', pk=order.pk)
                except ValueError as err:
                    messages.error(request, str(err))
    else:
        form = OrderReturnForm()

    context = {
        'order': order,
        'form': form,
    }
    return render(request, 'sales/order_return_form.html', context)
