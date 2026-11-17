from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('add/', views.product_create, name='create'),
    path('<int:pk>/', views.product_detail, name='detail'),
    path('<int:pk>/edit/', views.product_update, name='update'),
    path('<int:pk>/toggle-status/', views.product_toggle_status, name='toggle_status'),
    path('categories/', views.category_list, name='category_list'),
]
