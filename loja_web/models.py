from django.db import models
from django import forms
from django.utils import timezone
# Importar validadores para o campo de desconto
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date, timedelta
from django.dispatch import receiver
from django.db.models.signals import post_save
from decimal import Decimal
from django.db.models import Sum, Q
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='categorias'
    )

    def __str__(self):
        return self.nome


class Produto(models.Model):
    UNIDADE = 'un'
    QUILO = 'kg'
    LITRO = 'lt'
    UNIDADE_CHOICES = [
        (UNIDADE, 'Unidade'),
        (QUILO, 'Quilo (kg)'),
        (LITRO, 'Litro (lt)'),
    ]

    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='produtos'
    )
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    num_fabricante = models.CharField(max_length=100, blank=True)
    num_original = models.CharField(max_length=100, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    # decimal para suportar kg/lt
    estoque = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    unidade_medida = models.CharField(
        max_length=2,
        choices=UNIDADE_CHOICES,
        default=UNIDADE,
        verbose_name='Unidade de Medida',
    )
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    notafiscal = models.CharField(max_length=100, blank=True)
    valor_pago = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    eh_servico = models.BooleanField(default=False)
    garantia_dias = models.PositiveIntegerField(
        default=0,
        verbose_name='Garantia (dias)',
        help_text='Informe 0 para produtos sem garantia.',
    )

    @property
    def custo_calculado(self):
        if not self.pk:
            return Decimal('0.00')
        total = Decimal('0.00')
        for componente in self.componentes.select_related('ingrediente').all():
            total += (componente.quantidade or Decimal('0')) * \
                (componente.ingrediente.valor_pago or Decimal('0'))
        return total.quantize(Decimal('0.01'))

    def atualizar_valor_pago_por_composicao(self):
        if not self.pk:
            return
        if self.componentes.exists():
            self.valor_pago = self.custo_calculado
            self.save(update_fields=['valor_pago'])

    @property
    def estoque_exibicao(self):
        valor = self.estoque or Decimal('0')
        if self.unidade_medida == self.UNIDADE:
            return f"{valor:.0f}"
        return f"{valor:.3f}"

    def __str__(self):
        return self.nome


class ProdutoComposicao(models.Model):
    produto = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='componentes'
    )
    ingrediente = models.ForeignKey(
        Produto,
        on_delete=models.CASCADE,
        related_name='usado_em_receitas'
    )
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3, default=0)

    class Meta:
        verbose_name = 'Componente do Produto'
        verbose_name_plural = 'Componentes do Produto'
        unique_together = ('produto', 'ingrediente')

    def __str__(self):
        return f'{self.produto.nome} -> {self.quantidade} x {self.ingrediente.nome}'


class Servicos(models.Model):
    id = models.BigAutoField(primary_key=True)
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='servicos'
    )
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Cliente(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='clientes'
    )
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    endereco = models.CharField(max_length=200, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['nome']

    def __str__(self):
        return self.nome


# --- Condições de Pagamento ---
class CondicaoPagamento(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='condicoes_pagamento'
    )
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, null=True)
    numero_parcelas = models.IntegerField(default=1)
    intervalo_dias = models.IntegerField(default=30)
    entrada = models.BooleanField(default=False)
    juros = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Condição de Pagamento"
        verbose_name_plural = "Condições de Pagamento"
        ordering = ['nome']

    def __str__(self):
        return self.nome

# --- Pedido ---


class Pedido(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='pedidos'
    )
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data = models.DateTimeField(auto_now_add=True)
    condicao_pagamento = models.ForeignKey(
        CondicaoPagamento, on_delete=models.SET_NULL, null=True, blank=True)
    juros = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    observacoes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=(
        ('pendente', 'Pendente'),
        ('concluido', 'Concluído'),
    ))
    valor_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    desconto_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        verbose_name="Desconto (%)"
    )

    def __str__(self):
        return f'Pedido {self.id} - {self.cliente.nome}'

    @property
    def valor_liquido(self):
        desconto = (self.valor_total * self.desconto_percentual) / 100
        return self.valor_total - desconto

# class MovimentoFinanceiro(models.Model):
#     pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="financeiros")
#     descricao = models.CharField(max_length=200)
#     parcela = models.IntegerField(default=1)
#     total_parcelas = models.IntegerField(default=1)
#     condicao_id = models.ForeignKey(CondicaoPagamento, on_delete=models.SET_NULL, null=True, blank=True)

#     valor_parcela = models.DecimalField(max_digits=10, decimal_places=2)
#     data_vencimento = models.DateField()
#     data_pagamento = models.DateField(blank=True, null=True)

#     pago = models.BooleanField(default=False)
#     observacao = models.TextField(blank=True, null=True)

#     class Meta:
#         verbose_name = "Movimento Financeiro"
#         verbose_name_plural = "Movimentos Financeiros"
#         ordering = ['pedido', 'data_vencimento', 'parcela']
#     def __str__(self):
#         return f'Pedido {self.pedido.id} - Parcela {self.parcela}/{self.total_parcelas}'

#     @property
#     def status(self):
#         if self.pago:
#             return "Pago"
#         elif self.data_vencimento < date.today():
#             return "Vencido"
#         else:
#             return "Aberto"


class MovimentoFinanceiro(models.Model):
    TIPO_MOVIMENTO = (
        ('DESPESA', 'Despesa'),
        ('RECEITA', 'Receita'),
    )
    # Substituir ForeignKey por GenericForeignKey
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, related_name="financeiros", null=True, blank=True)
    pedido_compra = models.ForeignKey(
        'PedidoCompra', on_delete=models.CASCADE, related_name="financeiros", null=True, blank=True)
    descricao = models.CharField(max_length=200)
    parcela = models.IntegerField(default=1)
    total_parcelas = models.IntegerField(default=1)
    condicao_id = models.ForeignKey(
        CondicaoPagamento, on_delete=models.SET_NULL, null=True, blank=True)
    valor_parcela = models.DecimalField(max_digits=10, decimal_places=2)
    data_vencimento = models.DateField()
    data_pagamento = models.DateField(blank=True, null=True)
    pago = models.BooleanField(default=False)
    observacao = models.TextField(blank=True, null=True)
    tipo = models.CharField(
        max_length=10, choices=TIPO_MOVIMENTO, default='RECEITA')
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='movimentos_financeiros'
    )

    class Meta:
        verbose_name = "Movimento Financeiro"
        verbose_name_plural = "Movimentos Financeiros"
        ordering = ['pedido', 'data_vencimento', 'parcela']

    # def __str__(self):
    #     return f'Pedido {self.pedido.id} - Parcela {self.parcela}/{self.total_parcelas}'

    def __str__(self):
        if self.pedido:
            return f'Pedido {self.pedido.id} - Parcela {self.parcela}/{self.total_parcelas}'
        elif self.pedido_compra:
            return f'Pedido Compra {self.pedido_compra.id} - Parcela {self.parcela}/{self.total_parcelas}'
        return f'{self.tipo} - Parcela {self.parcela}/{self.total_parcelas}'

    @property
    def status(self):
        if self.pago:
            return "Pago"
        elif self.data_vencimento < date.today():
            return "Vencido"
        else:
            return "Aberto"


class FechamentoCaixa(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='fechamentos_caixa'
    )
    data_abertura = models.DateTimeField(default=timezone.now)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    saldo_inicial = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    saldo_final = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    caixa_aberto = models.BooleanField(default=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Fechamento de Caixa"
        verbose_name_plural = "Fechamentos de Caixa"

    def calcular_totais(self):
        inicio = self.data_abertura
        fim = self.data_fechamento or timezone.now()

        inicio_date = inicio.date()
        fim_date = fim.date()

        movimentos_periodo = MovimentoFinanceiro.objects.filter(
            pago=True,
            data_pagamento__range=[inicio_date, fim_date]
        )

        total_vendas = Pedido.objects.filter(
            status='concluido',
            data__range=[inicio, fim]
        ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')

        # Evita dupla contagem com vendas:
        # receitas vinculadas a pedido de venda entram em "total_vendas".
        total_entradas = movimentos_periodo.filter(
            pedido__isnull=True,
            pedido_compra__isnull=True
        ).filter(
            Q(tipo='RECEITA') | Q(valor_parcela__gt=0)
        ).aggregate(total=Sum('valor_parcela'))['total'] or Decimal('0.00')

        total_saidas_manuais = SaidaFinanceira.objects.filter(
            caixa=self,
            data__range=[inicio, fim]
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

        # Regras de saída:
        # 1) qualquer movimento vinculado a pedido de compra é saída
        # 2) demais movimentos de despesa ou valor negativo também são saída
        saidas_financeiras = movimentos_periodo.filter(
            Q(pedido_compra__isnull=False) |
            Q(tipo='DESPESA') |
            Q(valor_parcela__lt=0)
        ).values_list('valor_parcela', flat=True)

        total_saidas_financeiras = sum(
            (abs(valor) for valor in saidas_financeiras), Decimal('0.00'))
        total_saidas = total_saidas_manuais + total_saidas_financeiras

        saldo_esperado = self.saldo_inicial + \
            total_vendas + total_entradas - total_saidas

        return {
            'vendas': total_vendas,
            'entradas': total_entradas,
            'saidas': total_saidas,
            'esperado': saldo_esperado
        }

    def fechar_caixa(self, saldo_fisico, observacoes=''):
        if not self.caixa_aberto:
            raise ValueError("Caixa já fechado")
        if saldo_fisico < 0:
            raise ValueError("Saldo físico não pode ser negativo")

        self.data_fechamento = timezone.now()
        self.saldo_final = Decimal(saldo_fisico)
        self.observacoes = observacoes
        self.caixa_aberto = False
        self.save()

    def __str__(self):
        return f"Caixa {self.data_abertura.strftime('%d/%m/%Y %H:%M')}"


class SaidaFinanceira(models.Model):
    caixa = models.ForeignKey(
        FechamentoCaixa, on_delete=models.CASCADE, related_name='saidas')
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    descricao = models.CharField(max_length=200)
    data = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Saída R$ {self.valor} - {self.descricao}"


class ItensPedido(models.Model):
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    descricao = models.CharField(max_length=200)
    num_fabricante = models.CharField(max_length=100, blank=True)
    num_original = models.CharField(max_length=100, blank=True)
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3)  # suporta kg/lt (ex: 1.500)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"
        ordering = ['pedido', 'produto']

    @property
    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f'{self.descricao} (Qtd: {self.quantidade})'


class ItemServico(models.Model):
    pedido = models.ForeignKey(
        Pedido, on_delete=models.CASCADE, related_name='itens_servico')
    servico_id = models.ForeignKey(Servicos, on_delete=models.CASCADE,
                                   related_name='itens', null=True, blank=True)  # Ajustado related_name
    # Torna descricao opcional
    descricao = models.CharField(max_length=100, blank=True)
    quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Item de Serviço"
        verbose_name_plural = "Itens de Serviços"
        # Ajustado para ordenar por nome do serviço
        ordering = ['pedido', 'servico_id__nome']

    @property
    def total(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f"{self.servico_id.nome if self.servico_id else self.descricao} - Pedido {self.pedido.id}"


class Fornecedor(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='fornecedores'
    )
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.CharField(max_length=200, blank=True, null=True)
    cidade = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=100, blank=True, null=True)
    # máscara 00.000.000/0000-00
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    cep = models.CharField(max_length=9, blank=True, null=True)

    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
    # id é criado automaticamente como chave primária

# --- Entrada de produtos ---


class EntradaEstoque(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='entradas_estoque'
    )
    produto = models.ForeignKey(
        Produto, on_delete=models.PROTECT, related_name='entradas')
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3,
        verbose_name="Quantidade Recebida")
    data_entrada = models.DateTimeField(
        auto_now_add=True, verbose_name="Data da Entrada")
    fornecedor = models.ForeignKey(
        'Fornecedor', on_delete=models.SET_NULL, null=True, blank=True)
    nome_fornecedor = models.CharField(max_length=100, blank=True, null=True)
    numero_nota_fiscal = models.CharField(
        max_length=100, null=True, blank=True)
    custo_unitario = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    pedido_compra = models.ForeignKey(
        'PedidoCompra',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entradas'
    )

    def __str__(self):
        nome_produto = self.produto.nome if hasattr(
            self.produto, 'nome') else str(self.produto.pk)
        return f"Entrada de {self.quantidade}x {nome_produto} em {self.data_entrada.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Entrada de Estoque"
        verbose_name_plural = "Entradas de Estoque"
        ordering = ['-data_entrada']

# --- Fim Entrada de produtos ---


class SaidaEstoque(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='saidas_estoque_empresa'
    )
    produto = models.ForeignKey(
        Produto, on_delete=models.PROTECT, related_name='saidas_estoque')
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3, verbose_name="Quantidade Baixada")
    motivo = models.CharField(max_length=150, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)
    data_saida = models.DateTimeField(
        auto_now_add=True, verbose_name="Data da Baixa")

    def __str__(self):
        nome_produto = self.produto.nome if hasattr(
            self.produto, 'nome') else str(self.produto.pk)
        return f"Baixa de {self.quantidade}x {nome_produto} em {self.data_saida.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Baixa de Estoque"
        verbose_name_plural = "Baixas de Estoque"
        ordering = ['-data_saida']


class Empresa(models.Model):
    SEGMENTO_AUTOPECAS = 'autopecas'
    SEGMENTO_SORVETERIA = 'sorveteria'
    SEGMENTO_CHOICES = [
        (SEGMENTO_AUTOPECAS, 'Autopeças / Oficina'),
        (SEGMENTO_SORVETERIA, 'Sorveteria / Açaí'),
    ]

    nome = models.CharField(max_length=150)
    segmento = models.CharField(
        max_length=30,
        choices=SEGMENTO_CHOICES,
        default=SEGMENTO_AUTOPECAS,
    )
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    endereco = models.CharField(max_length=200, blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.BinaryField(blank=True, null=True)
    logo_tipo = models.CharField(max_length=50, blank=True, null=True)

    # CAMPOS ADICIONADOS PARA LICENÇA
    server_url = models.URLField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="URL do Servidor de Licença",
        help_text="Ex: http://127.0.0.1:8000/api/verificar_licenca"
    )
    cliente_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="ID do Cliente",
        help_text="ID usado no app para validar a licença"
    )
    chave_licenca = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Chave de Licença",
        help_text="Chave UUID ou string fornecida ao cliente"
    )

    def __str__(self):
        return self.nome


class Venda(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='vendas'
    )
    datavenda = models.DateTimeField(auto_now_add=True)
    cliente = models.CharField(max_length=100, blank=True, null=True)
    valortotal = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    condicao_pagamento = models.ForeignKey(
        CondicaoPagamento,
        on_delete=models.SET_NULL,
        null=True
    )

    def __str__(self):
        return f"Venda {self.id} - {self.datavenda.strftime('%d/%m/%Y')}"

    def calcular_total(self):
        valortotal = sum(item.subtotal() for item in self.itens.all())
        self.valortotal = valortotal
        self.save()


class ItemVenda(models.Model):
    venda = models.ForeignKey(
        Venda, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    garantia_dias = models.PositiveIntegerField(default=0)
    garantia_ate = models.DateField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.garantia_dias and self.produto_id:
            self.garantia_dias = self.produto.garantia_dias or 0

        if self.garantia_dias > 0:
            data_venda = timezone.localdate()
            if self.venda_id and self.venda.datavenda:
                data_venda = self.venda.datavenda.date()
            self.garantia_ate = data_venda + timedelta(days=self.garantia_dias)
        else:
            self.garantia_ate = None

        super().save(*args, **kwargs)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome}"


class PedidoCompra(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='pedidos_compra'
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.SET_NULL, null=True)
    numero_nota_fiscal = models.CharField(max_length=100, blank=True)
    condicao_pagamento = models.ForeignKey(
        CondicaoPagamento, on_delete=models.SET_NULL, null=True, blank=True)
    data_criacao = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(
        max_length=20,
        choices=[('pendente', 'Pendente'), ('concluido', 'Concluído')],
        default='pendente'
    )

    class Meta:
        verbose_name = "Pedido de Compra"
        verbose_name_plural = "Pedidos de Compra"
        ordering = ['-data_criacao']

    def __str__(self):
        return f'Pedido Compra {self.id} - {self.fornecedor.nome if self.fornecedor else "Sem Fornecedor"}'


class ItemPedidoCompra(models.Model):
    pedido_compra = models.ForeignKey(
        PedidoCompra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField()
    quantidade_atendida = models.PositiveIntegerField(default=0)
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.quantidade}x {self.produto.nome} - Pedido {self.pedido_compra.id}'


class PermissaoPersonalizada(models.Model):
    """Modelo vazio só para gerar permissões personalizadas"""
    nome = models.CharField(max_length=100, blank=True)

    class Meta:
        permissions = [
            ("gerenciar_usuarios", "Pode gerenciar usuários e grupos"),
            ("view_relatorio", "Pode ver relatórios"),
            ("add_produto", "Pode cadastrar produto"),
            ("edit_produto", "Pode editar produto"),
            ("delete_produto", "Pode excluir produto"),
        ]
        verbose_name = "Permissão Personalizada"
        verbose_name_plural = "Permissões Personalizadas"
        ordering = ['-id']  # ou outro campo existente, se quiser ordenar


class PermissaoSistema(models.Model):
    class Meta:
        permissions = [
            ("acessar_dashboard", "Pode acessar o dashboard"),
            ("gerenciar_usuarios", "Pode gerenciar usuários"),
            ("cadastrar_produto", "Pode cadastrar produto"),
            ("ver_relatorios", "Pode ver relatórios"),
            ("editar_config", "Pode editar configurações"),


            # NOVAS PERMISSÕES (adicione aqui)
            ("realizar_venda", "Pode realizar venda direta"),
            ("ver_clientes", "Pode ver clientes"),
            ("gerenciar_fornecedores", "Pode gerenciar fornecedores"),
            ("criar_produto", "Pode criar produto"),
            ("gerenciar_estoque", "Pode gerenciar estoque"),
            ("ver_pedidos", "Pode ver pedidos/OS"),
            ("criar_pedido", "Pode criar pedido/OS"),
            ("encerrar_pedido", "Pode encerrar pedido/OS"),
            ("gerenciar_pedidos", "Pode gerenciar pedidos/OS"),
            ("gerenciar_pedidos_compras", "Pode gerenciar pedidos de compras"),
            ("gerenciar_financeiro", "Pode gerenciar financeiro"),
            ("fechamento_caixa", "Pode fazer fechamento de caixa"),
            ("gerenciar_servicos", "Pode gerenciar serviços"),
            ("gerenciar_categorias", "Pode gerenciar categorias"),
            ("gerenciar_condicoes_pagamento",
             "Pode gerenciar condições de pagamento"),
            ("ver_condicoes_pagamento", "Pode ver condições de pagamento"),
            ("criar_condicao_pagamento", "Pode criar condição de pagamento"),
            ("gerenciar_cobranca_whatsapp",
             "Pode gerenciar regras de cobrança via WhatsApp"),
            ("ver_cobranca_whatsapp", "Pode ver cobranças via WhatsApp"),
        ]
        verbose_name = "Permissão do Sistema"
        verbose_name_plural = "Permissões do Sistema"


class LogAuditoria(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='logs_auditoria_empresa'
    )
    ACOES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('criar', 'Criar'),
        ('editar', 'Editar'),
        ('excluir', 'Excluir'),
        ('venda', 'Venda'),
        ('estoque', 'Estoque'),
        ('financeiro', 'Financeiro'),
        ('caixa', 'Caixa'),
        ('pedido', 'Pedido'),
        ('outro', 'Outro'),
    ]

    usuario = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='logs_auditoria'
    )
    acao = models.CharField(max_length=20, choices=ACOES, default='outro')
    entidade = models.CharField(max_length=100, blank=True)
    detalhes = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'

    def __str__(self):
        usuario_str = self.usuario.username if self.usuario else 'Anônimo'
        return f'[{self.created_at:%d/%m/%Y %H:%M}] {usuario_str} — {self.get_acao_display()} {self.entidade}'


# ---------------------------------------------------------------------------
# Acompanhamentos (sorveteria: caldas, coberturas, granulado etc.)
# Visível apenas quando segmento == 'sorveteria', mas a tabela é compartilhada
# ---------------------------------------------------------------------------

class Acompanhamento(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='acompanhamentos'
    )
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Acompanhamento'
        verbose_name_plural = 'Acompanhamentos'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ItensPedidoAcompanhamento(models.Model):
    """Acompanhamentos adicionados a um item específico do pedido."""
    item_pedido = models.ForeignKey(
        ItensPedido, on_delete=models.CASCADE, related_name='acompanhamentos'
    )
    acompanhamento = models.ForeignKey(
        Acompanhamento, on_delete=models.CASCADE
    )
    quantidade = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = 'Acompanhamento do Item'
        verbose_name_plural = 'Acompanhamentos do Item'

    @property
    def subtotal(self):
        return self.quantidade * self.acompanhamento.preco

    def __str__(self):
        return f'{self.quantidade}x {self.acompanhamento.nome} → Item {self.item_pedido.id}'


class UsuarioEmpresa(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='empresas_vinculadas'
    )
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='usuarios_vinculados'
    )
    ativo = models.BooleanField(default=True)
    padrao = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Vínculo Usuário-Empresa'
        verbose_name_plural = 'Vínculos Usuário-Empresa'
        unique_together = ('user', 'empresa')

    def __str__(self):
        return f'{self.user.username} -> {self.empresa.nome}'


# ---------------------------------------------------------------------------
# Cobrança automática de clientes via WhatsApp (pedidos de produtos e/ou
# serviços em aberto), com regras configuráveis de recorrência em dias.
# ---------------------------------------------------------------------------

class RegraCobrancaWhatsApp(models.Model):
    APLICAR_TODOS = 'todos'
    APLICAR_PRODUTOS = 'produtos'
    APLICAR_SERVICOS = 'servicos'
    APLICAR_CHOICES = [
        (APLICAR_TODOS, 'Pedidos e Serviços'),
        (APLICAR_PRODUTOS, 'Somente Pedidos (produtos)'),
        (APLICAR_SERVICOS, 'Somente Serviços'),
    ]

    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='regras_cobranca_whatsapp'
    )
    nome = models.CharField(max_length=100, verbose_name='Nome da regra')
    aplicar_a = models.CharField(
        max_length=10, choices=APLICAR_CHOICES, default=APLICAR_TODOS,
        verbose_name='Aplicar a'
    )
    dias_referencia = models.IntegerField(
        default=1,
        verbose_name='Disparar (dias)',
        help_text='Negativo = dias antes do vencimento. 0 = no dia do vencimento. Positivo = dias após o vencimento (atraso).'
    )
    repetir_a_cada_dias = models.PositiveIntegerField(
        default=0,
        verbose_name='Repetir a cada (dias)',
        help_text='Deixe 0 para enviar apenas uma vez. Ex: 5 = reenvia a cada 5 dias enquanto estiver em aberto.'
    )
    mensagem = models.TextField(
        verbose_name='Mensagem',
        default=(
            'Qualquer dúvida sobre este lançamento, estamos à disposição. '
            'Empresa: {empresa}.'
        ),
        help_text=('A cobrança já inclui os dados do financeiro. Use como complemento. '
                   'Placeholders: {cliente}, {valor}, {vencimento}, {pedido}, {empresa}, '
                   '{descricao}, {parcela}, {total_parcelas}, {status}, {observacao}')
    )
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Regra de Cobrança WhatsApp'
        verbose_name_plural = 'Regras de Cobrança WhatsApp'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class EnvioCobrancaWhatsApp(models.Model):
    empresa = models.ForeignKey(
        'Empresa', on_delete=models.CASCADE, null=True, blank=True, related_name='envios_cobranca_whatsapp'
    )
    regra = models.ForeignKey(
        RegraCobrancaWhatsApp, on_delete=models.SET_NULL, null=True, blank=True, related_name='envios'
    )
    movimento = models.ForeignKey(
        MovimentoFinanceiro, on_delete=models.CASCADE, related_name='envios_cobranca_whatsapp'
    )
    numero_destino = models.CharField(max_length=30, blank=True)
    mensagem_enviada = models.TextField(blank=True)
    sucesso = models.BooleanField(default=False)
    resposta_api = models.TextField(blank=True)
    data_envio = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envio de Cobrança WhatsApp'
        verbose_name_plural = 'Envios de Cobrança WhatsApp'
        ordering = ['-data_envio']

    def __str__(self):
        return f'Envio #{self.id} - Movimento {self.movimento_id} - {"OK" if self.sucesso else "Falha"}'
