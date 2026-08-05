from django import forms
from django_select2 import forms as s2forms
# Importe o novo modelo EntradaEstoque junto com os outros
from .models import Produto, Venda, ItemVenda, Categoria, Pedido, ItemServico, Cliente, ItensPedido, EntradaEstoque, SaidaEstoque, CondicaoPagamento, Servicos, Empresa, Fornecedor, PedidoCompra, ItemPedidoCompra, Acompanhamento, ProdutoComposicao
from django.forms import inlineformset_factory
from datetime import date
from decimal import Decimal, InvalidOperation


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ("nome", "telefone", "email", "endereco", "cidade")
        widgets = {
            "nome": forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome'
            }),
            "telefone": forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o telefone'
            }),
            "email": forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o email'
            }),
            "endereco": forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o endereço'
            }),
            "cidade": forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite a cidade'
            }),
        }


# class ClienteForm(forms.ModelForm):
#     class Meta:
#         model = Cliente
#         fields = ("nome", "telefone", "email", "endereco", "cidade")

# class ClienteWidget(s2forms.ModelSelect2Widget):
#     search_fields = [
#         "nome__icontains",
#         "email__icontains",
#         "endereco__icontains",
#         "cidade__icontains",
#     ]


class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['cliente', 'condicao_pagamento',
                  'desconto_percentual', 'status', 'observacoes']
        widgets = {
            'desconto_percentual': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'observacoes': forms.Textarea(attrs={'rows': 3}),
        }


class PedidoForm_old(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ["cliente", "condicao_pagamento",
                  "desconto_percentual", "observacoes", "status", "valor_total"]
        widgets = {
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
            "valor_total": forms.NumberInput(attrs={"class": "form-control", "readonly": True}),
        }
        labels = {
            "desconto_percentual": "Desconto (%)"
        }


ItensPedidoFormSet = inlineformset_factory(
    Pedido,
    ItensPedido,
    fields=("produto", "descricao", "quantidade", "preco_unitario"),
    extra=0,
    can_delete=True
)


ItemServicoFormSet = inlineformset_factory(
    Pedido,
    ItemServico,
    fields=('descricao', 'quantidade', 'preco_unitario'),
    extra=0,
    can_delete=True
    # widgets={
    #     'descricao': forms.TextInput(attrs={'class': 'form-control'}),
    #     'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    #     'preco_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    # }
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
        fields = ['nome', 'marca', 'preco', 'notafiscal', 'valor_pago',
                  'categoria', 'unidade_medida', 'garantia_dias', 'descricao', 'num_fabricante', 'num_original']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 4}),
            'preco': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'valor_pago': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'garantia_dias': forms.NumberInput(attrs={'step': '1', 'min': '0'}),

        }


class ProdutoComposicaoForm(forms.ModelForm):
    class Meta:
        model = ProdutoComposicao
        fields = ['ingrediente', 'quantidade']
        widgets = {
            'ingrediente': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.001', 'min': '0.001'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        opcoes = []
        for pk, label in self.fields['ingrediente'].choices:
            if not pk:
                opcoes.append((pk, label))
                continue
            pk_val = getattr(pk, 'value', pk)
            try:
                produto = Produto.objects.get(pk=pk_val)
                unidade = produto.unidade_medida
            except Produto.DoesNotExist:
                unidade = ''
            opcoes.append((pk, f"{label} [{unidade}]" if unidade else label))
        self.fields['ingrediente'].choices = opcoes

    def clean(self):
        cleaned = super().clean()
        ingrediente = cleaned.get('ingrediente')
        quantidade = cleaned.get('quantidade')

        if not ingrediente or quantidade in (None, ''):
            return cleaned

        if quantidade <= 0:
            raise forms.ValidationError(
                'A quantidade do ingrediente deve ser maior que zero.')

        # Ingredientes medidos em unidade não devem ter frações
        if ingrediente.unidade_medida == Produto.UNIDADE and quantidade != int(quantidade):
            raise forms.ValidationError(
                f'O ingrediente "{ingrediente.nome}" usa unidade (un), então a quantidade deve ser inteira.'
            )

        return cleaned


class BaseProdutoComposicaoFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()

        ingrediente_ids = []
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            ingrediente = form.cleaned_data.get('ingrediente')
            if ingrediente:
                ingrediente_ids.append(ingrediente.id)

        if len(ingrediente_ids) != len(set(ingrediente_ids)):
            raise forms.ValidationError(
                'Não repita o mesmo ingrediente na ficha técnica.')

        if self.instance and self.instance.pk and self.instance.id in ingrediente_ids:
            raise forms.ValidationError(
                'O produto não pode ser ingrediente de si mesmo.')


ProdutoComposicaoFormSet = inlineformset_factory(
    Produto,
    ProdutoComposicao,
    fk_name='produto',
    form=ProdutoComposicaoForm,
    formset=BaseProdutoComposicaoFormSet,
    extra=1,
    can_delete=True,
)


class ItemVendaForm(forms.Form):
    produto_id = forms.IntegerField(widget=forms.HiddenInput)
    quantidade = forms.IntegerField(min_value=1, initial=1)

    def clean_produto_id(self):
        produto_id = self.cleaned_data['produto_id']
        try:
            Produto.objects.get(id=produto_id)
        except Produto.DoesNotExist:
            raise forms.ValidationError("Produto não encontrado.")
        return produto_id

# class VendaForm(forms.Form):
#     cliente = forms.ModelChoiceField(queryset=Cliente.objects.all(), empty_label="Selecione o cliente", required=True)
#     condicao_pagamento = forms.ModelChoiceField(queryset=CondicaoPagamento.objects.all(), empty_label="Selecione", required=True)


class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = ['condicao_pagamento']
        widgets = {
            'condicao_pagamento': forms.Select(attrs={'class': 'form-select'})
        }


class ItemVendaForm(forms.Form):
    produto_id = forms.IntegerField(widget=forms.HiddenInput())
    quantidade = forms.IntegerField(min_value=1, initial=1, widget=forms.NumberInput(
        attrs={'class': 'form-control', 'min': '1'}))


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
        # Usando classe Bootstrap 5 como exemplo
        widget=forms.Select(attrs={"class": "form-select"})
        # Considere usar django-select2 se tiver muitos produtos:
        # widget=s2forms.ModelSelect2Widget(model=Produto, search_fields=["nome__icontains"], attrs={"data-placeholder": "Selecione um produto..."})
    )

    class Meta:
        model = EntradaEstoque
        # Inclua os campos que o usuário preencherá no formulário
        fields = ["produto", "quantidade"]
        # Você pode adicionar widgets para customizar a aparência
        widgets = {
            "quantidade": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Adiciona um placeholder ou opção vazia ao select de produto, se desejar
        self.fields["produto"].empty_label = "Selecione um Produto"

    def clean(self):
        cleaned = super().clean()
        produto = cleaned.get('produto')
        quantidade = cleaned.get('quantidade')

        if not produto or quantidade in (None, ''):
            return cleaned

        if quantidade <= 0:
            raise forms.ValidationError(
                'A quantidade da entrada deve ser maior que zero.')

        if produto.unidade_medida == Produto.UNIDADE and quantidade != int(quantidade):
            raise forms.ValidationError(
                'Para produto em unidade (un), a entrada deve ser inteira.')

        return cleaned

# --- Fim Formulário para Entrada de Estoque ---


class BaixaEstoqueForm(forms.ModelForm):
    produto = forms.ModelChoiceField(
        queryset=Produto.objects.filter(eh_servico=False),
        label="Produto",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    class Meta:
        model = SaidaEstoque
        fields = ["produto", "quantidade", "motivo", "observacao"]
        widgets = {
            "quantidade": forms.NumberInput(attrs={"class": "form-control", "step": "1", "min": "1"}),
            "motivo": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex.: perda, ajuste, uso interno"}),
            "observacao": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Detalhes da baixa"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["produto"].empty_label = "Selecione um Produto"

    def clean(self):
        cleaned = super().clean()
        produto = cleaned.get('produto')
        quantidade = cleaned.get('quantidade')

        if not produto or quantidade in (None, ''):
            return cleaned

        if quantidade <= 0:
            raise forms.ValidationError(
                'A quantidade da baixa deve ser maior que zero.')

        if produto.unidade_medida == Produto.UNIDADE and quantidade != int(quantidade):
            raise forms.ValidationError(
                'Para produto em unidade (un), a baixa deve ser inteira.')

        if produto.estoque < quantidade:
            raise forms.ValidationError(
                f'Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque_exibicao}'
            )

        return cleaned

# +++ Formulário de Filtro para Lista de Produtos +++


class ProdutoFilterForm(forms.Form):
    id = forms.IntegerField(
        required=False,
        label="ID",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "ID"})
    )
    nome = forms.CharField(
        required=False,
        label="Nome",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nome do produto"})
    )
    marca = forms.CharField(
        required=False,
        label="Marca",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Marca"})
    )
    categoria = forms.ModelChoiceField(
        queryset=Categoria.objects.all(),
        required=False,
        label="Categoria",
        empty_label="Todas as Categorias",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    num_fabricante = forms.CharField(
        required=False,
        label="Número do Fabricante",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Número do Fabricante"})
    )
    num_original = forms.CharField(
        required=False,
        label="Número Original",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Número Original"})
    )
# +++ Fim Formulário de Filtro +++


class PedidoFilterForm(forms.Form):
    id = forms.IntegerField(
        required=False,
        label="ID Pedido",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "ID"})
    )
    cliente = forms.ModelChoiceField(
        queryset=Cliente.objects.all(),
        required=False,
        label="Cliente",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos')] +
        list(Pedido._meta.get_field('status').choices),
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


# --- Condição de Pagamento ---
class CondicaoPagamentoForm(forms.ModelForm):
    numero_parcelas = forms.ChoiceField(
        choices=[(i, i) for i in range(1, 13)],
        label="Número de Parcelas"
    )
    intervalo_dias = forms.ChoiceField(
        choices=[(1, '1 dia'), (7, '7 dias'), (15, '15 dias'),
                 (30, '30 dias'), (60, '60 dias'), (90, '90 dias')],
        label="Intervalo entre Parcelas"
    )
    juros = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0,
        label="Juros (%)"
    )

    class Meta:
        model = CondicaoPagamento
        fields = ['nome', 'descricao', 'numero_parcelas',
                  'juros', 'intervalo_dias', 'entrada']
        labels = {
            'nome': 'Nome da Condição',
            'descricao': 'Descrição',
            'entrada': 'Entrada',
            'juros': 'Juros (%)',

        }


class ServicoForm(forms.ModelForm):
    class Meta:
        model = Servicos
        fields = ['nome', 'preco']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o nome do serviço'
            }),
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Digite o preço do serviço'
            }),
        }
        labels = {
            'nome': 'Nome do Serviço',
            'preco': 'Preço (R$)',
        }


class AcompanhamentoForm(forms.ModelForm):
    class Meta:
        model = Acompanhamento
        fields = ['nome', 'preco', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: Calda de chocolate, Granulado, Leite em pó'
            }),
            'preco': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0,00'
            }),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'nome': 'Nome do Acompanhamento',
            'preco': 'Preço (R$)',
            'ativo': 'Ativo',
        }


# --- NOVOS FORMS PARA O TESTE DE EDITAR O PEDIDO DE VENDA ---
class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['cliente', 'condicao_pagamento',
                  'status', 'desconto_percentual', 'observacoes']
        widgets = {
            'observacoes': forms.Textarea(attrs={'rows': 4}),
            'desconto_percentual': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ItensPedidoForm(forms.ModelForm):
    class Meta:
        model = ItensPedido
        fields = ['id', 'produto', 'descricao', 'quantidade',
                  'preco_unitario', 'num_fabricante', 'num_original']
        widgets = {
            'id': forms.HiddenInput(),
            'produto': forms.HiddenInput(),  # Campo oculto, pois é preenchido via JavaScript
        }

    def clean_produto(self):
        produto = self.cleaned_data.get('produto')
        if not produto:
            raise forms.ValidationError("O campo produto é obrigatório.")
        return produto

    def clean_quantidade(self):
        quantidade = self.cleaned_data.get('quantidade')
        if quantidade <= 0:
            raise forms.ValidationError(
                "A quantidade deve ser maior que zero.")
        return quantidade

    def clean_preco_unitario(self):
        preco = self.cleaned_data.get('preco_unitario')
        if preco < 0:
            raise forms.ValidationError(
                "O preço unitário não pode ser negativo.")
        return preco


class ItemServicoForm(forms.ModelForm):
    class Meta:
        model = ItemServico
        fields = ['servico_id', 'descricao', 'quantidade', 'preco_unitario']

    def clean_preco_unitario(self):
        preco = self.cleaned_data.get('preco_unitario')
        if preco is not None:
            try:
                if isinstance(preco, str):
                    preco = preco.replace(',', '.').strip()
                preco = Decimal(preco)
                if preco < 0:
                    raise forms.ValidationError(
                        "Preço unitário não pode ser negativo.")
            except (ValueError, TypeError, InvalidOperation):
                raise forms.ValidationError(
                    "Preço unitário deve ser um número válido (ex.: 99,90 ou 99.90).")
        return preco


# class EmpresaForm(forms.ModelForm):
#     class Meta:
#         model = Empresa
#         fields = ["nome", "cnpj", "endereco", "telefone", "email", "logo"]


class EmpresaForm(forms.ModelForm):
    logo_file = forms.FileField(required=False, label="Logo")

    class Meta:
        model = Empresa
        fields = [
            'nome', 'segmento', 'cnpj', 'endereco', 'telefone', 'email',
            'server_url', 'cliente_id', 'chave_licenca'
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        file = self.cleaned_data.get('logo_file')
        if file:
            instance.logo = file.read()
            instance.logo_tipo = file.content_type
        if commit:
            instance.save()
        return instance


class CondicaoPagamentoFilterForm(forms.Form):
    nome = forms.CharField(max_length=100, required=False, label="Nome")
    descricao = forms.CharField(required=False, label="Descrição")
    numero_parcelas = forms.IntegerField(
        required=False, label="Número de Parcelas")
    intervalo_dias = forms.IntegerField(
        required=False, label="Intervalo (dias)")
    entrada = forms.ChoiceField(
        choices=[('', 'Todos'), ('True', 'Sim'), ('False', 'Não')],
        required=False,
        label="Entrada"
    )


class FornecedorForm(forms.ModelForm):
    class Meta:
        model = Fornecedor
        fields = ['nome', 'telefone', 'email',
                  'endereco', 'cidade', 'estado', 'cnpj', 'cep']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'endereco': forms.TextInput(attrs={'class': 'form-control'}),
            'cidade': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.TextInput(attrs={'class': 'form-control'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00.000.000/0000-00'}),
            'cep': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '00000-000'}),
        }


class UploadXMLForm(forms.Form):
    xml_file = forms.FileField(label='XML da NF-e')


# Form simples para edição
class ReviewEntradaForm(forms.ModelForm):
    class Meta:
        model = EntradaEstoque
        fields = ['produto', 'quantidade',
                  'custo_unitario', 'numero_nota_fiscal']
        widgets = {'produto': forms.Select(attrs={'class': 'form-control'})}


class PedidoCompraForm(forms.ModelForm):
    class Meta:
        model = PedidoCompra
        fields = ['fornecedor', 'numero_nota_fiscal',
                  'condicao_pagamento', 'observacao']
        widgets = {
            'fornecedor': forms.HiddenInput(),  # Use HiddenInput for supplier ID
            'numero_nota_fiscal': forms.TextInput(attrs={'class': 'form-control'}),
            'condicao_pagamento': forms.Select(attrs={'class': 'form-control'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


ItemPedidoCompraFormSet = inlineformset_factory(
    PedidoCompra,
    ItemPedidoCompra,
    fields=['produto', 'quantidade', 'custo_unitario'],
    widgets={
        'produto': forms.Select(attrs={'class': 'form-control'}),
        'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        'custo_unitario': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
    },
    extra=1,
    can_delete=True
)


class ItemPedidoCompraForm(forms.Form):
    produto = forms.ModelChoiceField(queryset=Produto.objects.all(
    ), widget=forms.Select(attrs={'class': 'form-control'}))
    quantidade = forms.IntegerField(
        min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    custo_unitario = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=0, widget=forms.NumberInput(attrs={'class': 'form-control'}))
