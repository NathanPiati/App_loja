from django.shortcuts import render, redirect, get_object_or_404
# Importe o novo modelo e form
from .models import Empresa, Produto, Venda, ItemVenda, Pedido, Cliente, Categoria, CondicaoPagamento, Servicos, ItensPedido, ItemServico, MovimentoFinanceiro, Empresa, EntradaEstoque, SaidaEstoque, FechamentoCaixa, Fornecedor, SaidaFinanceira, ItemPedidoCompra, PedidoCompra, LogAuditoria, Acompanhamento, ItensPedidoAcompanhamento, UsuarioEmpresa, RegraCobrancaWhatsApp, EnvioCobrancaWhatsApp
# Adicionado ProdutoFilterForm
from .forms import (ProdutoForm, ProdutoComposicaoFormSet, ItemVendaForm, VendaForm, VendasFilterForm, ItemPedidoCompraForm, PedidoCompraForm, ItemPedidoCompraFormSet,
                    CategoriaForm, PedidoForm, ItensPedidoForm, ItemServicoForm, ClienteForm, EntradaEstoqueForm, BaixaEstoqueForm, FornecedorForm, UploadXMLForm, ReviewEntradaForm,
                    ProdutoFilterForm, ItensPedidoFormSet, ItemServicoFormSet, CondicaoPagamentoForm, ServicoForm, PedidoFilterForm, EmpresaForm, CondicaoPagamentoFilterForm, AcompanhamentoForm, RegraCobrancaWhatsAppForm, MovimentoFinanceiroForm)
from .cobranca_whatsapp import (
    enviar_cobranca_cliente,
    montar_mensagem_cliente,
    movimentos_abertos_cliente,
    processar_todas_regras,
)
from django.db.models import Sum, Avg, F, Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
# import pyodbc
from django.urls import reverse_lazy
from django.forms import modelform_factory, inlineformset_factory, modelformset_factory
from django.http import JsonResponse
from django.db import transaction, connection
from django.utils import timezone
import base64
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from .serializers import (
    ProdutoSerializer,
    ServicoSerializer,
    PedidoSerializer,
    ItensPedidoSerializer,
    ItemServicoSerializer,
    FornecedorSerializer
)
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.views.generic import DetailView
from django.views.generic.edit import UpdateView
from datetime import date, timedelta, datetime
from django.utils.decorators import method_decorator
from django.views.generic import UpdateView
from django.utils.formats import number_format
from django.views.decorators.http import require_GET, require_POST
import logging
import xml.etree.ElementTree as ET
from django.forms import formset_factory
from django.contrib.contenttypes.models import ContentType
from .filters import PedidoCompraFilterForm
from django.utils.dateparse import parse_date
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
import requests
import uuid
import json
from .tenancy import (
    TENANT_SESSION_KEY,
    atribuir_empresa,
    filtrar_queryset_empresa,
    get_empresa_ativa,
    get_empresa_padrao_usuario,
)

# Configura logging para depuração
logger = logging.getLogger(__name__)

ItemVendaFormSet = modelformset_factory(
    ItemVenda,
    fields=('produto', 'quantidade', 'preco_unitario'),
    extra=1,
    can_delete=True
)


def registrar_log(request, acao, entidade='', detalhes=''):
    """Registra um evento de auditoria no banco de dados."""
    try:
        empresa = get_empresa_ativa(request)
        ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
            or request.META.get('REMOTE_ADDR')
        LogAuditoria.objects.create(
            usuario=request.user if request.user.is_authenticated else None,
            empresa=empresa,
            acao=acao,
            entidade=entidade,
            detalhes=detalhes,
            ip_address=ip or None,
        )
    except Exception:
        pass  # Nunca deixar falha de log quebrar o fluxo principal


def formatar_valor_log(valor):
    try:
        return f"{Decimal(valor):.2f}"
    except Exception:
        return str(valor)


def resumir_itens_pedido(pedido, limite=6):
    itens_produto = []
    itens_servico = []

    for item in ItensPedido.objects.filter(pedido=pedido)[:limite]:
        nome = item.descricao or (
            item.produto.nome if item.produto else f'Item {item.id}')
        itens_produto.append(f'{nome} x{item.quantidade}')

    for item in ItemServico.objects.filter(pedido=pedido)[:limite]:
        nome = item.descricao or (
            item.servico_id.nome if item.servico_id else f'Serviço {item.id}')
        itens_servico.append(f'{nome} x{item.quantidade}')

    total_produtos = ItensPedido.objects.filter(pedido=pedido).count()
    total_servicos = ItemServico.objects.filter(pedido=pedido).count()

    resumo_partes = []
    if itens_produto:
        extra = f' (+{total_produtos - limite})' if total_produtos > limite else ''
        resumo_partes.append(f'Produtos: {", ".join(itens_produto)}{extra}')
    if itens_servico:
        extra = f' (+{total_servicos - limite})' if total_servicos > limite else ''
        resumo_partes.append(f'Serviços: {", ".join(itens_servico)}{extra}')

    return ' | '.join(resumo_partes) if resumo_partes else 'Sem itens detalhados'


def snapshot_pedido_log(pedido):
    itens_produtos = [
        f"{(item.descricao or (item.produto.nome if item.produto else f'Item {item.id}'))} x{
            item.quantidade}"
        for item in ItensPedido.objects.filter(pedido=pedido).order_by('id')
    ]
    itens_servicos = [
        f"{(item.descricao or (item.servico_id.nome if item.servico_id else f'Serviço {item.id}'))} x{
            item.quantidade}"
        for item in ItemServico.objects.filter(pedido=pedido).order_by('id')
    ]

    return {
        'status': str(pedido.status or ''),
        'total': formatar_valor_log(pedido.valor_total or Decimal('0.00')),
        'produtos': itens_produtos,
        'servicos': itens_servicos,
    }


def montar_detalhes_edicao_pedido(snapshot_antes, snapshot_depois):
    mudancas = []

    if snapshot_antes['status'] != snapshot_depois['status']:
        mudancas.append(
            f"Status: {snapshot_antes['status']} -> {snapshot_depois['status']}")

    if snapshot_antes['total'] != snapshot_depois['total']:
        mudancas.append(
            f"Total: R$ {snapshot_antes['total']} -> R$ {snapshot_depois['total']}")

    if snapshot_antes['produtos'] != snapshot_depois['produtos']:
        antes = ', '.join(
            snapshot_antes['produtos']) if snapshot_antes['produtos'] else 'nenhum'
        depois = ', '.join(
            snapshot_depois['produtos']) if snapshot_depois['produtos'] else 'nenhum'
        mudancas.append(f"Produtos: {antes} -> {depois}")

    if snapshot_antes['servicos'] != snapshot_depois['servicos']:
        antes = ', '.join(
            snapshot_antes['servicos']) if snapshot_antes['servicos'] else 'nenhum'
        depois = ', '.join(
            snapshot_depois['servicos']) if snapshot_depois['servicos'] else 'nenhum'
        mudancas.append(f"Serviços: {antes} -> {depois}")

    return ' | '.join(mudancas) if mudancas else 'Sem alterações detectadas nos campos auditados'


def montar_diff_campos(snapshot_antes, snapshot_depois, rotulos):
    mudancas = []
    for campo, rotulo in rotulos.items():
        valor_antes = snapshot_antes.get(campo)
        valor_depois = snapshot_depois.get(campo)
        if valor_antes != valor_depois:
            mudancas.append(f"{rotulo}: {valor_antes} -> {valor_depois}")
    return ' | '.join(mudancas) if mudancas else 'Sem alterações detectadas'


def snapshot_cliente_log(cliente):
    return {
        'nome': cliente.nome or '',
        'telefone': cliente.telefone or '',
        'cidade': cliente.cidade or '',
        'email': cliente.email or '',
    }


def snapshot_produto_log(produto):
    return {
        'nome': produto.nome or '',
        'preco': formatar_valor_log(produto.preco or Decimal('0.00')),
        'estoque': produto.estoque_exibicao if hasattr(produto, 'estoque_exibicao') else str(produto.estoque if produto.estoque is not None else ''),
        'unidade_medida': produto.get_unidade_medida_display() if hasattr(produto, 'get_unidade_medida_display') else '',
        'categoria': str(produto.categoria) if getattr(produto, 'categoria', None) else '',
        'eh_servico': 'Sim' if produto.eh_servico else 'Não',
    }


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.none()
    serializer_class = PedidoSerializer

    def get_queryset(self):
        return filtrar_queryset_empresa(self.request, Pedido.objects.all())


class ProdutoViewSet(viewsets.ModelViewSet):
    queryset = Produto.objects.none()
    serializer_class = ProdutoSerializer

    def get_queryset(self):
        return filtrar_queryset_empresa(self.request, Produto.objects.all())


class ServicoViewSet(viewsets.ModelViewSet):
    queryset = Servicos.objects.none()
    serializer_class = ServicoSerializer

    def get_queryset(self):
        return filtrar_queryset_empresa(self.request, Servicos.objects.all())


class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.none()
    serializer_class = PedidoSerializer

    def get_queryset(self):
        return filtrar_queryset_empresa(self.request, Pedido.objects.all())


class ItensPedidoViewSet(viewsets.ModelViewSet):
    queryset = ItensPedido.objects.none()
    serializer_class = ItensPedidoSerializer

    def get_queryset(self):
        empresa = get_empresa_ativa(self.request)
        if not empresa:
            return ItensPedido.objects.none()
        return ItensPedido.objects.filter(pedido__empresa=empresa)


class ItemServicoViewSet(viewsets.ModelViewSet):
    queryset = ItemServico.objects.none()
    serializer_class = ItemServicoSerializer

    def get_queryset(self):
        empresa = get_empresa_ativa(self.request)
        if not empresa:
            return ItemServico.objects.none()
        return ItemServico.objects.filter(pedido__empresa=empresa)


@login_required
def clientes(request):
    return render(request, 'clientes.html')


@login_required
def pedidos(request):
    return render(request, 'pedidos.html')


@login_required
def produtos(request):
    return render(request, 'produtos.html')


@login_required
def cliente_novo(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            cliente = form.save(commit=False)
            atribuir_empresa(cliente, request)
            cliente.save()
            registrar_log(
                request,
                'criar',
                'Cliente',
                f'Cliente #{cliente.id} criado | Nome: {cliente.nome} | Telefone: {cliente.telefone or "-"} | Cidade: {cliente.cidade or "-"} | Email: {cliente.email or "-"}'
            )
            return redirect('clientes')  # Redireciona para a lista de clientes
    else:
        form = ClienteForm()
    return render(request, 'cliente_novo.html', {'form': form})


@login_required
def cliente_lista(request):
    clientes = filtrar_queryset_empresa(request, Cliente.objects.all())
    return render(request, 'clientes.html', {'clientes': clientes})


@login_required
def cliente_editar(request, pk):
    cliente = get_object_or_404(
        filtrar_queryset_empresa(request, Cliente.objects.all()), pk=pk
    )
    snapshot_antes = snapshot_cliente_log(cliente)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            form.save()
            cliente.refresh_from_db()
            snapshot_depois = snapshot_cliente_log(cliente)
            alteracoes = montar_diff_campos(snapshot_antes, snapshot_depois, {
                'nome': 'Nome',
                'telefone': 'Telefone',
                'cidade': 'Cidade',
                'email': 'Email',
            })
            registrar_log(
                request,
                'editar',
                'Cliente',
                f'Cliente #{cliente.id} editado | Alterações: {alteracoes}'
            )
            return redirect('clientes')
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'cliente_editar.html', {'form': form})


@login_required
def cliente_pesquisa(request):
    nome = request.GET.get('nome', '').strip()
    telefone = request.GET.get('telefone', '').strip()
    cidade = request.GET.get('cidade', '').strip()

    clientes = filtrar_queryset_empresa(request, Cliente.objects.all())

    if nome:
        clientes = clientes.filter(nome__icontains=nome)
    if telefone:
        clientes = clientes.filter(telefone__icontains=telefone)
    if cidade:
        clientes = clientes.filter(cidade__icontains=cidade)

    paginator = Paginator(clientes, 8)  # 8 itens por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'clientes': page_obj,  # o próprio page_obj já contém os itens da página
        'page_obj': page_obj,
        'total_clientes': clientes.count(),
    }

    return render(request, 'cliente_pesquisa.html', context)


@login_required
def cliente_excluir(request, pk):
    cliente = get_object_or_404(
        filtrar_queryset_empresa(request, Cliente.objects.all()), pk=pk
    )
    registrar_log(
        request,
        'excluir',
        'Cliente',
        f'Cliente #{cliente.id} excluído | Nome: {cliente.nome} | Telefone: {cliente.telefone or "-"} | Cidade: {cliente.cidade or "-"}'
    )
    cliente.delete()
    return redirect('clientes')

# def nova_venda(request):
#     if request.method == 'POST':
#         form = VendaForm(request.POST)
#         formset = ItemVendaFormSet(request.POST)

#         if form.is_valid() and formset.is_valid():
#             venda = form.save(commit=False)
#             venda.total = 0  # Inicializa
#             venda.save()

#             itens = formset.save(commit=False)
#             total = 0

#             for item in itens:
#                 item.venda = venda
#                 # Corrigido: O modelo ItemVenda não tem subtotal_valor, calcula direto
#                 subtotal_item = item.quantidade * item.preco_unitario
#                 total += subtotal_item
#                 item.save()

#             venda.total = total
#             venda.save()

#             # formset.save_m2m() # Não necessário aqui pois não há M2M no formset base

#             return redirect('lista_vendas')  # Ajuste para sua URL de listagem
#     else:
#         form = VendaForm()
#         formset = ItemVendaFormSet()

#     return render(request, 'venda_form.html', {
#         'form': form,
#         'formset': formset
#     })


# def lista_vendas(request):
#     vendas = Venda.objects.all()
#     return render(request, 'lista_vendas.html', {'vendas': vendas})


def logout_view(request):
    registrar_log(
        request,
        'logout',
        'Sessão',
        f'Usuário: {request.user.username} | Evento: logout'
    )
    logout(request)
    return redirect('login')


def licenca_invalida(request):
    return render(request, 'licenca_invalida.html')

# def login_view(request):
#     if request.method == 'POST':
#         username = request.POST['username']
#         password = request.POST['password']
#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             login(request, user)
#             return redirect('home')  # ou sua view principal
#         else:
#             messages.error(request, 'Usuário ou senha inválidos.') # Adiciona mensagem de erro
#             return render(request, 'login.html', {'form': {}})

#     return render(request, 'login.html', {'form': {}})


@csrf_exempt
def login_view(request):
    logger.info("Acessou login_view")

    if request.method == 'POST':
        logger.info("Método POST recebido")

        empresa = None
        empresa_id_sessao = request.session.get(TENANT_SESSION_KEY)
        if empresa_id_sessao:
            empresa = Empresa.objects.filter(id=empresa_id_sessao).first()
        if empresa is None:
            empresa = Empresa.objects.first()

        if not empresa:
            logger.error("Nenhuma empresa cadastrada")
            messages.error(request, "Licença não configurada.")
            return render(request, 'login.html')

        logger.info(
            "Empresa=%s | ClienteID=%s | Chave=%s | URL=%s",
            empresa.nome if hasattr(empresa, 'nome') else empresa,
            empresa.cliente_id,
            empresa.chave_licenca,
            empresa.server_url
        )

        if not empresa.cliente_id or not empresa.chave_licenca:
            logger.error("Cliente ID ou chave da licença vazios")
            messages.error(request, "Licença não configurada.")
            return render(request, 'login.html')

        licenca_valida = False
        modo_simulado = False

        try:
            logger.info("Enviando requisição ao servidor de licença")

            resp = requests.get(
                empresa.server_url,
                params={
                    "cliente": empresa.cliente_id,
                    "chave": empresa.chave_licenca
                },
                timeout=8
            )

            logger.info("Status HTTP recebido: %s", resp.status_code)
            logger.info("Resposta bruta: %s", resp.text)

            if resp.status_code == 200:
                data = resp.json()
                logger.info("JSON recebido: %s", data)

                status = data.get("status")

                if status == "ativo":
                    logger.info("Licença ATIVA")
                    licenca_valida = True
                else:
                    logger.warning("Licença INATIVA (status=%s)", status)
                    messages.error(
                        request, "🔐 Licença inválida ou desativada, entre em contato com o suporte. 🔐 ")
                    return render(request, 'login.html')
            else:
                logger.warning(
                    "Servidor respondeu com erro (%s) - entrando em modo simulado",
                    resp.status_code
                )
                modo_simulado = True

        except requests.exceptions.RequestException as e:
            logger.error(
                "Erro ao conectar ao servidor de licença: %s", str(e)
            )
            modo_simulado = True

        # 🔓 MODO SIMULADO
        if modo_simulado:
            logger.warning("Sistema iniciado em MODO SIMULADO")
            messages.warning(
                request,
                "Servidor de licença indisponível. Sistema iniciado em MODO SIMULADO."
            )
            licenca_valida = True

        # 🔐 Autenticação do usuário
        if licenca_valida:
            logger.info("Tentando autenticar usuário")

            username = request.POST.get('username')
            password = request.POST.get('password')

            logger.info("Usuário informado: %s", username)

            user = authenticate(request, username=username, password=password)

            if user:
                logger.info("Usuário autenticado com sucesso")
                login(request, user)

                if empresa and not UsuarioEmpresa.objects.filter(user=user, empresa=empresa).exists():
                    UsuarioEmpresa.objects.create(
                        user=user, empresa=empresa, ativo=True)

                empresa_ativa = get_empresa_padrao_usuario(user) or empresa
                if empresa_ativa:
                    request.session[TENANT_SESSION_KEY] = empresa_ativa.id

                registrar_log(
                    request,
                    'login',
                    'Sessão',
                    f'Usuário: {username} | Evento: login bem-sucedido'
                )
                return redirect('home')
            else:
                logger.warning("Falha na autenticação do usuário")
                messages.error(request, "Usuário ou senha inválidos.")

    else:
        logger.info("Método GET - exibindo tela de login")

    return render(request, 'login.html')


@login_required
def home(request):
    produtos = filtrar_queryset_empresa(
        request, Produto.objects.filter(eh_servico=False)
    )
    servicos = filtrar_queryset_empresa(
        request, Produto.objects.filter(eh_servico=True)
    )
    return render(request, 'home.html', {'produtos': produtos, 'servicos': servicos})

# Removido relatorio_vendas duplicado
# def relatorio_vendas(request):
#     vendas = Venda.objects.all()
#     return render(request, 'relatorio.html', {'vendas': vendas})


def produto_create(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            atribuir_empresa(produto, request)
            produto.save()
            return redirect('home')
    else:
        form = ProdutoForm()
    return render(request, 'produto_form.html', {
        'form': form,
        'composicao_formset': ProdutoComposicaoFormSet(prefix='componentes'),
        'ingredientes_catalogo': filtrar_queryset_empresa(request, Produto.objects.all()).values('id', 'valor_pago', 'unidade_medida', 'nome'),
    })


@login_required
def produto_form(request):
    form = ProdutoForm()
    composicao_formset = ProdutoComposicaoFormSet(prefix='componentes')

    busca = request.GET.get('busca')
    if busca:
        produtos = filtrar_queryset_empresa(
            request, Produto.objects.filter(nome__icontains=busca)
        )
    else:
        produtos = filtrar_queryset_empresa(request, Produto.objects.all())

    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            produto = form.save(commit=False)
            atribuir_empresa(produto, request)
            produto.save()
            # Mensagem de sucesso
            messages.success(request, 'Produto salvo com sucesso!')
            return redirect('produto_form')  # ou a URL que desejar
        else:
            # Mensagem de erro
            messages.error(
                request, 'Erro ao salvar o produto. Verifique os campos.')

    return render(request, 'produto_form.html', {
        'form': form,
        'produtos': produtos,
        'composicao_formset': composicao_formset,
        'ingredientes_catalogo': filtrar_queryset_empresa(request, Produto.objects.all()).values('id', 'valor_pago', 'unidade_medida', 'nome'),
    })


@login_required
def produto_novo(request):
    empresa_atual = get_empresa_ativa(request) or Empresa.objects.first()
    segmento_atual = getattr(
        empresa_atual, 'segmento', Empresa.SEGMENTO_AUTOPECAS)
    usa_ficha_tecnica = segmento_atual == Empresa.SEGMENTO_SORVETERIA

    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        composicao_formset = ProdutoComposicaoFormSet(
            request.POST, prefix='componentes') if usa_ficha_tecnica else ProdutoComposicaoFormSet(prefix='componentes')

        form_valido = form.is_valid()
        composicao_valida = composicao_formset.is_valid() if usa_ficha_tecnica else True

        if form_valido and composicao_valida:
            produto = form.save(commit=False)
            atribuir_empresa(produto, request)
            produto.save()
            if usa_ficha_tecnica:
                composicao_formset.instance = produto
                composicao_formset.save()
                produto.atualizar_valor_pago_por_composicao()
            produto.refresh_from_db()
            snap = snapshot_produto_log(produto)
            registrar_log(
                request,
                'criar',
                'Produto',
                f'Produto #{produto.id} criado | Nome: {snap["nome"]} | Preço: R$ {snap["preco"]} | Estoque: {snap["estoque"]} {snap["unidade_medida"]} | Serviço: {snap["eh_servico"]}'
            )
            messages.success(
                request, f'Produto {produto.id} cadastrado com sucesso!')
            return redirect('produto_novo')
        else:
            erros_form = []
            for campo, erros in form.errors.items():
                nome_campo = form.fields.get(
                    campo).label if campo in form.fields else campo
                for erro in erros:
                    erros_form.append(f'{nome_campo}: {erro}')
            if usa_ficha_tecnica:
                for erro in composicao_formset.non_form_errors():
                    erros_form.append(f'Ficha técnica: {erro}')
            messages.error(
                request,
                'Erro ao cadastrar produto. ' +
                (' | '.join(erros_form)
                 if erros_form else 'Verifique os campos destacados.')
            )
    else:
        form = ProdutoForm()
        composicao_formset = ProdutoComposicaoFormSet(prefix='componentes')

    return render(request, 'produto_form.html', {
        'form': form,
        'composicao_formset': composicao_formset,
        'ingredientes_catalogo': filtrar_queryset_empresa(request, Produto.objects.all()).values('id', 'valor_pago', 'unidade_medida', 'nome'),
    })


@login_required
def produto_editar(request, id):
    empresa_atual = get_empresa_ativa(request) or Empresa.objects.first()
    segmento_atual = getattr(
        empresa_atual, 'segmento', Empresa.SEGMENTO_AUTOPECAS)
    usa_ficha_tecnica = segmento_atual == Empresa.SEGMENTO_SORVETERIA

    produto = get_object_or_404(
        filtrar_queryset_empresa(request, Produto.objects.all()), id=id
    )
    snapshot_antes = snapshot_produto_log(produto)
    form = ProdutoForm(request.POST or None, instance=produto)
    composicao_formset = ProdutoComposicaoFormSet(
        request.POST or None, instance=produto, prefix='componentes')
    form_valido = form.is_valid()
    composicao_valida = composicao_formset.is_valid() if usa_ficha_tecnica else True

    if form_valido and composicao_valida:
        form.save()
        if usa_ficha_tecnica:
            composicao_formset.save()
            produto.atualizar_valor_pago_por_composicao()
        produto.refresh_from_db()
        snapshot_depois = snapshot_produto_log(produto)
        alteracoes = montar_diff_campos(snapshot_antes, snapshot_depois, {
            'nome': 'Nome',
            'preco': 'Preço',
            'unidade_medida': 'Unidade',
            'categoria': 'Categoria',
            'eh_servico': 'Serviço',
        })
        registrar_log(
            request,
            'editar',
            'Produto',
            f'Produto #{produto.id} editado | Alterações: {alteracoes}'
        )
        messages.success(
            request, f'Produto {produto.id} atualizado com sucesso!')
        # Mantém na tela de edição para exibir feedback imediato.
        return redirect('produto_editar', id=produto.id)

    if request.method == 'POST':
        erros_form = []
        for campo, erros in form.errors.items():
            nome_campo = form.fields.get(
                campo).label if campo in form.fields else campo
            for erro in erros:
                erros_form.append(f'{nome_campo}: {erro}')
        if usa_ficha_tecnica:
            for erro in composicao_formset.non_form_errors():
                erros_form.append(f'Ficha técnica: {erro}')

        messages.error(
            request,
            'Erro ao atualizar produto. ' +
            (' | '.join(erros_form) if erros_form else 'Verifique os campos destacados.')
        )

    # Se GET, renderiza o formulário de edição (pode ser um template separado ou o mesmo)
    # Passando 'editando': True pode ajudar a diferenciar no template
    return render(request, 'produto_form.html', {
        'form': form,
        'editando': True,
        'composicao_formset': composicao_formset,
        'ingredientes_catalogo': Produto.objects.values('id', 'valor_pago', 'unidade_medida', 'nome'),
    })


@login_required
def produto_excluir(request, id):
    produto = get_object_or_404(Produto, id=id)
    nome_produto = produto.nome
    snap = snapshot_produto_log(produto)
    if request.method == 'POST':  # Confirmação via POST é mais segura
        produto.delete()
        registrar_log(
            request,
            'excluir',
            'Produto',
            f'Produto #{id} excluído | Nome: {nome_produto} | Preço: R$ {snap["preco"]} | Estoque: {snap["estoque"]}'
        )
        messages.success(request, 'Produto excluído com sucesso!')
        # Redireciona para a lista após excluir
        return redirect('produto_lista')
    # Se GET, pode mostrar uma página de confirmação (não implementado aqui)
    # Para simplificar, exclui direto no GET (menos seguro)
    produto.delete()
    registrar_log(
        request,
        'excluir',
        'Produto',
        f'Produto #{id} excluído | Nome: {nome_produto} | Preço: R$ {snap["preco"]} | Estoque: {snap["estoque"]}'
    )
    messages.success(request, 'Produto excluído com sucesso!')
    return redirect('produto_lista')  # Redireciona para a lista após excluir


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
            messages.error(
                request, 'Erro ao registrar a venda. Verifique os itens.')
    else:
        form = VendaForm()
        formset = ItemVendaFormSet()
    return render(request, 'venda_form.html', {'form': form, 'formset': formset})


@login_required
def relatorio_vendas(request):
    form = VendasFilterForm(request.GET or None)
    vendas = Venda.objects.prefetch_related(
        'itens__produto').order_by('-datavenda')

    if form.is_valid():
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')
        total_min = form.cleaned_data.get('total_min')
        total_max = form.cleaned_data.get('total_max')

        if data_inicio:
            vendas = vendas.filter(datavenda__date__gte=data_inicio)
        if data_fim:
            vendas = vendas.filter(datavenda__date__lte=data_fim)
        if total_min is not None:
            vendas = vendas.filter(valortotal__gte=total_min)
        if total_max is not None:
            vendas = vendas.filter(valortotal__lte=total_max)

    total_geral = vendas.aggregate(Sum('valortotal'))['valortotal__sum'] or 0
    quantidade_vendas = vendas.count()

    context = {
        'form': form,
        'vendas': vendas,
        'total_geral': total_geral,
        'quantidade_vendas': quantidade_vendas,
    }
    return render(request, 'relatorio.html', context)


@login_required
def imprimir_relatorio_vendas(request):
    form = VendasFilterForm(request.GET or None)
    vendas = Venda.objects.prefetch_related(
        'itens__produto').order_by('-datavenda')

    if form.is_valid():
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')
        total_min = form.cleaned_data.get('total_min')
        total_max = form.cleaned_data.get('total_max')

        if data_inicio:
            vendas = vendas.filter(datavenda__date__gte=data_inicio)
        if data_fim:
            vendas = vendas.filter(datavenda__date__lte=data_fim)
        if total_min is not None:
            vendas = vendas.filter(valortotal__gte=total_min)
        if total_max is not None:
            vendas = vendas.filter(valortotal__lte=total_max)

    total_geral = vendas.aggregate(Sum('valortotal'))['valortotal__sum'] or 0
    quantidade_vendas = vendas.count()
    data_atual = timezone.now().astimezone().strftime('%d/%m/%Y %H:%M')

    context = {
        'vendas': vendas,
        'total_geral': total_geral,
        'quantidade_vendas': quantidade_vendas,
        'data_atual': data_atual,
        'data_inicio': request.GET.get('data_inicio', ''),
        'data_fim': request.GET.get('data_fim', ''),
    }
    return render(request, 'imprimir_relatorio_vendas.html', context)

# Removido relatorio_view duplicado
# def relatorio_view(request):
#     ...


@login_required
def categoria_create(request):
    if request.method == 'POST':
        form = CategoriaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Categoria criada com sucesso!')
            # Ou qualquer outra view que tenha
            return redirect('categoria_create')
        else:
            messages.error(request, 'Erro ao criar categoria.')
    else:
        form = CategoriaForm()
    return render(request, 'categoria_form.html', {'form': form})

# +++ View de Lista de Produtos Modificada (v2) +++


@login_required
def produto_lista(request):
    produtos_list = Produto.objects.none()
    busca_realizada = False

    categorias = Categoria.objects.all()
    filter_form = ProdutoFilterForm(request.GET or None)

    if filter_form.is_bound and filter_form.is_valid():
        busca_realizada = True
        produtos_list = Produto.objects.filter(eh_servico=False).order_by('id')

        produto_id = filter_form.cleaned_data.get('id')
        nome = filter_form.cleaned_data.get('nome')
        marca = filter_form.cleaned_data.get('marca')
        categoria = filter_form.cleaned_data.get('categoria')
        num_fabricante = filter_form.cleaned_data.get('num_fabricante')
        num_original = filter_form.cleaned_data.get('num_original')

        if produto_id:
            produtos_list = produtos_list.filter(id=produto_id)
        if nome:
            produtos_list = produtos_list.filter(nome__icontains=nome)
        if marca:
            produtos_list = produtos_list.filter(marca__icontains=marca)
        if categoria:
            produtos_list = produtos_list.filter(categoria=categoria)
        if num_fabricante:
            produtos_list = produtos_list.filter(
                num_fabricante__icontains=num_fabricante)
        if num_original:
            produtos_list = produtos_list.filter(
                num_original__icontains=num_original)

    # Paginação
    paginator = Paginator(produtos_list, 10)  # 10 produtos por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'produtos': page_obj,
        'filter_form': filter_form,
        'categorias': categorias,
        'busca_realizada': busca_realizada,
        'total_produtos': produtos_list.count(),
        'page_obj': page_obj,
    }
    return render(request, 'produto_lista.html', context)
# +++ Fim View Modificada (v2) +++


@login_required
def nova_categoria(request):
    form = CategoriaForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, 'Categoria cadastrada com sucesso!✅')
        return redirect('nova_categoria')
    return render(request, 'nova_categoria.html', {'form': form})


@login_required
def pesquisar_categoria(request):
    categorias = None  # não mostra nada inicialmente

    if 'q' in request.GET:
        q = request.GET.get('q', '').strip()
        if q:
            categorias = Categoria.objects.filter(nome__icontains=q)
        else:
            categorias = Categoria.objects.all()

    return render(request, 'pesquisar_categoria.html', {'categorias': categorias})


@login_required
def editar_categoria(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    form = CategoriaForm(request.POST or None, instance=categoria)

    if form.is_valid():
        form.save()
        messages.success(request, 'Categoria atualizada com sucesso!')
        # ou 'nova_categoria', se preferir
        return redirect('pesquisar_categoria')

    return render(request, 'nova_categoria.html', {'form': form, 'editando': True})


@login_required
def excluir_categoria(request, id):
    categoria = get_object_or_404(Categoria, id=id)
    if request.method == 'POST':  # Adicionado confirmação POST
        categoria.delete()
        messages.success(request, 'Categoria excluída com sucesso!')
        return redirect('pesquisar_categoria')
    # Se GET, pode mostrar confirmação ou excluir direto (como estava)
    categoria.delete()
    messages.success(request, 'Categoria excluída com sucesso!')
    # ou o nome da URL onde lista as categorias
    return redirect('pesquisar_categoria')


# --- Pedidos ---
# from .forms import PedidoForm, ItensPedidoFormSet # Já importado no topo
# Formulário do Pedido
PedidoForm = modelform_factory(Pedido, fields=[
                               'cliente', 'condicao_pagamento', 'observacoes', 'status', 'desconto_percentual'])

# Formulários dos Itens (Produtos e Serviços)
ItensPedidoFormSet = inlineformset_factory(Pedido, ItensPedido, fields=[
                                           'produto', 'descricao', 'quantidade', 'preco_unitario'], extra=1, can_delete=True)
ItemServicoFormSet = inlineformset_factory(Pedido, ItemServico, fields=[
                                           'descricao', 'quantidade', 'preco_unitario'], extra=1, can_delete=True)


@login_required
@transaction.atomic
def criar_pedido(request):
    if request.method == 'POST':
        try:
            cliente_id = request.POST.get('cliente')
            cliente = Cliente.objects.get(id=cliente_id)

            pedido = Pedido.objects.create(
                empresa=get_empresa_ativa(request),
                cliente=cliente,
                condicao_pagamento_id=request.POST.get('condicao_pagamento'),
                status=request.POST.get('status', 'pendente'),
                juros=float(request.POST.get(
                    'juros', '0.00').replace(',', '.')),
                desconto_percentual=float(request.POST.get(
                    'desconto_percentual', '0.00').replace(',', '.')),
                observacoes=request.POST.get('observacoes', '')
            )

            # Processar Produtos
            produtos = request.POST.getlist('produtos')
            quantidades = request.POST.getlist('quantidades')
            precos = request.POST.getlist('precos_unitarios')

            for i in range(len(produtos)):
                if not produtos[i]:
                    continue  # Pula vazios

                produto = Produto.objects.get(id=produtos[i])
                quantidade = float(str(quantidades[i]).replace(',', '.'))
                preco_unitario = float(precos[i].replace(',', '.'))

                if produto.unidade_medida == Produto.UNIDADE and quantidade != int(quantidade):
                    messages.error(
                        request, f"O produto {produto.nome} usa unidade (un) e só aceita quantidade inteira.")
                    transaction.set_rollback(True)
                    return redirect('criar_pedido')

                if produto.estoque < quantidade:
                    messages.error(
                        request, f"Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque_exibicao}")
                    transaction.set_rollback(True)
                    return redirect('criar_pedido')

                ItensPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    descricao=produto.nome,
                    quantidade=quantidade,
                    preco_unitario=preco_unitario
                )

                produto.estoque -= quantidade
                produto.save()

            # Processar Serviços
            servicos = request.POST.getlist('servicos')
            quantidades_servico = request.POST.getlist('quantidades_servicos')
            precos_servico = request.POST.getlist('precos_servicos')

            for i in range(len(servicos)):
                if not servicos[i]:
                    continue  # Pula vazios

                servico = Servicos.objects.get(id=servicos[i])
                quantidade = float(quantidades_servico[i])
                preco_unitario = float(precos_servico[i].replace(',', '.'))

                ItemServico.objects.create(
                    pedido=pedido,
                    servico=servico,
                    descricao=servico.nome,
                    quantidade=quantidade,
                    preco_unitario=preco_unitario
                )

            resumo_itens = resumir_itens_pedido(pedido)
            registrar_log(
                request,
                'pedido',
                'Pedido de Venda',
                f'Pedido #{pedido.id} | Cliente: {cliente.nome} | Status: {pedido.status} | Itens: {resumo_itens}'
            )
            messages.success(request, 'Pedido criado com sucesso!')
            return redirect('listar_pedidos')

        except Exception as e:
            transaction.set_rollback(True)
            messages.error(request, f'Erro ao criar pedido: {str(e)}')
            return redirect('criar_pedido')

    clientes = Cliente.objects.all()
    produtos = Produto.objects.all()
    servicos = Servicos.objects.all()
    condicoes_pagamento = CondicaoPagamento.objects.all()

    return render(request, 'criar_pedido.html', {
        'clientes': clientes,
        'produtos': produtos,
        'servicos': servicos,
        'condicoes_pagamento': condicoes_pagamento
    })

# ✅ Endpoint que retorna os produtos em JSON (usado no frontend para preencher automaticamente)


def produtos_json(request):
    produtos = Produto.objects.all().values('id', 'nome', 'preco')
    data = {str(p['id']): {'descricao': p['nome'],
                           'preco': float(p['preco'])} for p in produtos}
    return JsonResponse(data)


def clientes_json(request):
    query = request.GET.get('q', '').strip()
    clientes = Cliente.objects.filter(
        Q(id__icontains=query) |
        Q(nome__icontains=query) |
        Q(telefone__icontains=query)
    ).values('id', 'nome', 'telefone')[:10]  # Limite para performance
    data = {str(c['id']): {'nome': c['nome'],
                           'telefone': c['telefone'] or ''} for c in clientes}
    return JsonResponse(data)


@login_required
@csrf_exempt
def salvar_pedido(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            cliente_id = data['cliente']
            cond_pag_id = data['condicao_pagamento']
            observacoes = data.get('observacoes', '')
            produtos = data.get('produtos', [])
            servicos = data.get('servicos', [])
            juros = Decimal(str(data.get('juros', '0.00').replace(',', '.')))
            desconto_percentual = Decimal(
                str(data.get('desconto_percentual', '0.00').replace(',', '.')))

            if juros < 0 or juros > 100:
                return JsonResponse({'status': 'error', 'msg': 'O percentual de juros deve estar entre 0 e 100.'}, status=400)
            if desconto_percentual < 0 or desconto_percentual > 100:
                return JsonResponse({'status': 'error', 'msg': 'O desconto percentual deve estar entre 0 e 100.'}, status=400)

            cliente = Cliente.objects.get(id=cliente_id)
            cond_pag = CondicaoPagamento.objects.get(id=cond_pag_id)

            # Calcula subtotal
            subtotal = Decimal('0.00')
            for p in produtos:
                quantidade = Decimal(str(p['quantidade']))
                preco_unitario = Decimal(
                    str(p['preco_unitario']).replace(',', '.'))
                subtotal += quantidade * preco_unitario
            for s in servicos:
                quantidade = Decimal(str(s['quantidade']))
                preco_unitario = Decimal(
                    str(s['preco_unitario']).replace(',', '.'))
                subtotal += quantidade * preco_unitario

            # Aplica juros
            valor_juros = (subtotal * juros) / Decimal('100')
            total_com_juros = subtotal + valor_juros

            # Aplica desconto
            valor_desconto = (total_com_juros *
                              desconto_percentual) / Decimal('100')
            total_final = total_com_juros - valor_desconto

            pedido = Pedido.objects.create(
                empresa=get_empresa_ativa(request),
                cliente=cliente,
                condicao_pagamento=cond_pag,
                observacoes=observacoes,
                valor_total=total_final,
                desconto_percentual=desconto_percentual,
                desconto=valor_desconto,
                juros=juros
            )

            # Salva itens de produto
            for p in produtos:
                produto = Produto.objects.get(id=p['id'])
                quantidade = int(p['quantidade'])
                if produto.estoque < quantidade:
                    return JsonResponse({'status': 'error', 'msg': f'Estoque insuficiente para {produto.nome}'}, status=400)
                preco_unitario = Decimal(
                    str(p['preco_unitario']).replace(',', '.'))
                subtotal_item = quantidade * preco_unitario
                ItensPedido.objects.create(
                    pedido=pedido,
                    produto=produto,
                    descricao=produto.nome,
                    num_fabricante=produto.num_fabricante or '',
                    num_original=produto.num_original or '',
                    quantidade=quantidade,
                    preco_unitario=preco_unitario
                )
                produto.estoque -= quantidade
                produto.save()

            # Salva itens de serviço
            for s in servicos:
                descricao = s['descricao']
                quantidade = int(s['quantidade'])
                preco_unitario = Decimal(
                    str(s['preco_unitario']).replace(',', '.'))
                subtotal_item = quantidade * preco_unitario
                ItemServico.objects.create(
                    pedido=pedido,
                    descricao=descricao,
                    quantidade=quantidade,
                    preco_unitario=preco_unitario
                )

            resumo_produtos = ', '.join([
                f"{Produto.objects.get(id=p['id']).nome} x{p['quantidade']}"
                for p in produtos if p.get('id')
            ]) or 'nenhum'
            resumo_servicos = ', '.join([
                f"{s.get('descricao', 'Serviço')} x{s.get('quantidade', 0)}"
                for s in servicos
            ]) or 'nenhum'
            registrar_log(
                request,
                'pedido',
                'Pedido de Venda',
                f'Pedido #{pedido.id} | Cliente: {cliente.nome} | Total: R$ {formatar_valor_log(total_final)} | Produtos: {resumo_produtos} | Serviços: {resumo_servicos}'
            )
            return JsonResponse({'status': 'success', 'msg': 'Pedido salvo com sucesso'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)

    return JsonResponse({'status': 'error', 'msg': 'Método não permitido'}, status=405)


@login_required
def novo_pedido(request):
    data_atual = timezone.localtime().strftime('%d/%m/%Y %H:%M')

    if request.method == 'POST':
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save(commit=False)

            # Calcula subtotal
            subtotal = 0
            produtos_ids = request.POST.getlist('produtos')
            quantidades = request.POST.getlist('quantidades')
            precos_unitarios = request.POST.getlist('precos_unitarios')
            servicos_ids = request.POST.getlist('servicos')
            quantidades_servicos = request.POST.getlist('quantidades_servicos')
            precos_servicos = request.POST.getlist('precos_servicos')
            juros = float(request.POST.get('juros', '0').replace(',', '.'))

            itens = []
            for prod_id, qtd, preco in zip(produtos_ids, quantidades, precos_unitarios):
                if prod_id and qtd and preco:
                    try:
                        produto = Produto.objects.get(id=prod_id)
                        quantidade = int(qtd)
                        preco_unitario = float(preco.replace(',', '.'))
                        subtotal += quantidade * preco_unitario
                        itens.append({
                            'produto': produto,
                            'quantidade': quantidade,
                            'preco_unitario': preco_unitario,
                            'num_fabricante': produto.num_fabricante,
                            'num_original': produto.num_original
                        })
                    except Produto.DoesNotExist:
                        messages.error(
                            request, f'Produto com ID {prod_id} não encontrado.')
                        return redirect('novo_pedido')
                    except ValueError:
                        messages.error(
                            request, f'Valores inválidos para o item com ID {prod_id}.')
                        return redirect('novo_pedido')

            for servico_id, qtd, preco in zip(servicos_ids, quantidades_servicos, precos_servicos):
                if servico_id and qtd and preco:
                    try:
                        quantidade = int(qtd)
                        preco_unitario = float(preco.replace(',', '.'))
                        subtotal += quantidade * preco_unitario
                        itens.append({
                            'servico_id': servico_id,
                            'quantidade': quantidade,
                            'preco_unitario': preco_unitario,
                            'descricao': f"Serviço ID {servico_id}"
                        })
                    except ValueError:
                        messages.error(
                            request, f'Valores inválidos para o serviço com ID {servico_id}.')
                        return redirect('novo_pedido')

            # Aplica juros
            if juros < 0 or juros > 100:
                messages.error(
                    request, 'O percentual de juros deve estar entre 0 e 100.')
                return redirect('novo_pedido')
            valor_juros = (subtotal * juros) / 100
            total_com_juros = subtotal + valor_juros

            # Aplica desconto
            desconto_percentual = float(request.POST.get(
                'desconto_percentual', '0').replace(',', '.'))
            if desconto_percentual < 0 or desconto_percentual > 100:
                messages.error(
                    request, 'O desconto percentual deve estar entre 0 e 100.')
                return redirect('novo_pedido')
            valor_desconto = (total_com_juros * desconto_percentual) / 100
            total_final = total_com_juros - valor_desconto

            # Atualiza no objeto Pedido
            pedido.valor_total = total_final
            pedido.desconto_percentual = desconto_percentual
            pedido.desconto = valor_desconto
            pedido.save()

            # Salva os itens e atualiza o estoque
            for item in itens:
                if 'produto' in item:
                    produto = item['produto']
                    if not produto.eh_servico:
                        if produto.estoque >= item['quantidade']:
                            produto.estoque -= item['quantidade']
                            produto.save()
                        else:
                            messages.error(
                                request,
                                f'Estoque insuficiente para {produto.nome}. '
                                f'Disponível: {produto.estoque}, Solicitado: {item["quantidade"]}'
                            )
                            pedido.delete()
                            return redirect('novo_pedido')

                    ItensPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        quantidade=item['quantidade'],
                        preco_unitario=item['preco_unitario'],
                        num_fabricante=item['num_fabricante'],
                        num_original=item['num_original']
                    )
                elif 'servico_id' in item:
                    ItensPedido.objects.create(
                        pedido=pedido,
                        servico_id=item['servico_id'],
                        quantidade=item['quantidade'],
                        preco_unitario=item['preco_unitario'],
                        descricao=item['descricao']
                    )

            resumo_itens = resumir_itens_pedido(pedido)
            registrar_log(
                request,
                'pedido',
                'Pedido de Venda',
                f'Pedido #{pedido.id} | Cliente: {pedido.cliente} | Status: {pedido.status} | Total: R$ {formatar_valor_log(total_final)} | Itens: {resumo_itens}'
            )
            messages.success(
                request, f'Pedido {pedido.id} criado com sucesso!')
            return redirect('novo_pedido')
        else:
            messages.error(
                request, 'Erro ao salvar o pedido. Verifique os campos.')
            print("Form errors:", form.errors)
    else:
        form = PedidoForm()
        formset = ItensPedidoFormSet()

    clientes = Cliente.objects.all()
    condicoes_pagamento = CondicaoPagamento.objects.all()
    produtos = Produto.objects.filter(eh_servico=False)

    return render(
        request,
        'pedido_form.html',
        {
            'form': form,
            'formset': formset,
            'data_atual': data_atual,
            'clientes': clientes,
            'condicoes_pagamento': condicoes_pagamento,
            'produtos': produtos
        }
    )


@login_required
def lista_pedidos(request):
    from .forms import PedidoFilterForm
    pedidos = Pedido.objects.all().order_by('-data')
    form = PedidoFilterForm(request.GET or None)

    if form.is_valid():
        id_pedido = form.cleaned_data.get('id')
        cliente = form.cleaned_data.get('cliente')
        condicao_pagamento = form.cleaned_data.get('condicao_pagamento')
        status = form.cleaned_data.get('status')
        data_inicio = form.cleaned_data.get('data_inicio')
        data_fim = form.cleaned_data.get('data_fim')

        if id_pedido:
            pedidos = pedidos.filter(id=id_pedido)
        if cliente:
            pedidos = pedidos.filter(cliente=cliente)
        if condicao_pagamento:
            pedidos = pedidos.filter(condicao_pagamento=condicao_pagamento)
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


@login_required
def listar_pedidos(request):
    pedidos = Pedido.objects.none()  # Começa vazio
    clientes = Cliente.objects.all()

    form = PedidoFilterForm(request.GET or None)

    if form.is_valid():
        pedidos = Pedido.objects.all().order_by('-id')

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

    quantidade_registros = pedidos.count()

    # 🔥 Paginação
    paginator = Paginator(pedidos, 10)  # 10 por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 🔥 Totais
    total_geral = pedidos.aggregate(
        total_valor=Sum('valor_total'),
        total_desconto=Avg('desconto_percentual')
    )

    return render(request, 'lista_pedidos.html', {
        'pedidos': page_obj,
        'clientes': clientes,
        'page_obj': page_obj,
        'total_geral': total_geral,
        'quantidade_registros': quantidade_registros,
        'form': form,  # 👉 Passa o form pra template
    })


# Editar pedido
@method_decorator(login_required, name='dispatch')
@method_decorator(transaction.atomic, name='dispatch')
@login_required
@transaction.atomic
def PedidoEditView(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)

    ItensPedidoFormSet = inlineformset_factory(
        Pedido, ItensPedido, form=ItensPedidoForm, fields=('produto', 'quantidade', 'preco_unitario'), extra=0, can_delete=True
    )
    ItemServicoFormSet = inlineformset_factory(
        Pedido, ItemServico, form=ItemServicoForm, fields=('servico_id', 'quantidade', 'preco_unitario'), extra=0, can_delete=True
    )

    clientes = Cliente.objects.all()
    condicoes_pagamento = CondicaoPagamento.objects.all()
    produtos = Produto.objects.all()
    servicos = Servicos.objects.all()

    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        formset_itens = ItensPedidoFormSet(
            request.POST, instance=pedido, prefix='itens')
        formset_servicos = ItemServicoFormSet(
            request.POST, instance=pedido, prefix='servicos')

        if form.is_valid() and formset_itens.is_valid() and formset_servicos.is_valid():
            # Salvar pedido e formsets
            pedido = form.save(commit=False)
            desconto_percentual = form.cleaned_data.get(
                'desconto_percentual', Decimal('0.00'))
            pedido.desconto_percentual = desconto_percentual
            pedido.save()

            # Salvar itens e serviços
            formset_itens.save()
            formset_servicos.save()

            # Calcular totais
            subtotal_itens = sum(
                item.quantidade * item.preco_unitario for item in ItensPedido.objects.filter(pedido=pedido))
            subtotal_servicos = sum(
                item.quantidade * item.preco_unitario for item in ItemServico.objects.filter(pedido=pedido))
            valor_total = subtotal_itens + subtotal_servicos
            desconto_valor = (
                valor_total * desconto_percentual) / Decimal('100')
            pedido.valor_total = valor_total - desconto_valor
            pedido.desconto = desconto_valor
            pedido.save()

            messages.success(
                request, f'Pedido {pedido_id} atualizado com sucesso!')
            return redirect('lista_pedidos')
        else:
            messages.error(request, 'Erro nos dados do formulário.')
            print("Form errors:", form.errors)
            print("Formset itens errors:", formset_itens.errors)
            print("Formset servicos errors:", formset_servicos.errors)
    else:
        form = PedidoForm(instance=pedido)
        formset_itens = ItensPedidoFormSet(instance=pedido, prefix='itens')
        formset_servicos = ItemServicoFormSet(
            instance=pedido, prefix='servicos')

    formatted_itens = [
        {
            'id': item.produto.id,
            'nome': item.produto.nome,
            'quantidade': item.quantidade,
            'preco_unitario': number_format(item.preco_unitario or item.produto.preco, decimal_pos=2, force_grouping=True),
            'subtotal': number_format(item.quantidade * item.preco_unitario, decimal_pos=2, force_grouping=True),
        } for item in ItensPedido.objects.filter(pedido=pedido)
    ]
    formatted_itens_servicos = [
        {
            'id': servico.servico_id.id,
            'nome': servico.servico_id.nome,
            'quantidade': servico.quantidade,
            'preco_unitario': number_format(servico.preco_unitario or servico.servico_id.preco, decimal_pos=2, force_grouping=True),
            'total': number_format(servico.quantidade * servico.preco_unitario, decimal_pos=2, force_grouping=True),
        } for servico in ItemServico.objects.filter(pedido=pedido)
    ]

    desconto_valor = (pedido.valor_total * pedido.desconto_percentual) / \
        Decimal('100') if pedido.desconto_percentual else Decimal('0.00')
    desconto = number_format(
        desconto_valor, decimal_pos=2, force_grouping=True)
    valor_total = number_format(pedido.valor_total or Decimal(
        '0.00'), decimal_pos=2, force_grouping=True)

    return render(request, 'pedido_edit.html', {
        'pedido': pedido,
        'form': form,
        'formset_itens': formset_itens,
        'formset_servicos': formset_servicos,
        'clientes': clientes,
        'condicoes_pagamento': condicoes_pagamento,
        'produtos': produtos,
        'servicos': servicos,
        'itens': formatted_itens,
        'itens_servicos': formatted_itens_servicos,
        'desconto': desconto,
        'valor_total': valor_total,
    })


@login_required
@transaction.atomic
def PedidoUpdateView(request, pedido_id):
    print("Acessando PedidoUpdateView com método:",
          request.method, "e URL:", request.path)
    if request.method != 'POST':
        messages.error(
            request, 'Método não permitido. Use POST para atualizar.')
        return redirect('lista_pedidos')

    pedido = get_object_or_404(Pedido, id=pedido_id)
    snapshot_antes = snapshot_pedido_log(pedido)
    post_data = request.POST
    print("POST data recebido:", dict(post_data))

    try:
        # Extrair dados do pedido
        cliente_id = post_data.get('cliente')
        condicao_pagamento_id = post_data.get('condicao_pagamento')
        status = post_data.get('status')
        desconto_percentual = post_data.get(
            'desconto_percentual', '0.00').replace(',', '.')
        observacoes = post_data.get('observacoes', '')

        # Validar dados obrigatórios
        if not cliente_id or not status:
            messages.error(request, 'Cliente e status são obrigatórios.')
            return redirect('PedidoEditView', pedido_id=pedido_id)

        # Converter desconto_percentual
        try:
            desconto_percentual = Decimal(desconto_percentual)
        except (ValueError, InvalidOperation):
            messages.error(request, 'Desconto percentual inválido.')
            return redirect('PedidoEditView', pedido_id=pedido_id)

        # Atualizar pedido
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE loja_web_pedido
                SET cliente_id = %s,
                    condicao_pagamento_id = %s,
                    status = %s,
                    desconto_percentual = %s,
                    observacoes = %s
                WHERE id = %s
            """, [cliente_id, condicao_pagamento_id or None, status, desconto_percentual, observacoes, pedido_id])
            print("Atualizado pedido:", {
                'id': pedido_id,
                'cliente_id': cliente_id,
                'condicao_pagamento_id': condicao_pagamento_id,
                'status': status,
                'desconto_percentual': desconto_percentual,
                'observacoes': observacoes
            })

        # Processar itens
        itens_ids_existentes = set()
        for key in post_data:
            if key.startswith('itens-') and '-produto' in key:
                index = key.split('-')[1]
                item_id = post_data.get(f'itens-{index}-id')
                produto_id = post_data.get(f'itens-{index}-produto')
                quantidade = post_data.get(f'itens-{index}-quantidade')
                preco_unitario_str = post_data.get(
                    f'itens-{index}-preco_unitario', '').replace('.', '').replace(',', '.')
                delete = post_data.get(f'itens-{index}-DELETE')

                if not produto_id or not quantidade:
                    messages.error(
                        request, f'Item {index}: Produto e quantidade são obrigatórios.')
                    return redirect('PedidoEditView', pedido_id=pedido_id)

                try:
                    quantidade = int(quantidade)
                    preco_unitario = Decimal(
                        preco_unitario_str) if preco_unitario_str else Decimal('0.00')
                    print(
                        f"Item {index}: preco_unitario_str={preco_unitario_str}, preco_unitario={preco_unitario}")
                except (ValueError, InvalidOperation):
                    messages.error(
                        request, f'Item {index}: Quantidade ou preço unitário inválido.')
                    return redirect('PedidoEditView', pedido_id=pedido_id)

                with connection.cursor() as cursor:
                    if delete == 'on' and item_id:
                        cursor.execute(
                            "DELETE FROM loja_web_itenspedido WHERE id = %s", [item_id])
                        print(f"Deletado item id: {item_id}")
                    else:
                        if item_id:
                            cursor.execute("""
                                UPDATE loja_web_itenspedido
                                SET produto_id = %s,
                                    quantidade = %s,
                                    preco_unitario = %s,
                                    descricao = (SELECT nome FROM loja_web_produto WHERE id = %s)
                                WHERE id = %s
                            """, [produto_id, quantidade, preco_unitario, produto_id, item_id])
                            print(
                                f"Atualizado item id: {item_id}, produto_id: {produto_id}, quantidade: {quantidade}, preco_unitario: {preco_unitario}")
                            itens_ids_existentes.add(item_id)
                        else:
                            cursor.execute("""
                                INSERT INTO loja_web_itenspedido (pedido_id, produto_id, quantidade, preco_unitario, descricao)
                                VALUES (%s, %s, %s, %s, (SELECT nome FROM loja_web_produto WHERE id = %s))
                                RETURNING id
                            """, [pedido_id, produto_id, quantidade, preco_unitario, produto_id])
                            item_id = cursor.fetchone()[0]
                            print(
                                f"Inserido item id: {item_id}, produto_id: {produto_id}, quantidade: {quantidade}, preco_unitario: {preco_unitario}")
                            itens_ids_existentes.add(str(item_id))

        # Deletar itens não presentes no POST
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM loja_web_itenspedido WHERE pedido_id = %s", [pedido_id])
            itens_atuais = {str(row[0]) for row in cursor.fetchall()}
            itens_a_deletar = itens_atuais - itens_ids_existentes
            for item_id in itens_a_deletar:
                cursor.execute(
                    "DELETE FROM loja_web_itenspedido WHERE id = %s", [item_id])
                print(f"Deletado item id: {item_id} (não mais no POST)")

        # Processar serviços
        servicos_ids_existentes = set()
        for key in post_data:
            if key.startswith('servicos-') and '-servico_id' in key:
                index = key.split('-')[1]
                item_id = post_data.get(f'servicos-{index}-id')
                servico_id = post_data.get(f'servicos-{index}-servico_id')
                quantidade = post_data.get(f'servicos-{index}-quantidade')
                preco_unitario_str = post_data.get(
                    f'servicos-{index}-preco_unitario', '').replace('.', '').replace(',', '.')
                delete = post_data.get(f'servicos-{index}-DELETE')

                if not servico_id or not quantidade:
                    messages.error(
                        request, f'Serviço {index}: Serviço e quantidade são obrigatórios.')
                    return redirect('PedidoEditView', pedido_id=pedido_id)

                try:
                    quantidade = int(quantidade)
                    preco_unitario = Decimal(
                        preco_unitario_str) if preco_unitario_str else Decimal('0.00')
                    print(
                        f"Serviço {index}: preco_unitario_str={preco_unitario_str}, preco_unitario={preco_unitario}")
                except (ValueError, InvalidOperation):
                    messages.error(
                        request, f'Serviço {index}: Quantidade ou preço unitário inválido.')
                    return redirect('PedidoEditView', pedido_id=pedido_id)

                with connection.cursor() as cursor:
                    if delete == 'on' and item_id:
                        cursor.execute(
                            "DELETE FROM loja_web_itemservico WHERE id = %s", [item_id])
                        print(f"Deletado serviço id: {item_id}")
                    else:
                        if item_id:
                            cursor.execute("""
                                UPDATE loja_web_itemservico
                                SET servico_id_id = %s,
                                    quantidade = %s,
                                    preco_unitario = %s,
                                    descricao = (SELECT nome FROM loja_web_servicos WHERE id = %s)
                                WHERE id = %s
                            """, [servico_id, quantidade, preco_unitario, servico_id, item_id])
                            print(
                                f"Atualizado serviço id: {item_id}, servico_id: {servico_id}, quantidade: {quantidade}, preco_unitario: {preco_unitario}")
                            servicos_ids_existentes.add(item_id)
                        else:
                            cursor.execute("""
                                INSERT INTO loja_web_itemservico (pedido_id, servico_id_id, quantidade, preco_unitario, descricao)
                                VALUES (%s, %s, %s, %s, (SELECT nome FROM loja_web_servicos WHERE id = %s))
                                RETURNING id
                            """, [pedido_id, servico_id, quantidade, preco_unitario, servico_id])
                            item_id = cursor.fetchone()[0]
                            print(
                                f"Inserido serviço id: {item_id}, servico_id: {servico_id}, quantidade: {quantidade}, preco_unitario: {preco_unitario}")
                            servicos_ids_existentes.add(str(item_id))

        # Deletar serviços não presentes no POST
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM loja_web_itemservico WHERE pedido_id = %s", [pedido_id])
            servicos_atuais = {str(row[0]) for row in cursor.fetchall()}
            servicos_a_deletar = servicos_atuais - servicos_ids_existentes
            for item_id in servicos_a_deletar:
                cursor.execute(
                    "DELETE FROM loja_web_itemservico WHERE id = %s", [item_id])
                print(f"Deletado serviço id: {item_id} (não mais no POST)")

        # Calcular e atualizar totais com precisão
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(CAST(quantidade AS DECIMAL(15,2)) * CAST(preco_unitario AS DECIMAL(15,2))), 0)
                FROM loja_web_itenspedido
                WHERE pedido_id = %s
            """, [pedido_id])
            subtotal_itens = Decimal(str(cursor.fetchone()[0] or 0))

            cursor.execute("""
                SELECT COALESCE(SUM(CAST(quantidade AS DECIMAL(15,2)) * CAST(preco_unitario AS DECIMAL(15,2))), 0)
                FROM loja_web_itemservico
                WHERE pedido_id = %s
            """, [pedido_id])
            subtotal_servicos = Decimal(str(cursor.fetchone()[0] or 0))

            valor_total = subtotal_itens + subtotal_servicos
            desconto_valor = (
                valor_total * desconto_percentual) / Decimal('100')
            valor_total_final = valor_total - desconto_valor

            print("Cálculo de totais:", {
                'subtotal_itens': subtotal_itens,
                'subtotal_servicos': subtotal_servicos,
                'valor_total_bruto': valor_total,
                'desconto_percentual': desconto_percentual,
                'desconto_valor': desconto_valor,
                'valor_total_final': valor_total_final
            })

            cursor.execute("""
                UPDATE loja_web_pedido
                SET valor_total = %s,
                    desconto = %s
                WHERE id = %s
            """, [valor_total_final, desconto_valor, pedido_id])

        # Verificar dados salvos
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, cliente_id, condicao_pagamento_id, status, desconto_percentual,
                       valor_total, desconto, observacoes
                FROM loja_web_pedido WHERE id = %s
            """, [pedido_id])
            pedido_data = cursor.fetchone()
            print("Após salvar pedido:", {
                'id': pedido_data[0],
                'cliente_id': pedido_data[1],
                'condicao_pagamento_id': pedido_data[2],
                'status': pedido_data[3],
                'desconto_percentual': pedido_data[4],
                'valor_total': pedido_data[5],
                'desconto': pedido_data[6],
                'observacoes': pedido_data[7]
            })

            cursor.execute(
                "SELECT id, produto_id, quantidade, preco_unitario, descricao FROM loja_web_itenspedido WHERE pedido_id = %s", [pedido_id])
            print("Itens salvos:", cursor.fetchall())

            cursor.execute(
                "SELECT id, servico_id_id, quantidade, preco_unitario, descricao FROM loja_web_itemservico WHERE pedido_id = %s", [pedido_id])
            print("Serviços salvos:", cursor.fetchall())

        messages.success(
            request, f'Pedido {pedido_id} atualizado com sucesso!')
        pedido.refresh_from_db()
        snapshot_depois = snapshot_pedido_log(pedido)
        alteracoes = montar_detalhes_edicao_pedido(
            snapshot_antes, snapshot_depois)
        registrar_log(
            request,
            'editar',
            'Pedido de Venda',
            f'Pedido #{pedido_id} | Cliente ID: {cliente_id} | Alterações: {alteracoes}'
        )
        return redirect('lista_pedidos')
    except Exception as e:
        messages.error(request, f'Erro ao atualizar pedido: {str(e)}')
        print(f"Erro ao salvar: {str(e)}")
        return redirect('PedidoEditView', pedido_id=pedido_id)


@transaction.atomic
@login_required
def editar_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    snapshot_antes = snapshot_pedido_log(pedido)
    ItensPedidoFormSet = modelformset_factory(
        ItensPedido, form=ItensPedidoForm, extra=0, can_delete=True)
    ItemServicoFormSet = modelformset_factory(
        ItemServico, form=ItemServicoForm, extra=0, can_delete=True)

    # Armazenar quantidades iniciais para controle de estoque
    itens_anteriores = {
        item.id: item.quantidade for item in ItensPedido.objects.filter(pedido=pedido)}

    if request.method == 'POST':
        form = PedidoForm(request.POST, instance=pedido)
        formset_itens = ItensPedidoFormSet(
            request.POST, prefix='itens', queryset=ItensPedido.objects.filter(pedido=pedido))
        formset_servicos = ItemServicoFormSet(
            request.POST, prefix='servicos', queryset=ItemServico.objects.filter(pedido=pedido))

        if form.is_valid() and formset_itens.is_valid() and formset_servicos.is_valid():
            try:
                with transaction.atomic():
                    # Salvar o pedido
                    pedido = form.save(commit=False)
                    desconto_percentual = form.cleaned_data.get(
                        'desconto_percentual', Decimal('0.00'))
                    juros = Decimal(request.POST.get(
                        'juros', '0.00').replace(',', '.'))

                    if desconto_percentual < 0 or desconto_percentual > 100:
                        raise ValueError(
                            'O desconto percentual deve estar entre 0 e 100.')
                    if juros < 0 or juros > 100:
                        raise ValueError(
                            'O percentual de juros deve estar entre 0 e 100.')

                    # Salvar juros no pedido
                    pedido.juros = juros

                    # Atualizar estoque e salvar itens
                    for item_form in formset_itens:
                        if item_form.cleaned_data.get('DELETE'):
                            if item_form.instance.pk:
                                # Restaurar estoque do item removido
                                item = item_form.instance
                                item.produto.estoque += item.quantidade
                                item.produto.save()
                                item.delete()
                        else:
                            item = item_form.save(commit=False)
                            item.pedido = pedido
                            quantidade_nova = item.quantidade
                            if item.pk:  # Item existente
                                quantidade_antiga = itens_anteriores.get(
                                    item.pk, 0)
                                diferenca = quantidade_antiga - quantidade_nova
                                item.produto.estoque += diferenca
                            else:  # Novo item
                                item.num_fabricante = item.produto.num_fabricante
                                item.num_original = item.produto.num_original
                                item.produto.estoque -= quantidade_nova
                            if item.produto.estoque < 0:
                                raise ValueError(
                                    f"Estoque insuficiente para o produto {item.produto.nome}")
                            item.produto.save()
                            item.save()

                            acompanhamentos_payload = request.POST.get(
                                f'{item_form.prefix}-acompanhamentos_json',
                                '[]'
                            )
                            try:
                                lista_acompanhamentos = json.loads(
                                    acompanhamentos_payload or '[]')
                            except json.JSONDecodeError:
                                lista_acompanhamentos = []

                            ItensPedidoAcompanhamento.objects.filter(
                                item_pedido=item).delete()

                            for adicional in lista_acompanhamentos:
                                adicional_id = adicional.get('id')
                                adicional_qtd = int(
                                    adicional.get('qtd', 1) or 1)
                                if not adicional_id or adicional_qtd < 1:
                                    continue

                                acompanhamento = Acompanhamento.objects.filter(
                                    id=adicional_id,
                                    ativo=True,
                                ).first()
                                if not acompanhamento:
                                    continue

                                ItensPedidoAcompanhamento.objects.create(
                                    item_pedido=item,
                                    acompanhamento=acompanhamento,
                                    quantidade=adicional_qtd,
                                )

                    # Salvar serviços
                    for servico_form in formset_servicos:
                        if servico_form.cleaned_data.get('DELETE'):
                            if servico_form.instance.pk:
                                servico_form.instance.delete()
                        else:
                            servico = servico_form.save(commit=False)
                            servico.pedido = pedido
                            servico.save()

                    # Calcular valor_total
                    subtotal = sum(item.subtotal for item in ItensPedido.objects.filter(pedido=pedido)) + \
                        sum(servico.total for servico in ItemServico.objects.filter(pedido=pedido)) + \
                        sum(acomp.subtotal for acomp in ItensPedidoAcompanhamento.objects.filter(
                            item_pedido__pedido=pedido).select_related('acompanhamento'))
                    valor_juros = (subtotal * juros) / Decimal('100')
                    total_com_juros = subtotal + valor_juros
                    desconto_valor = (total_com_juros *
                                      desconto_percentual) / Decimal('100')
                    valor_total = total_com_juros - desconto_valor
                    pedido.valor_total = valor_total
                    pedido.save()

                    # Atualizar MovimentoFinanceiro
                    MovimentoFinanceiro.objects.filter(pedido=pedido).delete()
                    if pedido.condicao_pagamento:
                        num_parcelas = pedido.condicao_pagamento.numero_parcelas
                        dias_entre_parcelas = pedido.condicao_pagamento.intervalo_dias
                        entrada = pedido.condicao_pagamento.entrada
                        total_parcelas = num_parcelas + 1 if entrada else num_parcelas
                        valor_parcela = valor_total / total_parcelas
                        data_vencimento = date.today()

                        if entrada:
                            MovimentoFinanceiro.objects.create(
                                empresa=pedido.empresa,
                                pedido=pedido,
                                descricao=f"Entrada do Pedido {pedido.id}",
                                parcela=0,
                                total_parcelas=total_parcelas,
                                condicao_id=pedido.condicao_pagamento,
                                valor_parcela=valor_parcela,
                                data_vencimento=data_vencimento,
                                pago=False
                            )

                        for i in range(num_parcelas):
                            dias = dias_entre_parcelas * \
                                (i + 1 if entrada else i)
                            MovimentoFinanceiro.objects.create(
                                empresa=pedido.empresa,
                                pedido=pedido,
                                descricao=f"Parcela {i + 1}/{num_parcelas} do Pedido {pedido.id}",
                                parcela=i + 1,
                                total_parcelas=total_parcelas,
                                condicao_id=pedido.condicao_pagamento,
                                valor_parcela=valor_parcela,
                                data_vencimento=data_vencimento +
                                timedelta(days=dias),
                                pago=False
                            )

                    messages.success(request, 'Pedido atualizado com sucesso!')
                    snapshot_depois = snapshot_pedido_log(pedido)
                    alteracoes = montar_detalhes_edicao_pedido(
                        snapshot_antes, snapshot_depois)
                    registrar_log(
                        request,
                        'editar',
                        'Pedido de Venda',
                        f'Pedido #{pedido.id} | Cliente: {pedido.cliente} | Alterações: {alteracoes}'
                    )
                    return redirect('lista_pedidos')
            except ValueError as e:
                messages.error(request, str(e))
        else:
            messages.error(
                request, 'Erro ao salvar o pedido. Verifique os dados.')
            print("Form errors:", form.errors)
            print("Formset itens errors:", formset_itens.errors)
            print("Formset serviços errors:", formset_servicos.errors)
    else:
        form = PedidoForm(instance=pedido)
        formset_itens = ItensPedidoFormSet(
            prefix='itens', queryset=ItensPedido.objects.filter(pedido=pedido))
        formset_servicos = ItemServicoFormSet(
            prefix='servicos', queryset=ItemServico.objects.filter(pedido=pedido))

    # Calcular valores para exibição no GET
    subtotal = sum(item.subtotal for item in ItensPedido.objects.filter(pedido=pedido)) + \
        sum(servico.total for servico in ItemServico.objects.filter(pedido=pedido)) + \
        sum(acomp.subtotal for acomp in ItensPedidoAcompanhamento.objects.filter(
            item_pedido__pedido=pedido).select_related('acompanhamento'))
    valor_desconto = (subtotal * pedido.desconto_percentual) / Decimal('100')
    valor_juros = (subtotal * pedido.juros) / Decimal('100')
    total_com_juros = subtotal + valor_juros
    desconto_valor = (total_com_juros *
                      pedido.desconto_percentual) / Decimal('100')
    valor_total = total_com_juros - desconto_valor

    return render(request, 'pedido_edit.html', {
        'form': form,
        'formset_itens': formset_itens,
        'formset_servicos': formset_servicos,
        'pedido': pedido,
        'clientes': filtrar_queryset_empresa(request, Cliente.objects.all()),
        'condicoes_pagamento': filtrar_queryset_empresa(request, CondicaoPagamento.objects.all()),
        'produtos': filtrar_queryset_empresa(request, Produto.objects.filter(eh_servico=False)),
        'acompanhamentos_ativos': filtrar_queryset_empresa(request, Acompanhamento.objects.filter(ativo=True)).order_by('nome'),
        'itens': ItensPedido.objects.filter(pedido=pedido),
        'itens_servicos': ItemServico.objects.filter(pedido=pedido),
        'desconto': desconto_valor,
        'valor_juros': valor_juros,
        'valor_total': valor_total,
    })


@login_required
def buscar_produtos(request):
    termo = request.GET.get('term', '').strip().lower()
    produtos = filtrar_queryset_empresa(
        request, Produto.objects.filter(eh_servico=False)
    )
    if termo:
        produtos = produtos.filter(
            Q(id__iexact=termo) |
            Q(nome__icontains=termo) |
            Q(num_fabricante__icontains=termo) |
            Q(num_original__icontains=termo)
        )
    resultados = [
        {
            'id': p.id,
            'nome': p.nome,
            'preco': str(p.preco),
            'num_fabricante': p.num_fabricante or '',
            'num_original': p.num_original or ''
        } for p in produtos
    ]
    return JsonResponse(resultados, safe=False)


@login_required
def buscar_servicos(request):
    termo = request.GET.get('term', '').strip()
    servicos = filtrar_queryset_empresa(
        request, Produto.objects.filter(eh_servico=True)
    )
    if termo:
        servicos = servicos.filter(
            Q(id__iexact=termo) |
            Q(nome__icontains=termo)
        )
    resultados = [{'id': s.id, 'nome': s.nome,
                   'preco': str(s.preco)} for s in servicos]
    return JsonResponse(resultados, safe=False)


@login_required
def lista_pedidos(request):
    pedidos = filtrar_queryset_empresa(request, Pedido.objects.all())
    return render(request, 'lista_pedidos.html', {'pedidos': pedidos})


def buscar_produtos(request):
    termo = request.GET.get('term', '')
    produtos = filtrar_queryset_empresa(
        request, Produto.objects.filter(nome__icontains=termo)
    )[:10]
    resultados = [{'id': p.id, 'nome': p.nome,
                   'preco': str(p.preco)} for p in produtos]
    return JsonResponse(resultados, safe=False)


def buscar_servicos(request):
    termo = request.GET.get('term', '')
    servicos = filtrar_queryset_empresa(
        request, Servicos.objects.filter(nome__icontains=termo)
    )[:10]
    resultados = [{'id': s.id, 'nome': s.nome,
                   'preco': str(s.preco)} for s in servicos]
    return JsonResponse(resultados, safe=False)


# Excluir pedido
@login_required
@transaction.atomic
def PedidoDeleteView(request, id):
    try:
        pedido = Pedido.objects.get(id=id)
        pedido_info = f'Pedido #{pedido.id} | Cliente: {pedido.cliente} | Status: {pedido.status} | Total: R$ {formatar_valor_log(pedido.valor_total)}'

        # 🔥 Repõe estoque de cada item do pedido
        itens = ItensPedido.objects.filter(pedido=pedido)
        for item in itens:
            produto = item.produto
            produto.estoque += item.quantidade
            produto.save()

        pedido.delete()
        registrar_log(request, 'excluir', 'Pedido de Venda',
                      f'{pedido_info} | Ação: excluído')

        messages.success(
            request, 'Pedido excluído e estoque atualizado com sucesso!')

    except Exception as e:
        messages.error(request, f'Erro ao excluir pedido: {e}')

    return redirect('lista_pedidos')


# --- View para Registrar Entrada de Estoque ---
@login_required  # Adicionar proteção de login se necessário
def registrar_entrada_estoque(request):
    if request.method == 'POST':
        form = EntradaEstoqueForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    entrada = form.save(commit=False)

                    # Atualiza estoque do produto
                    produto = entrada.produto
                    estoque_anterior = produto.estoque
                    produto.estoque += entrada.quantidade
                    produto.save()

                    # Obtém numero_nota_fiscal do request.POST
                    entrada.numero_nota_fiscal = request.POST.get(
                        'numero_nota_fiscal', '') or None

                    # Obtém fornecedor_id e nome_fornecedor
                    fornecedor_id = request.POST.get('fornecedor', '')
                    if fornecedor_id:
                        try:
                            fornecedor = Fornecedor.objects.get(
                                id=fornecedor_id)
                            entrada.fornecedor = fornecedor
                            entrada.nome_fornecedor = fornecedor.nome
                        except Fornecedor.DoesNotExist:
                            entrada.fornecedor = None
                            entrada.nome_fornecedor = ''
                    else:
                        entrada.fornecedor = None
                        entrada.nome_fornecedor = ''

                    # Vincular pedido de compra, se selecionado
                    if request.POST.get('vincular_pedido') and request.POST.get('pedido_compra'):
                        pedido_id = request.POST.get('pedido_compra')
                        try:
                            pedido = PedidoCompra.objects.get(id=pedido_id)
                            entrada.pedido_compra = pedido

                            # Atualizar itens do pedido
                            item_pedido = ItemPedidoCompra.objects.filter(
                                pedido_compra=pedido,  # Corrigido de 'pedido' para 'pedido_compra'
                                produto=entrada.produto
                            ).first()
                            if item_pedido:
                                quantidade_atendida = int(entrada.quantidade)
                                item_pedido.quantidade_atendida = (
                                    item_pedido.quantidade_atendida or 0
                                ) + quantidade_atendida
                                item_pedido.save()

                                # Verificar se todos os itens do pedido foram atendidos
                                itens_pendentes = ItemPedidoCompra.objects.filter(
                                    pedido_compra=pedido  # Corrigido de 'pedido' para 'pedido_compra'
                                ).exclude(quantidade_atendida__gte=F('quantidade'))
                                if not itens_pendentes.exists():
                                    pedido.status = 'concluido'
                                    pedido.save()
                                    messages.info(
                                        request, f"Pedido de compra {pedido.id} concluído!")
                        except PedidoCompra.DoesNotExist:
                            messages.error(
                                request, "Pedido de compra selecionado não encontrado.")

                    entrada.save()

                    registrar_log(
                        request,
                        'estoque',
                        'Entrada de Estoque',
                        f'Produto #{produto.id} | Nome: {produto.nome} | Quantidade entrada: {entrada.quantidade} | Estoque: {estoque_anterior} -> {produto.estoque} | NF: {entrada.numero_nota_fiscal or "-"}'
                    )
                    messages.success(
                        request, f"Entrada de {entrada.quantidade}x {produto.nome} registrada com sucesso! Novo estoque: {produto.estoque}")
                    return redirect('registrar_entrada_estoque')
            except Exception as e:
                messages.error(request, f"Erro ao registrar entrada: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"Erro em {field}: {error}")
    else:
        form = EntradaEstoqueForm()

    context = {
        'form': form,
        'titulo_pagina': 'Registrar Nova Entrada de Estoque'
    }
    return render(request, 'entrada_estoque_form.html', context)


@login_required
def registrar_baixa_estoque(request):
    if request.method == 'POST':
        form = BaixaEstoqueForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    saida = form.save(commit=False)
                    produto = saida.produto
                    estoque_anterior = produto.estoque

                    if produto.estoque < saida.quantidade:
                        messages.error(
                            request,
                            f'Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque}'
                        )
                        raise ValueError('Estoque insuficiente')

                    produto.estoque -= saida.quantidade
                    produto.save(update_fields=['estoque'])
                    saida.save()

                    registrar_log(
                        request,
                        'estoque',
                        'Baixa de Estoque',
                        f'Produto #{produto.id} | Nome: {produto.nome} | Quantidade baixa: {saida.quantidade} | Estoque: {estoque_anterior} -> {produto.estoque} | Motivo: {saida.motivo or "-"}'
                    )
                    messages.success(
                        request,
                        f'Baixa de {saida.quantidade}x {produto.nome} registrada com sucesso! Novo estoque: {produto.estoque}'
                    )
                    return redirect('registrar_baixa_estoque')
            except ValueError:
                pass
            except Exception as e:
                messages.error(request, f'Erro ao registrar baixa: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Erro em {field}: {error}')
    else:
        form = BaixaEstoqueForm()

    context = {
        'form': form,
        'titulo_pagina': 'Registrar Baixa de Estoque'
    }
    return render(request, 'baixa_estoque_form.html', context)


@login_required
def consultar_baixas(request):
    baixas = SaidaEstoque.objects.select_related(
        'produto').all().order_by('-data_saida')

    produto_id = request.GET.get('produto_id')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    if produto_id:
        baixas = baixas.filter(produto_id=produto_id)
    if data_inicio:
        baixas = baixas.filter(data_saida__date__gte=data_inicio)
    if data_fim:
        baixas = baixas.filter(data_saida__date__lte=data_fim)

    total_baixas = baixas.count()
    paginator = Paginator(baixas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'baixas': page_obj,
        'total_baixas': total_baixas,
        'titulo_pagina': 'Consultar Baixas de Estoque'
    }
    return render(request, 'consultar_baixas.html', context)


def consultar_entradas(request):
    entradas = EntradaEstoque.objects.all().order_by('-data_entrada')
    fornecedor_id = request.GET.get('fornecedor_id')
    produto_id = request.GET.get('produto_id')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')
    numero_nota_fiscal = request.GET.get('numero_nota_fiscal')
    pedido_compra_id = request.GET.get('pedido_compra_id')  # Novo filtro

    if fornecedor_id:
        entradas = entradas.filter(fornecedor_id=fornecedor_id)
    if produto_id:
        entradas = entradas.filter(produto_id=produto_id)
    if data_inicio:
        data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
        entradas = entradas.filter(data_entrada__gte=data_inicio)
    if data_fim:
        data_fim = datetime.strptime(data_fim, '%Y-%m-%d')
        entradas = entradas.filter(data_entrada__lte=data_fim)
    if numero_nota_fiscal:
        entradas = entradas.filter(
            numero_nota_fiscal__icontains=numero_nota_fiscal)
    if pedido_compra_id:
        entradas = entradas.filter(pedido_compra_id=pedido_compra_id)

    total_entradas = entradas.count()

    # Paginação: 10 entradas por página
    paginator = Paginator(entradas, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'entradas': page_obj,
        'total_entradas': total_entradas,
        'titulo_pagina': 'Consultar Entradas de Estoque'
    }
    return render(request, 'consultar_entradas.html', context)


def buscar_produtosentrada(request):
    termo = request.GET.get('term', '').strip()
    print(f"[DEBUG_PRODUTOS] Termo pesquisado: '{termo}'")
    if termo.isdigit():
        # Busca por ID exato ou nome que contém o termo
        produtos = Produto.objects.filter(
            Q(id=termo) | Q(nome__icontains=termo))[:10]
    else:
        # Busca apenas por nome
        produtos = Produto.objects.filter(nome__icontains=termo)[:10]
    resultados = [{
        'id': p.id,
        'nome': p.nome,
        'preco': str(p.preco or 0),
        'unidade_medida': p.unidade_medida,
        'unidade_label': p.get_unidade_medida_display() if hasattr(p, 'get_unidade_medida_display') else p.unidade_medida,
        'categoria': p.categoria.nome if p.categoria else '',
        'marca': getattr(p, 'marca', '') or '',
        'num_fabricante': getattr(p, 'num_fabricante', '') or '',
        'num_original': getattr(p, 'num_original', '') or '',
        'descricao': getattr(p, 'descricao', '') or '',
        'estoque': p.estoque_exibicao if hasattr(p, 'estoque_exibicao') else str(getattr(p, 'estoque', 0) or 0)
    } for p in produtos]
    print(f"[DEBUG_PRODUTOS] Resultados: {resultados}")
    return JsonResponse(resultados, safe=False)


def buscar_entradas_estoque(request):
    produto_id = request.GET.get('produto_id', '')
    print(f"[DEBUG_ENTRADAS] Produto ID: '{produto_id}'")
    if not produto_id or not produto_id.isdigit():
        print(f"[DEBUG_ENTRADAS] Erro: produto_id inválido ('{produto_id}')")
        return JsonResponse({'entradas': [], 'error': 'ID do produto inválido'}, safe=False)
    entradas = EntradaEstoque.objects.filter(
        produto_id=produto_id).order_by('-data_entrada')[:10]
    resultados = {
        'entradas': [{
            'data_entrada': entrada.data_entrada.strftime('%d/%m/%Y %H:%M'),
            'quantidade': entrada.quantidade
        } for entrada in entradas]
    }
    print(f"[DEBUG_ENTRADAS] Resultados: {resultados}")
    return JsonResponse(resultados, safe=False)
# --- Fim View Entrada de Estoque ---

# --- Condição de Pagamento ---
# Listar


@login_required
def lista_condicoes_pagamento(request):
    # Inicializa o formulário com os dados da requisição
    form = CondicaoPagamentoFilterForm(request.GET)

    # Obtém todas as condições
    condicoes = CondicaoPagamento.objects.all()

    # Aplica filtros se o formulário for válido
    if form.is_valid():
        nome = form.cleaned_data.get('nome')
        descricao = form.cleaned_data.get('descricao')
        numero_parcelas = form.cleaned_data.get('numero_parcelas')
        intervalo_dias = form.cleaned_data.get('intervalo_dias')
        entrada = form.cleaned_data.get('entrada')

        if nome:
            condicoes = condicoes.filter(nome__icontains=nome)
        if descricao:
            condicoes = condicoes.filter(descricao__icontains=descricao)
        if numero_parcelas is not None:
            condicoes = condicoes.filter(numero_parcelas=numero_parcelas)
        if intervalo_dias is not None:
            condicoes = condicoes.filter(intervalo_dias=intervalo_dias)
        if entrada:
            entrada_bool = entrada == 'True'
            condicoes = condicoes.filter(entrada=entrada_bool)

    return render(request, 'lista_cond_pagamentos.html', {
        'condicoes': condicoes,
        'form': form
    })

# Criar


@login_required
def criar_condicao_pagamento(request):
    if request.method == 'POST':
        form = CondicaoPagamentoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('lista_condicoes_pagamento')
    else:
        form = CondicaoPagamentoForm()
    return render(request, 'condicoes_pagamento_form.html', {'form': form})

# Editar


@login_required
def editar_condicao_pagamento(request, pk):
    condicao = get_object_or_404(CondicaoPagamento, pk=pk)
    if request.method == 'POST':
        form = CondicaoPagamentoForm(request.POST, instance=condicao)
        if form.is_valid():
            form.save()
            return redirect('lista_condicoes_pagamento')
    else:
        form = CondicaoPagamentoForm(instance=condicao)
    return render(request, 'condicoes_pagamento_form.html', {'form': form})

# Excluir


@login_required
def excluir_condicao_pagamento(request, pk):
    condicao = get_object_or_404(CondicaoPagamento, pk=pk)
    if request.method == 'POST':
        condicao.delete()
        return redirect('lista_condicoes_pagamento')
    return render(request, 'condicoes_pagamento_confirm_delete.html', {'condicao': condicao})


# --- Cobrança de clientes via WhatsApp ---

@login_required
def lista_regras_cobranca_whatsapp(request):
    regras = filtrar_queryset_empresa(
        request, RegraCobrancaWhatsApp.objects.all())
    return render(request, 'cobranca_whatsapp_lista.html', {'regras': regras})


@login_required
def criar_regra_cobranca_whatsapp(request):
    if request.method == 'POST':
        form = RegraCobrancaWhatsAppForm(request.POST)
        if form.is_valid():
            regra = form.save(commit=False)
            atribuir_empresa(regra, request)
            regra.save()
            registrar_log(
                request, 'criar', 'RegraCobrancaWhatsApp',
                f'Regra #{regra.id} criada | Nome: {regra.nome}'
            )
            messages.success(request, 'Regra de cobrança criada com sucesso.')
            return redirect('lista_regras_cobranca_whatsapp')
    else:
        form = RegraCobrancaWhatsAppForm()
    return render(request, 'cobranca_whatsapp_form.html', {'form': form})


@login_required
def editar_regra_cobranca_whatsapp(request, pk):
    regra = get_object_or_404(RegraCobrancaWhatsApp, pk=pk)
    if request.method == 'POST':
        form = RegraCobrancaWhatsAppForm(request.POST, instance=regra)
        if form.is_valid():
            form.save()
            registrar_log(
                request, 'editar', 'RegraCobrancaWhatsApp',
                f'Regra #{regra.id} editada | Nome: {regra.nome}'
            )
            messages.success(request, 'Regra de cobrança atualizada.')
            return redirect('lista_regras_cobranca_whatsapp')
    else:
        form = RegraCobrancaWhatsAppForm(instance=regra)
    return render(request, 'cobranca_whatsapp_form.html', {'form': form})


@login_required
def excluir_regra_cobranca_whatsapp(request, pk):
    regra = get_object_or_404(RegraCobrancaWhatsApp, pk=pk)
    if request.method == 'POST':
        regra.delete()
        registrar_log(
            request, 'excluir', 'RegraCobrancaWhatsApp',
            f'Regra #{pk} excluída | Nome: {regra.nome}'
        )
        messages.success(request, 'Regra de cobrança excluída.')
        return redirect('lista_regras_cobranca_whatsapp')
    return render(request, 'cobranca_whatsapp_confirm_delete.html', {'regra': regra})


@login_required
def historico_cobranca_whatsapp(request):
    envios = filtrar_queryset_empresa(
        request,
        EnvioCobrancaWhatsApp.objects.select_related(
            'regra', 'movimento__pedido__cliente').all()
    )
    return render(request, 'cobranca_whatsapp_historico.html', {'envios': envios})


@login_required
def disparo_manual_cobranca_whatsapp(request):
    empresa = get_empresa_ativa(request)
    clientes = Cliente.objects.filter(empresa=empresa).order_by('nome')
    cliente_id = request.POST.get(
        'cliente_id') or request.GET.get('cliente_id')
    cliente = clientes.filter(id=cliente_id).first() if cliente_id else None
    movimentos = list(movimentos_abertos_cliente(
        cliente, empresa=empresa)) if cliente else []
    resultado = None
    mensagem_preview = (
        montar_mensagem_cliente(cliente, movimentos, empresa=empresa)
        if cliente and movimentos else ''
    )

    if request.method == 'POST' and cliente:
        mensagem_preview = request.POST.get(
            'mensagem', '').strip() or mensagem_preview
        resultado = enviar_cobranca_cliente(
            cliente,
            empresa=empresa,
            mensagem_personalizada=mensagem_preview,
        )
        if resultado.get('sucesso'):
            messages.success(
                request, 'Cobrança enviada com sucesso pelo WhatsApp.')
        else:
            messages.error(
                request,
                f"Não foi possível enviar a cobrança: {resultado.get('erro', 'erro desconhecido')}.",
            )

    return render(request, 'cobranca_whatsapp_manual.html', {
        'clientes': clientes,
        'cliente_selecionado': cliente,
        'movimentos': movimentos,
        'today': date.today(),
        'mensagem_preview': mensagem_preview,
        'resultado': resultado,
    })


@login_required
def disparar_cobrancas_whatsapp_agora(request):
    if request.method == 'POST':
        empresa = get_empresa_ativa(request)
        resultados = processar_todas_regras(dry_run=False, empresa=empresa)
        enviados = sum(1 for r in resultados if r.get('sucesso'))
        registrar_log(
            request, 'outro', 'RegraCobrancaWhatsApp',
            f'Disparo manual de cobranças WhatsApp | Avaliadas: {len(resultados)} | Enviadas: {enviados}'
        )
        if resultados:
            messages.success(
                request, f'{len(resultados)} cobrança(s) avaliada(s), {enviados} enviada(s) com sucesso.')
        else:
            messages.info(
                request, 'Nenhuma cobrança elegível para envio no momento.')
    return redirect('historico_cobranca_whatsapp')


# Mostrar página de relatórios
@login_required
def relatorios(request):
    return render(request, 'relatorios.html')


@login_required
def visualizar_logs(request):
    logs = LogAuditoria.objects.select_related(
        'usuario').order_by('-created_at')

    # Filtros
    acao = request.GET.get('acao', '')
    usuario_id = request.GET.get('usuario', '')
    data_inicio = request.GET.get('data_inicio', '')
    data_fim = request.GET.get('data_fim', '')
    busca = request.GET.get('q', '').strip()

    if acao:
        logs = logs.filter(acao=acao)
    if usuario_id:
        logs = logs.filter(usuario_id=usuario_id)
    if data_inicio:
        logs = logs.filter(created_at__date__gte=data_inicio)
    if data_fim:
        logs = logs.filter(created_at__date__lte=data_fim)
    if busca:
        logs = logs.filter(
            Q(entidade__icontains=busca) | Q(detalhes__icontains=busca)
        )

    paginator = Paginator(logs, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    usuarios = User.objects.order_by('username')

    context = {
        'logs': page_obj,
        'page_obj': page_obj,
        'acoes': LogAuditoria.ACOES,
        'usuarios': usuarios,
        'filtro_acao': acao,
        'filtro_usuario': usuario_id,
        'filtro_data_inicio': data_inicio,
        'filtro_data_fim': data_fim,
        'filtro_q': busca,
    }
    return render(request, 'logs_auditoria.html', context)


@login_required
# Mostrar página de serviços
def servicos(request):
    return render(request, 'servicos.html')


@login_required
def listar_servicos(request):
    # Obtém o termo de busca do parâmetro 'q' na URL
    termo_busca = request.GET.get('q', '').strip()

    # Filtra serviços com base no termo de busca (ID ou nome, insensível a maiúsculas/minúsculas)
    servicos = Servicos.objects.all()
    if termo_busca:
        servicos = servicos.filter(
            Q(nome__icontains=termo_busca) | Q(id__iexact=termo_busca))

    return render(request, 'servico_lista.html', {
        'servicos': servicos,
        'termo_busca': termo_busca
    })


@login_required
def novo_servico(request):
    if request.method == 'POST':
        form = ServicoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Serviço cadastrado com sucesso!')
            return redirect('listar_servicos')
        else:
            messages.error(
                request, 'Erro ao cadastrar serviço. Verifique os dados.')
    else:
        form = ServicoForm()
    return render(request, 'novo_servico.html', {'form': form})


@login_required
def editar_servico(request, pk):
    servico = get_object_or_404(Servicos, pk=pk)
    if request.method == 'POST':
        form = ServicoForm(request.POST, instance=servico)
        if form.is_valid():
            form.save()
            messages.success(
                request, f'Serviço {servico.id} atualizado com sucesso!')
            return redirect('listar_servicos')
        else:
            messages.error(
                request, 'Erro ao atualizar serviço. Verifique os dados.')
    else:
        form = ServicoForm(instance=servico)
    return render(request, 'editar_servico.html', {'form': form, 'servico': servico})


@login_required
def excluir_servico(request, pk):
    servico = get_object_or_404(Servicos, pk=pk)
    servico.delete()
    return redirect('listar_servicos')  # nome da url que lista os serviços


@login_required
def listar_acompanhamentos(request):
    termo_busca = request.GET.get('q', '').strip()
    acompanhamentos = Acompanhamento.objects.all()

    if termo_busca:
        acompanhamentos = acompanhamentos.filter(
            Q(nome__icontains=termo_busca) | Q(id__iexact=termo_busca)
        )

    return render(request, 'acompanhamentos.html', {
        'acompanhamentos': acompanhamentos,
        'termo_busca': termo_busca,
    })


@login_required
def novo_acompanhamento(request):
    if request.method == 'POST':
        form = AcompanhamentoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Acompanhamento cadastrado com sucesso!')
            return redirect('listar_acompanhamentos')
        messages.error(
            request, 'Erro ao cadastrar acompanhamento. Verifique os dados.')
    else:
        form = AcompanhamentoForm()

    return render(request, 'acompanhamento_form.html', {'form': form, 'titulo': 'Novo Acompanhamento'})


@login_required
def editar_acompanhamento(request, pk):
    acompanhamento = get_object_or_404(Acompanhamento, pk=pk)

    if request.method == 'POST':
        form = AcompanhamentoForm(request.POST, instance=acompanhamento)
        if form.is_valid():
            form.save()
            messages.success(request, 'Acompanhamento atualizado com sucesso!')
            return redirect('listar_acompanhamentos')
        messages.error(
            request, 'Erro ao atualizar acompanhamento. Verifique os dados.')
    else:
        form = AcompanhamentoForm(instance=acompanhamento)

    return render(request, 'acompanhamento_form.html', {
        'form': form,
        'titulo': f'Editar Acompanhamento #{acompanhamento.id}',
        'acompanhamento': acompanhamento,
    })


@login_required
def excluir_acompanhamento(request, pk):
    acompanhamento = get_object_or_404(Acompanhamento, pk=pk)

    if request.method == 'POST':
        acompanhamento.delete()
        messages.success(request, 'Acompanhamento excluído com sucesso!')

    return redirect('listar_acompanhamentos')


# def relatorio_estoque(request):
#     nome = request.GET.get('nome', '').strip()
#     qtd_minima = request.GET.get('qtd_minima')
#     id_inicial = request.GET.get('id_inicial')
#     id_final = request.GET.get('id_final')

#     produtos = Produto.objects.filter(eh_servico=False)

#     if nome:
#         produtos = produtos.filter(nome__icontains=nome)

#     if qtd_minima:
#         try:
#             qtd = int(qtd_minima)
#             produtos = produtos.filter(estoque__gte=qtd)
#         except ValueError:
#             pass

#     if id_inicial:
#         try:
#             produtos = produtos.filter(id__gte=int(id_inicial))
#         except ValueError:
#             pass

#     if id_final:
#         try:
#             produtos = produtos.filter(id__lte=int(id_final))
#         except ValueError:
#             pass

#     data_atual = timezone.now().astimezone().strftime('%d/%m/%Y %H:%M')

#     total_estoque = produtos.aggregate(
#         total=Sum(F('preco') * F('estoque'))
#     )['total'] or 0.00
#     total_itens_estoque = produtos.aggregate(
#         total=Sum('estoque')
#     )['total'] or 0
#     quantidade_registros = produtos.count()

#     return render(request, 'relatorio_estoque.html', {
#         'produtos': produtos,
#         'filtro_nome': nome,
#         'filtro_qtd': qtd_minima,
#         'id_inicial': id_inicial,
#         'id_final': id_final,
#         'data_atual': data_atual,
#         'total_estoque': total_estoque,
#         'total_itens_estoque': total_itens_estoque,
#         'quantidade_registros': quantidade_registros,
#     })

@login_required
def relatorio_estoque(request):
    nome = request.GET.get('nome', '').strip()
    qtd_minima = request.GET.get('qtd_minima')
    id_inicial = request.GET.get('id_inicial')
    id_final = request.GET.get('id_final')
    num_fabricante = request.GET.get('num_fabricante', '').strip()
    num_original = request.GET.get('num_original', '').strip()

    produtos = Produto.objects.filter(
        eh_servico=False, preco__isnull=False, estoque__isnull=False)

    if nome:
        produtos = produtos.filter(nome__icontains=nome)
    if qtd_minima:
        try:
            qtd = int(qtd_minima)
            produtos = produtos.filter(estoque__gte=qtd)
        except ValueError:
            pass
    if id_inicial:
        try:
            produtos = produtos.filter(id__gte=int(id_inicial))
        except ValueError:
            pass
    if id_final:
        try:
            produtos = produtos.filter(id__lte=int(id_final))
        except ValueError:
            pass
    if num_fabricante:
        produtos = produtos.filter(num_fabricante__icontains=num_fabricante)
    if num_original:
        produtos = produtos.filter(num_original__icontains=num_original)

    data_atual = timezone.now().astimezone().strftime('%d/%m/%Y %H:%M')

    total_estoque = produtos.aggregate(
        total=Sum(F('preco') * F('estoque'))
    )['total'] or 0.00
    total_itens_estoque = produtos.aggregate(
        total=Sum('estoque')
    )['total'] or 0
    quantidade_registros = produtos.count()

    print(
        f"Produtos: {list(produtos.values('id', 'nome', 'preco', 'estoque', 'num_fabricante', 'num_original'))}")
    print(
        f"Total Estoque: {total_estoque}, Total Itens: {total_itens_estoque}")

    return render(request, 'relatorio_estoque.html', {
        'produtos': produtos,
        'filtro_nome': nome,
        'filtro_qtd': qtd_minima,
        'id_inicial': id_inicial,
        'id_final': id_final,
        'filtro_num_fabricante': num_fabricante,
        'filtro_num_original': num_original,
        'data_atual': data_atual,
        'total_estoque': total_estoque,
        'total_itens_estoque': total_itens_estoque,
        'quantidade_registros': quantidade_registros,
    })


@login_required
def imprimir_relatorio_estoque(request):
    nome = request.GET.get('nome', '').strip()
    qtd_minima = request.GET.get('qtd_minima')
    id_inicial = request.GET.get('id_inicial')
    id_final = request.GET.get('id_final')
    num_fabricante = request.GET.get('num_fabricante', '').strip()
    num_original = request.GET.get('num_original', '').strip()

    produtos = Produto.objects.filter(
        eh_servico=False, preco__isnull=False, estoque__isnull=False)

    if nome:
        produtos = produtos.filter(nome__icontains=nome)
    if qtd_minima:
        try:
            qtd = int(qtd_minima)
            produtos = produtos.filter(estoque__gte=qtd)
        except ValueError:
            pass
    if id_inicial:
        try:
            produtos = produtos.filter(id__gte=int(id_inicial))
        except ValueError:
            pass
    if id_final:
        try:
            produtos = produtos.filter(id__lte=int(id_final))
        except ValueError:
            pass
    if num_fabricante:
        produtos = produtos.filter(num_fabricante__icontains=num_fabricante)
    if num_original:
        produtos = produtos.filter(num_original__icontains=num_original)

    data_atual = timezone.now().astimezone().strftime('%d/%m/%Y %H:%M')

    total_estoque = produtos.aggregate(
        total=Sum(F('preco') * F('estoque'))
    )['total'] or 0.00
    total_itens_estoque = produtos.aggregate(
        total=Sum('estoque')
    )['total'] or 0
    quantidade_registros = produtos.count()

    print(
        f"Imprimir - Produtos: {list(produtos.values('id', 'nome', 'preco', 'estoque', 'num_fabricante', 'num_original'))}")
    print(
        f"Imprimir - Total Estoque: {total_estoque}, Total Itens: {total_itens_estoque}")

    return render(request, 'imprimir_relatorio_estoque.html', {
        'produtos': produtos,
        'filtro_nome': nome,
        'filtro_qtd': qtd_minima,
        'id_inicial': id_inicial,
        'id_final': id_final,
        'filtro_num_fabricante': num_fabricante,
        'filtro_num_original': num_original,
        'data_atual': data_atual,
        'total_estoque': total_estoque,
        'total_itens_estoque': total_itens_estoque,
        'quantidade_registros': quantidade_registros,
    })


def buscar_produtos(request):
    term = request.GET.get('term', '')
    produtos = Produto.objects.filter(nome__icontains=term)[:20]
    results = [
        {'id': p.id, 'nome': p.nome, 'preco': float(p.preco)}
        for p in produtos
    ]
    return JsonResponse(results, safe=False)


def buscar_servicos(request):
    term = request.GET.get('term', '')
    servicos = Servicos.objects.filter(nome__icontains=term)[:20]
    results = [
        {'id': s.id, 'nome': s.nome, 'preco': float(s.preco)}
        for s in servicos
    ]
    return JsonResponse(results, safe=False)


@login_required
@transaction.atomic
def PedidoTesteView(request):
    clientes = Cliente.objects.all()
    condicoes_pagamento = CondicaoPagamento.objects.all()
    produtos = Produto.objects.filter(eh_servico=False)
    servicos = Servicos.objects.all()
    acompanhamentos_ativos = Acompanhamento.objects.filter(
        ativo=True).order_by('nome')

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        condicao_pagamento_id = request.POST.get('condicao_pagamento')
        observacoes = request.POST.get('observacoes', '')
        status = request.POST.get('status')
        desconto_percentual = request.POST.get(
            'desconto_percentual', '0.00').replace(',', '.')
        juros = request.POST.get('juros', '0.00').replace(',', '.')

        produtos_ids = request.POST.getlist('produtos')
        quantidades = request.POST.getlist('quantidades')
        precos_unitarios = request.POST.getlist('precos_unitarios')
        acompanhamentos_json = request.POST.getlist('acompanhamentos_json')
        servicos_ids = request.POST.getlist('servicos')
        quantidades_servicos = request.POST.getlist('quantidades_servicos')
        precos_servicos = request.POST.getlist('precos_servicos')

        if not cliente_id or not status:
            messages.error(request, 'Preencha todos os campos obrigatórios.')
            return redirect('pedido_teste')

        try:
            cliente = Cliente.objects.get(id=cliente_id)
            condicao_pagamento = CondicaoPagamento.objects.get(
                id=condicao_pagamento_id) if condicao_pagamento_id else None
            desconto_decimal = Decimal(
                desconto_percentual) if desconto_percentual else Decimal('0.00')
            juros_decimal = Decimal(juros) if juros else Decimal('0.00')

            if desconto_decimal < 0 or desconto_decimal > 100:
                messages.error(
                    request, 'O desconto percentual deve estar entre 0 e 100.')
                return redirect('pedido_teste')
            if juros_decimal < 0 or juros_decimal > 100:
                messages.error(
                    request, 'O percentual de juros deve estar entre 0 e 100.')
                return redirect('pedido_teste')

            if not produtos_ids and not servicos_ids:
                messages.error(
                    request, 'Adicione pelo menos um produto ou serviço.')
                return redirect('pedido_teste')

            pedido = Pedido.objects.create(
                empresa=get_empresa_ativa(request),
                cliente=cliente,
                condicao_pagamento=condicao_pagamento,
                observacoes=observacoes,
                status=status,
                desconto_percentual=desconto_decimal,
                juros=juros_decimal,
                valor_total=Decimal('0.00')
            )

            valor_total = Decimal('0.00')

            # Processa produtos
            for idx, produto_id in enumerate(produtos_ids):
                if not produto_id:
                    continue
                try:
                    produto = Produto.objects.get(id=produto_id)
                    quantidade = Decimal(quantidades[idx].replace(',', '.')) if idx < len(
                        quantidades) and quantidades[idx] else Decimal('1.000')
                    preco_str = precos_unitarios[idx].replace(',', '.') if idx < len(
                        precos_unitarios) and precos_unitarios[idx] else str(produto.preco)
                    preco_unitario = Decimal(preco_str)

                    if quantidade <= 0:
                        raise ValueError(
                            f"Quantidade inválida para {produto.nome}.")
                    if preco_unitario <= 0:
                        raise ValueError(
                            f"Preço unitário inválido para {produto.nome}.")

                    subtotal = preco_unitario * quantidade
                    valor_total += subtotal

                    if hasattr(produto, 'estoque') and produto.estoque is not None:
                        if produto.estoque < quantidade:
                            messages.error(
                                request, f"Estoque insuficiente para {produto.nome}.")
                            # volta para a tela do pedido
                            return redirect('pedido_teste')
                        produto.estoque -= quantidade
                        produto.save()

                    item_pedido = ItensPedido.objects.create(
                        pedido=pedido,
                        produto=produto,
                        descricao=produto.nome,
                        quantidade=quantidade,
                        preco_unitario=preco_unitario
                    )

                    lista_acompanhamentos = []
                    if idx < len(acompanhamentos_json) and acompanhamentos_json[idx]:
                        try:
                            lista_acompanhamentos = json.loads(
                                acompanhamentos_json[idx])
                        except json.JSONDecodeError:
                            lista_acompanhamentos = []

                    for adicional in lista_acompanhamentos:
                        adicional_id = adicional.get('id')
                        adicional_qtd = int(adicional.get('qtd', 1) or 1)
                        if not adicional_id or adicional_qtd < 1:
                            continue

                        acompanhamento = Acompanhamento.objects.filter(
                            id=adicional_id,
                            ativo=True,
                        ).first()
                        if not acompanhamento:
                            continue

                        ItensPedidoAcompanhamento.objects.create(
                            item_pedido=item_pedido,
                            acompanhamento=acompanhamento,
                            quantidade=adicional_qtd,
                        )
                        valor_total += acompanhamento.preco * \
                            Decimal(adicional_qtd)
                except Produto.DoesNotExist:
                    messages.error(
                        request, f'Produto com ID {produto_id} não encontrado.')
                    pedido.delete()
                    return redirect('pedido_teste')
                except ValueError as e:
                    messages.error(request, str(e))
                    pedido.delete()
                    return redirect('pedido_teste')

            # Processa serviços
            for idx, servico_id in enumerate(servicos_ids):
                if not servico_id:
                    continue
                try:
                    servico = Servicos.objects.get(id=servico_id)
                    quantidade = Decimal(quantidades_servicos[idx].replace(',', '.')) if idx < len(
                        quantidades_servicos) and quantidades_servicos[idx] else Decimal('1.00')
                    preco_str = precos_servicos[idx].replace(',', '.') if idx < len(
                        precos_servicos) and precos_servicos[idx] else str(servico.preco)
                    preco_unitario = Decimal(preco_str)

                    if quantidade < 1:
                        raise ValueError(
                            f"Quantidade inválida para {servico.nome}.")
                    if preco_unitario <= 0:
                        raise ValueError(
                            f"Preço unitário inválido para {servico.nome}.")

                    subtotal = preco_unitario * quantidade
                    valor_total += subtotal

                    ItemServico.objects.create(
                        pedido=pedido,
                        servico_id=servico,
                        descricao=servico.nome,
                        quantidade=quantidade,
                        preco_unitario=preco_unitario
                    )
                except Servicos.DoesNotExist:
                    messages.error(
                        request, f'Serviço com ID {servico_id} não encontrado.')
                    pedido.delete()
                    return redirect('pedido_teste')
                except ValueError as e:
                    messages.error(request, str(e))
                    pedido.delete()
                    return redirect('pedido_teste')

            # Aplica juros
            valor_juros = (valor_total * juros_decimal) / Decimal('100')
            total_com_juros = valor_total + valor_juros

            # Aplica desconto
            if desconto_decimal > 0:
                desconto_valor = (total_com_juros *
                                  desconto_decimal) / Decimal('100')
                valor_total = total_com_juros - desconto_valor
            else:
                valor_total = total_com_juros

            pedido.valor_total = valor_total
            pedido.save()

            resumo_itens = resumir_itens_pedido(pedido)
            registrar_log(
                request,
                'pedido',
                'Pedido de Venda',
                f'Pedido #{pedido.id} | Cliente: {cliente.nome} | Status: {pedido.status} | Total: R$ {formatar_valor_log(valor_total)} | Itens: {resumo_itens}'
            )

            # Gera Movimento Financeiro
            if condicao_pagamento:
                numero_parcelas = condicao_pagamento.numero_parcelas
                intervalo_dias = condicao_pagamento.intervalo_dias
                tem_entrada = condicao_pagamento.entrada
                total_parcelas = numero_parcelas + 1 if tem_entrada else numero_parcelas
                hoje = date.today()
                parcelas = []

                if tem_entrada:
                    valor_parcela = (
                        valor_total / total_parcelas).quantize(Decimal('0.01'))
                    parcelas.append({
                        'descricao': f'Entrada do Pedido {pedido.id}',
                        'data_vencimento': hoje,
                        'parcela': 0,
                        'valor': valor_parcela
                    })
                else:
                    valor_parcela = (
                        valor_total / numero_parcelas).quantize(Decimal('0.01'))

                for i in range(1, numero_parcelas + 1):
                    vencimento = hoje + \
                        timedelta(days=intervalo_dias *
                                  (i - (0 if tem_entrada else 1)))
                    parcelas.append({
                        'descricao': f'Parcela {i}/{numero_parcelas} do Pedido {pedido.id}',
                        'data_vencimento': vencimento,
                        'parcela': i,
                        'valor': valor_parcela
                    })

                for p in parcelas:
                    MovimentoFinanceiro.objects.create(
                        empresa=pedido.empresa,
                        pedido=pedido,
                        descricao=p['descricao'],
                        parcela=p['parcela'],
                        total_parcelas=total_parcelas,
                        condicao_id=condicao_pagamento,
                        valor_parcela=p['valor'],
                        data_vencimento=p['data_vencimento']
                    )

            messages.success(
                request, f'Pedido {pedido.id} cadastrado com sucesso!')
            return redirect('pedido_teste')

        except Exception as e:
            messages.error(request, f'Erro ao cadastrar pedido: {str(e)}')
            return redirect('pedido_teste')

    return render(request, 'pedidos_teste.html', {
        'clientes': clientes,
        'condicoes_pagamento': condicoes_pagamento,
        'produtos': produtos,
        'servicos': servicos,
        'acompanhamentos_ativos': acompanhamentos_ativos,
    })


def buscar_produtos(request):
    term = request.GET.get('term', '')
    produtos = Produto.objects.filter(
        nome__icontains=term, eh_servico=False)[:10]
    return JsonResponse([
        {
            'id': p.id,
            'nome': p.nome,
            'preco': str(p.preco),
            'unidade_medida': p.unidade_medida,
            'unidade_label': p.get_unidade_medida_display(),
        }
        for p in produtos
    ], safe=False)


def buscar_servicos(request):
    term = request.GET.get('term', '')
    servicos = Servicos.objects.filter(nome__icontains=term)[:10]
    return JsonResponse([{'id': s.id, 'nome': s.nome, 'preco': str(s.preco)} for s in servicos], safe=False)


# -- Imprimir pedido pela lista de pedidos --

class PedidoImprimirView(DetailView):
    model = Pedido
    template_name = 'pedido_imprimir.html'
    context_object_name = 'pedido'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pedido = self.get_object()

        # Produtos
        itens_produto = pedido.itens.select_related('produto').all()
        produtos = [
            {
                'id': item.produto.id if item.produto else item.id,
                'tipo': 'Produto',
                'nome': item.produto.nome if item.produto else item.descricao or 'Sem nome',
                'descricao': item.produto.descricao if item.produto and item.produto.descricao else item.descricao or 'Sem descrição',
                'quantidade': item.quantidade,
                'preco_unitario': item.preco_unitario,
                'subtotal': item.quantidade * item.preco_unitario,
            }
            for item in itens_produto
        ]

        # Serviços
        itens_servico = pedido.itens_servico.select_related('servico_id').all()
        servicos = [
            {
                'id': item.servico_id.id if item.servico_id else item.id,
                'tipo': 'Serviço',
                'nome': item.servico_id.nome if item.servico_id else 'Sem nome',
                'descricao': 'Sem descrição',
                'quantidade': item.quantidade,
                'preco_unitario': item.preco_unitario,
                'subtotal': item.quantidade * item.preco_unitario,
            }
            for item in itens_servico
        ]

        # Combina
        context['itens'] = produtos + servicos

        # Calcula total sem desconto
        total_sem_desconto = sum(item['subtotal'] for item in context['itens'])

        # Calcula juros
        valor_juros = (total_sem_desconto * pedido.juros) / Decimal('100')
        total_com_juros = total_sem_desconto + valor_juros

        # Calcula desconto
        valor_desconto = (total_com_juros *
                          pedido.desconto_percentual) / Decimal('100')

        # Adiciona ao contexto
        context['valor_desconto'] = valor_desconto
        context['valor_juros'] = valor_juros
        context['valor_total'] = total_com_juros - valor_desconto

        # Observações
        context['observacoes'] = pedido.observacoes
        context['data_hora_impressao'] = timezone.now()

        # Empresa
        empresa = get_empresa_ativa(self.request) or Empresa.objects.first()
        if empresa:
            empresa_dict = {
                "nome": empresa.nome,
                "cnpj": empresa.cnpj,
                "endereco": empresa.endereco,
                "telefone": empresa.telefone,
                "email": empresa.email,
                "logo": None
            }
            if empresa.logo:
                value = empresa.logo
                if isinstance(value, memoryview):
                    value = value.tobytes()
                if isinstance(value, str):
                    value = value.encode()
                empresa_dict["logo"] = base64.b64encode(value).decode()
            context["empresa"] = empresa_dict

        return context


# cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)
#     data = models.DateTimeField(auto_now_add=True)
#     condicao_pagamento = models.ForeignKey(CondicaoPagamento, on_delete=models.SET_NULL, null=True, blank=True)
#     observacoes = models.TextField(blank=True, null=True)
#     status

@login_required
def lista_financeiro(request):
    financeiro = filtrar_queryset_empresa(
        request,
        MovimentoFinanceiro.objects.select_related(
            'pedido__cliente', 'pedido_compra__fornecedor', 'condicao_id'
        ).all()
    )

    # Filtros
    status_filtro = request.GET.get('status')
    cliente_fornecedor_filtro = request.GET.get('cliente_fornecedor')
    pedido_filtro = request.GET.get('pedido')
    tipo_pedido_filtro = request.GET.get('tipo_pedido')
    condicao_filtro = request.GET.get('condicao')
    descricao_filtro = request.GET.get('descricao')
    data_inicio = request.GET.get('data_inicio')
    data_fim = request.GET.get('data_fim')

    # Aplica filtros
    if status_filtro == 'aberto':
        financeiro = financeiro.filter(
            pago=False, data_vencimento__gte=date.today())
    elif status_filtro == 'vencido':
        financeiro = financeiro.filter(
            pago=False, data_vencimento__lt=date.today())
    elif status_filtro == 'pago':
        financeiro = financeiro.filter(pago=True)

    if cliente_fornecedor_filtro:
        financeiro = financeiro.filter(
            Q(pedido__cliente__id=cliente_fornecedor_filtro) |
            Q(pedido_compra__fornecedor__id=cliente_fornecedor_filtro)
        )
    if pedido_filtro:
        financeiro = financeiro.filter(
            Q(pedido__id=pedido_filtro) |
            Q(pedido_compra__id=pedido_filtro)
        )
    if tipo_pedido_filtro == 'venda':
        financeiro = financeiro.filter(pedido__isnull=False)
    elif tipo_pedido_filtro == 'compra':
        financeiro = financeiro.filter(pedido_compra__isnull=False)
    if condicao_filtro:
        financeiro = financeiro.filter(condicao_id__id=condicao_filtro)
    if descricao_filtro:
        financeiro = financeiro.filter(descricao__icontains=descricao_filtro)
    if data_inicio:
        financeiro = financeiro.filter(data_vencimento__gte=data_inicio)
    if data_fim:
        financeiro = financeiro.filter(data_vencimento__lte=data_fim)

    # Ordenação dinâmica
    order_by = request.GET.get('order_by', 'data_vencimento')
    direction = request.GET.get('direction', 'asc')
    if direction == 'desc':
        order_by = f'-{order_by}'
    financeiro = financeiro.order_by(order_by)

    # Dados para o template
    clientes = Cliente.objects.all()
    fornecedores = Fornecedor.objects.all()
    condicoes = CondicaoPagamento.objects.all()

    return render(request, 'financeiro_lista.html', {
        'financeiro': financeiro,
        'status_filtro': status_filtro,
        'cliente_fornecedor_filtro': cliente_fornecedor_filtro,
        'pedido_filtro': pedido_filtro,
        'tipo_pedido_filtro': tipo_pedido_filtro,
        'condicao_filtro': condicao_filtro,
        'descricao_filtro': descricao_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'clientes': clientes,
        'fornecedores': fornecedores,
        'condicoes': condicoes,
        'today': date.today(),
        'order_by': order_by.lstrip('-'),
        'direction': direction,
    })


@login_required
def pagar_parcela(request, id):
    parcela = get_object_or_404(MovimentoFinanceiro, id=id)
    pago_antes = parcela.pago
    data_pagamento_antes = parcela.data_pagamento
    parcela.pago = True
    parcela.data_pagamento = date.today()
    parcela.save()

    registrar_log(
        request,
        'financeiro',
        'Parcela',
        f'Parcela #{parcela.id} | Pedido: {parcela.pedido_id or "-"} | Pago: {pago_antes} -> {parcela.pago} | Data pagamento: {data_pagamento_antes or "-"} -> {parcela.data_pagamento} | Valor: R$ {formatar_valor_log(parcela.valor_parcela)}'
    )
    messages.success(
        request, f'Parcela {parcela.descricao} marcada como paga.')
    return redirect('lista_financeiro')


@login_required
def editar_movimento_financeiro(request, id):
    movimento = get_object_or_404(
        filtrar_queryset_empresa(request, MovimentoFinanceiro.objects.all()),
        id=id,
    )
    if request.method == 'POST':
        form = MovimentoFinanceiroForm(request.POST, instance=movimento)
        if form.is_valid():
            movimento_atualizado = form.save()
            registrar_log(
                request,
                'editar',
                'Movimento Financeiro',
                f'Movimento #{movimento_atualizado.id} editado | '
                f'Vencimento: {movimento_atualizado.data_vencimento} | '
                f'Valor: R$ {formatar_valor_log(movimento_atualizado.valor_parcela)}'
            )
            messages.success(
                request, 'Movimento financeiro atualizado com sucesso.')
            return redirect('lista_financeiro')
    else:
        form = MovimentoFinanceiroForm(instance=movimento)
    return render(request, 'financeiro_editar.html', {
        'form': form,
        'movimento': movimento,
    })


@login_required
def imprimir_financeiro(request):
    financeiro = MovimentoFinanceiro.objects.select_related(
        'pedido__cliente', 'condicao_id').all().order_by('data_vencimento')

    # Copia os filtros da lista
    status_filtro = 'Todos' if request.GET.get(
        'status') in [None, '', 'None'] else request.GET.get('status')
    cliente_filtro = request.GET.get('cliente') or None
    pedido_filtro = request.GET.get('pedido') or None
    condicao_filtro = request.GET.get('condicao') or None
    descricao_filtro = request.GET.get('descricao') or None
    data_inicio = request.GET.get('data_inicio') or None
    data_fim = request.GET.get('data_fim') or None

    # Converte 'None' (string) para None e strings de data para datetime.date
    if cliente_filtro == 'None':
        cliente_filtro = None
    if pedido_filtro == 'None':
        pedido_filtro = None
    if condicao_filtro == 'None':
        condicao_filtro = None
    if descricao_filtro == 'None':
        descricao_filtro = None
    if data_inicio == 'None':
        data_inicio = None
    if data_fim == 'None':
        data_fim = None

    # Converte strings de data para datetime.date
    if data_inicio and data_inicio != '':
        try:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        except ValueError:
            data_inicio = None
    if data_fim and data_fim != '':
        try:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        except ValueError:
            data_fim = None

    # Aplica filtros
    if status_filtro == 'aberto':
        financeiro = financeiro.filter(
            pago=False, data_vencimento__gte=date.today())
    elif status_filtro == 'vencido':
        financeiro = financeiro.filter(
            pago=False, data_vencimento__lt=date.today())
    elif status_filtro == 'pago':
        financeiro = financeiro.filter(pago=True)

    if cliente_filtro:
        financeiro = financeiro.filter(pedido__cliente__id=cliente_filtro)
    if pedido_filtro:
        financeiro = financeiro.filter(pedido__id=pedido_filtro)
    if condicao_filtro:
        financeiro = financeiro.filter(condicao_id__id=condicao_filtro)
    if descricao_filtro:
        financeiro = financeiro.filter(descricao__icontains=descricao_filtro)
    if data_inicio:
        financeiro = financeiro.filter(data_vencimento__gte=data_inicio)
    if data_fim:
        financeiro = financeiro.filter(data_vencimento__lte=data_fim)

    # Calcula os totais
    total_geral = financeiro.aggregate(Sum('valor_parcela'))[
        'valor_parcela__sum'] or 0
    total_pago = financeiro.filter(pago=True).aggregate(
        Sum('valor_parcela'))['valor_parcela__sum'] or 0
    total_vencido = financeiro.filter(pago=False, data_vencimento__lt=date.today(
    )).aggregate(Sum('valor_parcela'))['valor_parcela__sum'] or 0
    total_aberto = financeiro.filter(pago=False, data_vencimento__gte=date.today(
    )).aggregate(Sum('valor_parcela'))['valor_parcela__sum'] or 0

    # Dados para o template
    clientes = Cliente.objects.all()
    condicoes = CondicaoPagamento.objects.all()

    return render(request, 'imprimir_financeiro.html', {
        'financeiro': financeiro,
        'status_filtro': status_filtro,
        'cliente_filtro': cliente_filtro,
        'pedido_filtro': pedido_filtro,
        'condicao_filtro': condicao_filtro,
        'descricao_filtro': descricao_filtro,
        'data_inicio': data_inicio,
        'data_fim': data_fim,
        'clientes': clientes,
        'condicoes': condicoes,
        'today': date.today(),
        'data_hora_impressao': timezone.now(),
        'total_geral': total_geral,
        'total_pago': total_pago,
        'total_vencido': total_vencido,
        'total_aberto': total_aberto,
    })


def relatorio_pedidos(request):
    pedidos = Pedido.objects.all()

    # Captura dos filtros GET
    id_inicial = request.GET.get('id_inicial')
    id_final = request.GET.get('id_final')
    filtro_cliente = request.GET.get('cliente', '')
    filtro_status = request.GET.get('status')

    # Aplicando filtros
    if id_inicial:
        pedidos = pedidos.filter(id__gte=id_inicial)
    if id_final:
        pedidos = pedidos.filter(id__lte=id_final)
    if filtro_cliente:
        pedidos = pedidos.filter(cliente__nome__icontains=filtro_cliente)
    if filtro_status:
        pedidos = pedidos.filter(status=filtro_status)

    # Ordenação
    ordenacao = request.GET.get('ordenacao', '-id')

    # Lista de campos permitidos para evitar FieldError
    ordenacoes_validas = [
        'id', '-id',
        'cliente__nome', '-cliente__nome',
        'data', '-data',
        'status', '-status',
        'valor_total', '-valor_total',
        'desconto_percentual', '-desconto_percentual'
    ]

    if ordenacao not in ordenacoes_validas:
        ordenacao = '-id'  # fallback seguro

    pedidos = pedidos.order_by(ordenacao)

    # Calcular lucro total para cada pedido e o total geral
    pedidos_com_lucro = []
    total_geral = Decimal('0')

    for pedido in pedidos:
        lucro_total = Decimal('0')

        # === Itens de produto ===
        for item in pedido.itens.all():
            venda = Decimal(str(item.preco_unitario)) * \
                Decimal(str(item.quantidade))
            custo = Decimal(str(item.produto.valor_pago or 0)
                            ) * Decimal(str(item.quantidade))
            lucro_total += venda - custo

        # === Itens de serviço ===
        for servico in pedido.itens_servico.all():
            # Serviço não tem "custo", então lucro é igual ao valor total do serviço
            lucro_total += Decimal(str(servico.preco_unitario)) * \
                Decimal(str(servico.quantidade))

        # Aplicar desconto percentual no lucro
        if pedido.desconto_percentual:
            lucro_total = lucro_total * \
                (Decimal('1') - Decimal(str(pedido.desconto_percentual)) / Decimal('100'))

        total_geral += lucro_total

        pedidos_com_lucro.append({
            'pedido': pedido,
            'lucro_total': lucro_total
        })

    contexto = {
        'pedidos': pedidos_com_lucro,
        'id_inicial': id_inicial,
        'id_final': id_final,
        'filtro_cliente': filtro_cliente,
        'filtro_status': filtro_status,
        'data_atual': timezone.now().strftime('%d/%m/%Y %H:%M'),
        'quantidade_registros': len(pedidos_com_lucro),
        'total_geral': total_geral,
        'ordenacao': ordenacao,
    }

    return render(request, 'relatorio_pedidos.html', contexto)


@login_required
@permission_required('loja_web.editar_config', raise_exception=True)
def configuracao_empresa(request):
    empresa = get_empresa_ativa(request) or Empresa.objects.first()
    if not empresa:
        empresa = Empresa.objects.create(nome="Minha Empresa")
    if request.user.is_authenticated:
        UsuarioEmpresa.objects.get_or_create(
            user=request.user,
            empresa=empresa,
            defaults={'ativo': True, 'padrao': True}
        )
        request.session[TENANT_SESSION_KEY] = empresa.id

    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            form.save()
            return redirect("config_empresa")  # nome da rota
    else:
        form = EmpresaForm(instance=empresa)

    return render(request, "config_empresa.html", {"form": form})


def api_servicos(request):
    busca = request.GET.get('q', '').strip()
    servicos = filtrar_queryset_empresa(
        request, Produto.objects.filter(eh_servico=True)
    )
    if busca:
        servicos = servicos.filter(
            nome__icontains=busca) | servicos.filter(id__iexact=busca)
    resultados = [{'id': s.id, 'nome': s.nome,
                   'preco': str(s.preco)} for s in servicos]
    return JsonResponse(resultados, safe=False)


@login_required
# `venda-direta/` should behave exactly like nova_venda so that the template
# receives clientes, condicoes, cliente_padrao and carries out all the
# POST/add-item logic.  Instead of duplicating code we simply delegate to
# the existing view.  Keeping the same URL (mercado) is important for links
# that may already point here.
def mercado_view(request):
    # delegate to nova_venda, which already handles both GET and POST
    return nova_venda(request)


@login_required
def busca_produtosVenda(request):

    term = request.GET.get('term', '').strip()

    if not term:
        return JsonResponse({'error': 'Termo de busca vazio'}, status=400)

    try:

        if term.isdigit():

            produtos = Produto.objects.filter(
                Q(id=term) | Q(nome__icontains=term)
            )

        else:

            produtos = Produto.objects.filter(
                nome__icontains=term
            )

        data = [

            {
                'id': p.id,
                'nome': p.nome,
                'preco': float(p.preco),
                'valor_pago': float(p.valor_pago),
                'garantia_dias': p.garantia_dias,
                'estoque': p.estoque,
                'marca': p.marca or '',
                'unidade_medida': p.unidade_medida,
                'unidade_label': p.get_unidade_medida_display(),
            }

            for p in produtos[:10]

        ]

        return JsonResponse(data, safe=False)

    except Exception as e:

        return JsonResponse({'error': str(e)}, status=500)


def busca_condicoes_pagamento(request):
    try:
        condicoes = CondicaoPagamento.objects.all()
        data = [{'id': c.id, 'nome': c.nome} for c in condicoes]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def busca_clientes(request):
    term = request.GET.get('term', '').strip()
    clientes = Cliente.objects.filter(nome__icontains=term)[:10]
    data = [{'id': c.id, 'nome': c.nome} for c in clientes]
    return JsonResponse(data, safe=False)


@login_required
def nova_venda(request):

    # 🔹 Criar nova venda manual
    if request.GET.get('nova'):
        request.session.pop('carrinho_venda', None)
        request.session.pop('venda_id', None)

    # 🛒 Carrinho
    carrinho = request.session.get('carrinho_venda', [])

    # 🔎 Venda atual
    venda_id = request.session.get('venda_id')
    venda_atual = None

    if venda_id:
        try:
            venda_atual = Venda.objects.get(id=venda_id)
        except Venda.DoesNotExist:
            venda_atual = None

    # 🔧 Cliente padrão
    cliente_id = request.POST.get('cliente') or 1

    try:
        cliente_padrao = Cliente.objects.get(id=cliente_id)
    except Cliente.DoesNotExist:

        cliente_padrao = Cliente.objects.filter(
            nome__icontains='consumidor'
        ).first()

        if not cliente_padrao:
            cliente_padrao = Cliente.objects.create(
                nome='Consumidor',
                endereco='',
                telefone='',
                email=''
            )

    # 🔧 Condição padrão
    try:
        condicao_padrao = CondicaoPagamento.objects.get(id=1)
    except CondicaoPagamento.DoesNotExist:
        condicao_padrao = CondicaoPagamento.objects.first()

    # 📄 Formulário
    if request.method == 'POST':
        venda_form = VendaForm(request.POST)
    else:
        venda_form = VendaForm(initial={
            'cliente': cliente_padrao.id,
            'condicao_pagamento': condicao_padrao.id
        })

    # 🔹 Criar venda se não existir
    if not venda_atual:
        venda_atual = Venda.objects.create(
            cliente=cliente_padrao
        )

        request.session['venda_id'] = venda_atual.id

    # ❌ CANCELAR VENDA
    if request.method == 'POST' and 'cancelar_venda' in request.POST:
        request.session.pop('carrinho_venda', None)
        request.session.pop('venda_id', None)
        request.session.modified = True
        messages.info(request, "Venda cancelada.")
        return redirect('nova_venda')

    # ➕ ADICIONAR ITEM
    if request.method == 'POST' and 'adicionar_item' in request.POST:

        try:

            produto_id = int(request.POST.get('produto_id'))
            quantidade = float(request.POST.get('quantidade', 1))
            preco = float(request.POST.get('preco_produto'))

            if quantidade <= 0:
                return JsonResponse({'error': 'Quantidade deve ser maior que zero.'}, status=400)

            if preco < 0:
                return JsonResponse({'error': 'Preco invalido.'}, status=400)

            produto = Produto.objects.get(id=produto_id)

            if produto.unidade_medida == Produto.UNIDADE and quantidade != int(quantidade):
                return JsonResponse({'error': f'O produto {produto.nome} usa unidade (un) e só aceita quantidade inteira.'}, status=400)

            # Processar acompanhamentos (sorveteria)
            acomp_payload = request.POST.get('acompanhamentos_json', '[]')
            try:
                acomps_raw = json.loads(acomp_payload or '[]')
            except json.JSONDecodeError:
                acomps_raw = []

            acomp_details = []
            acomp_total = 0.0
            for a in acomps_raw:
                acomp_obj = Acompanhamento.objects.filter(
                    id=a.get('id'), ativo=True
                ).first()
                if acomp_obj:
                    qtd = max(1, int(a.get('qtd', 1) or 1))
                    acomp_details.append({
                        'id': str(acomp_obj.id),
                        'nome': acomp_obj.nome,
                        'preco': float(acomp_obj.preco),
                        'qtd': qtd,
                    })
                    acomp_total += float(acomp_obj.preco) * qtd

            item = {
                'id': str(uuid.uuid4()),
                'produto_id': produto.id,
                'nome': produto.nome,
                'quantidade': quantidade,
                'preco': preco,
                'custo': float(produto.valor_pago),
                'garantia_dias': produto.garantia_dias,
                'total': preco * quantidade + acomp_total,
                'eh_servico': produto.eh_servico,
                'acompanhamentos': acomp_details,
            }

            # Só agrega itens iguais quando não há acompanhamentos
            produto_existe = False
            if not acomp_details:
                for i in carrinho:
                    if i['produto_id'] == produto.id and not i.get('acompanhamentos'):
                        i['quantidade'] += quantidade
                        i['total'] = i['quantidade'] * i['preco']
                        produto_existe = True
                        break

            if not produto_existe:
                carrinho.append(item)

            request.session['carrinho_venda'] = carrinho
            request.session.modified = True

            valor_total = sum(i['total'] for i in carrinho)

            return JsonResponse({
                'success': True,
                'carrinho': carrinho,
                'valor_total': valor_total
            })

        except Produto.DoesNotExist:
            return JsonResponse({'error': 'Produto não encontrado'}, status=400)

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    # ❌ REMOVER ITEM
    if request.method == 'POST' and 'remover_item' in request.POST:

        item_id = request.POST.get('remover_item')

        carrinho = [i for i in carrinho if i['id'] != item_id]

        request.session['carrinho_venda'] = carrinho
        request.session.modified = True

        valor_total = sum(i['total'] for i in carrinho)

        return JsonResponse({
            'success': True,
            'carrinho': carrinho,
            'valor_total': valor_total
        })

    # 💾 FINALIZAR VENDA
    if request.method == 'POST' and 'salvar_venda' in request.POST:

        carrinho = request.session.get('carrinho_venda', [])

        if not carrinho:
            messages.error(request, "Adicione itens à venda.")
            return redirect('nova_venda')

        if not venda_form.is_valid():
            messages.error(request, "Preencha os dados da venda.")
            return redirect('nova_venda')

        cliente_final_id = request.POST.get('cliente')
        cliente_final = Cliente.objects.filter(
            id=cliente_final_id).first() if cliente_final_id else None

        if not cliente_final:
            cliente_final = cliente_padrao

        try:

            with transaction.atomic():

                # 🔎 Verifica estoque
                for item in carrinho:

                    if not item['eh_servico']:

                        produto = Produto.objects.select_for_update().get(
                            id=item['produto_id']
                        )

                        if produto.estoque < item['quantidade']:

                            messages.error(
                                request,
                                f"Estoque insuficiente para {produto.nome}. "
                                f"Disponível: {produto.estoque_exibicao}"
                            )

                            return redirect('nova_venda')

                # 🧾 Atualiza venda atual
                venda = venda_atual

                venda.cliente = cliente_final.nome
                venda.condicao_pagamento = venda_form.cleaned_data['condicao_pagamento']
                venda.valortotal = sum(i['total'] for i in carrinho)
                venda.save()

                # 📦 Cria itens
                for item in carrinho:

                    produto = Produto.objects.select_for_update().get(
                        id=item['produto_id']
                    )

                    ItemVenda.objects.create(
                        venda=venda,
                        produto=produto,
                        quantidade=item['quantidade'],
                        preco_unitario=item['preco'],
                        garantia_dias=item.get(
                            'garantia_dias', produto.garantia_dias or 0),
                    )

                    if not produto.eh_servico:
                        produto.estoque -= item['quantidade']
                        produto.save()

                # 🧹 Limpar sessão
                request.session.pop('carrinho_venda', None)
                request.session.pop('venda_id', None)
                request.session.modified = True

                messages.success(
                    request,
                    f"Venda {venda.id} finalizada com sucesso."
                )

                return redirect('nova_venda')

        except Exception as e:

            messages.error(
                request,
                f"Erro ao finalizar venda: {str(e)}"
            )

            return redirect('nova_venda')

    # 📊 Totais
    valor_total = sum(i['total'] for i in carrinho)
    custo_total = sum(i['custo'] * i['quantidade'] for i in carrinho)

    clientes = Cliente.objects.all().order_by('nome')
    condicoes = CondicaoPagamento.objects.all()

    context = {
        'venda_form': venda_form,
        'clientes': clientes,
        'condicoes': condicoes,
        'cliente_padrao': cliente_padrao,
        'condicao_padrao': condicao_padrao,
        'carrinho': carrinho,
        'valor_total': valor_total,
        'custo_total': custo_total,
        'lucro': valor_total - custo_total,
        'venda_atual': venda_atual,
        'acompanhamentos_ativos': Acompanhamento.objects.filter(ativo=True).order_by('nome'),
    }

    return render(request, 'venda_direta.html', context)


@login_required
def finalizar_venda(request):

    try:
        venda = Venda.objects.latest('id')

        venda.valortotal = sum(
            item.quantidade * item.preco_unitario
            for item in venda.itemvenda_set.all()
        )

        venda.save()

        resumo_itens = ', '.join(
            [f'{item.produto.nome} x{item.quantidade}' for item in venda.itemvenda_set.select_related(
                'produto').all()]
        ) or 'Sem itens'
        registrar_log(
            request,
            'venda',
            'Venda Direta',
            f'Venda #{venda.id} finalizada | Total: R$ {formatar_valor_log(venda.valortotal)} | Itens: {resumo_itens}'
        )
        messages.success(request, f"Venda {venda.id} finalizada com sucesso.")

    except Venda.DoesNotExist:

        messages.error(request, "Nenhuma venda encontrada.")

    return redirect('nova_venda')


@login_required
def encerrar_pedido(request):
    pedido = None
    error_message = None

    if request.method == "POST":
        pedido_id = request.POST.get("pedido_id")
        action = request.POST.get("action")

        if pedido_id:
            try:
                pedido = Pedido.objects.get(id=pedido_id)
                logger.debug(
                    f"Processando ação '{action}' para o pedido {pedido_id}")

                if action == "pagar_parcelas" and "parcelas_pagas_hidden" in request.POST:
                    parcelas_selecionadas = request.POST.get(
                        "parcelas_pagas_hidden").split(",")
                    if not parcelas_selecionadas or parcelas_selecionadas == ['']:
                        return JsonResponse({"status": "error", "message": "Nenhuma parcela selecionada.", "display_alert": True})

                    # Marca as parcelas selecionadas como pagas
                    for parcela in parcelas_selecionadas:
                        try:
                            mov = pedido.financeiros.get(parcela=parcela)
                            if not mov.data_pagamento:
                                mov.data_pagamento = timezone.now()
                                mov.pago = True
                                mov.save()
                                logger.debug(
                                    f"Parcela {parcela} marcada como paga")
                            else:
                                logger.warning(
                                    f"Parcela {parcela} já estava paga")
                        except MovimentoFinanceiro.DoesNotExist:
                            logger.error(f"Parcela {parcela} não encontrada")
                            return JsonResponse({"status": "error", "message": f"Parcela {parcela} não encontrada.", "display_alert": True})

                    # Prepara os dados atualizados das parcelas
                    parcelas = [{
                        "parcela": mov.parcela,
                        "total_parcelas": mov.total_parcelas,
                        "valor_parcela": str(mov.valor_parcela),
                        "data_vencimento": mov.data_vencimento.strftime('%d/%m/%Y'),
                        "data_pagamento": mov.data_pagamento.strftime('%d/%m/%Y') if mov.data_pagamento else None,
                        "pago": mov.pago
                    } for mov in pedido.financeiros.all()]

                    registrar_log(
                        request,
                        'financeiro',
                        'Pedido de Venda',
                        f'Pedido #{pedido.id} | Ação: pagar parcelas | Parcelas: {", ".join(parcelas_selecionadas)}'
                    )

                    return JsonResponse({
                        "status": "success",
                        "message": "Parcelas marcadas como pagas!",
                        "parcelas": parcelas,
                        "desconto_percentual": str(pedido.desconto_percentual),
                        "display_alert": True
                    })

                elif action == "encerrar":
                    # Verifica se há parcelas não pagas
                    parcelas_nao_pagas = pedido.financeiros.filter(pago=False)
                    if parcelas_nao_pagas.exists():
                        logger.debug(
                            f"Marcando {parcelas_nao_pagas.count()} parcelas como pagas")
                        for mov in parcelas_nao_pagas:
                            mov.data_pagamento = timezone.now()
                            mov.pago = True
                            mov.save()
                            logger.debug(
                                f"Parcela {mov.parcela} marcada como paga")

                    # Atualiza o status do pedido
                    pedido.status = "concluido"
                    pedido.save()
                    logger.debug(f"Pedido {pedido_id} marcado como concluído")

                    # Prepara os dados atualizados das parcelas
                    parcelas = [{
                        "parcela": mov.parcela,
                        "total_parcelas": mov.total_parcelas,
                        "valor_parcela": str(mov.valor_parcela),
                        "data_vencimento": mov.data_vencimento.strftime('%d/%m/%Y'),
                        "data_pagamento": mov.data_pagamento.strftime('%d/%m/%Y') if mov.data_pagamento else None,
                        "pago": mov.pago
                    } for mov in pedido.financeiros.all()]

                    registrar_log(
                        request,
                        'pedido',
                        'Pedido de Venda',
                        f'Pedido #{pedido.id} | Status: aberto -> {pedido.status} | Parcelas pendentes quitadas: {parcelas_nao_pagas.count()}'
                    )

                    return JsonResponse({
                        "status": "success",
                        "message": "Pedido concluído com sucesso! Todas as parcelas foram marcadas como pagas.",
                        "parcelas": parcelas,
                        "desconto_percentual": str(pedido.desconto_percentual),
                        "pedido_status": pedido.status,
                        "display_alert": True
                    })

            except Pedido.DoesNotExist:
                logger.error(f"Pedido {pedido_id} não encontrado")
                error_message = f"Pedido {pedido_id} não encontrado. Verifique o código e tente novamente."
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({"status": "error", "message": error_message, "display_alert": True})
                messages.error(request, error_message)

    return render(request, "encerrar_pedidos.html", {"pedido": pedido, "error_message": error_message})


@login_required
def relatorio_clientes(request):
    # Obtém os parâmetros de filtro da query string
    nome = request.GET.get('nome', '')
    telefone = request.GET.get('telefone', '')
    cidade = request.GET.get('cidade', '')

    # Filtra os clientes com base nos parâmetros
    clientes = filtrar_queryset_empresa(request, Cliente.objects.all())

    if nome:
        clientes = clientes.filter(nome__icontains=nome)
    if telefone:
        clientes = clientes.filter(telefone__icontains=telefone)
    if cidade:
        clientes = clientes.filter(cidade__icontains=cidade)

    # Passa os dados para o template
    return render(request, 'relatorios_clientes.html', {
        'clientes': clientes,
        'request': request  # Para manter os valores dos filtros no template
    })


@login_required
def relatorio_clientes_imprimir(request):
    nome = request.GET.get('nome', '')
    telefone = request.GET.get('telefone', '')
    cidade = request.GET.get('cidade', '')

    clientes = filtrar_queryset_empresa(request, Cliente.objects.all())

    if nome:
        clientes = clientes.filter(nome__icontains=nome)
    if telefone:
        clientes = clientes.filter(telefone__icontains=telefone)
    if cidade:
        clientes = clientes.filter(cidade__icontains=cidade)

    return render(request, 'relatorio_clientes_imprimir.html', {
        'clientes': clientes
    })

# @login_required
# def fechamento_caixa(request):
#     data_selecionada = None
#     if request.method == 'POST':
#         if 'abrir' in request.POST:
#             try:
#                 saldo_inicial = Decimal(request.POST.get('saldo_inicial', '0.00'))
#                 if saldo_inicial < 0:
#                     messages.error(request, 'Saldo inicial não pode ser negativo.')
#                 else:
#                     FechamentoCaixa.objects.create(saldo_inicial=saldo_inicial, user=request.user)
#                     messages.success(request, 'Caixa aberto com sucesso!')
#             except ValueError:
#                 messages.error(request, 'Saldo inicial inválido.')
#             return redirect('fechamento_caixa')

#         if 'fechar' in request.POST:
#             caixa = FechamentoCaixa.objects.filter(caixa_aberto=True).last()
#             if caixa:
#                 try:
#                     saldo_fisico = Decimal(request.POST.get('saldo_fisico', '0.00'))
#                     observacoes = request.POST.get('observacoes', '')
#                     data_selecionada = request.POST.get('data_selecionada')
#                     data_selecionada = datetime.strptime(data_selecionada, '%Y-%m-%d').date() if data_selecionada else None
#                     if saldo_fisico < 0:
#                         messages.error(request, 'Saldo físico não pode ser negativo.')
#                     else:
#                         caixa.fechar_caixa(saldo_fisico, observacoes, data_selecionada)
#                         messages.success(request, 'Caixa fechado com sucesso!')
#                 except ValueError as e:
#                     messages.error(request, str(e) or 'Saldo físico inválido.')
#             else:
#                 messages.error(request, 'Nenhum caixa aberto encontrado.')
#             return redirect('fechamento_caixa')

#         if 'filtrar' in request.POST:
#             data_selecionada = request.POST.get('data_selecionada')
#             try:
#                 data_selecionada = datetime.strptime(data_selecionada, '%Y-%m-%d').date() if data_selecionada else None
#             except ValueError:
#                 messages.error(request, 'Data inválida.')
#                 data_selecionada = None

#     caixa_ativo = FechamentoCaixa.objects.filter(caixa_aberto=True).first()
#     if caixa_ativo:
#         caixa_ativo.atualizar_totais(data_selecionada=data_selecionada)
#         data_inicio = timezone.datetime.combine(data_selecionada, timezone.datetime.min.time()) if data_selecionada else caixa_ativo.data_abertura
#         data_fim = timezone.datetime.combine(data_selecionada, timezone.datetime.max.time()) if data_selecionada else (caixa_ativo.data_fechamento or timezone.now())
#         pedidos_periodo = Pedido.objects.filter(
#             status='concluido',
#             data__range=[data_inicio, data_fim]
#         )
#         entradas_periodo = MovimentoFinanceiro.objects.filter(
#             pago=True,
#             data_pagamento__range=[data_inicio, data_fim]
#         )
#         saidas_periodo = SaidaFinanceira.objects.filter(
#             caixa=caixa_ativo,
#             data__range=[data_inicio, data_fim]
#         )
#     else:
#         pedidos_periodo = []
#         entradas_periodo = []
#         saidas_periodo = []
#         data_selecionada = None

#     fechamentos = FechamentoCaixa.objects.all().order_by('-data_abertura')

#     return render(request, 'fechamento_caixa.html', {
#         'caixa_ativo': caixa_ativo,
#         'fechamentos': fechamentos,
#         'pedidos_periodo': pedidos_periodo,
#         'entradas_periodo': entradas_periodo,
#         'saidas_periodo': saidas_periodo,
#         'data_selecionada': data_selecionada,
#     })


@login_required
def fechamento_caixa(request):
    LIMITE_ALERTA_DIVERGENCIA_CAIXA = Decimal('50.00')
    caixa_ativo = FechamentoCaixa.objects.filter(
        caixa_aberto=True,
        user=request.user
    ).order_by('-data_abertura').first()

    if request.method == 'POST':
        if 'abrir' in request.POST:
            try:
                with transaction.atomic():
                    caixa_ativo = FechamentoCaixa.objects.select_for_update().filter(
                        caixa_aberto=True,
                        user=request.user
                    ).order_by('-data_abertura').first()

                    if caixa_ativo:
                        registrar_log(
                            request,
                            'caixa',
                            'Caixa',
                            'Tentativa de abrir caixa com caixa já aberto para o usuário.'
                        )
                        messages.warning(
                            request, 'Ja existe um caixa aberto para este usuário. Feche o caixa atual antes de abrir outro.')
                        return redirect('fechamento_caixa')

                    saldo_inicial = Decimal(
                        request.POST.get('saldo_inicial', '0.00'))
                    if saldo_inicial < 0:
                        registrar_log(
                            request,
                            'caixa',
                            'Caixa',
                            f'Tentativa de abrir caixa com saldo inicial negativo: R$ {formatar_valor_log(saldo_inicial)}'
                        )
                        messages.error(
                            request, 'Saldo inicial não pode ser negativo.')
                    else:
                        FechamentoCaixa.objects.create(
                            saldo_inicial=saldo_inicial, user=request.user)
                        registrar_log(
                            request,
                            'caixa',
                            'Caixa',
                            f'Ação: abrir caixa | Saldo inicial: R$ {formatar_valor_log(saldo_inicial)}'
                        )
                        messages.success(request, 'Caixa aberto com sucesso!')
            except (ValueError, InvalidOperation):
                registrar_log(
                    request,
                    'caixa',
                    'Caixa',
                    'Tentativa de abrir caixa com saldo inicial inválido.'
                )
                messages.error(request, 'Saldo inicial inválido.')
            return redirect('fechamento_caixa')

        if 'fechar' in request.POST:
            try:
                with transaction.atomic():
                    caixa = FechamentoCaixa.objects.select_for_update().filter(
                        caixa_aberto=True,
                        user=request.user
                    ).order_by('-data_abertura').first()
                    if caixa:
                        saldo_fisico = Decimal(
                            request.POST.get('saldo_fisico', '0.00'))
                        observacoes = request.POST.get('observacoes', '')

                        if saldo_fisico < 0:
                            registrar_log(
                                request,
                                'caixa',
                                'Caixa',
                                f'Tentativa de fechar caixa com saldo físico negativo: R$ {formatar_valor_log(saldo_fisico)}'
                            )
                            messages.error(
                                request, 'Saldo físico não pode ser negativo.')
                        else:
                            totais = caixa.calcular_totais()
                            diferenca = saldo_fisico - totais['esperado']

                            caixa.fechar_caixa(
                                saldo_fisico, observacoes=observacoes)
                            registrar_log(
                                request,
                                'caixa',
                                'Caixa',
                                f'Ação: fechar caixa | Esperado: R$ {formatar_valor_log(totais["esperado"])} | Físico: R$ {formatar_valor_log(saldo_fisico)} | Diferença: R$ {formatar_valor_log(diferenca)} | Obs: {observacoes or "-"}'
                            )
                            if abs(diferenca) > LIMITE_ALERTA_DIVERGENCIA_CAIXA:
                                registrar_log(
                                    request,
                                    'caixa',
                                    'Caixa',
                                    f'Alerta de divergência alta no fechamento | Caixa #{caixa.id} | Diferença: R$ {formatar_valor_log(diferenca)} | Limite: R$ {formatar_valor_log(LIMITE_ALERTA_DIVERGENCIA_CAIXA)}'
                                )
                            messages.success(
                                request,
                                f"Caixa fechado com sucesso! Diferença apurada: R$ {diferenca:.2f}"
                            )
                    else:
                        registrar_log(
                            request,
                            'caixa',
                            'Caixa',
                            'Tentativa de fechar caixa sem caixa aberto para o usuário.'
                        )
                        messages.error(
                            request, 'Nenhum caixa aberto encontrado para este usuário.')
            except (ValueError, InvalidOperation) as e:
                registrar_log(
                    request,
                    'caixa',
                    'Caixa',
                    f'Tentativa de fechar caixa com saldo físico inválido. Detalhes: {str(e) or "-"}'
                )
                messages.error(request, str(
                    e) or 'Saldo físico inválido.')
            return redirect('fechamento_caixa')

    caixa_ativo = FechamentoCaixa.objects.filter(
        caixa_aberto=True,
        user=request.user
    ).order_by('-data_abertura').first()
    if caixa_ativo:
        # Define o período real do caixa (abertura até agora/fechamento)
        data_inicio = caixa_ativo.data_abertura
        data_fim = caixa_ativo.data_fechamento or timezone.now()
        data_inicio_date = data_inicio.date()
        data_fim_date = data_fim.date()

        pedidos_periodo = Pedido.objects.filter(
            status='concluido',
            data__range=[data_inicio, data_fim]
        )
        entradas_periodo = MovimentoFinanceiro.objects.filter(
            pago=True,
            data_pagamento__range=[data_inicio_date, data_fim_date],
            pedido__isnull=True,
            pedido_compra__isnull=True
        ).filter(
            Q(tipo='RECEITA') | Q(valor_parcela__gt=0)
        )
        saidas_periodo = SaidaFinanceira.objects.filter(
            caixa=caixa_ativo,
            data__range=[data_inicio, data_fim]
        )
        compras_periodo = MovimentoFinanceiro.objects.filter(
            pago=True,
            data_pagamento__range=[data_inicio_date, data_fim_date],
            pedido_compra__isnull=False
        )
        totais_caixa = caixa_ativo.calcular_totais()
    else:
        pedidos_periodo = []
        entradas_periodo = []
        saidas_periodo = []
        compras_periodo = []
        totais_caixa = {
            'vendas': Decimal('0.00'),
            'entradas': Decimal('0.00'),
            'saidas': Decimal('0.00'),
            'esperado': Decimal('0.00'),
        }

    fechamentos = FechamentoCaixa.objects.all().order_by('-data_abertura')
    fechamentos_detalhados = []

    for fechamento in fechamentos:
        totais_fechamento = fechamento.calcular_totais()
        diferenca_fechamento = None

        if fechamento.saldo_final is not None:
            diferenca_fechamento = fechamento.saldo_final - \
                totais_fechamento['esperado']

        fechamentos_detalhados.append({
            'caixa': fechamento,
            'totais': totais_fechamento,
            'diferenca': diferenca_fechamento,
        })

    return render(request, 'fechamento_caixa.html', {
        'caixa_ativo': caixa_ativo,
        'fechamentos': fechamentos,
        'fechamentos_detalhados': fechamentos_detalhados,
        'pedidos_periodo': pedidos_periodo,
        'entradas_periodo': entradas_periodo,
        'saidas_periodo': saidas_periodo,
        'compras_periodo': compras_periodo,
        'totais_caixa': totais_caixa,
    })


@login_required
def visualizar_caixa(request, caixa_id):
    caixa = get_object_or_404(FechamentoCaixa, id=caixa_id)
    registrar_log(
        request,
        'caixa',
        'Caixa',
        f'Visualização de caixa | Caixa #{caixa.id} | Usuário do caixa: {caixa.user.username if caixa.user else "-"}'
    )

    inicio = caixa.data_abertura
    fim = caixa.data_fechamento or timezone.now()

    # Período como date
    inicio_date = inicio.date()
    fim_date = fim.date()

    # Total VENDAS (Pedido)
    total_vendas = Pedido.objects.filter(
        status='concluido',
        data__range=[inicio, fim]
    ).aggregate(total=Sum('valor_total'))['total'] or Decimal('0.00')

    # MOVIMENTOS FINANCEIROS
    movimentos = MovimentoFinanceiro.objects.filter(
        pago=True,
        data_pagamento__range=[inicio_date, fim_date]
    )

    # Entradas: somente movimentos que NÃO são de pedido de compra
    total_entradas = movimentos.filter(
        pedido__isnull=True,
        pedido_compra__isnull=True
    ).filter(
        Q(tipo='RECEITA') | Q(valor_parcela__gt=0)
    ).aggregate(total=Sum('valor_parcela'))['total'] or Decimal('0.00')

    # Saídas financeiras: pedido de compra sempre é saída,
    # além de despesas e valores negativos.
    saidas_financeiras = movimentos.filter(
        Q(pedido_compra__isnull=False) |
        Q(tipo='DESPESA') |
        Q(valor_parcela__lt=0)
    ).values_list('valor_parcela', flat=True)
    total_saidas_financeiras = sum(
        (abs(valor) for valor in saidas_financeiras), Decimal('0.00'))

    total_compras = movimentos.filter(
        pedido_compra__isnull=False
    ).values_list('valor_parcela', flat=True)
    total_compras = sum((abs(valor)
                        for valor in total_compras), Decimal('0.00'))

    # Saídas manuais
    total_saidas_manuais = SaidaFinanceira.objects.filter(
        caixa=caixa,
        data__range=[inicio, fim]
    ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    total_saidas = total_saidas_financeiras + total_saidas_manuais

    saldo_esperado = caixa.saldo_inicial + \
        total_vendas + total_entradas - total_saidas

    context = {
        'caixa': caixa,
        'total_vendas': total_vendas,
        'total_compras': total_compras,
        'total_entradas': total_entradas,
        'total_saidas': total_saidas,
        'saldo_esperado': saldo_esperado,
        'diferenca': (caixa.saldo_final - saldo_esperado) if caixa.saldo_final is not None else Decimal('0.00'),
        'pedidos_periodo': Pedido.objects.filter(status='concluido', data__range=[inicio, fim]),
        'compras_periodo': movimentos.filter(pedido_compra__isnull=False),
        'entradas_periodo': movimentos.filter(
            pedido__isnull=True,
            pedido_compra__isnull=True
        ).filter(Q(tipo='RECEITA') | Q(valor_parcela__gt=0)),
        'saidas_periodo': SaidaFinanceira.objects.filter(caixa=caixa, data__range=[inicio, fim]),
    }
    return render(request, 'visualizar_caixa.html', context)


# *** Fornecedores  ***

# class FornecedorViewSet(viewsets.ModelViewSet):
#     queryset = Fornecedor.objects.all()
#     serializer_class = FornecedorSerializer


def fornecedor_list(request):
    query = request.GET.get('q', '')
    fornecedores = Fornecedor.objects.all()
    if query:
        fornecedores = fornecedores.filter(
            Q(nome__icontains=query) |
            Q(cnpj__icontains=query) |
            Q(email__icontains=query)
        )
    form = FornecedorForm()
    if request.method == 'POST':
        form = FornecedorForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fornecedor cadastrado com sucesso!')
            return redirect('fornecedor_list')
    return render(request, 'fornecedores.html', {
        'fornecedores': fornecedores,
        'form': form,
        'query': query
    })


def fornecedor_edit(request, id):
    fornecedor = get_object_or_404(Fornecedor, id=id)
    if request.method == 'POST':
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Fornecedor atualizado com sucesso!')
            return redirect('fornecedor_list')
    else:
        form = FornecedorForm(instance=fornecedor)
    return render(request, 'fornecedores.html', {
        'fornecedores': Fornecedor.objects.all(),
        'form': form,
        'edit_fornecedor': fornecedor,
        'query': request.GET.get('q', '')
    })


def fornecedor_delete(request, id):
    fornecedor = get_object_or_404(Fornecedor, id=id)
    if request.method == 'POST':
        fornecedor.delete()
        messages.success(request, 'Fornecedor excluído com sucesso!')
        return redirect('fornecedor_list')
    return render(request, 'fornecedores.html', {
        'fornecedores': Fornecedor.objects.all(),
        'form': FornecedorForm(),
        'delete_fornecedor': fornecedor,
        'query': request.GET.get('q', '')
    })


def fornecedor_form(request, pk=None):
    if pk:  # edição
        fornecedor = get_object_or_404(Fornecedor, pk=pk)
    else:   # novo
        fornecedor = None

    if request.method == 'POST':
        form = FornecedorForm(request.POST, instance=fornecedor)
        if form.is_valid():
            form.save()
            if pk:
                messages.success(request, "Fornecedor atualizado com sucesso!")
            else:
                messages.success(request, "Fornecedor cadastrado com sucesso!")
            return redirect('fornecedor_list')
    else:
        form = FornecedorForm(instance=fornecedor)

    return render(request, 'fornecedor_form.html', {'form': form})


def buscar_fornecedores(request):
    termo = request.GET.get('term', '')
    fornecedores = Fornecedor.objects.filter(
        nome__icontains=termo) | Fornecedor.objects.filter(id__icontains=termo)
    data = [
        {
            'id': forn.id,
            'nome': forn.nome,
            'cnpj': forn.cnpj if hasattr(forn, 'cnpj') else '',
            'email': forn.email if hasattr(forn, 'email') else '',
            'telefone': forn.telefone if hasattr(forn, 'telefone') else ''
        } for forn in fornecedores[:10]  # Limita a 10 resultados
    ]
    return JsonResponse(data, safe=False)


def extrair_dados_nfe(xml_content):
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    root = ET.fromstring(xml_content)

    # NF number
    nfe_id = root.find(".//nfe:infNFe", ns)
    numero_nf = nfe_id.find(
        ".//nfe:nNF", ns).text if nfe_id is not None else ""

    # Fornecedor (emit)
    emit = root.find(".//nfe:emit", ns)
    cnpj = emit.find("nfe:CNPJ", ns).text if emit is not None else ""
    nome_forn = emit.find("nfe:xNome", ns).text if emit is not None else ""

    # Criar ou obter Fornecedor
    fornecedor, created = Fornecedor.objects.get_or_create(
        cnpj=cnpj, defaults={'nome': nome_forn}
    )

    # Produtos e entradas
    itens = root.findall(".//nfe:det", ns)
    entradas = []
    for item in itens:
        prod_xml = item.find(".//nfe:prod", ns)
        if prod_xml is not None:
            cProd = prod_xml.find("nfe:cProd", ns).text or ""
            descricao = prod_xml.find("nfe:xProd", ns).text or ""
            qtd = float(prod_xml.find("nfe:qCom", ns).text or 0)
            valor_unit = float(prod_xml.find("nfe:vUnCom", ns).text or 0)

            # Buscar ou criar Produto (simplificado; ajuste por cProd ou descricao)
            produto, created = Produto.objects.get_or_create(
                num_fabricante=cProd,
                defaults={
                    'nome': descricao[:100],
                    'descricao': descricao,
                    'preco': valor_unit,
                    'estoque': 0,
                    'categoria': Categoria.objects.first(),  # Defina default
                    'notafiscal': numero_nf,
                    'valor_pago': valor_unit,
                    'eh_servico': False
                }
            )

            # Atualizar estoque
            produto.estoque += qtd
            produto.save()

            # Criar EntradaEstoque
            entrada = EntradaEstoque.objects.create(
                produto=produto,
                quantidade=qtd,
                fornecedor=fornecedor,
                numero_nota_fiscal=numero_nf,
                custo_unitario=valor_unit
            )
            entradas.append({
                'produto': produto.nome,
                'qtd': qtd,
                'valor_unit': valor_unit,
                'entrada_id': entrada.id
            })
    return entradas, fornecedor


def extrair_dados_nfe_review(xml_content):  # Modificada para não salvar
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    root = ET.fromstring(xml_content)

    nfe_id = root.find(".//nfe:infNFe", ns)
    numero_nf = nfe_id.find(".//nfe:nNF", ns).text if nfe_id else ""

    emit = root.find(".//nfe:emit", ns)
    cnpj = emit.find("nfe:CNPJ", ns).text if emit else ""
    nome_forn = emit.find("nfe:xNome", ns).text if emit else ""
    telefone_forn = emit.find("nfe:fone", ns).text if emit and emit.find(
        "nfe:fone", ns) is not None else ""

    # Buscar fornecedor existente
    fornecedor = Fornecedor.objects.filter(cnpj=cnpj).first()
    if not fornecedor:
        fornecedor = {'id': None, 'telefone': telefone_forn,
                      'nome': nome_forn, 'cnpj': cnpj, 'existe': False}
    else:
        fornecedor = {'id': fornecedor.id, 'telefone': fornecedor.telefone,
                      'nome': fornecedor.nome, 'cnpj': cnpj, 'existe': True}

    itens = root.findall(".//nfe:det", ns)
    entradas_data = []
    for item in itens:
        prod_xml = item.find(".//nfe:prod", ns)
        if prod_xml:
            cProd = prod_xml.find("nfe:cProd", ns).text or ""
            descricao = prod_xml.find("nfe:xProd", ns).text or ""
            qtd = float(prod_xml.find("nfe:qCom", ns).text or 0)
            valor_unit = float(prod_xml.find("nfe:vUnCom", ns).text or 0)

            # Buscar produto existente por num_fabricante ou nome similar
            produto = Produto.objects.filter(num_fabricante=cProd).first()
            if not produto:
                produto = Produto.objects.filter(
                    nome__icontains=descricao[:50]).first()
            if produto:
                produto_id = produto.id
                nome = produto.nome
            else:
                produto_id = None
                nome = descricao[:100]

            entradas_data.append({
                'cProd': cProd,
                'produto_id': produto_id,
                'nome': nome,
                'descricao': descricao,
                'qtd': qtd,
                'valor_unit': valor_unit,
                'numero_nf': numero_nf
            })
    return entradas_data, fornecedor


def upload_xml(request):
    if request.method == 'POST':
        form = UploadXMLForm(request.POST, request.FILES)
        if form.is_valid():
            xml_content = request.FILES['xml_file'].read().decode('utf-8')
            try:
                entradas_data, fornecedor = extrair_dados_nfe_review(
                    xml_content)
                request.session['xml_entradas'] = entradas_data
                request.session['xml_fornecedor'] = fornecedor
                request.session['xml_numero_nf'] = entradas_data[0]['numero_nf'] if entradas_data else ''
                return redirect('review_xml')
            except Exception as e:
                messages.error(request, f'Erro ao processar XML: {str(e)}')
    else:
        form = UploadXMLForm()
    return render(request, 'upload_xml.html', {'form': form})


def review_xml(request):
    entradas_data = request.session.get('xml_entradas', [])
    fornecedor = request.session.get('xml_fornecedor', {})
    numero_nf = request.session.get('xml_numero_nf', '')

    if not entradas_data:
        messages.warning(
            request, 'Nenhum dado extraído. Faça upload novamente.')
        return redirect('upload_xml')

    # Formset para edição de entradas
    EntradaFormSet = modelformset_factory(
        EntradaEstoque, form=ReviewEntradaForm, extra=0)
    # Mas como não salvamos ainda, use formset vazio e preencha manualmente no template

    context = {
        'entradas_data': entradas_data,
        'fornecedor': fornecedor,
        'numero_nf': numero_nf,
        'num_itens': len(entradas_data)
    }
    return render(request, 'review_xml.html', context)


def review_confirm(request):
    if request.method == 'POST':
        entradas_data = request.session.get('xml_entradas', [])
        fornecedor_data = request.session.get('xml_fornecedor', {})
        numero_nf = request.session.get('xml_numero_nf', '')

        # Criar/atualizar fornecedor
        fornecedor_id = request.POST.get('fornecedor_id')
        if fornecedor_id:
            fornecedor = Fornecedor.objects.get(id=fornecedor_id)
            fornecedor.nome = request.POST.get(
                'fornecedor_nome', fornecedor.nome)
            fornecedor.save()
        else:
            cnpj = request.POST.get(
                'fornecedor_cnpj') or fornecedor_data.get('cnpj')
            nome = request.POST.get(
                'fornecedor_nome') or fornecedor_data.get('nome', '')
            fornecedor, _ = Fornecedor.objects.get_or_create(
                cnpj=cnpj,
                defaults={'nome': nome}
            )
            fornecedor.nome = nome
            fornecedor.save()

        total_itens = 0
        for i, data in enumerate(entradas_data):
            produto_id = request.POST.get(f'produto_id_{i}')
            qtd = float(request.POST.get(f'qtd_{i}', data['qtd']))
            valor_unit = float(request.POST.get(
                f'valor_unit_{i}', data['valor_unit']))
            nome = request.POST.get(f'nome_{i}', data['nome'])
            cProd = data['cProd']

            # Produto
            if produto_id:
                produto = Produto.objects.get(id=produto_id)
            else:
                produto, _ = Produto.objects.get_or_create(
                    num_fabricante=cProd,
                    defaults={
                        'nome': nome,
                        'descricao': data['descricao'],
                        'preco': valor_unit,
                        'estoque': 0,
                        'categoria': Categoria.objects.first(),
                        'notafiscal': numero_nf,
                        'valor_pago': valor_unit,
                        'eh_servico': False
                    }
                )

            # Atualizar estoque
            produto.estoque += qtd
            produto.save()

            # Criar entrada
            EntradaEstoque.objects.create(
                produto=produto,
                quantidade=qtd,
                fornecedor=fornecedor if fornecedor_id else None,
                nome_fornecedor=fornecedor.nome if not fornecedor_id else None,
                numero_nota_fiscal=numero_nf,
                custo_unitario=valor_unit
            )
            total_itens += 1

        # Limpar session
        del request.session['xml_entradas']
        del request.session['xml_fornecedor']
        del request.session['xml_numero_nf']

        messages.success(
            request, f'Confirmado: {total_itens} itens processados.')
        return redirect('produtos_geral')
    return redirect('review_xml')


@login_required
@permission_required('loja_web.gerenciar_pedidos_compras', raise_exception=True)
def criar_pedido_compra(request):
    ItemPedidoFormSet = formset_factory(ItemPedidoCompraForm, extra=1)
    if request.method == 'POST':
        form = PedidoCompraForm(request.POST)
        formset = ItemPedidoFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            # Save the PedidoCompra first
            pedido = form.save(commit=False)
            pedido.empresa = get_empresa_ativa(request)
            pedido.data_criacao = date.today()
            total_valor = 0

            # Calculate total before saving items
            for item_form in formset:
                quantidade = item_form.cleaned_data['quantidade']
                custo_unitario = item_form.cleaned_data['custo_unitario']
                total_valor += quantidade * custo_unitario

            # Assign total to pedido and save
            pedido.total = total_valor  # Ensure 'total' field exists in PedidoCompra model
            pedido.save()  # Save PedidoCompra to generate primary key

            # Now create ItemPedidoCompra objects
            for item_form in formset:
                ItemPedidoCompra.objects.create(
                    pedido_compra=pedido,  # Use the saved pedido
                    produto=item_form.cleaned_data['produto'],
                    quantidade=item_form.cleaned_data['quantidade'],
                    custo_unitario=item_form.cleaned_data['custo_unitario']
                )

            # Create MovimentoFinanceiro as despesa
            condicao = form.cleaned_data['condicao_pagamento']
            parcelas = condicao.numero_parcelas if condicao else 1
            intervalo = condicao.intervalo_dias if condicao else 30
            valor_parcela = total_valor / parcelas if parcelas > 0 else total_valor
            for i in range(parcelas):
                vencimento = date.today() + timedelta(days=intervalo *
                                                      (i + 1 if condicao and condicao.entrada else i))
                MovimentoFinanceiro.objects.create(
                    empresa=pedido.empresa,
                    pedido_compra=pedido,
                    descricao=f'Parcela {i+1}/{parcelas} - Pedido Compra {pedido.id}',
                    parcela=i + 1,
                    total_parcelas=parcelas,
                    condicao_id=condicao,
                    valor_parcela=valor_parcela,
                    data_vencimento=vencimento,
                    tipo='DESPESA'
                )

            messages.success(request, f'Pedido de Compra {pedido.id} criado!')
            itens_compra = ', '.join([
                f"{item.produto.nome} x{item.quantidade}"
                for item in pedido.itens.all()
            ]) or 'nenhum'
            registrar_log(
                request,
                'pedido',
                'Pedido de Compra',
                f'Pedido de Compra #{pedido.id} | Fornecedor: {pedido.fornecedor} | Total: R$ {formatar_valor_log(total_valor)} | Itens: {itens_compra}'
            )
            return redirect('pedidos_compra_lista')
    else:
        form = PedidoCompraForm()
        formset = ItemPedidoFormSet()

    return render(request, 'criar_pedido_compra.html', {'form': form, 'formset': formset})


@login_required
@permission_required('loja_web.gerenciar_pedidos_compras', raise_exception=True)
def pedidos_compra_lista(request):
    form = PedidoCompraFilterForm(request.GET or None)
    pedidos = PedidoCompra.objects.all()

    if form.is_valid():
        if form.cleaned_data['id']:
            pedidos = pedidos.filter(id=form.cleaned_data['id'])
        if form.cleaned_data['fornecedor']:
            pedidos = pedidos.filter(
                fornecedor=form.cleaned_data['fornecedor'])
        if form.cleaned_data['numero_nota_fiscal']:
            pedidos = pedidos.filter(
                numero_nota_fiscal__icontains=form.cleaned_data['numero_nota_fiscal'])
        if form.cleaned_data['data_criacao']:
            pedidos = pedidos.filter(
                data_criacao=form.cleaned_data['data_criacao'])
        if form.cleaned_data['condicao_pagamento']:
            pedidos = pedidos.filter(
                condicao_pagamento=form.cleaned_data['condicao_pagamento'])

    total_pedidos = pedidos.count()
    total_geral = pedidos.aggregate(Sum('total'))['total__sum'] or 0
    busca_realizada = bool(request.GET)

    return render(request, 'pedidos_compra_lista.html', {
        'filter_form': form,
        'pedidos': pedidos,
        'total_pedidos': total_pedidos,
        'total_geral': total_geral,
        'busca_realizada': busca_realizada,
    })


@login_required
@permission_required('loja_web.gerenciar_pedidos_compras', raise_exception=True)
def buscar_pedidos_compra(request):
    termo = request.GET.get('term', '').strip()
    # Filtra apenas pedidos pendentes, ajuste conforme necessário
    pedidos = PedidoCompra.objects.filter(status='pendente')
    if termo:
        pedidos = pedidos.filter(id__icontains=termo) | pedidos.filter(
            numero_nota_fiscal__icontains=termo)
    pedidos = pedidos[:10]  # Limita a 10 resultados
    data = [
        {
            'id': pedido.id,
            'numero_nota_fiscal': pedido.numero_nota_fiscal,
            'data_criacao': pedido.data_criacao.strftime('%d/%m/%Y'),
            'total': float(pedido.total or 0)
        } for pedido in pedidos
    ]
    return JsonResponse(data, safe=False)


@login_required
@permission_required('loja_web.gerenciar_pedidos_compras', raise_exception=True)
def editar_pedido_compra(request, pk):
    pedido = get_object_or_404(PedidoCompra, pk=pk)
    if request.method == 'POST':
        form = PedidoCompraForm(request.POST, instance=pedido)
        formset = ItemPedidoCompraFormSet(request.POST, instance=pedido)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
                total = sum(item.quantidade * item.custo_unitario for item in pedido.itens.all()
                            if not item._state.db or not request.POST.get(f'form-{item.id}-DELETE'))
                pedido.total = total
                pedido.save()
                messages.success(
                    request, 'Pedido de compra atualizado com sucesso.')
                return redirect('pedidos_compra_lista')
        else:
            messages.error(
                request, 'Erro ao salvar o pedido. Verifique os campos.')
            # Log errors for debugging
            print("Form errors:", form.errors)
            print("Formset errors:", formset.errors)
    else:
        form = PedidoCompraForm(instance=pedido)
        formset = ItemPedidoCompraFormSet(instance=pedido)
    return render(request, 'editar_pedido_compra.html', {'form': form, 'formset': formset, 'pedido': pedido})


@login_required
@permission_required('loja_web.gerenciar_financeiro', raise_exception=True)
def relatorio_movimentos_financeiros(request):
    # Obter parâmetros de filtro
    ordenacao = request.GET.get('ordenacao', '-id')
    id_inicial = request.GET.get('id_inicial', '')
    id_final = request.GET.get('id_final', '')
    filtro_descricao = request.GET.get('descricao', '')
    filtro_status = request.GET.get('status', '')
    filtro_tipo = request.GET.get('tipo', '')
    filtro_vencimento_inicial = request.GET.get('vencimento_inicial', '')
    filtro_vencimento_final = request.GET.get('vencimento_final', '')
    filtro_pagamento_inicial = request.GET.get('pagamento_inicial', '')
    filtro_pagamento_final = request.GET.get('pagamento_final', '')

    # Filtrar movimentos financeiros
    movimentos = MovimentoFinanceiro.objects.all()

    # Aplicar filtros
    if id_inicial:
        movimentos = movimentos.filter(id__gte=id_inicial)
    if id_final:
        movimentos = movimentos.filter(id__lte=id_final)
    if filtro_descricao:
        movimentos = movimentos.filter(descricao__icontains=filtro_descricao)
    if filtro_status:
        if filtro_status == 'pago':
            movimentos = movimentos.filter(pago=True)
        elif filtro_status == 'vencido':
            movimentos = movimentos.filter(
                pago=False, data_vencimento__lt=datetime.today().date())
        elif filtro_status == 'aberto':
            movimentos = movimentos.filter(
                pago=False, data_vencimento__gte=datetime.today().date())
    if filtro_tipo:
        movimentos = movimentos.filter(tipo=filtro_tipo)
    if filtro_vencimento_inicial:
        vencimento_inicial = parse_date(filtro_vencimento_inicial)
        if vencimento_inicial:
            movimentos = movimentos.filter(
                data_vencimento__gte=vencimento_inicial)
    if filtro_vencimento_final:
        vencimento_final = parse_date(filtro_vencimento_final)
        if vencimento_final:
            movimentos = movimentos.filter(
                data_vencimento__lte=vencimento_final)
    if filtro_pagamento_inicial:
        pagamento_inicial = parse_date(filtro_pagamento_inicial)
        if pagamento_inicial:
            movimentos = movimentos.filter(
                data_pagamento__gte=pagamento_inicial)
    if filtro_pagamento_final:
        pagamento_final = parse_date(filtro_pagamento_final)
        if pagamento_final:
            movimentos = movimentos.filter(data_pagamento__lte=pagamento_final)

    # Aplicar ordenação
    movimentos = movimentos.order_by(ordenacao)

    # Calcular total geral
    total_geral = movimentos.aggregate(Sum('valor_parcela'))[
        'valor_parcela__sum'] or 0
    quantidade_registros = movimentos.count()

    # Contexto para o template
    context = {
        'movimentos': movimentos,
        'ordenacao': ordenacao,
        'id_inicial': id_inicial,
        'id_final': id_final,
        'filtro_descricao': filtro_descricao,
        'filtro_status': filtro_status,
        'filtro_tipo': filtro_tipo,
        'filtro_vencimento_inicial': filtro_vencimento_inicial,
        'filtro_vencimento_final': filtro_vencimento_final,
        'filtro_pagamento_inicial': filtro_pagamento_inicial,
        'filtro_pagamento_final': filtro_pagamento_final,
        'data_atual': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'quantidade_registros': quantidade_registros,
        'total_geral': total_geral,
    }

    return render(request, 'relatorio_movimentos_financeiros.html', context)


# Alterar usuarios e permissoes
@login_required
@permission_required('loja_web.gerenciar_usuarios', raise_exception=True)
def gerenciar_usuarios_permissoes(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        # --- Atualizar grupo de um usuário ---
        if form_type == 'permissoes_usuario':
            usuario_id = request.POST.get('usuario')
            grupo_id = request.POST.get('grupo')

            usuario = User.objects.get(id=usuario_id)
            usuario.groups.clear()
            if grupo_id:
                grupo = Group.objects.get(id=grupo_id)
                usuario.groups.add(grupo)

            messages.success(
                request, 'Grupo do usuário atualizado com sucesso.')

        # --- Criar / editar grupos e permissões ---
        elif form_type == 'gerenciar_grupo':
            grupo_id = request.POST.get('grupo_id')
            grupo_nome = request.POST.get('grupo_nome').strip()
            permissoes_ids = request.POST.getlist('permissoes_grupo')

            if grupo_id:
                grupo = Group.objects.get(id=grupo_id)
                grupo.name = grupo_nome
                grupo.save()
            else:
                grupo = Group.objects.create(name=grupo_nome)

            # Pega o content type correto do modelo PermissaoSistema (no app loja_web)
            content_type = ContentType.objects.get(
                app_label='loja_web', model='permissaosistema')

            # Filtra e aplica as permissões do grupo
            grupo.permissions.set(
                Permission.objects.filter(
                    content_type=content_type,
                    id__in=permissoes_ids
                )
            )

            messages.success(
                request, f'Grupo "{grupo_nome}" salvo com sucesso.')

        return redirect('gerenciar_usuarios_permissoes')

    # --- GET: carregar usuários, grupos e permissões ---
    usuarios = User.objects.all().prefetch_related('groups')
    grupos = Group.objects.all()

    # Recupera o ContentType do modelo de permissões do sistema
    content_type = ContentType.objects.get(
        app_label='loja_web', model='permissaosistema')

    # Lista as permissões associadas a esse ContentType
    permissoes = Permission.objects.filter(
        content_type=content_type).order_by('name')

    usuario_atual = usuarios.first()
    grupo_atual = grupos.first()

    context = {
        'usuarios': usuarios,
        'grupos': grupos,
        'permissoes': permissoes,
        'usuario_atual': usuario_atual,
        'grupo_atual': grupo_atual,
        'group_perms': list(
            grupo_atual.permissions.filter(
                content_type=content_type).values_list('id', flat=True)
        ) if grupo_atual else [],
    }
    return render(request, 'gerenciar_usuarios_permissoes.html', context)


# --- AJAX: Grupo atual do usuário ---
@permission_required('loja_web.gerenciar_usuarios', raise_exception=True)
def get_usuario_grupo(request, uid):
    usuario = User.objects.get(id=uid)
    grupo = usuario.groups.first()
    if grupo:
        content_type = ContentType.objects.get(
            app_label='loja_web', model='permissaosistema')
        permissoes = grupo.permissions.filter(content_type=content_type)
        return JsonResponse({
            'grupo_id': grupo.id,
            'grupo_nome': grupo.name,
            'permissoes': [p.name for p in permissoes]
        })
    return JsonResponse({'grupo_id': None, 'grupo_nome': 'Nenhum', 'permissoes': []})


# --- AJAX: Detalhes do grupo ---
@permission_required('loja_web.gerenciar_usuarios', raise_exception=True)
def get_grupo(request, gid):
    grupo = Group.objects.get(id=gid)
    content_type = ContentType.objects.get(
        app_label='loja_web', model='permissaosistema')
    permissoes = grupo.permissions.filter(content_type=content_type)
    return JsonResponse({
        'name': grupo.name,
        'permissoes': [p.name for p in permissoes],
        'perms': list(permissoes.values_list('id', flat=True))
    })


@login_required
def custom_403_view(request, exception=None):
    # Mensagem amigável (pode personalizar)
    motivo = str(
        exception) if exception else "Você não tem permissão para acessar esta página."

    # Usa o sistema de messages do Django (aparece como toast no seu base.html)
    messages.error(request, motivo)

    return render(request, '403.html', status=403)


# Testando novas views de frente de caixa (PDV)

def frente_caixa(request):

    carrinho = request.session.get('carrinho', [])

    total = sum(Decimal(item['subtotal']) for item in carrinho)

    context = {
        'carrinho': carrinho,
        'total': total
    }

    return render(request, 'venda_direta.html', context)


def adicionar_produto(request):

    codigo = request.POST.get('codigo')

    try:
        produto = Produto.objects.get(id=codigo)
    except Produto.DoesNotExist:
        messages.error(request, "Produto não encontrado")
        return redirect('frente_caixa')

    carrinho = request.session.get('carrinho', [])

    for item in carrinho:
        if item['produto_id'] == produto.id:
            item['quantidade'] += 1
            item['subtotal'] = float(item['quantidade']) * float(produto.preco)
            request.session['carrinho'] = carrinho
            return redirect('frente_caixa')

    carrinho.append({
        'produto_id': produto.id,
        'nome': produto.nome,
        'quantidade': 1,
        'preco': float(produto.preco),
        'subtotal': float(produto.preco),
        'valor_pago': float(produto.valor_pago)
    })

    request.session['carrinho'] = carrinho

    return redirect('frente_caixa')


def remover_item(request, produto_id):

    carrinho = request.session.get('carrinho', [])

    carrinho = [item for item in carrinho if item['produto_id'] != produto_id]

    request.session['carrinho'] = carrinho

    return redirect('frente_caixa')


def cancelar_venda(request):

    request.session['carrinho'] = []

    return redirect('frente_caixa')


def finalizar_venda(request):

    carrinho = request.session.get('carrinho', [])

    if not carrinho:
        messages.error(request, "Carrinho vazio")
        return redirect('frente_caixa')

    venda = Venda.objects.create()

    total = Decimal('0.00')

    for item in carrinho:

        produto = Produto.objects.get(id=item['produto_id'])

        quantidade = int(item['quantidade'])
        preco = Decimal(item['preco'])

        if produto.estoque < quantidade:
            messages.error(
                request, f'Estoque insuficiente para {produto.nome}')
            return redirect('frente_caixa')

        ItemVenda.objects.create(
            venda=venda,
            produto=produto,
            quantidade=quantidade,
            preco_unitario=preco
        )

        produto.estoque -= quantidade
        produto.save()

        total += quantidade * preco

    venda.valortotal = total
    venda.save()

    request.session['carrinho'] = []

    resumo_itens = ', '.join(
        [f'{item.produto.nome} x{item.quantidade}' for item in venda.itemvenda_set.select_related(
            'produto').all()]
    ) or 'Sem itens'
    registrar_log(
        request,
        'venda',
        'Venda Direta (Caixa)',
        f'Venda #{venda.id} finalizada | Total: R$ {formatar_valor_log(venda.valortotal)} | Itens: {resumo_itens}'
    )
    messages.success(request, f'Venda #{venda.id} finalizada com sucesso')

    return redirect('frente_caixa')
