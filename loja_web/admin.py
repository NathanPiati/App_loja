from django.contrib import admin
from .models import Categoria, Produto, Venda, ItemVenda

admin.site.register(Categoria)
admin.site.register(Produto)
admin.site.register(Venda)
admin.site.register(ItemVenda)
