import json
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import requests
from django.conf import settings
from django.utils import timezone

from loja_web.models import Empresa

from .models import Assinatura, Plano


class AsaasPaymentService:
    """Serviço simples de integração com a API do Asaas para cobrança e webhook."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv('ASAAS_API_KEY', '')
        self.base_url = base_url or os.getenv(
            'ASAAS_BASE_URL', 'https://api.asaas.com/v3').rstrip('/')

    def _headers(self) -> Dict[str, str]:
        return {
            'access_token': self.api_key,
            'Content-Type': 'application/json',
        }

    def criar_cobranca(self, assinatura: Assinatura, cliente_email: str, cliente_nome: str) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError('ASAAS_API_KEY não configurada.')

        payload = {
            'customer': None,
            'billingType': 'BOLETO',
            'value': str(assinatura.plano.valor_mensal),
            'dueDate': timezone.localdate().strftime('%Y-%m-%d'),
            'description': f'Plano {assinatura.plano.nome}',
            'externalReference': str(assinatura.id),
            'email': cliente_email,
            'name': cliente_nome,
        }

        response = requests.post(
            f'{self.base_url}/payments',
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def processar_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        event = payload.get('event') or payload.get('eventType') or ''
        payment = payload.get('payment') or payload
        external_reference = payment.get(
            'externalReference') or payment.get('external_reference') or ''

        assinatura = None
        if external_reference.isdigit():
            assinatura = Assinatura.objects.filter(
                id=int(external_reference)).first()

        if not assinatura:
            return {'status': 'ignored', 'reason': 'assinatura_nao_encontrada'}

        status = payment.get('status')
        if status in {'CONFIRMED', 'PAID'}:
            assinatura.status = Assinatura.STATUS_ATIVA
            assinatura.gateway = 'asaas'
            assinatura.gateway_customer_id = payment.get(
                'customer') or assinatura.gateway_customer_id
            assinatura.gateway_subscription_id = payment.get(
                'id') or assinatura.gateway_subscription_id
            assinatura.save(update_fields=[
                            'status', 'gateway', 'gateway_customer_id', 'gateway_subscription_id', 'atualizado_em'])
            return {'status': 'activated', 'assinatura_id': assinatura.id}

        if status in {'OVERDUE', 'REFUNDED', 'CANCELLED'}:
            assinatura.status = Assinatura.STATUS_ATRASADA if status == 'OVERDUE' else Assinatura.STATUS_CANCELADA
            assinatura.save(update_fields=['status', 'atualizado_em'])
            return {'status': 'updated', 'assinatura_id': assinatura.id}

        return {'status': 'ignored', 'reason': 'status_nao_tratado'}
