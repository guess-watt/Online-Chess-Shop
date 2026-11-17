from django.shortcuts import render
import json
from . import services
from sales.models import Order


def dashboard_view(request):
    """
    Main business executive dashboard displaying retail performance,
    KPIs, multi-channel comparisons, visual charts, and best-sellers.
    """
    kpis = services.get_dashboard_kpis()
    channel_comparison = services.get_channel_comparison()
    category_breakdown = services.get_category_breakdown()
    monthly_trends = services.get_monthly_sales_trends()
    best_sellers = services.get_best_selling_products(limit=5)
    recent_orders = Order.objects.select_related('customer', 'store').prefetch_related('items').order_by('-created_at')[:8]

    # JSON serializable data for Chart.js
    chart_category_labels = [c['category_name'] for c in category_breakdown]
    chart_category_revenues = [c['revenue'] for c in category_breakdown]

    chart_channel_labels = [ch['store_name'] for ch in channel_comparison]
    chart_channel_revenues = [ch['revenue'] for ch in channel_comparison]
    chart_channel_counts = [ch['order_count'] for ch in channel_comparison]

    context = {
        'kpis': kpis,
        'channel_comparison': channel_comparison,
        'category_breakdown': category_breakdown,
        'best_sellers': best_sellers,
        'recent_orders': recent_orders,
        # Chart JSON
        'chart_monthly_labels': json.dumps(monthly_trends['labels']),
        'chart_monthly_revenues': json.dumps(monthly_trends['revenues']),
        'chart_category_labels': json.dumps(chart_category_labels),
        'chart_category_revenues': json.dumps(chart_category_revenues),
        'chart_channel_labels': json.dumps(chart_channel_labels),
        'chart_channel_revenues': json.dumps(chart_channel_revenues),
        'chart_channel_counts': json.dumps(chart_channel_counts),
    }
    return render(request, 'dashboard/index.html', context)
