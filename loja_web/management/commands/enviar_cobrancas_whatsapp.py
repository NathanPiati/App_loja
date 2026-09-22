from django.core.management.base import BaseCommand

from loja_web.cobranca_whatsapp import processar_todas_regras


class Command(BaseCommand):
    help = (
        'Verifica as regras de cobrança via WhatsApp ativas e dispara mensagens '
        'para clientes com pedidos/serviços em aberto que se enquadram nas regras.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas simula, sem enviar mensagens nem gravar histórico.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        resultados = processar_todas_regras(dry_run=dry_run)

        if not resultados:
            self.stdout.write(self.style.WARNING(
                'Nenhuma cobrança elegível para envio agora.'))
            return

        for item in resultados:
            if dry_run:
                self.stdout.write(
                    f"[DRY-RUN] Movimento {item['movimento_id']} -> {item['numero']}")
            elif item['sucesso']:
                self.stdout.write(self.style.SUCCESS(
                    f"Enviado: movimento {item['movimento_id']} -> {item['numero']}"))
            else:
                self.stdout.write(self.style.ERROR(
                    f"Falha: movimento {item['movimento_id']} -> {item['numero']}"))

        self.stdout.write(self.style.SUCCESS(
            f'Processamento concluído. {len(resultados)} cobrança(s) avaliada(s).'))
