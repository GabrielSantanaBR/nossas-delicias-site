# Nossas Delícias — Plataforma de Confeitaria

Aplicação completa da **Nossas Delícias**, com vitrine pública para clientes e uma área privada de operação para a equipe.

> Para ChatGPT Work, Codex, Claude Code ou outro agente que continuar este projeto, leia primeiro [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md).

## Branches

- `main` — aplicação Django de produção e fonte do deploy no Render.
- `feature/full-commerce-platform` — histórico da evolução inicial da plataforma.

O GitHub Pages não faz parte da arquitetura de produção.

## O produto

### Área pública

- portfólio da confeitaria;
- cardápio administrável;
- ateliê visual para montar bolos personalizados por etapas;
- cardápio inicial de brigadeiros, brownies, camafeus, banoffee e doces de evento;
- clientes e contas;
- edição de perfil, endereços salvos e favoritos;
- sacola e pedidos;
- regiões e datas de entrega;
- cafeterias B2B;
- eventos/orçamentos com proposta, aceite, conversa e conversão em pedido;
- acompanhamento de pedidos;
- mensagens ligadas ao contexto do pedido.

A vitrine pública deve parecer uma confeitaria profissional. Financeiro, estoque, BI, planilha e controles internos ficam privados.

### Área privada

A Central de Gestão concentra, conforme o módulo:

- pedidos;
- mensagens;
- clientes;
- cafeterias;
- eventos;
- logística;
- produtos e catálogo;
- cadastro integrado de produtos, canais, preços e custo de produção;
- registro de vendas diretas (balcão, WhatsApp, eventos e cafeterias), com cliente, recebimento e baixa de estoque;
- precificação;
- ingredientes e fichas técnicas;
- estoque;
- despesas e custos fixos;
- contas a receber/pagar;
- fluxo de caixa;
- relatórios financeiros;
- dados/BI;
- importação/exportação da Planilha Automatizada 4.0;
- auditoria e configurações.

O simulador privado de precificação calcula custo unitário, preço recomendado, margem, impacto por lote e ponto de equilíbrio sem alterar o cardápio real.

O Django Admin em `/nd-admin/` funciona como retaguarda técnica. A operação diária deve preferir a Central de Gestão própria.

## Stack

- Django 5.x
- PostgreSQL
- Redis
- Django Channels / WebSockets
- fotos locais de demonstração com fallback automático, sem dependência de hotlinks externos;
- ASGI / Daphne
- `openpyxl`
- Mercado Pago
- WhiteNoise
- storage S3/R2 opcional para mídia

## Desenvolvimento local

```bash
python -m venv .venv
```

### Windows

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Linux/macOS

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Depois:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Validação antes de concluir alterações

```bash
python -m compileall -q config store
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
python manage.py test
```

JavaScript:

```bash
find static -type f -name '*.js' -print0 | xargs -0 -n1 node --check
```

A CI também valida migrations, Django, arquivos estáticos, JavaScript e testes.

## Produção

Destino configurado: **Render**, por meio do [`render.yaml`](./render.yaml).

Arquitetura mínima:

1. Django/ASGI
2. PostgreSQL
3. Render Key Value/Valkey, compatível com Redis

O Blueprint cria o serviço web, PostgreSQL e cache. Para persistir fotos enviadas pelo painel, configure as variáveis R2 solicitadas pelo Render. Consulte [`DEPLOYMENT.md`](./DEPLOYMENT.md), [`SECURITY.md`](./SECURITY.md) e [`.env.example`](./.env.example).

## Regra importante

Não habilitar pagamentos reais nem domínio definitivo sem configurar os secrets, validar o webhook do Mercado Pago e executar um smoke test no ambiente publicado.
