from django.contrib import admin
from django.urls import path, include
# Importe as views do seu app (assumindo que o app se chama loja_web)
from loja_web import views 

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("relatorios/", views.relatorio_vendas, name="relatorio_vendas"),
    # path("produto/novo/", views.produto_create, name="produto_create"), # Comentado, parece substituído
    # path("venda/novo/", views.venda_create, name="venda_create"), # Comentado, parece substituído
    path("nova-venda/", views.nova_venda, name="nova_venda"),
    path("vendas/", views.lista_vendas, name="lista_vendas"),

    path("produto/novo/", views.produto_novo, name="produto_novo"),
    path("produto/editar/<int:id>/", views.produto_editar, name="produto_editar"),
    path("produto/excluir/<int:id>/", views.produto_excluir, name="produto_excluir"),
    path("produtos/gerenciar/", views.produto_form, name="produto_form"), # Renomeado para clareza
    # path("categoria/novo/", views.categoria_create, name="categoria_create"), # Comentado, parece substituído
    path("categoria/novo/", views.nova_categoria, name="nova_categoria"),
    path("categoria/pesquisar/", views.pesquisar_categoria, name="pesquisar_categoria"),
    path("produtos/listar/", views.produto_lista, name="produto_lista"), # Renomeado para clareza
    path("servicos/listar/", views.servico_lista, name="servico_lista"), # Renomeado para clareza
    path("categorias/editar/<int:id>/", views.editar_categoria, name="editar_categoria"),
    path("categorias/excluir/<int:id>/", views.excluir_categoria, name="excluir_categoria"),


    path("pedidos/", views.pedidos, name="pedidos"), # Página geral de pedidos?
    path("pedidos/listar/", views.lista_pedidos, name="lista_pedidos"), # Renomeado para clareza
    path("pedido/novo/", views.novo_pedido, name="novo_pedido"), # Renomeado para clareza
    #path('pedidos/', views.lista_pedidos, name='lista_pedidos'),
    path('pedido/editar/<int:id>/', views.editar_pedido, name='editar_pedido'),
    path('pedido/excluir/<int:id>/', views.excluir_pedido, name='excluir_pedido'),
    # path("pedido/novo/", views.novo_pedido, name="novo_pedido"), # Comentado, duplicado

    # path("pedido/novo/", views.criar_pedido, name="criar_pedido"), # Comentado
    path("buscar-produtos/", views.buscar_produtos, name="buscar_produtos"), # API para busca?
    path("pedido/editar/<int:id>/", views.editar_pedido, name="editar_pedido"), # Corrigido para usar id
    path("pedido/excluir/<int:id>/", views.excluir_pedido, name="excluir_pedido"), # Corrigido para usar id

    path("select2/", include("django_select2.urls")), # URLs do Django Select2
    path("clientes/", views.clientes, name="clientes"), # Página geral de clientes?
    path("clientes/listar/", views.cliente_lista, name="cliente_lista"), # Adicionado para listar clientes
    path("clientes/novo/", views.cliente_novo, name="cliente_novo"),
    path("clientes/editar/<int:pk>/", views.cliente_editar, name="cliente_editar"),
    path("clientes/excluir/<int:pk>/", views.cliente_excluir, name="cliente_excluir"),
    path("clientes/pesquisar/", views.cliente_pesquisa, name="cliente_pesquisa"),

    # --- URL para Entrada de Estoque --- 
    path("estoque/entrada/registrar/", views.registrar_entrada_estoque, name="registrar_entrada_estoque"),
    # --- Fim URL Entrada de Estoque ---

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
