# Segurança — Nossas Delícias

## Princípios

- Nenhuma chave, senha, token de pagamento ou credencial deve ser commitada no GitHub.
- O painel interno não é protegido por obscuridade: a rota é discreta, mas o acesso depende de autenticação, permissões e sessão segura.
- O sistema não armazena número completo de cartão, CVV ou dados equivalentes. O provedor de pagamento deve tokenizar/processar esses dados.
- Todo tráfego de produção deve usar HTTPS.

## Aplicação

- Django CSRF ativo para todas as mutações web.
- Cookies de sessão e CSRF com `Secure` em produção; sessão `HttpOnly` e `SameSite=Lax`.
- HSTS e `X-Frame-Options: DENY` em produção.
- Senhas armazenadas somente pelos hashers do Django.
- Validação de autorização no servidor para pedidos e WebSockets.
- Uploads limitados por tamanho/tipo no proxy e validados na aplicação antes de produção.
- Logs nunca devem incluir `SECRET_KEY`, tokens, cookies, senhas ou payload completo de pagamento.

## Borda / Cloudflare

Configurar em produção:

1. Proxy DNS pela Cloudflare.
2. WAF/managed rules.
3. Rate limiting mais rígido em `/entrar/`, endpoints de cadastro, checkout, webhooks e APIs.
4. Turnstile em login/cadastro/recuperação quando houver comportamento suspeito ou após tentativas falhas.
5. Proteção DDoS e Bot Fight/Managed Challenge conforme o plano.
6. Bloquear acesso direto ao origin quando a infraestrutura permitir, aceitando apenas tráfego do proxy confiável.

## Pagamentos

- Segredos em variáveis de ambiente ou secret manager.
- Webhooks devem verificar assinatura do provedor antes de alterar estado de pagamento.
- O valor final é sempre recalculado no servidor; nunca confiar no preço enviado pelo navegador.
- Use idempotência para criação/confirmação de cobranças e processamento de webhook.
- Armazene apenas referência externa, status e valor necessários para conciliação.

## Banco e backups

- PostgreSQL privado, sem porta pública quando possível.
- Usuário de banco com privilégios mínimos.
- Backup automatizado e teste periódico de restauração.
- Criptografia em trânsito e, se disponível no provedor, em repouso.

## Antes de produção

- `DEBUG=False`.
- `SECRET_KEY` longa e aleatória.
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` específicos.
- `python manage.py check --deploy` sem alertas críticos.
- Redis de produção autenticado/privado.
- Revisar permissões de usuários staff e superuser.
- Configurar monitoramento, alertas e rotação de segredos.
