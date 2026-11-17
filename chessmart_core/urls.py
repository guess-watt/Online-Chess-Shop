from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='base.html'), name='home'),
    path('products/', include('products.urls')),
    path('inventory/', include('inventory.urls')),
    path('sales/', include('sales.urls')),
]
