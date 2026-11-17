from django import forms
from .models import Product, Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Chess Clocks'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Category description...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name',
            'sku',
            'category',
            'selling_price',
            'cost_price',
            'low_stock_threshold',
            'is_active',
            'description',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. DGT 2010 Digital Chess Clock'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CLK-DGT-2010'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'low_stock_threshold': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Detailed product specifications...'}),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku', '').strip().upper()
        # Verify SKU uniqueness excluding self if editing
        qs = Product.objects.filter(sku__iexact=sku)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A product with this SKU already exists.")
        return sku

    def clean(self):
        cleaned_data = super().clean()
        selling_price = cleaned_data.get('selling_price')
        cost_price = cleaned_data.get('cost_price')

        if selling_price is not None and selling_price < 0:
            self.add_error('selling_price', "Selling price cannot be negative.")
        if cost_price is not None and cost_price < 0:
            self.add_error('cost_price', "Cost price cannot be negative.")
        if selling_price is not None and cost_price is not None and selling_price < cost_price:
            # We allow it with a warning, but highlight that selling price is below cost price
            pass
        return cleaned_data
