# Privacidade e dados de clientes

Este arquivo é uma especificação técnica interna, não substitui uma política jurídica final.

## Dados necessários
- Conta: nome, e-mail, credencial protegida por hash e, quando informado, telefone.
- Pedido: produtos, endereço necessário à entrega, região, data, valores e status.
- Pagamento: somente identificadores, valor, método e status retornados pelo provedor; nunca número de cartão/CVV.
- Conversa: mensagens vinculadas ao pedido para atendimento.
- Relacionamento: quantidade de pedidos e valor acumulado para oferecer benefícios quando permitido.

## Regras
- Minimizar coleta e retenção.
- Separar observações internas de dados visíveis ao cliente.
- Consentimento de marketing é opcional e separado da prestação do serviço.
- Não expor dados pessoais em logs, URLs públicas, analytics, issues ou repositório.
- Acesso administrativo segue menor privilégio.
- Implementar rotinas de exportação/correção/exclusão ou anonimização quando a política operacional for definida.
