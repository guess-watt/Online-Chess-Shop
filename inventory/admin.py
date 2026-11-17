from django.contrib import admin
from .models import Store, Inventory, InventoryMovement


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'store_type', 'is_active', 'created_at')
    list_filter = ('store_type', 'is_active')
    search_fields = ('name',)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ('product', 'store', 'quantity', 'updated_at')
    list_filter = ('store', 'product__category')
    search_fields = ('product__name', 'product__sku', 'store__name')


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'product', 'store', 'quantity', 'movement_type', 'reason')
    list_filter = ('movement_type', 'store')
    search_fields = ('product__name', 'product__sku', 'reason')
    readonly_fields = ('created_at',)
