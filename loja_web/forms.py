from django import forms
from django_select2 import forms as s2forms
from .models import Produto, Venda, ItemVenda, Categoria, Pedido, ItemProduto, ItemServico
from django.forms import inlineformset_factory



class ClienteWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        'nome__icontains',
    ]


class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['cliente', 'data']
        widgets = {
            'cliente': ClienteWidget(
                attrs={'data-placeholder': 'Selecione o cliente...'}
            ),
            'data': forms.DateInput(
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }



class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = '__all__'
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }


ItemProdutoFormSet = inlineformset_factory(
    Pedido, ItemProduto,
    fields=['descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)

ItemServicoFormSet = inlineformset_factory(
    Pedido, ItemServico,
    fields=['descricao', 'quantidade', 'preco_unitario'],
    extra=1, can_delete=True
)

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['id', 'nome', 'descricao', 'marca', 'preco', 'estoque', 'categoria', 'eh_servico']

class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = ['cliente']


class ItemVendaForm(forms.ModelForm):
    class Meta:
        model = ItemVenda
        fields = ['produto', 'quantidade', 'preco_unitario']


ItemVendaFormSet = inlineformset_factory(
    Venda,
    ItemVenda,
    form=ItemVendaForm,
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


class ConfiguracaoDBForm(forms.Form):
    servidor = forms.CharField(label='Servidor', max_length=100)
    banco = forms.CharField(label='Banco de Dados', max_length=100)
    usuario = forms.CharField(label='Usuário', max_length=100)
    senha = forms.CharField(label='Senha', widget=forms.PasswordInput)