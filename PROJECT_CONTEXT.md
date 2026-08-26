# Nossas Delícias — Contexto Mestre do Projeto

> Documento principal para ChatGPT Work, Codex, Claude Code e qualquer agente que continue este projeto.
>
> Antes de alterar código, leia este arquivo inteiro e confronte as instruções com o estado real do repositório. O código é a fonte de verdade sobre o que já está implementado; este documento define a direção, as regras de negócio e os critérios de qualidade.

## 1. Identidade do projeto

**Produto:** Nossas Delícias

**Tipo:** plataforma completa para uma confeitaria real.

O projeto possui duas experiências separadas:

1. **Site público da confeitaria** — marca, portfólio, cardápio, pedidos, clientes, cafeterias e eventos.
2. **Sistema privado de gestão** — pedidos, mensagens, cafeterias, eventos, logística, dados, financeiro, precificação, estoque, produção e administração.

A aplicação real é Django. A versão estática da `main` existe somente como demonstração visual/publicável em GitHub Pages.

## 2. Branches e regra de trabalho

- `main`: demonstração pública estática. Não é o backend de produção.
- `feature/full-commerce-platform`: aplicação Django real e branch principal de desenvolvimento do produto completo.

### Regra

Trabalhar por padrão em `feature/full-commerce-platform`.

Não fazer merge em `main` sem autorização explícita.

Não substituir a aplicação Django pela demo estática.

## 3. Princípio central de UX

O visitante **não deve entrar em um site de doces e receber uma apresentação sobre como o sistema administrativo funciona**.

### Área pública deve parecer uma confeitaria

Prioridades públicas:

- marca;
- produtos;
- fotos reais;
- portfólio de trabalhos;
- brownies, bolos e mimos;
- encomendas;
- cafeterias parceiras;
- eventos;
- entrega;
- sacola;
- conta do cliente;
- acompanhamento do pedido;
- conversa relacionada ao pedido.

### Nunca expor na vitrine pública

- dashboard administrativo;
- financeiro interno;
- BI interno;
- estoque;
- custos;
- margem;
- planilha;
- arquitetura técnica;
- explicações de como a operação funciona internamente;
- links para `/gestao/`, `/financeiro/` ou `/nd-admin/` para visitante anônimo.

O sistema privado pode ser sofisticado, mas deve permanecer invisível para o consumidor comum.

## 4. Público e canais de venda

A plataforma atende três canais principais.

### 4.1 Cliente final

- conta própria;
- cardápio de varejo;
- favoritos;
- sacola;
- endereço;
- região de entrega;
- datas disponíveis;
- pagamento;
- histórico;
- status do pedido;
- conversa contextual;
- promoções elegíveis.

### 4.2 Cafeterias / B2B

Cafeteria não é cliente comum.

Deve existir:

- cadastro/solicitação de parceria;
- aprovação administrativa;
- conta vinculada à cafeteria;
- tabela de preços B2B;
- pedido mínimo;
- condições comerciais próprias;
- histórico de pedidos;
- histórico financeiro;
- notas de entrega;
- conversa contextual;
- recorrência;
- desempenho por cafeteria.

#### Regra de edição da nota da cafeteria

A nota é editável até **16:00 do dia da entrega**, usando o timezone `America/Sao_Paulo`.

Antes das 16:00 pode:

- adicionar produto;
- remover produto;
- aumentar quantidade;
- diminuir quantidade;
- alterar observações;
- recalcular total conforme regras atuais.

A partir de 16:00:

- itens ficam congelados;
- valores comerciais ficam congelados;
- snapshot financeiro permanece fixo;
- nota não pode mais sofrer edição comercial.

Ainda podem evoluir:

- status de produção;
- status de entrega;
- status de pagamento;
- comunicação operacional.

A trava deve ser validada no servidor. Não confiar somente no frontend.

### 4.3 Eventos

Fluxo próprio, separado do pedido comum:

1. solicitação;
2. análise;
3. proposta/orçamento;
4. negociação;
5. aprovação;
6. conversão em pedido;
7. produção/entrega;
8. pagamento;
9. histórico e conversa.

## 5. Site público e portfólio

"Portfólio" significa **portfólio da confeitaria**, não portfólio do software.

Exemplos de seções:

- Brownies & doces;
- Bolos;
- Caixas e presentes;
- Produções para cafeterias;
- Eventos e mesas;
- trabalhos recentes;
- fotos oficiais da marca.

A home deve ter uma narrativa comercial simples:

**marca → desejo → produtos → trabalho realizado → formas de pedir → cafeterias/eventos → confiança → CTA**.

## 6. Direção visual

A estética precisa transmitir:

- confeitaria artesanal;
- elegância;
- profissionalismo;
- acolhimento;
- produto premium sem parecer luxo frio;
- boa fotografia;
- forte hierarquia editorial.

### Paleta base

- creme;
- cacau;
- caramelo;
- rosa suave;
- tons de papel/manteiga.

### Tipografia atual/direção

- `Playfair Display` para títulos/editorial;
- `DM Sans` para interface e texto funcional.

### Logo

Priorizar marca vetorial/nítida. Não ampliar raster pequeno.

O lockup pode usar símbolo SVG + texto nativo quando isso resultar em melhor nitidez que o arquivo original.

## 7. Motion e scroll

O site deve ser animado, mas **nunca instável**.

### Permitido/preferido

- `IntersectionObserver`;
- `opacity`;
- pequeno `translateY`;
- stagger curto;
- zoom de imagem;
- parallax somente na imagem interna;
- header reagindo ao scroll;
- barra de progresso discreta;
- transições de botões e cards;
- microinterações;
- marquee suave;
- movimento com `requestAnimationFrame` quando realmente necessário.

### Evitar

- múltiplos scripts alterando o mesmo `transform`;
- transformar containers responsáveis por `position: sticky`;
- transforms grandes em seções que alteram percepção de layout;
- tilt 3D em excesso;
- animações que brigam com hover;
- mudanças que provoquem layout shift;
- efeitos pesados em mobile.

Sempre respeitar `prefers-reduced-motion`.

Se uma animação causar salto, tremida, sobreposição ou travamento, estabilidade vence efeito visual.

## 8. Arquitetura técnica

### Backend

- Django 5.x;
- PostgreSQL em produção;
- Redis em produção;
- Django Channels / WebSockets para chat;
- ASGI/Daphne;
- `openpyxl` para importação/exportação de planilhas;
- Mercado Pago para pagamento;
- object storage/CDN para mídia quando configurado.

### Produção planejada

Railway inicialmente, com:

- aplicação Django/ASGI;
- PostgreSQL;
- Redis.

Cloudflare/R2 pode ser usado para mídia/CDN/WAF conforme evolução.

## 9. Sistema privado — Central de Gestão

O trabalho diário da empresa deve acontecer em uma interface própria de gestão.

O Django Admin continua existindo como **retaguarda técnica**, não como interface operacional principal.

Módulos esperados:

1. Visão geral
2. Pedidos
3. Mensagens
4. Clientes
5. Cafeterias
6. Eventos
7. Agenda / calendário operacional
8. Logística
9. Produtos
10. Cardápio
11. Precificação
12. Ingredientes
13. Fichas técnicas / receitas
14. Estoque
15. Despesas
16. Custos fixos
17. Contas a receber
18. Contas a pagar
19. Fluxo de caixa
20. Financeiro
21. Dados / BI
22. Importação da planilha
23. Exportação Excel
24. Configurações
25. Auditoria

A Central deve parecer um produto real, com sidebar, KPIs, filtros, tabelas legíveis, ações rápidas, estados vazios, loading e feedback claros.

## 10. Pedidos

Pedido deve conectar:

- cliente/cafeteria/evento;
- itens;
- quantidades;
- preço aplicado;
- descontos;
- entrega;
- região;
- data;
- pagamento;
- status;
- conversa;
- snapshot financeiro;
- histórico/auditoria.

Nunca confiar em preço enviado pelo navegador. O servidor calcula preço final.

## 11. Financeiro

O sistema precisa reproduzir e superar os resumos usados anteriormente na planilha.

### Indicadores principais

- faturamento;
- recebido;
- a receber;
- custo vendido;
- lucro bruto;
- margem;
- despesas;
- custos fixos;
- resultado;
- fluxo de caixa;
- ticket médio;
- quantidade vendida;
- pedidos pagos/abertos/vencidos.

### Visões

- por período;
- por mês;
- por ano;
- por produto;
- por cafeteria;
- por canal: cliente / cafeteria / evento.

### Regra de snapshot

Uma venda antiga **nunca deve mudar retroativamente** porque o preço de um ingrediente mudou hoje.

Ao vender, guardar no item:

- preço unitário vendido;
- quantidade;
- faturamento;
- custo unitário daquele momento;
- custo total;
- lucro;
- margem.

O custo atual serve para novas simulações/vendas. O snapshot serve para histórico.

## 12. Precificação

Fluxo conceitual:

`ingrediente → custo por g/ml/un → ficha técnica → custo de produção → rendimento → custo unitário → preço B2B → preço varejo → lucro → margem → preço recomendado`

Também considerar:

- margem desejada;
- taxa de pagamento;
- impostos;
- contingência;
- custos extras;
- simulador de aumento;
- ponto de equilíbrio;
- alertas de preço faltando;
- alertas de margem abaixo da meta;
- receita sem custo correto;
- receita sem produto vinculado.

Simuladores não devem alterar preços reais automaticamente.

## 13. Ingredientes, receitas e estoque

### Ingredientes

Guardar, quando aplicável:

- código;
- nome padrão;
- aliases;
- categoria;
- fornecedor;
- preço da embalagem;
- quantidade da embalagem;
- unidade base (`g`, `ml`, `un` etc.);
- custo unitário;
- estoque atual;
- estoque mínimo;
- ativo/inativo;
- histórico de preço.

### Fichas técnicas / receitas

Guardar:

- código;
- nome;
- categoria;
- ingredientes e quantidades;
- custos extras;
- perdas;
- rendimento;
- unidade de venda;
- custo total;
- custo unitário;
- produto público vinculado, quando existir.

### Movimentações de estoque

- compra/entrada;
- consumo em produção;
- perda/descarte;
- devolução;
- ajuste.

Movimentações precisam ser auditáveis.

## 14. Planilha Automatizada 4.0

A planilha histórica continua sendo uma referência e uma rota de importação/exportação, mas o sistema deve ser capaz de operar sem depender dela diariamente.

Abas/referências importantes:

- `PAINEL`;
- `BASE DE PREÇOS`;
- `PRECIFICAÇÃO`;
- `VENDAS CLIENTES`;
- `VENDAS CAFETERIAS`;
- `VENDAS EVENTOS`;
- `ANÁLISE DE VENDAS`;
- `DESPESAS`;
- `CUSTOS FIXOS`;
- `ESTOQUE`;
- `FLUXO DE CAIXA`.

### Importação

- validar extensão e estrutura interna do `.xlsx`;
- limitar tamanho;
- tratar valores brasileiros (`R$ 1.234,56`, `%` etc.);
- não publicar produto automaticamente;
- ingredientes/receitas podem entrar na área interna;
- preços públicos só devem atualizar quando o produto estiver corretamente vinculado;
- registrar lote/importação e erros.

### Exportação

Gerar workbook compatível com análise externa/contador e preservar separação entre canais.

## 15. Logística

Controlar:

- CEP/prefixos;
- regiões;
- taxa de entrega;
- pedido mínimo;
- dias disponíveis;
- horários;
- capacidade diária;
- bloqueios;
- rotas;
- datas especiais.

O cliente só deve selecionar datas realmente válidas.

### Concorrência

A última vaga de uma data não pode ser vendida para dois pedidos simultâneos.

Usar controle transacional no servidor/PostgreSQL quando a reserva for confirmada.

Pedidos abandonados/aguardando pagamento não devem bloquear capacidade indefinidamente.

## 16. Mensagens

Evitar chat genérico sem contexto.

Uma conversa deve estar ligada a uma entidade, por exemplo:

- pedido;
- nota de cafeteria;
- evento/orçamento.

A interface administrativa deve funcionar como caixa de entrada operacional.

Requisitos:

- isolamento por proprietário;
- staff autorizado;
- timestamps;
- lidas/não lidas;
- encerramento/reabertura;
- limite de tamanho;
- rate limiting;
- WebSocket em produção;
- persistência no banco como fonte de verdade.

Redis não é fonte de verdade.

## 17. Segurança — não negociável

- Argon2 para senha;
- CSRF;
- cookies `HttpOnly`;
- cookies `Secure` em produção;
- HSTS;
- CSP;
- `X-Frame-Options` / proteção equivalente;
- validação server-side;
- rate limiting em login, cadastro, pedido, chat e webhooks;
- secrets apenas em variáveis de ambiente;
- PostgreSQL obrigatório em produção;
- Redis obrigatório para canais em produção;
- 2FA/OTP para administração sensível;
- isolamento de dados por usuário;
- upload com limites e validação;
- logs sem segredos/PII desnecessária;
- trilha de auditoria para ações sensíveis;
- não armazenar dados de cartão.

Em produção, não cair silenciosamente para SQLite ou channel layer em memória.

## 18. Mercado Pago

- valor autoritativo vem do pedido calculado no servidor;
- nunca confiar em total do cliente;
- credenciais em secrets;
- validar webhook;
- consultar pagamento no provedor quando necessário;
- comparar moeda/valor com o pedido;
- usar idempotência;
- somente HTTPS em produção;
- não armazenar dados de cartão.

## 19. Mídia

Não guardar imagens grandes diretamente no banco.

Preferir object storage/CDN em produção.

Frontend:

- tamanhos adequados;
- WebP/AVIF quando possível;
- `loading=lazy` abaixo da dobra;
- imagem principal prioritária;
- alt text útil.

## 20. Deploy / Railway

Antes de produção, conferir `.env.example` e `DEPLOYMENT.md`.

Variáveis importantes incluem:

- `DJANGO_SECRET_KEY`;
- `ALLOWED_HOSTS`;
- `CSRF_TRUSTED_ORIGINS`;
- `DATABASE_URL`;
- `REDIS_URL`;
- Mercado Pago;
- R2, se usado;
- e-mail.

Domínio personalizado será conectado depois que a aplicação estiver estável no domínio temporário do Railway.

## 21. Health check e observabilidade

Produção deve possuir health endpoint capaz de verificar pelo menos:

- aplicação;
- banco;
- cache/Redis quando aplicável.

Não considerar "site abriu" como prova de que toda infraestrutura está saudável.

## 22. Processo de desenvolvimento

Antes de editar:

1. confirmar a branch;
2. ler este arquivo;
3. revisar o código relacionado;
4. verificar migrations;
5. procurar implementação já existente antes de criar outra;
6. identificar CSS/JS legado que pode conflitar;
7. preservar dados e compatibilidade sempre que possível.

### Evitar empilhamento infinito

Não criar `v18`, `v19`, `v20` apenas para sobrepor bugs de versões anteriores se o correto for consolidar/refatorar.

Quando uma área estiver madura, remover duplicação e fazer uma implementação canônica.

## 23. Checklist obrigatório antes de concluir alteração

Executar, conforme aplicável:

```bash
python -m compileall -q config store
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear
python manage.py test
```

Validar JavaScript:

```bash
find static -type f -name '*.js' -print0 | xargs -0 -n1 node --check
```

Também revisar:

- desktop;
- tablet;
- celular;
- menu;
- formulário;
- scroll;
- modal/drawer;
- estados vazios;
- erros;
- acessibilidade básica;
- `prefers-reduced-motion`.

Não declarar conclusão com teste falhando.

## 24. Estado conhecido da aplicação

No último ciclo validado antes deste documento:

- migrations `0001` e `0002` estavam versionadas;
- `django check` estava limpo;
- JavaScript estático estava passando por `node --check` na CI;
- banco de teste era criado do zero;
- `collectstatic` concluía;
- suíte completa tinha **33 testes passando**;
- testes cobriam também a separação entre vitrine pública e gestão privada.

Isto é um snapshot histórico. Sempre confirmar o estado atual da CI antes de assumir que continua válido.

## 25. Prioridades de evolução

Ordem sugerida para próximos ciclos:

1. consolidar/refatorar frontend e remover CSS/JS legado conflitante;
2. fazer revisão visual real em múltiplos breakpoints;
3. garantir que a Central de Gestão seja suficiente para operação diária sem depender do Django Admin;
4. revisar profundamente pedidos, mensagens e cafeteria B2B;
5. completar fluxo de eventos;
6. revisar financeiro, precificação, estoque e planilha ponta a ponta;
7. testes de concorrência/logística;
8. testes de autorização/segurança;
9. preparar Railway com PostgreSQL + Redis;
10. smoke test de produção;
11. somente então conectar domínio próprio e pagamentos reais.

## 26. Instrução curta para iniciar um novo Work

Use esta mensagem ao abrir um novo agente/workspace:

> Leia `PROJECT_CONTEXT.md` inteiro antes de alterar qualquer arquivo. Depois audite o estado atual de `feature/full-commerce-platform`, compare o código com as regras deste documento e continue o desenvolvimento sem remover funcionalidades existentes. O site público deve vender a confeitaria; todo sistema operacional/financeiro deve permanecer privado. Priorize estabilidade, consolidação de código, segurança e UX. Execute a suíte de validação antes de concluir e não faça merge em `main` sem autorização explícita.
