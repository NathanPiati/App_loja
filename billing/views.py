import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt

from .models import Assinatura, Plano, Sistema
from .services import AsaasPaymentService


def lista_planos(request):
    sistemas = Sistema.objects.filter(ativo=True)
    sistema_slug = request.GET.get('sistema', '')
    sistema_selecionado = sistemas.filter(slug=sistema_slug).first()
    planos = Plano.objects.filter(ativo=True).order_by('valor_mensal', 'nome')
    if sistema_selecionado:
        planos = planos.filter(sistema=sistema_selecionado)
    elif sistema_slug:
        planos = planos.none()
    return render(request, 'billing/lista_planos.html', {
        'planos': planos,
        'sistemas': sistemas,
        'sistema_selecionado': sistema_selecionado,
    })


def iniciar_assinatura(request, plano_id):
    plano = get_object_or_404(Plano, id=plano_id, ativo=True)
    if request.method == 'POST' and request.user.is_authenticated:
        assinatura, created = Assinatura.objects.get_or_create(
            empresa=request.user.empresa_set.first() if hasattr(
                request.user, 'empresa_set') else None,
            plano=plano,
            defaults={
                'responsavel': request.user,
                'status': Assinatura.STATUS_TRIAL,
            },
        )
        try:
            service = AsaasPaymentService()
            cobranca = service.criar_cobranca(
                assinatura=assinatura,
                cliente_email=request.user.email or 'cliente@example.com',
                cliente_nome=request.user.get_full_name() or request.user.username,
            )
        except RuntimeError as exc:
            return render(request, 'billing/iniciar_assinatura.html', {
                'plano': plano,
                'erro': str(exc),
            })
        except Exception as exc:
            return render(request, 'billing/iniciar_assinatura.html', {
                'plano': plano,
                'erro': f'Falha ao criar cobrança: {exc}',
            })

        return render(request, 'billing/iniciar_assinatura.html', {
            'plano': plano,
            'cobranca': cobranca,
        })

    return render(request, 'billing/iniciar_assinatura.html', {'plano': plano})


@login_required
def minha_assinatura(request):
    assinatura = Assinatura.objects.filter(responsavel=request.user).select_related(
        'plano', 'empresa'
    ).first()
    return render(request, 'billing/minha_assinatura.html', {'assinatura': assinatura})


@csrf_exempt
def webhook_asaas(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Método não permitido'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'message': 'Payload inválido'}, status=400)

    service = AsaasPaymentService()
    result = service.processar_webhook(payload)
    return JsonResponse({'ok': True, 'result': result})
