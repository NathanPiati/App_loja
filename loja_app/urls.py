from django.contrib import admin
from django.urls import path
from loja_web import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('relatorios/', views.relatorio_vendas, name='relatorio_vendas'),
    #path('produto/novo/', views.produto_create, name='produto_create'),
    path('venda/novo/', views.venda_create, name='venda_create'),
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
    path('configurar-banco/', views.configurar_banco, name='configurar_banco'),



]



