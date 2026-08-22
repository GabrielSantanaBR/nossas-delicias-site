# Produção recomendada

## Camadas
1. Cloudflare na borda: DNS, CDN para estáticos, WAF, proteção DDoS e rate limiting.
2. Django/ASGI: aplicação e WebSockets.
3. PostgreSQL gerenciado: fonte de verdade de clientes, pedidos e pagamentos.
4. Redis gerenciado: channel layer do chat; nunca fonte de verdade.
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
