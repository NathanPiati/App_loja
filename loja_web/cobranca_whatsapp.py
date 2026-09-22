"""Regras de cobrança de clientes via WhatsApp (pedidos e/ou serviços em aberto).

Este módulo concentra a lógica de decisão (quando disparar) e de envio,
reaproveitada tanto pelo management command `enviar_cobrancas_whatsapp`
quanto pelo disparo manual feito via tela do sistema.
"""
import json
import logging
import re
from datetime import date

from django.conf import settings
from django.utils import timezone

from .evolution import EvolutionClient
from .models import EnvioCobrancaWhatsApp, MovimentoFinanceiro, RegraCobrancaWhatsApp

logger = logging.getLogger(__name__)

NOME_EMPRESA_COBRANCA = 'Inovacore Tecnologia'


def _formatar_numero(telefone):
    digitos = re.sub(r'\D', '', telefone or '')
    if not digitos:
        return ''
    # Assume DDI 55 (Brasil) quando o número não vier com código de país.
    if not digitos.startswith('55'):
        digitos = '55' + digitos
    return digitos


def _pedido_aplica(regra, movimento):
    pedido = movimento.pedido
    if not pedido:
        return False
    if regra.aplicar_a == RegraCobrancaWhatsApp.APLICAR_PRODUTOS:
        return pedido.itens.exists()
    if regra.aplicar_a == RegraCobrancaWhatsApp.APLICAR_SERVICOS:
        return pedido.itens_servico.exists()
    return True


def montar_mensagem(regra, movimento):
    cliente = movimento.pedido.cliente if movimento.pedido else None
    hoje = date.today()
    if movimento.data_vencimento < hoje:
        status = 'Vencida'
    elif movimento.data_vencimento == hoje:
        status = 'Vence hoje'
    else:
        status = 'A vencer'

    contexto = {
        'cliente': cliente.nome if cliente else '',
        'valor': f'{movimento.valor_parcela:.2f}',
        'vencimento': movimento.data_vencimento.strftime('%d/%m/%Y'),
        'pedido': movimento.pedido_id or '-',
        'empresa': regra.empresa.nome if regra.empresa else '',
        'descricao': movimento.descricao or '-',
        'parcela': movimento.parcela,
        'total_parcelas': movimento.total_parcelas,
        'status': status,
        'observacao': movimento.observacao or '-',
    }
    complemento = (regra.mensagem or '').strip().format(**contexto)
    mensagem = (
        f"Olá {contexto['cliente']}, tudo bem?\n\n"
        'Identificamos este lançamento em aberto no seu financeiro:\n'
        f"• Referência: {contexto['descricao']}\n"
        f"• Pedido: {contexto['pedido']}\n"
        f"• Parcela: {contexto['parcela']}/{contexto['total_parcelas']}\n"
        f"• Valor: R$ {contexto['valor']}\n"
        f"• Vencimento: {contexto['vencimento']} ({contexto['status']})"
    )
    if movimento.observacao:
        mensagem += f"\n• Observação: {movimento.observacao}"
    if complemento:
        mensagem += f'\n\n{complemento}'
    return mensagem


def movimentos_abertos_cliente(cliente, empresa=None):
    movimentos = MovimentoFinanceiro.objects.filter(
        pedido__cliente=cliente,
        pago=False,
    ).select_related('pedido__cliente', 'pedido__empresa')
    if empresa:
        movimentos = movimentos.filter(empresa=empresa)
    return movimentos.order_by('data_vencimento', 'id')


def _identificar_lancamento(movimento):
    pedido = movimento.pedido
    if pedido:
        servicos = list(
            pedido.itens_servico.select_related('servico_id').all())
        if servicos:
            nomes = ', '.join(
                item.servico_id.nome if item.servico_id else item.descricao
                for item in servicos
            )
            return f'Serviço/OS: {nomes or "Serviço não informado"}'

        produtos = list(pedido.itens.select_related('produto').all())
        if produtos:
            nomes = ', '.join(
                item.descricao or item.produto.nome for item in produtos)
            return f'Pedido: {nomes or movimento.descricao or "Produtos"}'

    return movimento.descricao or 'Lançamento financeiro'


def montar_mensagem_cliente(cliente, movimentos, empresa=None):
    hoje = date.today()
    vencidos = [m for m in movimentos if m.data_vencimento < hoje]
    a_vencer = [m for m in movimentos if m.data_vencimento >= hoje]
    total = sum((m.valor_parcela for m in movimentos), 0)
    nome_empresa = NOME_EMPRESA_COBRANCA

    linhas = [
        f'Olá, {cliente.nome}.',
        '',
        f'{nome_empresa} informa que identificou pendências financeiras em seu cadastro.',
        'Confira abaixo os valores em aberto:',
    ]
    if vencidos:
        linhas.append('\n*PENDÊNCIAS VENCIDAS*')
        for movimento in vencidos:
            linhas.append(
                f'- {_identificar_lancamento(movimento)}\n'
                f'  Valor: R$ {movimento.valor_parcela:.2f} | '
                f'Vencimento: {movimento.data_vencimento:%d/%m/%Y}'
            )
    if a_vencer:
        linhas.append('\n*PRÓXIMOS VENCIMENTOS*')
        for movimento in a_vencer:
            status = 'vence hoje' if movimento.data_vencimento == hoje else (
                f'vence em {movimento.data_vencimento:%d/%m/%Y}'
            )
            linhas.append(
                f'- {_identificar_lancamento(movimento)}\n'
                f'  Valor: R$ {movimento.valor_parcela:.2f} | {status}'
            )
    linhas.extend([
        '',
        f'*Total em aberto: R$ {total:.2f}*',
        '',
        'Solicitamos a regularização dos valores vencidos e a programação '
        'dos próximos vencimentos.',
        'Por favor, responda esta mensagem para confirmarmos o pagamento ou '
        'alinharmos uma data.',
        '',
        '*Aviso importante:* a falta de pagamento poderá acarretar a adoção '
        'de medidas de cobrança e, quando aplicável, a inclusão do débito '
        'nos cadastros de proteção ao crédito, como o Serasa, observadas as '
        'exigências legais.',
        '',
        'Atenciosamente,',
        nome_empresa,
        '',
        'Agradecemos a parceria! 🤝',
        'Bora para cima! 🚀',
    ])
    return '\n'.join(linhas)


def enviar_cobranca_cliente(cliente, empresa=None, mensagem_personalizada=None):
    movimentos = list(movimentos_abertos_cliente(cliente, empresa=empresa))
    logger.info(
        'Cobranca manual preparada | cliente_id=%s | empresa_id=%s | movimentos=%s',
        cliente.id, getattr(empresa, 'id', None), len(movimentos)
    )
    if not movimentos:
        logger.warning(
            'Cobranca manual cancelada: nenhum lancamento em aberto | cliente_id=%s',
            cliente.id
        )
        return {'sucesso': False, 'erro': 'nenhum_lancamento_em_aberto', 'movimentos': []}

    numero = _formatar_numero(cliente.telefone)
    if not numero:
        logger.warning(
            'Cobranca manual cancelada: cliente sem telefone valido | cliente_id=%s',
            cliente.id
        )
        return {'sucesso': False, 'erro': 'cliente_sem_telefone', 'movimentos': movimentos}

    mensagem = (mensagem_personalizada or '').strip() or montar_mensagem_cliente(
        cliente, movimentos, empresa=empresa)
    sucesso = False
    resposta = ''
    if not settings.EVOLUTION_ENABLED:
        resposta = 'integracao_evolution_desabilitada'
        logger.error('Cobranca manual bloqueada: EVOLUTION_ENABLED=False')
    else:
        try:
            client = EvolutionClient()
            status_code, body = client.send_text(number=numero, text=mensagem)
            sucesso = 200 <= status_code < 300
            resposta = json.dumps(body, ensure_ascii=False)
            logger.info(
                'Cobranca manual finalizada | cliente_id=%s | status=%s | sucesso=%s',
                cliente.id, status_code, sucesso
            )
        except Exception as exc:
            logger.exception(
                'Falha no envio manual para cliente=%s', cliente.id)
            resposta = str(exc)

    for movimento in movimentos:
        EnvioCobrancaWhatsApp.objects.create(
            empresa=empresa,
            regra=None,
            movimento=movimento,
            numero_destino=numero,
            mensagem_enviada=mensagem,
            sucesso=sucesso,
            resposta_api=resposta,
        )
    return {
        'sucesso': sucesso,
        'erro': resposta if not sucesso else '',
        'numero': numero,
        'mensagem': mensagem,
        'movimentos': movimentos,
    }


def _deve_enviar_hoje(regra, movimento, hoje):
    diferenca_dias = (hoje - movimento.data_vencimento).days
    if regra.repetir_a_cada_dias > 0:
        return (
            diferenca_dias >= regra.dias_referencia
            and (diferenca_dias - regra.dias_referencia) % regra.repetir_a_cada_dias == 0
        )
    return diferenca_dias == regra.dias_referencia


def processar_regra(regra, hoje=None, dry_run=False):
    """Avalia uma regra e dispara (ou simula) o envio das cobranças elegíveis."""
    hoje = hoje or date.today()
    resultados = []

    movimentos = MovimentoFinanceiro.objects.filter(
        pago=False, pedido__isnull=False
    ).select_related('pedido__cliente', 'pedido__empresa')
    if regra.empresa_id:
        movimentos = movimentos.filter(empresa_id=regra.empresa_id)

    for movimento in movimentos:
        if not _pedido_aplica(regra, movimento):
            continue

        cliente = movimento.pedido.cliente if movimento.pedido else None
        if not cliente or not cliente.telefone:
            continue

        if not _deve_enviar_hoje(regra, movimento, hoje):
            continue

        ja_enviado_hoje = EnvioCobrancaWhatsApp.objects.filter(
            regra=regra, movimento=movimento, data_envio__date=hoje
        ).exists()
        if ja_enviado_hoje:
            continue

        numero = _formatar_numero(cliente.telefone)
        if not numero:
            continue

        mensagem = montar_mensagem(regra, movimento)

        if dry_run:
            resultados.append({
                'movimento_id': movimento.id,
                'numero': numero,
                'mensagem': mensagem,
                'sucesso': None,
            })
            continue

        sucesso = False
        resposta = ''
        if not settings.EVOLUTION_ENABLED:
            resposta = 'integracao_evolution_desabilitada'
        else:
            try:
                client = EvolutionClient()
                status_code, body = client.send_text(
                    number=numero, text=mensagem)
                sucesso = 200 <= status_code < 300
                resposta = json.dumps(body, ensure_ascii=False)
            except Exception as exc:
                logger.exception(
                    'Falha ao enviar cobrança WhatsApp (movimento=%s)', movimento.id)
                resposta = str(exc)

        EnvioCobrancaWhatsApp.objects.create(
            empresa=regra.empresa,
            regra=regra,
            movimento=movimento,
            numero_destino=numero,
            mensagem_enviada=mensagem,
            sucesso=sucesso,
            resposta_api=resposta,
        )
        resultados.append({
            'movimento_id': movimento.id,
            'numero': numero,
            'sucesso': sucesso,
        })

    return resultados


def processar_todas_regras(dry_run=False, empresa=None):
    regras = RegraCobrancaWhatsApp.objects.filter(ativo=True)
    if empresa:
        regras = regras.filter(empresa=empresa)

    resultados = []
    for regra in regras:
        resultados.extend(processar_regra(regra, dry_run=dry_run))
    return resultados
