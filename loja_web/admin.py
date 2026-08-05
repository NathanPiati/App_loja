from django.contrib import admin
from .models import (
    Categoria, Produto, Venda, ItemVenda, Pedido, ItensPedido, PermissaoPersonalizada, PermissaoSistema,
    Servicos, Cliente, ItemServico, EntradaEstoque, MovimentoFinanceiro, CondicaoPagamento, FechamentoCaixa, Fornecedor,
    Empresa, UsuarioEmpresa
)

# 🔥 Models básicos
admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Venda)
admin.site.register(ItemVenda)
admin.site.register(Pedido)
admin.site.register(ItensPedido)
admin.site.register(Servicos)
admin.site.register(Cliente)
admin.site.register(ItemServico)
admin.site.register(EntradaEstoque)
admin.site.register(CondicaoPagamento)
admin.site.register(FechamentoCaixa)
admin.site.register(Fornecedor)
admin.site.register(Empresa)


@admin.register(UsuarioEmpresa)
class UsuarioEmpresaAdmin(admin.ModelAdmin):
    list_display = ['user', 'empresa', 'ativo', 'padrao']
    list_filter = ['ativo', 'padrao', 'empresa']
    search_fields = ['user__username', 'empresa__nome']

# 🔥 Admin customizado para o Financeiro


@admin.register(MovimentoFinanceiro)
class MovimentoFinanceiroAdmin(admin.ModelAdmin):
    list_display = [
        'pedido', 'descricao', 'parcela', 'total_parcelas',
        'valor_parcela', 'data_vencimento', 'pago', 'status'
    ]
    list_filter = ['pago', 'data_vencimento']
    search_fields = ['pedido__id', 'descricao']


@admin.register(PermissaoPersonalizada)
class PermissaoAdmin(admin.ModelAdmin):
    list_display = ['nome']
    # Não precisa preencher nada – só para aparecer no Admin


@admin.register(PermissaoSistema)
class PermissaoAdmin(admin.ModelAdmin):
    def has_module_permission(self, request):
        return True  # mostra no admin
