from django import forms
from products.models import Product
from .models import Store, InventoryMovement


class StockAdjustmentForm(forms.Form):
    ACTION_CHOICES = [
        ('ADD', 'Add Stock (Supplier Purchase / Restock)'),
        ('DEDUCT', 'Deduct Stock (Damage / Write-Off / Audit Correction)'),
    ]

    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )
    store = forms.ModelChoiceField(
        queryset=Store.objects.filter(is_active=True).order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter quantity (e.g. 10)'})
    )
    reason = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Batch #4092 from DGT distributor'})
    )
