from .models import Empresa
from django.conf import settings
from .tenancy import get_empresa_ativa

DEFAULT_UI_LABELS = {
    'produtos_modulo': 'Produtos',
    'produtos_desc': 'Gerencie seu estoque com praticidade.',
    'produtos_verbo': 'Ver Produtos',
    'produtos_novo': 'Novo Produto',
    'produtos_listar': 'Listar/Editar',
    'produtos_gerenciamento': 'Gerenciamento de Produtos',
    'servicos_modulo': 'Serviços',
    'servicos_desc': 'Visualize e organize os serviços oferecidos.',
    'servicos_verbo': 'Ver Serviços',
    'servicos_novo': 'Novo Serviço',
    'servicos_listar': 'Pesquisar',
    'servicos_gerenciamento': 'Gerenciamento de Serviços',
    'pedidos_modulo': 'Pedidos/OS',
    'pedidos_desc': 'Visualize e organize os pedidos ou ordens de serviços.',
    'pedidos_verbo': 'Ver Pedidos/OS',
    'pedidos_novo': 'Novo Pedido/OS',
    'pedidos_listar': 'Listar Pedidos/OS',
    'pedidos_encerrar': 'Encerrar Pedido/OS',
    'pedidos_gerenciamento': 'Gerenciamento de Pedidos/OS',
    'segmento_nome': 'Autopeças / Oficina',
}

SEGMENT_UI_OVERRIDES = {
    Empresa.SEGMENTO_SORVETERIA: {
        'produtos_modulo': 'Cardápio',
        'produtos_desc': 'Cadastre sabores, tamanhos, potes, bebidas e adicionais.',
        'produtos_verbo': 'Ver Cardápio',
        'produtos_novo': 'Novo Item do Cardápio',
        'produtos_listar': 'Listar/Editar Cardápio',
        'produtos_gerenciamento': 'Gerenciamento de Cardápio e Estoque',
        'servicos_modulo': 'Complementos',
        'servicos_desc': 'Organize coberturas, adicionais e itens de preparo.',
        'servicos_verbo': 'Ver Complementos',
        'servicos_novo': 'Novo Complemento',
        'servicos_listar': 'Listar Complementos',
        'servicos_gerenciamento': 'Gerenciamento de Complementos',
        'pedidos_modulo': 'Pedidos',
        'pedidos_desc': 'Gerencie pedidos do balcão, retirada e delivery.',
        'pedidos_verbo': 'Ver Pedidos',
        'pedidos_novo': 'Novo Pedido',
        'pedidos_listar': 'Listar Pedidos',
        'pedidos_encerrar': 'Fechar Pedido',
        'pedidos_gerenciamento': 'Gerenciamento de Pedidos',
        'segmento_nome': 'Sorveteria / Açaí',
    },
}


def get_ui_labels(segmento):
    labels = DEFAULT_UI_LABELS.copy()
    labels.update(SEGMENT_UI_OVERRIDES.get(segmento, {}))
    return labels


def empresa(request):
    empresa_atual = get_empresa_ativa(request) or Empresa.objects.first()
    segmento = getattr(empresa_atual, 'segmento', Empresa.SEGMENTO_AUTOPECAS)
    return {
        'empresa': empresa_atual,
        'ui_labels': get_ui_labels(segmento),
        'segmento_atual': segmento,
    }


def version_context(request):
    return {
        'versao': settings.VERSION
    }
