#!/bin/bash
# Script de deploy para App_loja (clona repositório inteiro, preservando systemdb.sqlite3)

echo "🚀 Iniciando deploy do App_loja com clone completo do repositório..."

# Cria diretório temporário para clonar o repositório
TEMP_DIR="/tmp/App_loja_clone_$(date +%s)"
echo "📂 Criando diretório temporário: $TEMP_DIR..."
mkdir -p "$TEMP_DIR"

# Clona o repositório inteiro no diretório temporário
echo "📥 Clonando repositório inteiro..."
git clone <REPO_URL> "$TEMP_DIR" || { echo "❌ Falha ao clonar repositório"; exit 1; }

# Copia arquivos para a pasta do projeto, excluindo systemdb.sqlite3, venv e .git
echo "📂 Copiando arquivos para /home/App_loja (preservando systemdb.sqlite3)..."
rsync -a --exclude='venv' --exclude='.git' --exclude='systemdb.sqlite3' "$TEMP_DIR/" /home/App_loja/

# Remove diretório temporário
echo "🗑️ Removendo diretório temporário..."
rm -rf "$TEMP_DIR"

# Vai para a pasta do projeto
cd /home/App_loja || exit

# Ativa venv
echo "🐍 Ativando virtualenv..."
source venv/bin/activate

# Atualiza dependências (se houver novas)
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Migrações
echo "🗂️ Rodando migrations..."
python manage.py migrate

# Coleta estáticos
echo "🎨 Atualizando arquivos estáticos..."
python manage.py collectstatic --noinput

# Verifica se o serviço loja existe antes de reiniciar
echo "🔄 Verificando e reiniciando serviço loja..."
if systemctl --quiet is-active loja; then
    sudo systemctl restart loja
else
    echo "⚠️ Serviço loja não encontrado. Verifique a configuração do systemd."
    exit 1
fi

echo "✅ Deploy com clone completo finalizado com sucesso!"