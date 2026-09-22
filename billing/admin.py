from django.contrib import admin

from .models import Assinatura, Lead, Plano, Sistema


@admin.register(Sistema)
class SistemaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'ativo']
    list_filter = ['ativo']
    search_fields = ['nome', 'slug']


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'sistema', 'valor_mensal',
                    'limite_usuarios', 'ativo', 'destaque']
    list_filter = ['sistema', 'ativo', 'destaque']
    search_fields = ['nome', 'slug']


@admin.register(Assinatura)
class AssinaturaAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'plano', 'status',
                    'responsavel', 'inicio_ciclo', 'fim_ciclo']
    list_filter = ['status', 'plano']
    search_fields = ['empresa__nome',
                     'responsavel__username', 'gateway_subscription_id']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'empresa_nome', 'criado_em']
    search_fields = ['nome', 'email', 'empresa_nome']
