from django import forms
from .models import Produto, Venda, ItemVenda, Categoria
from django.forms import inlineformset_factory

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['id', 'nome', 'descricao', 'marca', 'preco', 'estoque', 'categoria', 'eh_servico']

class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = []  # A venda será criada automaticamente; o total será calculado

# Formset para os itens da venda

ItemVendaFormSet = inlineformset_factory(
    Venda, ItemVenda,
    fields=['produto', 'quantidade', 'preco_unitario'],
    extra=1,
    can_delete=True
)

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome da categoria'
            })
        }
        labels = {
            'nome': 'Nome da Categoria',
        }


class VendasFilterForm(forms.Form):
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Data Inicio"
    )
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="Data Fim"
    )
    total_min = forms.DecimalField(
        required=False,
        decimal_places=2,
        label="Total minimo"
    )
    total_max = forms.DecimalField(
        required=False,
        decimal_places=2,
        label="Total maximo"
    )

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da Categoria'}),
        }
