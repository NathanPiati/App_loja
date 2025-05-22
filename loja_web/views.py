from django.shortcuts import render, redirect, get_object_or_404
from .models import Produto, Venda, Servicos, ItemVenda, Pedido, ItemProduto, ItemServico
from .forms import ProdutoForm, VendaForm, ItemVendaFormSet, VendasFilterForm, CategoriaForm, Categoria, ConfiguracaoDBForm, PedidoForm, ItemProdutoFormSet, ItemServicoFormSet
from django.db.models import Sum
from .forms import VendasFilterForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pyodbc



def nova_venda(request):
    if request.method == 'POST':
        form = VendaForm(request.POST)
        formset = ItemVendaFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            venda = form.save(commit=False)
            venda.total = 0  # Inicializa
            venda.save()

            itens = formset.save(commit=False)
            total = 0

            for item in itens:
                item.venda = venda
                item.subtotal_valor = item.quantidade * item.preco_unitario
                total += item.subtotal_valor
                item.save()

            venda.total = total
            venda.save()

            formset.save_m2m()

            return redirect('lista_vendas')  # Ajuste para sua URL de listagem
    else:
        form = VendaForm()
        formset = ItemVendaFormSet()

    return render(request, 'venda_form.html', {
        'form': form,
        'formset': formset
    })


def lista_vendas(request):
    vendas = Venda.objects.all()
    return render(request, 'lista_vendas.html', {'vendas': vendas})


def logout_view(request):
    logout(request)
    return redirect('login')

def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')  # ou sua view principal
        else:
            return render(request, 'login.html', {'form': {'errors': True}})

    return render(request, 'login.html', {'form': {}})

@login_required
def home(request):
    produtos = Produto.objects.filter(eh_servico=False)
    servicos = Produto.objects.filter(eh_servico=True)
    return render(request, 'home.html', {'produtos': produtos, 'servicos': servicos})

def relatorio_vendas(request):
    vendas = Venda.objects.all()
    return render(request, 'relatorio.html', {'vendas': vendas})


def produto_create(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('home')
    else:
        form = ProdutoForm()
    return render(request, 'produto_form.html', {'form': form})

def produto_form(request):
    form = ProdutoForm()

    busca = request.GET.get('busca')
    if busca:
        produtos = Produto.objects.filter(nome__icontains=busca)
    else:
        produtos = Produto.objects.all()

    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('produto_form')  # ou a URL que desejar

    return render(request, 'produto_form.html', {
        'form': form,
        'produtos': produtos,
    })

def produto_novo(request):
    form = ProdutoForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('produto_novo')
    
    busca = request.GET.get('busca', '')
    produtos = Produto.objects.filter(nome__icontains=busca) if busca else Produto.objects.all()

    return render(request, 'produto_form.html', {
        'form': form,
        'produtos': produtos
    })

def produto_editar(request, id):
    produto = get_object_or_404(Produto, id=id)
    form = ProdutoForm(request.POST or None, instance=produto)
    if form.is_valid():
        form.save()
        return redirect('produto_novo')

    produtos = Produto.objects.all()
    return render(request, 'produto_form.html', {
        'form': form,
        'produtos': produtos
    })    


def produto_excluir(request, id):
    produto = get_object_or_404(Produto, id=id)
    produto.delete()
    return redirect('produto_novo')


def venda_create(request):
    if request.method == 'POST':
        form = VendaForm(request.POST)
        formset = ItemVendaFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            venda = form.save(commit=False)
            venda.total = 0  # Inicializa
            venda.save()
            total = 0
            for item_form in formset:
                item = item_form.save(commit=False)
                item.venda = venda
                total += item.quantidade * item.preco_unitario
                item.save()
            venda.total = total
            venda.save()
            return redirect('relatorio_vendas')
    else:
        form = VendaForm()
        formset = ItemVendaFormSet()
    return render(request, 'venda_form.html', {'form': form, 'formset': formset})




def relatorio_vendas(request):
    form = VendasFilterForm(request.GET or None)
    vendas = Venda.objects.all().order_by('-data')
    
    if form.is_valid():
        data_inicial = form.cleaned_data.get('data_inicial')
        data_final = form.cleaned_data.get('data_final')
        if data_inicial:
            vendas = vendas.filter(data__gte=data_inicial)
        if data_final:
            vendas = vendas.filter(data__lte=data_final)
    
    total_vendas = vendas.aggregate(Sum('total'))['total__sum'] or 0

    context = {
        'form': form,
        'vendas': vendas,
        'total_vendas': total_vendas,
    }
    return render(request, 'relatorio.html', context)


def relatorio_view(request):
    form = VendasFilterForm(request.GET or None)
    vendas = Venda.objects.all()

    if form.is_valid():
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')
        total_min = form.cleaned_data.get('total_min')
        total_max = form.cleaned_data.get('total_max')

        if data_inicio:
            vendas = vendas.filter(data__date__gte=data_inicio)
        if data_fim:
            vendas = vendas.filter(data__date__lte=data_fim)
        if total_min is not None:
            vendas = vendas.filter(total__gte=total_min)
        if total_max is not None:
            vendas = vendas.filter(total__lte=total_max)

    return render(request, 'relatorio.html', {'form': form, 'vendas': vendas})


def categoria_create(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('categoria_create')  # Ou qualquer outra view que tenha
    else:
        form = CategoriaForm()
    return render(request, 'categoria_form.html', {'form': form})

def produto_lista(request):
    produtos = Produto.objects.all()
    return render(request, 'produto_lista.html', {'produtos': produtos})

def servico_lista(request):
    servicos = Servicos.objects.all()
    return render(request, 'servico_lista.html', {'servicos': servicos})


def nova_categoria(request):
    form = CategoriaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoria cadastrada com sucesso!✅')
        return redirect('nova_categoria')
    return render(request, 'nova_categoria.html', {'form': form})


def pesquisar_categoria(request):
    categorias = None  # não mostra nada inicialmente

    if 'q' in request.GET:
        q = request.GET.get('q', '').strip()
        if q:
            categorias = Categoria.objects.filter(nome__icontains=q)
        else:
            categorias = Categoria.objects.all()

    return render(request, 'pesquisar_categoria.html', {'categorias': categorias})

def editar_categoria(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    form = CategoriaForm(request.POST or None, instance=categoria)
    
    if form.is_valid():
        form.save()
        return redirect('pesquisar_categoria')  # ou 'nova_categoria', se preferir

    return render(request, 'nova_categoria.html', {'form': form, 'editando': True})


def excluir_categoria(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    categoria.delete()
    messages.success(request, 'Categoria excluída com sucesso!')
    return redirect('pesquisar_categoria')  # ou o nome da URL onde lista as categorias    




def pedido_view(request, pk=None):
    if pk:
        pedido = get_object_or_404(Pedido, pk=pk)
    else:
        pedido = None

    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        formset_produto = ItemProdutoFormSet(request.POST, instance=pedido)
        formset_servico = ItemServicoFormSet(request.POST, instance=pedido)

        if form.is_valid() and formset_produto.is_valid() and formset_servico.is_valid():
            pedido = form.save()
            formset_produto.instance = pedido
            formset_servico.instance = pedido
            formset_produto.save()
            formset_servico.save()
            return redirect('listar_pedidos')

    else:
        form = PedidoForm(instance=pedido)
        formset_produto = ItemProdutoFormSet(instance=pedido)
        formset_servico = ItemServicoFormSet(instance=pedido)

    return render(request, 'venda_form.html', {
        'form': form,
        'formset_produtos': formset_produto,
        'formset_servicos': formset_servico,
    })


def listar_pedidos(request):
    pedidos = Pedido.objects.all()
    return render(request, 'listar_pedidos.html', {'pedidos': pedidos})