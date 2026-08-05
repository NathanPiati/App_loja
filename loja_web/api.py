from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Servicos
from .serializers import ServicoSerializer
from rest_framework.generics import ListAPIView
from rest_framework.filters import SearchFilter


class ServicoSearchAPIView(APIView):
    def get(self, request):
        query = request.GET.get('q', '').strip()
        if query:
            servicos = Servicos.objects.filter(nome__icontains=query) | Servicos.objects.filter(id__icontains=query)
        else:
            servicos = Servicos.objects.all()
        serializer = ServicoSerializer(servicos, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

# class ClienteAPIList(ListAPIView):
#     queryset = Cliente.objects.all()
#     serializer_class = ClienteSerializer
#     filter_backends = [SearchFilter]
#     search_fields = ['id', 'nome', 'telefone']