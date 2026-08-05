from django.urls import path

from . import views

app_name = 'site_publico'

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('planos/', views.planos_publicos, name='planos'),
    path('contato/', views.contato_publico, name='contato'),
]
