from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.order_list, name='list'),
    path('pos/', views.pos_checkout, name='pos'),
    path('online/create/', views.online_order_create, name='online_create'),
    path('<int:pk>/', views.order_detail, name='detail'),
    path('<int:pk>/transition/', views.order_transition_status, name='transition'),
    path('<int:pk>/return/', views.order_return_create, name='return_create'),
]
