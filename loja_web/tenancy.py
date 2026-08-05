from django.db.models import QuerySet

from .models import Empresa, UsuarioEmpresa

TENANT_SESSION_KEY = 'empresa_id'


def get_empresas_usuario(user):
    if not user.is_authenticated:
        return Empresa.objects.none()

    if user.is_superuser:
        return Empresa.objects.all().order_by('id')

    return Empresa.objects.filter(
        usuarios_vinculados__user=user,
        usuarios_vinculados__ativo=True,
    ).distinct().order_by('id')


def get_empresa_padrao_usuario(user):
    empresas = get_empresas_usuario(user)

    if not user.is_authenticated:
        return None

    if user.is_superuser:
        return empresas.first()

    vinculo_padrao = UsuarioEmpresa.objects.filter(
        user=user,
        ativo=True,
        padrao=True,
    ).select_related('empresa').first()

    if vinculo_padrao:
        return vinculo_padrao.empresa

    return empresas.first()


def get_empresa_ativa(request):
    empresa = getattr(request, 'empresa_ativa', None)
    if empresa:
        return empresa

    if not request.user.is_authenticated:
        return None

    empresa_id = request.session.get(TENANT_SESSION_KEY)
    if empresa_id:
        try:
            return get_empresas_usuario(request.user).get(id=empresa_id)
        except Empresa.DoesNotExist:
            return None

    return get_empresa_padrao_usuario(request.user)


def filtrar_queryset_empresa(request, queryset: QuerySet, campo_empresa='empresa'):
    if not hasattr(queryset.model, campo_empresa):
        return queryset

    empresa = get_empresa_ativa(request)
    if not empresa:
        return queryset.none()

    return queryset.filter(**{campo_empresa: empresa})


def atribuir_empresa(instancia, request, campo_empresa='empresa'):
    if not hasattr(instancia, campo_empresa):
        return instancia

    empresa = get_empresa_ativa(request)
    if empresa and getattr(instancia, campo_empresa + '_id', None) is None:
        setattr(instancia, campo_empresa, empresa)

    return instancia
