from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_list, name='list'),
    path('adjust/', views.stock_adjust, name='adjust'),
    path('history/', views.movement_history, name='history'),
    path('low-stock/', views.low_stock_list, name='low_stock'),
]
