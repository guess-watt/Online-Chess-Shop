from django import forms
from customers.models import Customer
from inventory.models import Store
from sales.models import Order, OrderReturn


class POSSaleForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select an existing customer or walk-in account"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Paid in Cash / Counter Register 1'})
    )


class OnlineOrderForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Shipping instructions or customer notes...'})
    )


class OrderReturnForm(forms.Form):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for customer return...'})
    )
    restock_inventory = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Accept sellable items back into available store stock"
    )
