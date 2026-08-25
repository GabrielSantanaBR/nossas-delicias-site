# Nossas Delícias — Plataforma de Confeitaria

Aplicação completa da **Nossas Delícias**, com vitrine pública para clientes e uma área privada de operação para a equipe.

> Para ChatGPT Work, Codex, Claude Code ou outro agente que continuar este projeto, leia primeiro [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md).

## Branches

- `main` — demonstração pública estática/GitHub Pages.
- `feature/full-commerce-platform` — aplicação Django real e branch principal do desenvolvimento completo.

Não trate a `main` como backend de produção.

## O produto

### Área pública

- portfólio da confeitaria;
- cardápio administrável;
- clientes e contas;
- sacola e pedidos;
- regiões e datas de entrega;
- cafeterias B2B;
- eventos/orçamentos;
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

O Django Admin em `/nd-admin/` funciona como retaguarda técnica. A operação diária deve preferir a Central de Gestão própria.

## Stack

- Django 5.x
- PostgreSQL
- Redis
- Django Channels / WebSockets
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

Destino inicial planejado: **Railway**.

Arquitetura mínima:

1. Django/ASGI
2. PostgreSQL
3. Redis

Mídia pode usar R2/object storage e CDN. Consulte [`DEPLOYMENT.md`](./DEPLOYMENT.md), [`SECURITY.md`](./SECURITY.md) e [`.env.example`](./.env.example).

## Regra importante

Não fazer merge em `main` nem habilitar pagamentos/domínio de produção sem validação e autorização explícita.
