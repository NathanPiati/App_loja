from rest_framework import serializers
from .models import Produto, Servicos, Pedido, ItensPedido, ItemServico, Cliente, Fornecedor


class ProdutoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produto
        fields = '__all__'


class ServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicos
        fields = '__all__'


class ItensPedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItensPedido
        fields = '__all__'


class ItemServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemServico
        fields = '__all__'


class PedidoSerializer(serializers.ModelSerializer):
    itens = ItensPedidoSerializer(many=True, read_only=True)
    itens_servico = ItemServicoSerializer(many=True, read_only=True)

    class Meta:
        model = Pedido
        fields = '__all__'


class ItensPedidoSerializer(serializers.ModelSerializer):
    produto_id = serializers.PrimaryKeyRelatedField(queryset=Produto.objects.all(), source='produto')

    class Meta:
        model = ItensPedido
        fields = ['produto_id', 'descricao', 'quantidade', 'preco_unitario']

class ItemServicoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemServico
        fields = ['descricao', 'quantidade', 'preco_unitario']

class PedidoSerializer(serializers.ModelSerializer):
    cliente_id = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all(), source='cliente')
    itens = ItensPedidoSerializer(many=True)
    itens_servico = ItemServicoSerializer(many=True)

    class Meta:
        model = Pedido
        fields = ['id', 'cliente_id', 'itens', 'itens_servico']

    def create(self, validated_data):
        itens_data = validated_data.pop('itens')
        servicos_data = validated_data.pop('itens_servico')
        pedido = Pedido.objects.create(**validated_data)

        for item in itens_data:
            ItensPedido.objects.create(pedido=pedido, **item)

        for servico in servicos_data:
            ItemServico.objects.create(pedido=pedido, **servico)

        return pedido



class FornecedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fornecedor
        fields = '__all__'        