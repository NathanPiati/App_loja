from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('planos/', views.lista_planos, name='lista_planos'),
    path('assinar/<int:plano_id>/', views.iniciar_assinatura,
         name='iniciar_assinatura'),
    path('minha-assinatura/', views.minha_assinatura, name='minha_assinatura'),
    path('webhook/asaas/', views.webhook_asaas, name='webhook_asaas'),
]
