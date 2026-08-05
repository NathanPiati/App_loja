from django.urls import path

from . import evolution

urlpatterns = [
    path('status/', evolution.evolution_status, name='evolution_status'),
    path('webhook/', evolution.evolution_webhook, name='evolution_webhook'),
    path('enviar-teste/', evolution.evolution_send_test,
         name='evolution_send_test'),
    path('', evolution.evolution_panel, name='evolution_panel'),
]
