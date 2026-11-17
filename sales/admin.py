from django.contrib import admin
from .models import Order, OrderItem, OrderReturn, ReturnItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('subtotal',)


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer', 'store', 'order_status', 'total_amount', 'created_at')
    list_filter = ('order_status', 'store', 'created_at')
    search_fields = ('order_number', 'customer__name', 'customer__email')
    inlines = [OrderItemInline]
    readonly_fields = ('order_number', 'created_at', 'updated_at')


@admin.register(OrderReturn)
class OrderReturnAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'order', 'return_status', 'restock_inventory', 'refund_amount', 'created_at')
    list_filter = ('return_status', 'restock_inventory')
    search_fields = ('return_number', 'order__order_number')
    inlines = [ReturnItemInline]
    readonly_fields = ('return_number', 'created_at', 'updated_at')
