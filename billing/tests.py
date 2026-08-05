from django.contrib.auth import get_user_model
from django.test import TestCase

from loja_web.models import Empresa

from .models import Assinatura, Plano
from .services import AsaasPaymentService


class AsaasWebhookTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='tester', password='12345')
        self.empresa = Empresa.objects.create(nome='Empresa Teste')
        self.plano = Plano.objects.create(
            nome='Plano Teste', slug='plano-teste', valor_mensal='49.90')
        self.assinatura = Assinatura.objects.create(
            empresa=self.empresa,
            plano=self.plano,
            responsavel=self.user,
            status=Assinatura.STATUS_TRIAL,
        )

    def test_webhook_confirma_assinatura(self):
        service = AsaasPaymentService(
            api_key='fake-key', base_url='https://example.test')
        payload = {
            'event': 'PAYMENT_RECEIVED',
            'payment': {
                'id': 'pay_123',
                'status': 'CONFIRMED',
                'externalReference': str(self.assinatura.id),
                'customer': 'cus_123',
            },
        }

        result = service.processar_webhook(payload)

        self.assertEqual(result['status'], 'activated')
        self.assinatura.refresh_from_db()
        self.assertEqual(self.assinatura.status, Assinatura.STATUS_ATIVA)
        self.assertEqual(self.assinatura.gateway, 'asaas')
