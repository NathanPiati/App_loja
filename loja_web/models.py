from django.db import models
from django import forms

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
    estoque = models.PositiveIntegerField()
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    eh_servico = models.BooleanField(default=False)

    def __str__(self):
        return self.nome

class Venda(models.Model):
    data = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Venda {self.id} - {self.data.strftime('%d/%m/%Y')}"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade = models.PositiveIntegerField()
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

class Servicos(models.Model):
    id = models.BigAutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.nome

