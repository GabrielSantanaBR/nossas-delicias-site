# Dados de demonstração — Nossas Delícias

A branch `feature/full-commerce-platform` possui um seed determinístico para visualizar a plataforma preenchida sem usar dados reais de clientes.

## Executar

Para montar **dados + calendário** em um único comando:

```bash
python manage.py migrate
python manage.py seed_nossas_delicias_full_demo --year 2026
```

Para permitir login nas contas fictícias durante um ambiente de teste:

```bash
python manage.py seed_nossas_delicias_full_demo \
  --year 2026 \
  --demo-password "UMA-SENHA-TEMPORARIA" \
  --admin-password "OUTRA-SENHA-TEMPORARIA"
```

Nunca versione essas senhas e não use credenciais de demonstração em produção real. A Central de Gestão e o Admin avançado exigem o fluxo administrativo/OTP configurado no ambiente.

## O que é criado

- 14 clientes fictícios;
- 6 cafeterias fictícias aprovadas;
- 1 cafeteria aguardando aprovação;
- tabela de preços de cliente e tabela B2B;
- 8 produtos com custo e preço por canal;
- histórico de pedidos e entregas durante agosto;
- entregas B2B nas terças, quintas e sextas;
- regiões de clientes em Nilópolis e Zona Oeste;
- regiões B2B em Centro e Zona Sul;
- calendário de agosto explicitamente preenchido e janela futura de agendamento;
- estoque, insumos, custos fixos e despesas;
- pagamentos e snapshots financeiros;
- conversas ligadas aos pedidos;
- orçamentos de eventos;
- pedidos recorrentes das cafeterias.

## Regras demonstradas

### Clientes

- antecedência mínima: 7 dias;
- máximo global: 5 agendamentos por dia;
- rota: Nilópolis + Zona Oeste;
- preços de cliente;
- domingo fechado no calendário demo.

### Cafeterias

- preço B2B só depois de `CafeAccount.approved=True` e `active=True`;
- candidatura pendente continua recebendo comportamento/preço de cliente;
- entregas: terça, quinta e sexta;
- rota: Centro + Zona Sul;
- pedido mínimo B2B;
- nota de entrega e snapshot financeiro.

## Endereços internos

- Central de Gestão: `/gestao/`
- Financeiro: `/financeiro/`
- Admin avançado com OTP: `/nd-admin/`

Os emails usam `example.invalid` e todos os registros são claramente fictícios.
