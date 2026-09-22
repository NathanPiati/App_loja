from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView

# Importa as views do app 'loja_web'
from loja_web import views
from rest_framework import routers
from loja_web.api import ServicoSearchAPIView

router = routers.DefaultRouter()
router.register(r'produtos', views.ProdutoViewSet)
router.register(r'servicos', views.ServicoViewSet)
router.register(r'pedidos', views.PedidoViewSet)
router.register(r'itens-pedido', views.ItensPedidoViewSet)
router.register(r'itens-servico', views.ItemServicoViewSet)


urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', RedirectView.as_view(
        url='/static/inovasys_logo.ico', permanent=True)),
    path('', include('site_publico.urls')),
    path('assinatura/', include('billing.urls')),

    path('integracoes/evolution/', include('loja_web.evolution_urls')),

    path('api/servicos/', ServicoSearchAPIView.as_view(),
         name='servico-search-api'),
    path('api/', include(router.urls)),


    # (opcional) interface de login no navegador
    path('api-auth/', include('rest_framework.urls')),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("app/", views.home, name="home"),
    path("relatorios/", views.relatorios, name="relatorios"),
    path('relatorio_pedidos/', views.relatorio_pedidos, name='relatorio_pedidos'),
    # path("produto/novo/", views.produto_create, name="produto_create"), # Comentado, parece substituído
    # path("venda/novo/", views.venda_create, name="venda_create"), # Comentado, parece substituído
    # path("nova-venda/", views.nova_venda, name="nova_venda"),
    # path("vendas/", views.lista_vendas, name="lista_vendas"),
    path('nova-venda/', views.nova_venda, name='nova_venda'),
    path('buscar-produtos/', views.busca_produtosVenda,
         name='busca_produtosVenda'),
    path('buscar-condicoes-pagamento/', views.busca_condicoes_pagamento,
         name='busca_condicoes_pagamento'),
    path('finalizar-venda/', views.finalizar_venda, name='finalizar_venda'),


    # Renomeado para clareza
    path("produtos/", views.produtos, name="produtos_geral"),
    path("produto/novo/", views.produto_novo, name="produto_novo"),
    path("produto/editar/<int:id>/", views.produto_editar, name="produto_editar"),
    path("produto/excluir/<int:id>/",
         views.produto_excluir, name="produto_excluir"),
    path("produtos/gerenciar/", views.produto_form,
         name="produto_form"),  # Renomeado para clareza
    # path("categoria/novo/", views.categoria_create, name="categoria_create"), # Comentado, parece substituído
    path("categoria/novo/", views.nova_categoria, name="nova_categoria"),
    path("categoria/pesquisar/", views.pesquisar_categoria,
         name="pesquisar_categoria"),
    path("produtos/listar/", views.produto_lista,
         name="produto_lista"),  # Renomeado para clareza

    path("categorias/editar/<int:id>/",
         views.editar_categoria, name="editar_categoria"),
    path("categorias/excluir/<int:id>/",
         views.excluir_categoria, name="excluir_categoria"),


    # Página geral de pedidos?
    path("pedidos/", views.pedidos, name="pedidos"),
    path("pedidos/listar/", views.lista_pedidos,
         name="lista_pedidos"),  # Renomeado para clareza
    path('pedidos/encerrar/', views.encerrar_pedido, name='encerrar_pedido'),


    # path("pedido/novo/", views.novo_pedido, name="novo_pedido"), # Renomeado para clareza
    # path('pedidoteste/', views.PedidoTesteView, name='pedido_teste'),  # Exemplo de view teste
    # Exemplo de view teste template novo
    path('pedido/novo/', views.PedidoTesteView, name='pedido_teste'),

    # path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    # path('pedido/editar/<int:pedido_id>/', views.PedidoEditView, name='PedidoEditView'), # Corrigido para usar id
    path('pedido/atualizar/<int:pedido_id>/',
         views.PedidoUpdateView, name='PedidoUpdateView'),
    path('pedido/editar/<int:pedido_id>/',
         views.editar_pedido, name='editar_pedido'),



    path('pedido/excluir/<int:id>/',
         views.PedidoDeleteView, name='PedidoDeleteView'),
    path('pedido/imprimir/<int:pk>/',
         views.PedidoImprimirView.as_view(), name='pedido_imprimir'),

    path('financeiro/', views.lista_financeiro, name='lista_financeiro'),
    path('financeiro/pagar/<int:id>/', views.pagar_parcela, name='pagar_parcela'),
    path('financeiro/editar/<int:id>/', views.editar_movimento_financeiro,
         name='editar_movimento_financeiro'),
    path('financeiro/imprimir/', views.imprimir_financeiro,
         name='imprimir_financeiro'),



    path("configuracao-empresa/", views.configuracao_empresa, name="config_empresa"),
    path('logs/', views.visualizar_logs, name='visualizar_logs'),
    path('api/servicos/', views.api_servicos, name='api_servicos'),


    # path('criar-pedido/', views.criar_pedido, name='criar_pedido'),
    # Cria essa view depois se quiser
    path('lista-pedidos/', views.listar_pedidos, name='lista_pedidos'),
    path('api/produtos/', views.produtos_json, name='produtos_json'),
    path('api/salvar_pedido/', views.salvar_pedido, name='salvar_pedido'),

    # 🔍 Buscas
    path('buscar-produtos/', views.buscar_produtos, name='buscar_produtos'),
    path('buscar-servicos/', views.buscar_servicos, name='buscar_servicos'),

    path("select2/", include("django_select2.urls")),  # URLs do Django Select2
    # Página geral de clientes?
    path("clientes/", views.clientes, name="clientes"),
    # Adicionado para listar clientes
    path("clientes/listar/", views.cliente_lista, name="cliente_lista"),
    path("clientes/novo/", views.cliente_novo, name="cliente_novo"),
    path("clientes/editar/<int:pk>/", views.cliente_editar, name="cliente_editar"),
    path("clientes/excluir/<int:pk>/",
         views.cliente_excluir, name="cliente_excluir"),
    path("clientes/pesquisar/", views.cliente_pesquisa, name="cliente_pesquisa"),
    path('relatorio-clientes/', views.relatorio_clientes,
         name='relatorio_clientes'),
    path('relatorio-clientes/imprimir/', views.relatorio_clientes_imprimir,
         name='relatorio_clientes_imprimir'),

    # --- URL para Entrada de Estoque ---
    path("estoque/entrada/registrar/", views.registrar_entrada_estoque,
         name="registrar_entrada_estoque"),
    path('buscar-produtosentrada/', views.buscar_produtosentrada,
         name='buscar_produtosentrada'),
    path('buscar-entradas-estoque/', views.buscar_entradas_estoque,
         name='buscar_entradas_estoque'),
    path('estoque/entradas/consultar/',
         views.consultar_entradas, name='consultar_entradas'),
    path('estoque/baixa/registrar/', views.registrar_baixa_estoque,
         name='registrar_baixa_estoque'),
    path('estoque/baixas/consultar/', views.consultar_baixas,
         name='consultar_baixas'),
    # --- Fim URL Entrada de Estoque ---

    # --- URL para Condições de Pagamento ---
    path('condicoes-pagamento/', views.lista_condicoes_pagamento,
         name='lista_condicoes_pagamento'),
    path('condicoes-pagamento/novo/', views.criar_condicao_pagamento,
         name='criar_condicao_pagamento'),
    path('condicoes-pagamento/editar/<int:pk>/',
         views.editar_condicao_pagamento, name='editar_condicao_pagamento'),
    path('condicoes-pagamento/excluir/<int:pk>/',
         views.excluir_condicao_pagamento, name='excluir_condicao_pagamento'),

    # --- URL para Cobrança de clientes via WhatsApp ---
    path('cobranca-whatsapp/', views.lista_regras_cobranca_whatsapp,
         name='lista_regras_cobranca_whatsapp'),
    path('cobranca-whatsapp/novo/', views.criar_regra_cobranca_whatsapp,
         name='criar_regra_cobranca_whatsapp'),
    path('cobranca-whatsapp/editar/<int:pk>/',
         views.editar_regra_cobranca_whatsapp, name='editar_regra_cobranca_whatsapp'),
    path('cobranca-whatsapp/excluir/<int:pk>/',
         views.excluir_regra_cobranca_whatsapp, name='excluir_regra_cobranca_whatsapp'),
    path('cobranca-whatsapp/historico/', views.historico_cobranca_whatsapp,
         name='historico_cobranca_whatsapp'),
    path('cobranca-whatsapp/manual/', views.disparo_manual_cobranca_whatsapp,
         name='disparo_manual_cobranca_whatsapp'),
    path('cobranca-whatsapp/disparar-agora/', views.disparar_cobrancas_whatsapp_agora,
         name='disparar_cobrancas_whatsapp_agora'),


    # Renomeado para clareza
    path("servicos/", views.servicos, name="servicos"),
    # path('', views.listar_servicos, name='listar_servicos'),
    path('novo/', views.novo_servico, name='novo_servico'),
    path('editar/<int:pk>/', views.editar_servico, name='editar_servico'),
    path('excluir/<int:pk>/', views.excluir_servico, name='excluir_servico'),
    path('listar/', views.listar_servicos, name='listar_servicos'),
    path('acompanhamentos/', views.listar_acompanhamentos,
         name='listar_acompanhamentos'),
    path('acompanhamentos/novo/', views.novo_acompanhamento,
         name='novo_acompanhamento'),
    path('acompanhamentos/editar/<int:pk>/', views.editar_acompanhamento,
         name='editar_acompanhamento'),
    path('acompanhamentos/excluir/<int:pk>/', views.excluir_acompanhamento,
         name='excluir_acompanhamento'),


    # --- URLs para Relatórios ---
    path('relatorio-estoque/', views.relatorio_estoque, name='relatorio_estoque'),
    path('relatorio/estoque/imprimir/', views.imprimir_relatorio_estoque,
         name='imprimir_relatorio_estoque'),

    path('venda-direta/', views.mercado_view, name='mercado'),

    path('fechamento-caixa/', views.fechamento_caixa, name='fechamento_caixa'),
    path('fechamento-caixa/', views.fechamento_caixa, name='fechamento_caixa'),
    path('caixa/<int:caixa_id>/', views.visualizar_caixa, name='visualizar_caixa'),

    path('relatorio-vendas-diretas/',
         views.relatorio_vendas, name='relatorio_vendas'),
    path('relatorio-vendas-diretas/imprimir/',
         views.imprimir_relatorio_vendas, name='imprimir_relatorio_vendas'),
    path('relatorio/movimentos-financeiros/', views.relatorio_movimentos_financeiros,
         name='relatorio_movimentos_financeiros'),


    # path('fornecedores/', TemplateView.as_view(template_name='fornecedores.html'), name='fornecedores'),
    path('fornecedores/novo/', views.fornecedor_form, name='fornecedor_create'),
    path('fornecedores/', views.fornecedor_list, name='fornecedor_list'),
    path('fornecedores/edit/<int:id>/',
         views.fornecedor_edit, name='fornecedor_edit'),
    path('fornecedores/delete/<int:id>/',
         views.fornecedor_delete, name='fornecedor_delete'),
    path('buscar_fornecedores/', views.buscar_fornecedores,
         name='buscar_fornecedores'),

    path('review-xml/', views.review_xml, name='review_xml'),
    path('review-confirm/', views.review_confirm, name='review_confirm'),
    path('upload-xml/', views.upload_xml, name='upload_xml'),


    path('criar-pedido-compra/', views.criar_pedido_compra,
         name='criar_pedido_compra'),
    path('pedidos-compra/', views.pedidos_compra_lista,
         name='pedidos_compra_lista'),
    path('pedido-compra/editar/<int:pk>/',
         views.editar_pedido_compra, name='editar_pedido_compra'),
    path('buscar-pedidos-compra/', views.buscar_pedidos_compra,
         name='buscar_pedidos_compra'),

    path('gerenciar/', views.gerenciar_usuarios_permissoes,
         name='gerenciar_usuarios_permissoes'),

    path('licenca-invalida/', lambda request: render(request,
         'licenca_invalida.html'), name='licenca_invalida'),


    path('gerenciar/', views.gerenciar_usuarios_permissoes,
         name='gerenciar_usuarios_permissoes'),
    path('get_usuario_grupo/<int:uid>/',
         views.get_usuario_grupo, name='get_usuario_grupo'),
    path('get_grupo/<int:gid>/', views.get_grupo, name='get_grupo'),



    # Nova venda TESTE
    path('vendas/nova/', views.nova_venda, name='nova_venda'),
    path('vendas/busca-produtos/', views.busca_produtosVenda,
         name='busca_produtosVenda'),  # crie essa view se quiser busca ajax
    path('busca-produtos-venda/', views.busca_produtosVenda,
         name='busca_produtosVenda'),  # URL para busca de produtos na venda
    # path('api/clientes/', views.ClienteAPIList.as_view(), name='api_clientes'),
    path('busca-clientes/', views.busca_clientes, name='busca_clientes'),




    path('caixa/', views.frente_caixa, name='frente_caixa'),

    path('caixa/add/', views.adicionar_produto, name='add_produto'),

    path('caixa/remover/<int:produto_id>/',
         views.remover_item, name='remover_item'),

    path('caixa/finalizar/', views.finalizar_venda, name='finalizar_venda'),

    path('caixa/cancelar/', views.cancelar_venda, name='cancelar_venda'),


]

# --- Notas ---
# 1. Assumi que seu app se chama 'loja_web' baseado no import inicial.
#    Se for outro nome, ajuste o import `from loja_web import views`.
# 2. Renomeei algumas URLs para melhor clareza (ex: /produtos/listar/, /pedidos/listar/).
#    Se você já usa os nomes antigos em templates, precisará atualizá-los ou reverter as mudanças.
# 3. Corrigi as URLs de editar/excluir pedido para usar 'id' em vez de 'numero'.
# 4. Adicionei a nova URL para a view `registrar_entrada_estoque`.
# 5. Certifique-se que este arquivo é o `urls.py` principal do seu projeto ou que as URLs
#    do app estão corretamente incluídas no `urls.py` principal se este for o `urls.py` do app.
