import json
import logging
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)


def _numero_log(numero):
    numero = str(numero or '')
    if len(numero) <= 4:
        return '****'
    return f'{numero[:4]}***{numero[-2:]}'


class EvolutionClient:
    def __init__(self):
        self.base_url = settings.EVOLUTION_BASE_URL.rstrip('/')
        self.api_key = settings.EVOLUTION_API_KEY
        self.instance = settings.EVOLUTION_INSTANCE
        self.send_text_path = settings.EVOLUTION_SEND_TEXT_PATH

    def _headers(self):
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['apikey'] = self.api_key
        return headers

    def _send_text_url(self):
        path = self.send_text_path.format(instance=self.instance).lstrip('/')
        return urljoin(f'{self.base_url}/', path)

    def send_text(self, number: str, text: str, delay: int = 1200):
        url = self._send_text_url()
        logger.info(
            'Evolution envio iniciado | url=%s | instance=%s | numero=%s | caracteres=%s',
            url, self.instance, _numero_log(number), len(text or '')
        )
        payload = {
            'number': number,
            'text': text,
            'delay': delay,
        }
        response = requests.post(
            self._send_text_url(),
            headers=self._headers(),
            data=json.dumps(payload),
            timeout=20,
        )

        try:
            body = response.json()
        except Exception:
            body = {'raw': response.text}

        logger.info(
            'Evolution resposta recebida | status=%s | numero=%s | resposta=%s',
            response.status_code, _numero_log(number), str(body)[:500]
        )

        return response.status_code, body

    def check_connection(self):
        # Tenta endpoints comuns para identificar rapidamente se a API esta acessivel.
        candidates = [
            self.base_url,
            f'{self.base_url}/manager',
            f'{self.base_url}/docs',
        ]
        headers = self._headers()

        last_error = None
        for url in candidates:
            try:
                response = requests.get(url, headers=headers, timeout=10)
            except requests.RequestException as exc:
                last_error = str(exc)
                continue

            body = response.text[:500]
            return {
                'ok': response.status_code < 500,
                'url': url,
                'status_code': response.status_code,
                'body_preview': body,
            }

        return {
            'ok': False,
            'url': self.base_url,
            'status_code': None,
            'body_preview': '',
            'error': last_error or 'nao_foi_possivel_conectar',
        }


def _status_payload():
    enabled = settings.EVOLUTION_ENABLED
    ready = enabled and bool(settings.EVOLUTION_BASE_URL) and bool(
        settings.EVOLUTION_INSTANCE)
    return {
        'enabled': enabled,
        'ready': ready,
        'base_url': settings.EVOLUTION_BASE_URL,
        'instance': settings.EVOLUTION_INSTANCE,
    }


@login_required
def evolution_panel(request):
    status_data = _status_payload()
    response_data = None
    response_pretty = ''
    connection_data = None
    connection_pretty = ''

    if request.method == 'POST':
        action = str(request.POST.get('action', 'send_text')
                     ).strip() or 'send_text'
        number = str(request.POST.get('number', '')).strip()
        text = str(request.POST.get('text', '')).strip()

        if not settings.EVOLUTION_ENABLED:
            messages.error(
                request, 'Integracao Evolution esta desabilitada no ambiente.')
        else:
            client = EvolutionClient()

            if action == 'check_connection':
                connection_data = client.check_connection()
                connection_pretty = json.dumps(
                    connection_data, indent=2, ensure_ascii=False)
                if connection_data.get('ok'):
                    messages.success(
                        request, 'Conexao com Evolution validada com sucesso.')
                else:
                    messages.error(
                        request, 'Nao foi possivel validar conexao com Evolution.')
            else:
                if not number or not text:
                    messages.error(
                        request, 'Informe numero e mensagem para envio de teste.')
                else:
                    try:
                        status_code, body = client.send_text(
                            number=number, text=text)
                    except requests.RequestException as exc:
                        messages.error(
                            request, f'Falha ao conectar na Evolution: {exc}')
                    else:
                        response_data = {
                            'ok': 200 <= status_code < 300,
                            'status_code': status_code,
                            'response': body,
                        }
                        if response_data['ok']:
                            messages.success(
                                request, 'Mensagem de teste enviada com sucesso.')
                        else:
                            messages.error(
                                request, f'Falha no envio. HTTP {status_code}.')
                        response_pretty = json.dumps(
                            response_data, indent=2, ensure_ascii=False)

    context = {
        'status_data': status_data,
        'response_data': response_data,
        'response_pretty': response_pretty,
        'connection_data': connection_data,
        'connection_pretty': connection_pretty,
        'default_text': 'Teste de integracao do sistema de loja.',
        'webhook_url': request.build_absolute_uri('webhook/'),
    }
    return render(request, 'integracao_evolution.html', context)


@require_GET
def evolution_status(request):
    return JsonResponse(_status_payload())


@csrf_exempt
@require_POST
def evolution_webhook(request):
    if not settings.EVOLUTION_ENABLED:
        return JsonResponse({'ok': False, 'error': 'integracao_desabilitada'}, status=503)

    expected_secret = settings.EVOLUTION_WEBHOOK_SECRET
    provided_secret = request.headers.get('X-Webhook-Secret', '')

    if expected_secret and provided_secret != expected_secret:
        return JsonResponse({'ok': False, 'error': 'segredo_invalido'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return JsonResponse({'ok': False, 'error': 'json_invalido'}, status=400)

    event = payload.get('event')
    logger.info('Webhook Evolution recebido: event=%s', event)

    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def evolution_send_test(request):
    if not settings.EVOLUTION_ENABLED:
        return JsonResponse({'ok': False, 'error': 'integracao_desabilitada'}, status=503)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = request.POST

    number = str(payload.get('number', '')).strip()
    text = str(payload.get('text', '')).strip()

    if not number or not text:
        return JsonResponse({'ok': False, 'error': 'number_e_text_sao_obrigatorios'}, status=400)

    client = EvolutionClient()
    status_code, body = client.send_text(number=number, text=text)

    return JsonResponse({
        'ok': 200 <= status_code < 300,
        'status_code': status_code,
        'response': body,
    }, status=200 if 200 <= status_code < 300 else 502)
