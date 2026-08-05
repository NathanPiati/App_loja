from rest_framework import serializers
from .models import Servicos

class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicos
        fields = ['id', 'nome', 'preco']



# class ClienteSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Cliente
#         fields = ['id', 'nome', 'telefone']