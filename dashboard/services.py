from django.db.models import Sum, Count, F, Q, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from decimal import Decimal
from datetime import datetime
from sales.models import Order, OrderItem, OrderReturn, ReturnItem
from products.models import Product, Category
from inventory.models import Store, Inventory
from inventory import services as inv_services


def get_dashboard_kpis():
    """
    Computes high-level retail business KPIs:
    - Gross & Net Revenue
    - Cost of Goods Sold (COGS) & Net Profit
    - Total Orders & Channel split
    - Catalog count & On-hand inventory
    - Low-stock alert count
    """
    valid_statuses = [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]
    valid_orders = Order.objects.filter(order_status__in=valid_statuses)

    # 1. Total Orders & Status counts
    total_orders = valid_orders.count()
    all_non_cancelled_orders = Order.objects.exclude(order_status=Order.CANCELLED).count()

    # 2. Revenue calculations
    gross_revenue = valid_orders.aggregate(
        total=Coalesce(Sum('total_amount'), Decimal('0.00'))
    )['total']

    # Total accepted returns / refunds
    total_refunds = OrderReturn.objects.filter(
        return_status__in=[OrderReturn.APPROVED, OrderReturn.RESTOCKED]
    ).aggregate(
        total=Coalesce(Sum('refund_amount'), Decimal('0.00'))
    )['total']

    net_revenue = max(gross_revenue - total_refunds, Decimal('0.00'))

    # 3. Cost of Goods Sold (COGS) & Net Profit
    # Sum(unit_cost * quantity) for all items in valid orders
    cogs_items = OrderItem.objects.filter(
        order__order_status__in=valid_statuses
    ).aggregate(
        total_cogs=Coalesce(
            Sum(F('unit_cost') * F('quantity'), output_field=DecimalField()),
            Decimal('0.00')
        )
    )['total_cogs']

    # Account for restocked returns (inventory added back)
    restocked_cogs_recovery = ReturnItem.objects.filter(
        order_return__restock_inventory=True,
        condition=ReturnItem.SELLABLE
    ).aggregate(
        recovered=Coalesce(
            Sum(F('order_item__unit_cost') * F('quantity'), output_field=DecimalField()),
            Decimal('0.00')
        )
    )['recovered']

    adjusted_cogs = max(cogs_items - restocked_cogs_recovery, Decimal('0.00'))
    net_profit = net_revenue - adjusted_cogs

    profit_margin_percent = (
        (net_profit / net_revenue * 100) if net_revenue > Decimal('0.00') else Decimal('0.00')
    )

    # 4. Products & Inventory
    total_products = Product.objects.filter(is_active=True).count()
    total_available_stock = Inventory.objects.aggregate(
        total=Coalesce(Sum('quantity'), 0)
    )['total']
    low_stock_products = inv_services.get_low_stock_products()
    low_stock_count = len(low_stock_products)

    return {
        'total_orders': total_orders,
        'all_orders_count': all_non_cancelled_orders,
        'gross_revenue': gross_revenue,
        'total_refunds': total_refunds,
        'net_revenue': net_revenue,
        'cogs': adjusted_cogs,
        'net_profit': net_profit,
        'profit_margin_percent': profit_margin_percent,
        'total_products': total_products,
        'total_available_stock': total_available_stock,
        'low_stock_count': low_stock_count,
        'low_stock_products': low_stock_products[:5],
    }


def get_channel_comparison():
    """
    Compares sales volume and revenue between Physical Store (POS) and Online Webstore.
    """
    valid_statuses = [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]
    stores = Store.objects.filter(is_active=True)

    channel_data = []
    total_revenue_all = Decimal('0.00')

    for store in stores:
        store_orders = Order.objects.filter(store=store, order_status__in=valid_statuses)
        order_count = store_orders.count()
        rev = store_orders.aggregate(
            total=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )['total']
        total_revenue_all += rev

        channel_data.append({
            'store': store,
            'store_name': store.name,
            'store_type': store.store_type,
            'order_count': order_count,
            'revenue': float(rev),
        })

    # Calculate share percentage
    for ch in channel_data:
        if total_revenue_all > Decimal('0.00'):
            ch['share_percent'] = round((Decimal(str(ch['revenue'])) / total_revenue_all) * 100, 1)
        else:
            ch['share_percent'] = 0.0

    return channel_data


def get_category_breakdown():
    """
    Aggregates sales revenue and units sold by Product Category.
    """
    valid_statuses = [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]

    # Query Category aggregations
    categories = Category.objects.filter(is_active=True)
    category_data = []

    for cat in categories:
        items = OrderItem.objects.filter(
            product__category=cat,
            order__order_status__in=valid_statuses
        )
        cat_revenue = items.aggregate(
            total=Coalesce(Sum('subtotal'), Decimal('0.00'))
        )['total']
        cat_units = items.aggregate(
            units=Coalesce(Sum('quantity'), 0)
        )['units']

        category_data.append({
            'category_name': cat.name,
            'revenue': float(cat_revenue),
            'units_sold': cat_units,
        })

    # Sort by revenue descending
    category_data.sort(key=lambda x: x['revenue'], reverse=True)
    return category_data


def get_monthly_sales_trends():
    """
    Aggregates monthly sales performance for the last 6 months.
    """
    valid_statuses = [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]
    monthly_data = (
        Order.objects.filter(order_status__in=valid_statuses)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            revenue=Coalesce(Sum('total_amount'), Decimal('0.00')),
            orders_count=Count('id')
        )
        .order_by('month')
    )

    labels = []
    revenues = []
    order_counts = []

    for entry in monthly_data:
        m = entry['month']
        if m:
            labels.append(m.strftime('%b %Y'))
            revenues.append(float(entry['revenue']))
            order_counts.append(entry['orders_count'])

    # If no monthly data exists yet, provide current month placeholder
    if not labels:
        now = datetime.now()
        labels.append(now.strftime('%b %Y'))
        revenues.append(0.0)
        order_counts.append(0)

    return {
        'labels': labels,
        'revenues': revenues,
        'order_counts': order_counts,
    }


def get_best_selling_products(limit=5):
    """
    Ranks top products by volume sold and revenue generated.
    """
    valid_statuses = [Order.CONFIRMED, Order.PROCESSING, Order.SHIPPED, Order.DELIVERED]

    ranked_items = (
        OrderItem.objects.filter(order__order_status__in=valid_statuses)
        .values('product__id', 'product__name', 'product__sku', 'product__category__name')
        .annotate(
            units_sold=Coalesce(Sum('quantity'), 0),
            total_revenue=Coalesce(Sum('subtotal'), Decimal('0.00')),
            total_cost=Coalesce(Sum(F('unit_cost') * F('quantity'), output_field=DecimalField()), Decimal('0.00'))
        )
        .order_by('-units_sold', '-total_revenue')[:limit]
    )

    best_sellers = []
    for item in ranked_items:
        profit = item['total_revenue'] - item['total_cost']
        best_sellers.append({
            'product_id': item['product__id'],
            'name': item['product__name'],
            'sku': item['product__sku'],
            'category': item['product__category__name'],
            'units_sold': item['units_sold'],
            'total_revenue': item['total_revenue'],
            'profit': profit,
        })

    return best_sellers
