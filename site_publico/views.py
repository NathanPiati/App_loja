from django.shortcuts import render

from billing.models import Plano, Sistema


def _planos_publicos_por_sistema(request):
    sistemas = Sistema.objects.filter(ativo=True)
    sistema_slug = request.GET.get('sistema', '')
    sistema_selecionado = sistemas.filter(slug=sistema_slug).first()
    planos = Plano.objects.filter(ativo=True)

    if sistema_selecionado:
        planos = planos.filter(sistema=sistema_selecionado)
    elif sistema_slug:
        planos = planos.none()

    return sistemas, sistema_selecionado, planos


def landing_page(request):
    sistemas, sistema_selecionado, planos = _planos_publicos_por_sistema(
        request)
    sistema_personais = (
        sistemas.filter(slug='personais').first()
        or sistemas.filter(nome__icontains='personal').first()
    )
    context = {
        'site_nome': 'InovaSys SaaS',
        'headline': 'Venda seu sistema como servico sem criar outro projeto agora.',
        'subheadline': 'Seu app atual continua como painel do cliente. O projeto ganha uma camada publica de marketing, planos, assinatura e onboarding no mesmo Django.',
        'sistemas': sistemas,
        'sistema_personais': sistema_personais,
        'sistema_selecionado': sistema_selecionado,
        'planos': planos[:3],
    }
    return render(request, 'site_publico/landing.html', context)


def planos_publicos(request):
    sistemas, sistema_selecionado, planos = _planos_publicos_por_sistema(
        request)
    return render(request, 'site_publico/planos.html', {
        'sistemas': sistemas,
        'sistema_selecionado': sistema_selecionado,
        'planos': planos,
    })


def contato_publico(request):
    return render(request, 'site_publico/contato.html')
