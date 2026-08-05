from django import forms
from .models import Fornecedor, CondicaoPagamento
from .tenancy import filtrar_queryset_empresa


class VendasFilterForm(forms.Form):
    data_inicial = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Data Inicial'
    )
    data_final = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Data Final'
    )


class PedidoCompraFilterForm(forms.Form):
    id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'placeholder': 'ID'}),
        label='ID'
    )
    fornecedor = forms.ModelChoiceField(
        queryset=Fornecedor.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Fornecedor'
    )
    numero_nota_fiscal = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Número NF'}),
        label='Número NF'
    )
    data_criacao = forms.DateField(
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'form-control'}),
        label='Data Criação'
    )
    condicao_pagamento = forms.ModelChoiceField(
        queryset=CondicaoPagamento.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Condição de Pagamento'
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request is not None:
            self.fields['fornecedor'].queryset = filtrar_queryset_empresa(
                request, Fornecedor.objects.all()
            )
            self.fields['condicao_pagamento'].queryset = filtrar_queryset_empresa(
                request, CondicaoPagamento.objects.all()
            )
