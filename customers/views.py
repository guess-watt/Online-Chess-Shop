from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q, Sum, Count
from decimal import Decimal
from .models import Customer
from .forms import CustomerForm
from sales.models import Order


def customer_list(request):
    """
    Lists customers with search and category filtering.
    """
    query = request.GET.get('q', '').strip()
    customer_type = request.GET.get('type', '').strip()

    customers = Customer.objects.all().prefetch_related('orders').order_by('name')

    if query:
        customers = customers.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(address__icontains=query)
        )
    if customer_type:
        customers = customers.filter(customer_type=customer_type)

    context = {
        'customers': customers,
        'customer_types': Customer.CUSTOMER_TYPES,
        'selected_type': customer_type,
        'search_query': query,
    }
    return render(request, 'customers/customer_list.html', context)


def customer_detail(request, pk):
    """
    Shows full customer profile, financial metrics, and comprehensive order history.
    """
    customer = get_object_or_404(Customer, pk=pk)
    orders = customer.orders.select_related('store').prefetch_related('items').order_by('-created_at')

    # Metrics
    valid_orders = orders.exclude(order_status=Order.CANCELLED)
    total_valid_orders = valid_orders.count()
    total_spent = sum(order.total_amount for order in valid_orders.filter(
        order_status__in=[Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]
    ))
    
    aov = (total_spent / total_valid_orders) if total_valid_orders > 0 else Decimal('0.00')

    context = {
        'customer': customer,
        'orders': orders,
        'total_valid_orders': total_valid_orders,
        'total_spent': total_spent,
        'aov': aov,
    }
    return render(request, 'customers/customer_detail.html', context)


def customer_create(request):
    """
    Registers a new customer profile.
    """
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save()
            messages.success(request, f"Customer '{customer.name}' registered successfully.")
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'customers/customer_form.html', {'form': form, 'title': 'Register New Customer'})


def customer_update(request, pk):
    """
    Updates an existing customer profile.
    """
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, f"Customer '{customer.name}' updated successfully.")
            return redirect('customers:detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'customers/customer_form.html', {'form': form, 'title': f"Edit Customer: {customer.name}", 'customer': customer})
