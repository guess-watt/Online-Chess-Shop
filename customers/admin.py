from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'customer_type', 'total_orders', 'created_at')
    list_filter = ('customer_type',)
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
