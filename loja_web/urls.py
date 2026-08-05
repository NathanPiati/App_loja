from django.urls import path
from . import views

urlpatterns = [
    path('pedidos/', views.PedidoListCreateAPIView.as_view(), name='pedido-list-create'),
    # outras URLs da API do app
]
