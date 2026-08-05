from .tenancy import TENANT_SESSION_KEY, get_empresa_padrao_usuario, get_empresas_usuario


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa_ativa = None

        if request.user.is_authenticated:
            empresa_id = request.session.get(TENANT_SESSION_KEY)
            empresas_usuario = get_empresas_usuario(request.user)

            if empresa_id:
                request.empresa_ativa = empresas_usuario.filter(
                    id=empresa_id).first()

            if request.empresa_ativa is None:
                request.empresa_ativa = get_empresa_padrao_usuario(
                    request.user)
                if request.empresa_ativa:
                    request.session[TENANT_SESSION_KEY] = request.empresa_ativa.id

        response = self.get_response(request)
        return response
