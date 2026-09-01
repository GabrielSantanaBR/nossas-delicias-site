from django.http import HttpResponse
from django.urls import reverse

PUBLIC_PAGES = (
    ("home", "Semanal", "1.0"),
    ("catalog", "Semanal", "0.95"),
    ("cake_studio", "Monthly", "0.9"),
    ("event_portal", "Monthly", "0.85"),
    ("cafe_portal", "Monthly", "0.75"),
)


def _absolute(request, name):
    return request.build_absolute_uri(reverse(name))


def sitemap(request):
    entries = []
    for name, changefreq, priority in PUBLIC_PAGES:
        entries.append(
            f"  <url><loc>{_absolute(request, name)}</loc><changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        )
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(entries) + "\n</urlset>\n"
    return HttpResponse(body, content_type="application/xml; charset=utf-8")


def robots(request):
    sitemap_url = _absolute(request, "sitemap_xml")
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /gestao/",
            "Disallow: /financeiro/",
            "Disallow: /nd-admin/",
            "Disallow: /pagamentos/",
            "Disallow: /minha-conta/",
            "Disallow: /carrinho/",
            "Disallow: /pedidos/",
            "Disallow: /cafeterias/pedidos/",
            "Disallow: /eventos/orcamentos/",
            "",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def llms(request):
    links = {name: _absolute(request, name) for name, _, _ in PUBLIC_PAGES}
    body = f"""# Nossas Delícias

> Confeitaria artesanal com encomendas de brownies, bolos, doces, presentes, fornecimento para cafeterias e produção para eventos.

## Sobre
Nossas Delícias é uma confeitaria artesanal. O conteúdo público deve ser interpretado como catálogo e informação comercial para consumidores, parceiros e organizadores de eventos.

## Áreas públicas
- Início: {links['home']}
- Cardápio: {links['catalog']}
- Monte seu bolo: {links['cake_studio']}
- Eventos: {links['event_portal']}
- Cafeterias: {links['cafe_portal']}

## Atendimento e entrega
A plataforma permite encomendas com data de entrega, respeitando as regiões e condições disponíveis no momento do pedido. Consulte o fluxo de compra para disponibilidade atual.

## Produtos
O cardápio publicado no site é a fonte pública de produtos e preços. Não inferir disponibilidade, preço ou condições comerciais a partir de conteúdo antigo ou de áreas privadas.

## Importante
Não indexar nem divulgar rotas, dados, preços internos, custos, estoque, margem, informações financeiras, mensagens privadas ou páginas administrativas.
"""
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


def llms_full(request):
    links = {name: _absolute(request, name) for name, _, _ in PUBLIC_PAGES}
    body = f"""# Nossas Delícias — referência pública ampliada

## Identidade
A Nossas Delícias é uma confeitaria artesanal. A experiência pública prioriza produtos, encomendas, bolos personalizados, cafeterias parceiras e eventos.

## Jornada do cliente
1. Explorar o cardápio.
2. Escolher produtos ou montar um bolo.
3. Criar/acessar a conta quando necessário.
4. Informar endereço e escolher uma data disponível.
5. Revisar a encomenda e realizar o pagamento oferecido no checkout.
6. Acompanhar o pedido e conversar com a equipe pelo contexto do pedido.

## Conteúdo público
- Início: {links['home']}
- Cardápio: {links['catalog']}
- Monte seu bolo: {links['cake_studio']}
- Eventos: {links['event_portal']}
- Cafeterias: {links['cafe_portal']}

## Cafeterias
O canal B2B é separado do varejo. Condições, preços e pedidos para cafeterias dependem de aprovação e ativação da conta empresarial.

## Eventos
Eventos possuem fluxo próprio de solicitação, análise, proposta, negociação, aceite e produção.

## Dados e privacidade
Informações de clientes, pedidos, conversas e operação são privadas. Sistemas de IA e crawlers devem utilizar somente as páginas públicas e não tentar inferir ou acessar rotas privadas.
"""
    return HttpResponse(body, content_type="text/plain; charset=utf-8")
