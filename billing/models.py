from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone


class Plano(models.Model):
    nome = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    descricao = models.TextField(blank=True)
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2)
    limite_usuarios = models.PositiveIntegerField(default=1)
    limite_empresas = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    destaque = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['valor_mensal', 'nome']

    def __str__(self):
        return self.nome


class Assinatura(models.Model):
    STATUS_TRIAL = 'trial'
    STATUS_ATIVA = 'ativa'
    STATUS_ATRASADA = 'atrasada'
    STATUS_CANCELADA = 'cancelada'
    STATUS_SUSPENSA = 'suspensa'
    STATUS_CHOICES = [
        (STATUS_TRIAL, 'Trial'),
        (STATUS_ATIVA, 'Ativa'),
        (STATUS_ATRASADA, 'Atrasada'),
        (STATUS_CANCELADA, 'Cancelada'),
        (STATUS_SUSPENSA, 'Suspensa'),
    ]

    empresa = models.ForeignKey(
        'loja_web.Empresa', on_delete=models.CASCADE, related_name='assinaturas'
    )
    plano = models.ForeignKey(
        Plano, on_delete=models.PROTECT, related_name='assinaturas')
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assinaturas_responsavel'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_TRIAL)
    gateway = models.CharField(max_length=40, blank=True)
    gateway_customer_id = models.CharField(max_length=120, blank=True)
    gateway_subscription_id = models.CharField(max_length=120, blank=True)
    inicio_ciclo = models.DateField(default=date.today)
    fim_ciclo = models.DateField(null=True, blank=True)
    trial_ate = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.empresa.nome} - {self.plano.nome}'


class Lead(models.Model):
    nome = models.CharField(max_length=120)
    email = models.EmailField()
    telefone = models.CharField(max_length=30, blank=True)
    empresa_nome = models.CharField(max_length=150, blank=True)
    mensagem = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.nome} - {self.email}'
