# Projeto App_loja
Projeto web Django para oficinas e distribuidoras de pecas!

Configuracao local/deploy

O projeto agora pode usar variaveis de ambiente via arquivo .env na raiz. Isso permite rodar no mesmo servidor ou no mesmo computador de outros sistemas sem deixar banco, debug e hosts fixos no codigo.

Exemplo de .env para PostgreSQL:

DJANGO_SECRET_KEY=sua-chave-aqui
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,seu-dominio.com
DB_ENGINE=postgresql
DB_NAME=sistema
DB_USER=sistema2
DB_PASSWORD=123456
DB_HOST=localhost
DB_PORT=5432

Exemplo de .env para SQLite local:

DJANGO_SECRET_KEY=sua-chave-aqui
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
DB_ENGINE=sqlite
SQLITE_PATH=BD/systemdb.sqlite3

Se nenhum .env for definido, o sistema usa SQLite local por padrao.

Use o arquivo .env.example como base para criar o seu .env do ambiente onde o sistema vai rodar.

Integracao Evolution API (WhatsApp)

O projeto agora tem endpoints prontos para integrar com Evolution API:

- GET /integracoes/evolution/status/
- POST /integracoes/evolution/webhook/
- POST /integracoes/evolution/enviar-teste/

Variaveis no .env:

EVOLUTION_ENABLED=True
EVOLUTION_BASE_URL=http://localhost:8080
EVOLUTION_API_KEY=sua-chave
EVOLUTION_INSTANCE=loja
EVOLUTION_SEND_TEXT_PATH=/message/sendText/{instance}
EVOLUTION_WEBHOOK_SECRET=um-segredo-forte

Fluxo rapido:

1. Suba a Evolution API (container) na porta 8080.
2. Configure a instancia e conecte o WhatsApp via QR Code na Evolution.
3. Configure webhook para:
	http://SEU_HOST:8000/integracoes/evolution/webhook/
4. Teste status no navegador:
	http://127.0.0.1:8000/integracoes/evolution/status/

Observacao:
- Evolution e Django rodam no mesmo projeto/repositorio, mas sao servicos separados.
