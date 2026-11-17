from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Product, Category
from .forms import ProductForm, CategoryForm
from inventory.models import Store, Inventory


def product_list(request):
    """
    Lists products with search, category filtering, and status filtering.
    """
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'all')

    products = Product.objects.select_related('category').prefetch_related('inventory_records', 'inventory_records__store')

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(description__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)

    categories = Category.objects.filter(is_active=True)

    context = {
        'products': products,
        'categories': categories,
        'selected_category': category_id,
        'selected_status': status_filter,
        'search_query': query,
    }
    return render(request, 'products/product_list.html', context)


def product_detail(request, pk):
    """
    Displays detailed product information including stock distribution across stores.
    """
    product = get_object_or_404(Product.objects.select_related('category'), pk=pk)
    stores = Store.objects.filter(is_active=True)
    
    # Map inventory by store
    store_stocks = []
    for store in stores:
        inv = product.inventory_records.filter(store=store).first()
        qty = inv.quantity if inv else 0
        store_stocks.append({
            'store': store,
            'quantity': qty
        })

    recent_movements = product.inventory_movements.select_related('store').order_by('-created_at')[:10]

    context = {
        'product': product,
        'store_stocks': store_stocks,
        'recent_movements': recent_movements,
    }
    return render(request, 'products/product_detail.html', context)


def product_create(request):
    """
    Creates a new product and initializes zero inventory for active stores.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save()
            # Initialize zero-stock record for each active store
            stores = Store.objects.filter(is_active=True)
            for store in stores:
                Inventory.objects.get_or_create(product=product, store=store, defaults={'quantity': 0})

            messages.success(request, f"Product '{product.name}' created successfully.")
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {'form': form, 'title': 'Add New Chess Product'})


def product_update(request, pk):
    """
    Updates an existing product's details.
    """
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect('products:detail', pk=product.pk)
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/product_form.html', {'form': form, 'title': f"Edit Product: {product.name}", 'product': product})


def product_toggle_status(request, pk):
    """
    Toggles product between active and inactive state.
    """
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        product.is_active = not product.is_active
        product.save(update_fields=['is_active', 'updated_at'])
        state = "activated" if product.is_active else "deactivated"
        messages.info(request, f"Product '{product.name}' has been {state}.")
    return redirect('products:detail', pk=pk)


def category_list(request):
    """
    Lists all categories and allows creating new categories.
    """
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            cat = form.save()
            messages.success(request, f"Category '{cat.name}' added successfully.")
            return redirect('products:category_list')
    else:
        form = CategoryForm()

    categories = Category.objects.all().prefetch_related('products')
    return render(request, 'products/category_list.html', {'categories': categories, 'form': form})
