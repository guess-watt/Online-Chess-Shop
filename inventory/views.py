from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from products.models import Product
from .models import Store, Inventory, InventoryMovement
from .forms import StockAdjustmentForm
from . import services


def inventory_list(request):
    """
    Overview of on-hand inventory across all sales channels.
    Displays physical store vs online channel stocks.
    """
    search_query = request.GET.get('q', '').strip()
    stores = list(Store.objects.filter(is_active=True).order_by('id'))

    products = Product.objects.filter(is_active=True).select_related('category').prefetch_related('inventory_records')

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) | Q(sku__icontains=search_query)
        )

    # Build inventory matrix: product -> store_id -> quantity
    inventory_rows = []
    for product in products:
        stock_by_store = {inv.store_id: inv.quantity for inv in product.inventory_records.all()}
        store_quantities = []
        for store in stores:
            store_quantities.append({
                'store': store,
                'quantity': stock_by_store.get(store.id, 0)
            })

        inventory_rows.append({
            'product': product,
            'stores': store_quantities,
            'total_stock': product.total_stock,
            'is_low_stock': product.is_low_stock,
        })

    low_stock_count = sum(1 for row in inventory_rows if row['is_low_stock'])

    context = {
        'stores': stores,
        'inventory_rows': inventory_rows,
        'low_stock_count': low_stock_count,
        'search_query': search_query,
    }
    return render(request, 'inventory/inventory_list.html', context)


def stock_adjust(request):
    """
    Interface to record stock additions (purchase) or reductions (damage/adjustment).
    """
    initial_data = {}
    product_id = request.GET.get('product')
    store_id = request.GET.get('store')
    if product_id:
        initial_data['product'] = product_id
    if store_id:
        initial_data['store'] = store_id

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            product = form.cleaned_data['product']
            store = form.cleaned_data['store']
            action = form.cleaned_data['action']
            quantity = form.cleaned_data['quantity']
            reason = form.cleaned_data['reason']

            if action == 'ADD':
                delta = quantity
                movement_type = InventoryMovement.PURCHASE
                default_reason = reason or "Supplier Stock In"
            else:
                delta = -quantity
                movement_type = InventoryMovement.ADJUSTMENT
                default_reason = reason or "Manual Stock Reduction"

            try:
                user = request.user if request.user.is_authenticated else None
                inv, mov = services.adjust_stock(
                    product=product,
                    store=store,
                    quantity_delta=delta,
                    movement_type=movement_type,
                    reason=default_reason,
                    user=user
                )
                action_text = f"Added {quantity}" if delta > 0 else f"Deducted {quantity}"
                messages.success(
                    request,
                    f"Successfully updated stock for '{product.name}' at '{store.name}'. "
                    f"{action_text} units (New balance: {inv.quantity})."
                )
                return redirect('inventory:list')
            except ValueError as err:
                messages.error(request, str(err))
    else:
        form = StockAdjustmentForm(initial=initial_data)

    return render(request, 'inventory/stock_adjust.html', {'form': form})


def movement_history(request):
    """
    Immutable audit history of all inventory movements.
    """
    movement_type = request.GET.get('type', '')
    product_id = request.GET.get('product', '')
    store_id = request.GET.get('store', '')

    movements = InventoryMovement.objects.select_related('product', 'store', 'created_by').order_by('-created_at')

    if movement_type:
        movements = movements.filter(movement_type=movement_type)
    if product_id:
        movements = movements.filter(product_id=product_id)
    if store_id:
        movements = movements.filter(store_id=store_id)

    movements = movements[:100]  # Show recent 100 entries

    stores = Store.objects.filter(is_active=True)
    products = Product.objects.all().order_by('name')

    context = {
        'movements': movements,
        'movement_types': InventoryMovement.MOVEMENT_TYPES,
        'stores': stores,
        'products': products,
        'selected_type': movement_type,
        'selected_product': product_id,
        'selected_store': store_id,
    }
    return render(request, 'inventory/movement_history.html', context)


def low_stock_list(request):
    """
    Lists products whose stock has dropped to or below their low-stock threshold.
    """
    low_stock_products = services.get_low_stock_products()
    stores = Store.objects.filter(is_active=True)

    context = {
        'low_stock_products': low_stock_products,
        'stores': stores,
    }
    return render(request, 'inventory/low_stock.html', context)
