from django.shortcuts import render

from billing.models import Plano


def landing_page(request):
    planos = Plano.objects.filter(ativo=True).order_by(
        'valor_mensal', 'nome')[:3]
    context = {
        'site_nome': 'InovaSys SaaS',
        'headline': 'Venda seu sistema como servico sem criar outro projeto agora.',
        'subheadline': 'Seu app atual continua como painel do cliente. O projeto ganha uma camada publica de marketing, planos, assinatura e onboarding no mesmo Django.',
        'planos': planos,
    }
    return render(request, 'site_publico/landing.html', context)


def planos_publicos(request):
    planos = Plano.objects.filter(ativo=True).order_by('valor_mensal', 'nome')
    return render(request, 'site_publico/planos.html', {'planos': planos})


def contato_publico(request):
    return render(request, 'site_publico/contato.html')
