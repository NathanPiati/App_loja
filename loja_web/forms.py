from django import forms
from django_select2 import forms as s2forms
# Importe o novo modelo EntradaEstoque junto com os outros
from .models import Produto, Venda, ItemVenda, Categoria, Pedido, ItemServico, Cliente, ItensPedido, EntradaEstoque
from django.forms import inlineformset_factory

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ("nome", "telefone")
        
class ClienteWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "nome__icontains",
    ]




class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        # Adicionar o novo campo 'desconto_percentual' aos fields
        fields = ["cliente", "data", "condicao_pagamento", "desconto_percentual", "observacoes", "status"]
        widgets = {
            "data": forms.DateInput(
                attrs={
                    "type": "date", 
                    "class": "form-control", 
                    "style": "max-width: 200px;"
                }
            ),
            # Adicionar um widget para o campo de desconto, se desejado (ex: NumberInput)
            "desconto_percentual": forms.NumberInput(
                attrs={
                    "class": "form-control", 
                    "step": "0.01", 
                    "min": "0.00", 
                    "max": "100.00",
                    "placeholder": "0.00"
                }
            ),
            "cliente": forms.Select(attrs={"class": "form-select"}),
            "condicao_pagamento": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "observacoes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }
        labels = {
            "desconto_percentual": "Desconto (%)" # Definir um label amigável
        }



ItensPedidoFormSet = inlineformset_factory(
    Pedido,
    ItensPedido,
    fields=("produto", "descricao", "quantidade", "preco_unitario"),
    extra=0,
    can_delete=True
)


# Removido FormSet duplicado
# ItensPedidoFormSet = inlineformset_factory(
#     Pedido, ItensPedido,
#     fields=("produto", "descricao", "quantidade", "preco_unitario"),
#     extra=0,
#     can_delete=True
# )

class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemServico
        fields = "__all__"

class PedidoForm2(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = "__all__"
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
        }


ItemProdutoFormSet = inlineformset_factory(
    Pedido, ItensPedido,
    fields=["descricao", "quantidade", "preco_unitario"],
    extra=1, can_delete=True
)

ItemServicoFormSet = inlineformset_factory(
    Pedido, ItemServico,
    fields=["descricao", "quantidade", "preco_unitario"],
    extra=1, can_delete=True
)

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ["id", "nome", "descricao", "marca", "preco", "estoque", "categoria", "eh_servico"]

class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = ["cliente"]


class ItemVendaForm(forms.ModelForm):
    class Meta:
        model = ItemVenda
        fields = ["produto", "quantidade", "preco_unitario"]


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
        fields = ["nome"]
        widgets = {
            "nome": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Digite o nome da categoria"
            })
        }
        labels = {
            "nome": "Nome da Categoria",
        }


class VendasFilterForm(forms.Form):
    data_inicio = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Data Inicio"
    )
    data_fim = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
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

# Removido CategoriaForm duplicado
# class CategoriaForm(forms.ModelForm):
#     class Meta:
#         model = Categoria
#         fields = ["nome"]
#         widgets = {
#             "nome": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome da Categoria"}),
#         }


class ConfiguracaoDBForm(forms.Form):
    servidor = forms.CharField(label="Servidor", max_length=100)
    banco = forms.CharField(label="Banco de Dados", max_length=100)
    usuario = forms.CharField(label="Usuário", max_length=100)
    senha = forms.CharField(label="Senha", widget=forms.PasswordInput)

# --- Formulário para Entrada de Estoque --- 
class EntradaEstoqueForm(forms.ModelForm):
    # Para selecionar o produto, usamos um ModelChoiceField.
    # Filtramos para mostrar apenas produtos que NÃO são serviços.
    produto = forms.ModelChoiceField(
        queryset=Produto.objects.filter(eh_servico=False),
        label="Produto",
        widget=forms.Select(attrs={"class": "form-select"}) # Usando classe Bootstrap 5 como exemplo
        # Considere usar django-select2 se tiver muitos produtos:
        # widget=s2forms.ModelSelect2Widget(model=Produto, search_fields=["nome__icontains"], attrs={"data-placeholder": "Selecione um produto..."})
    )

    class Meta:
        model = EntradaEstoque
        # Inclua os campos que o usuário preencherá no formulário
        fields = ["produto", "quantidade"]
        # Você pode adicionar widgets para customizar a aparência
        widgets = {
            "quantidade": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona um placeholder ou opção vazia ao select de produto, se desejar
        self.fields["produto"].empty_label = "Selecione um Produto"

# --- Fim Formulário para Entrada de Estoque ---

# +++ Formulário de Filtro para Lista de Produtos +++
class ProdutoFilterForm(forms.Form):
    id = forms.IntegerField(required=False, label="ID", widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "ID"}))
    nome = forms.CharField(required=False, label="Nome", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nome do produto"}))
    marca = forms.CharField(required=False, label="Marca", widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Marca"}))
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        label="Categoria",
        empty_label="Todas as Categorias",
        widget=forms.Select(attrs={"class": "form-select"})
    )
# +++ Fim Formulário de Filtro +++

class PedidoFilterForm(forms.Form):
    id = forms.IntegerField(
        required=False,
        label="ID Pedido",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "ID"})
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        label="Cliente",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] + list(Pedido._meta.get_field('status').choices),
        required=False,
        label="Status",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    data_inicio = forms.DateField(
        required=False,
        label="Data Inicial",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
    data_fim = forms.DateField(
        required=False,
        label="Data Final",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )
