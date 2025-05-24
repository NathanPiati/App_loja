from django.shortcuts import render, redirect, get_object_or_404
# Importe o novo modelo e form
from .models import Produto, Venda, Servicos, ItemVenda, Pedido, ItemServico, Cliente, Categoria, EntradaEstoque
# Adicionado ProdutoFilterForm
from .forms import (ProdutoForm, VendaForm, ItemVendaFormSet, VendasFilterForm, 
                    CategoriaForm, ConfiguracaoDBForm, PedidoForm, ItemServicoForm, 
                    ClienteForm, EntradaEstoqueForm, ProdutoFilterForm) 
from django.db.models import Sum
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import pyodbc
from django.urls import reverse_lazy
from django.forms import inlineformset_factory
from django.http import JsonResponse
from django.db import transaction # Importado para atomicidade



def clientes(request):
    return render(request, 'clientes.html')

def pedidos(request):
    return render(request, 'pedidos.html')

def cliente_novo(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('clientes')  # Redireciona para a lista de clientes
    else:
        form = ClienteForm()
    return render(request, 'cliente_novo.html', {'form': form})

def cliente_lista(request):
    clientes = Cliente.objects.all()
    return render(request, 'clientes.html', {'clientes': clientes})

def cliente_editar(request, pk):
    cliente = Cliente.objects.get(pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            return redirect('clientes')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'cliente_editar.html', {'form': form})

def cliente_pesquisa(request):
    clientes = None  # Começa sem resultados

    if 'nome' in request.GET or 'email' in request.GET:  # Só pesquisa se clicar em pesquisar (ou seja, tiver query)
        nome = request.GET.get('nome', '').strip()
        email = request.GET.get('email', '').strip()

        clientes = Cliente.objects.all()

        if nome:
            clientes = clientes.filter(nome__icontains=nome)
        if email:
            clientes = clientes.filter(email__icontains=email)

    return render(request, 'cliente_pesquisa.html', {'clientes': clientes})




def cliente_excluir(request, pk):
    cliente = Cliente.objects.get(pk=pk)
    cliente.delete()
    return redirect('clientes')

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
                # Corrigido: O modelo ItemVenda não tem subtotal_valor, calcula direto
                subtotal_item = item.quantidade * item.preco_unitario 
                total += subtotal_item
                item.save()

            venda.total = total
            venda.save()

            # formset.save_m2m() # Não necessário aqui pois não há M2M no formset base

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
            messages.error(request, 'Usuário ou senha inválidos.') # Adiciona mensagem de erro
            return render(request, 'login.html', {'form': {}})

    return render(request, 'login.html', {'form': {}})

@login_required
def home(request):
    produtos = Produto.objects.filter(eh_servico=False)
    servicos = Produto.objects.filter(eh_servico=True)
    return render(request, 'home.html', {'produtos': produtos, 'servicos': servicos})

# Removido relatorio_vendas duplicado
# def relatorio_vendas(request):
#     vendas = Venda.objects.all()
#     return render(request, 'relatorio.html', {'vendas': vendas})

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
            messages.success(request, 'Produto salvo com sucesso!') # Mensagem de sucesso
            return redirect('produto_form')  # ou a URL que desejar
        else:
             messages.error(request, 'Erro ao salvar o produto. Verifique os campos.') # Mensagem de erro

    return render(request, 'produto_form.html', {
        'form': form,
        'produtos': produtos,
    })

def produto_novo(request):
    form = ProdutoForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Produto cadastrado com sucesso!')
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
        messages.success(request, 'Produto atualizado com sucesso!')
        # Redireciona para a lista de produtos após editar
        return redirect('produto_lista') 

    # Se GET, renderiza o formulário de edição (pode ser um template separado ou o mesmo)
    # Passando 'editando': True pode ajudar a diferenciar no template
    return render(request, 'produto_form.html', {
        'form': form,
        'editando': True 
    })    


def produto_excluir(request, id):
    produto = get_object_or_404(Produto, id=id)
    if request.method == 'POST': # Confirmação via POST é mais segura
        produto.delete()
        messages.success(request, 'Produto excluído com sucesso!')
        return redirect('produto_lista') # Redireciona para a lista após excluir
    # Se GET, pode mostrar uma página de confirmação (não implementado aqui)
    # Para simplificar, exclui direto no GET (menos seguro)
    produto.delete()
    messages.success(request, 'Produto excluído com sucesso!')
    return redirect('produto_lista') # Redireciona para a lista após excluir

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
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE'):
                    item = item_form.save(commit=False)
                    item.venda = venda
                    total += item.quantidade * item.preco_unitario
                    item.save()
            venda.total = total
            venda.save()
            messages.success(request, 'Venda registrada com sucesso!')
            return redirect('relatorio_vendas')
        else:
            messages.error(request, 'Erro ao registrar a venda. Verifique os itens.')
    else:
        form = VendaForm()
        formset = ItemVendaFormSet()
    return render(request, 'venda_form.html', {'form': form, 'formset': formset})




def relatorio_vendas(request):
    form = VendasFilterForm(request.GET or None)
    vendas = Venda.objects.all().order_by('-data')
    
    if form.is_valid():
        # Corrigido: Usar data_inicio e data_fim do VendasFilterForm
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
    
    total_vendas = vendas.aggregate(Sum('total'))['total__sum'] or 0

    context = {
        'form': form,
        'vendas': vendas,
        'total_vendas': total_vendas,
    }
    return render(request, 'relatorio.html', context)

# Removido relatorio_view duplicado
# def relatorio_view(request):
#     ...

def categoria_create(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria criada com sucesso!')
            return redirect('categoria_create')  # Ou qualquer outra view que tenha
        else:
            messages.error(request, 'Erro ao criar categoria.')
    else:
        form = CategoriaForm()
    return render(request, 'categoria_form.html', {'form': form})

# +++ View de Lista de Produtos Modificada (v2) +++
@login_required # Adicionar login required se necessário
def produto_lista(request):
    # Inicializa a lista de produtos como vazia
    produtos_list = Produto.objects.none() # Use .none() for an empty queryset
    # Flag para saber se uma busca foi realizada
    busca_realizada = False

    # Pega todas as categorias para o filtro (necessário para o dropdown)
    categorias = Categoria.objects.all()

    # Cria o formulário de filtro com os dados da requisição GET (se houver)
    filter_form = ProdutoFilterForm(request.GET or None)

    # Verifica se algum filtro foi submetido (request.GET não está vazio)
    # E se o formulário é válido (para evitar erros com dados inválidos)
    # Usamos `filter_form.is_bound` para checar se o form recebeu dados (via GET)
    if filter_form.is_bound and filter_form.is_valid():
        busca_realizada = True # Marca que uma busca foi feita
        # Começa com todos os produtos (não serviços)
        produtos_list = Produto.objects.filter(eh_servico=False).order_by('id')

        # Aplica os filtros
        produto_id = filter_form.cleaned_data.get('id')
        nome = filter_form.cleaned_data.get('nome')
        marca = filter_form.cleaned_data.get('marca')
        categoria = filter_form.cleaned_data.get('categoria')

        if produto_id:
            produtos_list = produtos_list.filter(id=produto_id)
        if nome:
            produtos_list = produtos_list.filter(nome__icontains=nome)
        if marca:
            produtos_list = produtos_list.filter(marca__icontains=marca)
        if categoria:
            produtos_list = produtos_list.filter(categoria=categoria)
    # Se o formulário não foi submetido ou é inválido, produtos_list continua vazio (Produto.objects.none())

    context = {
        'produtos': produtos_list,
        'filter_form': filter_form, # Passa o formulário para o template
        'categorias': categorias, # Passa categorias se precisar em outro lugar
        'busca_realizada': busca_realizada # Informa ao template se a busca foi feita
    }
    return render(request, 'produto_lista.html', context)
# +++ Fim View Modificada (v2) +++

def servico_lista(request):
    # Corrigido: Modelo Servicos não existe mais, usar Produto com eh_servico=True
    servicos = Produto.objects.filter(eh_servico=True)
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
        messages.success(request, 'Categoria atualizada com sucesso!')
        return redirect('pesquisar_categoria')  # ou 'nova_categoria', se preferir

    return render(request, 'nova_categoria.html', {'form': form, 'editando': True})


def excluir_categoria(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    if request.method == 'POST': # Adicionado confirmação POST
        categoria.delete()
        messages.success(request, 'Categoria excluída com sucesso!')
        return redirect('pesquisar_categoria')
    # Se GET, pode mostrar confirmação ou excluir direto (como estava)
    categoria.delete()
    messages.success(request, 'Categoria excluída com sucesso!')
    return redirect('pesquisar_categoria')  # ou o nome da URL onde lista as categorias    




# --- Pedidos --- 
# from .forms import PedidoForm, ItensPedidoFormSet # Já importado no topo

def novo_pedido(request):
    # Corrigido: Import desnecessário dentro da função
    if request.method == 'POST':
        form = PedidoForm(request.POST)
        # Corrigido: Usar o formset correto definido no forms.py
        from .forms import ItensPedidoFormSet 
        formset = ItensPedidoFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            pedido = form.save()
            itens = formset.save(commit=False)
            for item in itens:
                item.pedido = pedido
                item.save()
            messages.success(request, f'Pedido {pedido.id} criado com sucesso!')
            return redirect('novo_pedido')
        else:
            messages.error(request, 'Erro ao criar pedido. Verifique os campos.')
    else:
        form = PedidoForm()
        from .forms import ItensPedidoFormSet # Precisa instanciar o formset correto
        formset = ItensPedidoFormSet()

    return render(request, 'pedido_form.html', {'form': form, 'formset': formset})


def buscar_produtos(request):
    term = request.GET.get('term', '')
    # Filtra apenas produtos (não serviços) para busca
    produtos = Produto.objects.filter(nome__icontains=term, eh_servico=False)
    results = []
    for produto in produtos:
        results.append({
            'id': produto.id,
            'nome': produto.nome,
            'preco': str(produto.preco),
            # Adicionar estoque pode ser útil no frontend
            # 'estoque': produto.estoque 
        })
    return JsonResponse(results, safe=False)

def lista_pedidos(request):
    from .forms import PedidoFilterForm
    pedidos = Pedido.objects.all().order_by('-data')
    form = PedidoFilterForm(request.GET or None)

    if form.is_valid():
        id_pedido = form.cleaned_data.get('id')
        cliente = form.cleaned_data.get('cliente')
        status = form.cleaned_data.get('status')
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')

        if id_pedido:
            pedidos = pedidos.filter(id=id_pedido)
        if cliente:
            pedidos = pedidos.filter(cliente=cliente)
        if status:
            pedidos = pedidos.filter(status=status)
        if data_inicio:
            pedidos = pedidos.filter(data__date__gte=data_inicio)
        if data_fim:
            pedidos = pedidos.filter(data__date__lte=data_fim)

    context = {
        'pedidos': pedidos,
        'form': form,
    }
    return render(request, 'lista_pedidos.html', context)


# Editar pedido
def editar_pedido(request, id): # Corrigido: Usar id como PK padrão
    pedido = get_object_or_404(Pedido, id=id)
    # Precisa definir o formset para edição também
    from .forms import ItensPedidoFormSet
    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        formset = ItensPedidoFormSet(request.POST, instance=pedido)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Pedido {pedido.id} atualizado com sucesso!')
            return redirect('lista_pedidos')
        else:
            messages.error(request, 'Erro ao atualizar pedido.')
    else:
        form = PedidoForm(instance=pedido)
        formset = ItensPedidoFormSet(instance=pedido)
    return render(request, 'pedido_form.html', {'form': form, 'formset': formset, 'pedido': pedido, 'editando': True})


# Excluir pedido
def excluir_pedido(request, id): # Corrigido: Usar id como PK padrão
    pedido = get_object_or_404(Pedido, id=id)
    if request.method == 'POST':
        pedido.delete()
        messages.success(request, f'Pedido {id} excluído com sucesso!')
        return redirect('lista_pedidos')
    # Se GET, renderiza confirmação (template não fornecido, mas recomendado)
    # return render(request, 'pedido_confirmar_exclusao.html', {'pedido': pedido})
    # Excluindo direto no GET (como estava, menos seguro)
    pedido.delete()
    messages.success(request, f'Pedido {id} excluído com sucesso!')
    return redirect('lista_pedidos')

# --- View para Registrar Entrada de Estoque --- 
@login_required # Adicionar proteção de login se necessário
def registrar_entrada_estoque(request):
    if request.method == 'POST':
        form = EntradaEstoqueForm(request.POST)
        if form.is_valid():
            try:
                # Usar transaction.atomic para garantir consistência
                with transaction.atomic():
                    entrada = form.save(commit=False)
                    
                    # --- ATUALIZAÇÃO DO ESTOQUE --- 
                    produto = entrada.produto 
                    # O campo 'estoque' existe no modelo Produto
                    produto.estoque += entrada.quantidade
                    produto.save()
                    # ------------------------------
                    
                    # Agora salva a entrada de estoque
                    entrada.save()

                    messages.success(request, f"Entrada de {entrada.quantidade}x {produto.nome} registrada com sucesso! Novo estoque: {produto.estoque}")
                    # Redireciona para a mesma página para registrar nova entrada
                    return redirect('registrar_entrada_estoque') 
            except Exception as e:
                messages.error(request, f"Erro ao registrar entrada: {e}")
        else:
            messages.error(request, "Erro ao preencher o formulário. Verifique os campos.")
    else:
        form = EntradaEstoqueForm()

    context = {
        'form': form,
        'titulo_pagina': 'Registrar Nova Entrada de Estoque'
    }
    # Renderiza o template (precisa ser criado)
    # Assumindo que você criará 'entrada_estoque_form.html' no seu diretório de templates
    return render(request, 'entrada_estoque_form.html', context)

# --- Fim View Entrada de Estoque ---
