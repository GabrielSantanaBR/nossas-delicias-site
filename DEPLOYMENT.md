# Deploy de produção no Render

O repositório possui um Blueprint em `render.yaml`. Ao conectá-lo no Render, ele provisiona a aplicação Django/ASGI, PostgreSQL e Render Key Value na mesma região. O build coleta os arquivos estáticos e aplica somente migrations versionadas; o health check em `/health/` verifica aplicação, banco e cache.

O runtime está fixado em Python 3.12 por `.python-version`, evitando mudanças inesperadas quando o Render atualizar sua versão padrão.

## Camadas
1. Cloudflare na borda: DNS, CDN para estáticos, WAF, proteção DDoS e rate limiting.
2. Django/ASGI no Render: aplicação e WebSockets.
3. Render PostgreSQL: fonte de verdade de clientes, pedidos e pagamentos.
4. Render Key Value/Valkey: channel layer, cache e rate limiting; nunca fonte de verdade.
5. Object storage/CDN: fotos de produtos e uploads.
6. Mercado Pago: processamento de cartão/Pix; a aplicação não armazena cartão.

## Alta disponibilidade e desempenho
- Não carregar fotos gigantes; gerar versões WebP/AVIF e usar `loading=lazy` abaixo da dobra.
- Cachear páginas e catálogo público na borda quando possível, nunca páginas de conta/pedido.
- Definir timeouts, health checks e pelo menos duas instâncias quando o volume justificar.
- Banco com backup automático e teste periódico de restauração.
- Rate limiting em login, cadastro, criação de pedido, chat e webhooks.
- Logs estruturados sem PII sensível.

## Admin
- `/nd-admin/` não substitui autenticação forte. Use usuário individual, senha única e MFA no provedor/SSO quando adotado.
- Nunca liberar `is_staff` para clientes.
- Operações de preço, entrega e pedido devem ser auditáveis.

## Pagamentos
- Credenciais somente no secret manager do host.
- Produção somente HTTPS.
- Validar assinatura de webhook e consultar o recurso no Mercado Pago via servidor antes de alterar o pedido.
- Usar idempotência na criação de pagamentos.

## Secrets solicitados pelo Blueprint

- Mercado Pago: `MERCADO_PAGO_ACCESS_TOKEN` e `MERCADO_PAGO_WEBHOOK_SECRET`.
- Cloudflare R2: conta, bucket, chaves e domínio público para persistir uploads.
- E-mail SMTP deve ser configurado diretamente no ambiente antes de usar recuperação de senha em produção.

Não habilite `DEMO_MODE` no serviço de produção. Depois do primeiro deploy, crie o superusuário pelo Shell do Render, cadastre um dispositivo TOTP e teste `/health/`, login, upload, checkout e WebSocket.
