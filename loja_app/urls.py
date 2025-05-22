from django.contrib import admin
from django.urls import path, include
from loja_web import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('relatorios/', views.relatorio_vendas, name='relatorio_vendas'),
    #path('produto/novo/', views.produto_create, name='produto_create'),
    path('venda/novo/', views.venda_create, name='venda_create'),
    path('nova-venda/', views.nova_venda, name='nova_venda'),
    path('vendas/', views.lista_vendas, name='lista_vendas'),
    path('produto/novo/', views.produto_novo, name='produto_novo'),
    path('produto/editar/<int:id>/', views.produto_editar, name='produto_editar'),
    path('produto/excluir/<int:id>/', views.produto_excluir, name='produto_excluir'),
    path('produtos/', views.produto_form, name='produto_form'),
    #path('categoria/novo/', views.categoria_create, name='categoria_create'),
    path('categoria/novo/', views.nova_categoria, name='nova_categoria'),
    path('categoria/pesquisar/', views.pesquisar_categoria, name='pesquisar_categoria'),
    path('produtos/', views.produto_lista, name='produto_lista'),
    path('servicos/', views.servico_lista, name='servico_lista'),
    path('categorias/editar/<int:id>/', views.editar_categoria, name='editar_categoria'),
    path('categorias/excluir/<int:id>/', views.excluir_categoria, name='excluir_categoria'),
    path('pedido/', views.pedido_view, name='novo_pedido'),
    path('pedido/<int:pk>/', views.pedido_view, name='editar_pedido'),
    path('pedidos/', views.listar_pedidos, name='listar_pedidos'),
    path('select2/', include('django_select2.urls')),



]



