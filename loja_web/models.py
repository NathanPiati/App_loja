from django.db import models
from django import forms
from django.utils import timezone
# Importar validadores para o campo de desconto
from django.core.validators import MinValueValidator, MaxValueValidator
import datetime


class Categoria(models.Model):
    nome = models.CharField(max_length=100)

    def __str__(self):
        return self.nome

class Produto(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    marca = models.CharField(max_length=100, blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.PositiveIntegerField() # Campo de estoque já existe!
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    eh_servico = models.BooleanField(default=False)

    def __str__(self):
        return self.nome

class Venda(models.Model):
    data = models.DateTimeField(auto_now_add=True)
    cliente = models.CharField(max_length=100, blank=True, null=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Venda {self.id} - {self.data.strftime('%d/%m/%Y')}"

    def calcular_total(self):
        total = sum(item.subtotal() for item in self.itens.all())
        self.total = total
        self.save()

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, related_name='itens', on_delete=models.CASCADE)
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome}"

class Servicos(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nome




class Cliente(models.Model):
    nome = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)

    def __str__(self):
        return self.nome

class Pedido(models.Model):
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
    data = models.DateTimeField(default=timezone.now)
    condicao_pagamento = models.IntegerField(choices=(
        (1, 'À Vista'),
        (2, 'Parcelado'),
    ))
    observacoes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=(
        ('pendente', 'Pendente'),
        ('concluido', 'Concluído'),
    ))
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Novo campo para desconto percentual
    desconto_percentual = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0.00, 
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        verbose_name="Desconto (%)"
    )

    def __str__(self):
        return f'Pedido {self.id} - {self.cliente.nome}'



class ItensPedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    descricao = models.CharField(max_length=200)
    quantidade = models.IntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f'{self.descricao} (Qtd: {self.quantidade})'

class ItemServico(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='itens_servico')
    descricao = models.CharField(max_length=100)
    quantidade = models.DecimalField(max_digits=10, decimal_places=2)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def total(self):
        return self.quantidade * self.preco_unitario




# --- Entrada de produtos --- 
class EntradaEstoque(models.Model):
    # Link para o produto que está entrando (Corrigido para apontar para o modelo Produto local)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='entradas')
    quantidade = models.PositiveIntegerField(verbose_name="Quantidade Recebida")
    data_entrada = models.DateTimeField(auto_now_add=True, verbose_name="Data da Entrada")
    # Opcional: Adicionar campos como fornecedor, número da nota, custo, etc.
    # fornecedor = models.ForeignKey('Fornecedor', on_delete=models.SET_NULL, null=True, blank=True)
    # numero_nota_fiscal = models.CharField(max_length=100, null=True, blank=True)
    # custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        # Tenta acessar o nome do produto, se existir
        nome_produto = self.produto.nome if hasattr(self.produto, 'nome') else str(self.produto.pk)
        return f"Entrada de {self.quantidade}x {nome_produto} em {self.data_entrada.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        verbose_name = "Entrada de Estoque"
        verbose_name_plural = "Entradas de Estoque"
        ordering = ['-data_entrada']

# --- Fim Entrada de produtos ---

