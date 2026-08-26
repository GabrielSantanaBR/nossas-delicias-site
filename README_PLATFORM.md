# Nossas Delícias — Plataforma de Pedidos

## O que a plataforma entrega

- Django + PostgreSQL para catálogo, clientes, pedidos e histórico.
- Categorias e produtos totalmente editáveis pelo painel administrativo.
- Galeria de fotos, descrição, destaque, quantidade mínima e antecedência por produto.
- Tabelas de preço para cliente, cafeteria, evento e preços personalizados.
- Regiões, taxa de entrega, pedido mínimo, rotas e capacidade por data.
- Conta do cliente com perfil editável, endereços, favoritos, histórico de pedidos, pagamentos e promoções elegíveis.
- Eventos com proposta detalhada, histórico, conversa contextual, aceite do cliente e conversão transacional em pedido.
- Simulador de precificação com margem, lucro projetado e ponto de equilíbrio sem alterar preços reais.
- Chat em tempo real por pedido com WebSocket e Redis em produção.
- Integração de pagamentos desenhada para Mercado Pago sem armazenar dados de cartão.
- Segurança de produção com Argon2, CSRF, cookies seguros, HSTS, limites de upload e secrets em ambiente.

## Desenvolvimento local

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations store
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse `/nd-admin/` para cadastrar categorias, produtos, imagens, preços, regiões, rotas, dias disponíveis e promoções.

## Produção

Use PostgreSQL e Redis gerenciados, armazenamento de mídia em serviço de objetos/CDN, HTTPS obrigatório e WAF/rate limiting na borda. Execute `python manage.py check --deploy` antes da publicação.

A integração de pagamento só deve ser habilitada depois de configurar credenciais reais em secrets do provedor e validar o webhook assinado. Nunca use credenciais em arquivos versionados.
