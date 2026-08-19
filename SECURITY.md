# Segurança — Nossas Delícias

## Princípios
- Nunca versionar tokens, senhas, chaves privadas ou dados reais de clientes.
- Produção somente com HTTPS, PostgreSQL, Redis autenticado/restrito e backups.
- Dados de cartão nunca são armazenados pela aplicação; o checkout é delegado ao provedor de pagamento.
- O admin usa rota separada, conta individual, permissões mínimas e autenticação em dois fatores (OTP).
- Uploads devem ter tamanho e tipo limitados e ser servidos fora do processo Django em produção.
- Conversas são vinculadas a pedidos e só podem ser acessadas pelo cliente proprietário ou staff.
- Preços, cupons, disponibilidade e status de pagamento são sempre validados no servidor.

## Primeiro acesso administrativo com 2FA

O `OTPAdminSite` bloqueia staff sem um segundo fator configurado. Para resolver o primeiro acesso sem desativar a proteção, use o comando oficial do django-otp em um terminal seguro do servidor:

```bash
python manage.py addstatictoken SEU_USUARIO_ADMIN
```

Use o token de uso único para entrar em `/nd-admin/`, cadastre um dispositivo TOTP para seu aplicativo autenticador e depois mantenha os tokens estáticos apenas como recuperação de emergência. Não execute esse bootstrap em logs públicos ou CI.

## Antes de produção
1. Defina `DJANGO_SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` e `REDIS_URL` por secrets do provedor.
2. Execute `python manage.py check --deploy`.
3. Crie um superusuário com senha longa e única e configure TOTP; habilite MFA também no provedor de infraestrutura e GitHub.
4. Configure Mercado Pago com credenciais de produção e webhook HTTPS assinado.
5. Configure rate limiting/WAF/DDoS protection na Cloudflare e limites de upload.
6. Configure Cloudflare R2 (ou storage equivalente) para fotos e mídia.
7. Configure backups automáticos do PostgreSQL e teste restauração.
8. Configure logs sem conteúdo de mensagens, senhas, tokens ou dados de cartão.
9. Publique Política de Privacidade e Termos adequados à operação e à LGPD.

## Incidentes
- Revogue/rotacione imediatamente qualquer secret exposto.
- Preserve logs de auditoria e bloqueie a credencial suspeita.
- Não copie dados pessoais para issues públicas do GitHub.
