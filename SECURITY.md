# Segurança — Nossas Delícias

## Princípios
- Nunca versionar tokens, senhas, chaves privadas ou dados reais de clientes.
- Produção somente com HTTPS, PostgreSQL, Redis autenticado/restrito e backups.
- Dados de cartão nunca são armazenados pela aplicação; o checkout é delegado ao provedor de pagamento.
- O admin usa rota separada, conta individual e permissões mínimas. Staff não deve compartilhar login.
- Uploads devem ter tamanho e tipo limitados e ser servidos fora do processo Django em produção.
- Conversas são vinculadas a pedidos e só podem ser acessadas pelo cliente proprietário ou staff.

## Antes de produção
1. Defina `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` e `REDIS_URL` por secrets do provedor.
2. Execute `python manage.py check --deploy`.
3. Crie um superusuário com senha longa e única; habilite MFA no provedor de infraestrutura e GitHub.
4. Configure Mercado Pago com credenciais de produção e webhook HTTPS assinado.
5. Configure rate limiting/WAF no proxy/CDN e limite de upload.
6. Configure backups automáticos e teste restauração.
7. Configure logs sem conteúdo de mensagens, senhas, tokens ou dados de cartão.
8. Publique Política de Privacidade e Termos adequados à operação e à LGPD.

## Incidentes
- Revogue/rotacione imediatamente qualquer secret exposto.
- Preserve logs de auditoria e bloqueie a credencial suspeita.
- Não copie dados pessoais para issues públicas do GitHub.
