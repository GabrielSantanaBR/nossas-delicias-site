(()=>{
  const $=ND.$,$$=ND.$$,s=ND.state;
  const SITE='https://gabrielsantanabr.github.io/nossas-delicias-site/';

  /* Accessibility: skip link and semantic main target */
  const main=document.querySelector('main');if(main&&!main.id)main.id='conteudo';
  if(!document.querySelector('.skip-link')){const a=document.createElement('a');a.className='skip-link';a.href='#conteudo';a.textContent='Pular para o conteúdo';document.body.prepend(a)}

  /* Dynamic metadata fallback for crawlers that execute JS */
  const meta=(name,content,property=false)=>{let q=property?`meta[property="${name}"]`:`meta[name="${name}"]`,m=document.querySelector(q);if(!m){m=document.createElement('meta');m.setAttribute(property?'property':'name',name);document.head.appendChild(m)}m.content=content};
  meta('robots','index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1');
  meta('og:title','Nossas Delícias | Confeitaria, encomendas e eventos',true);meta('og:description','Cardápio, pedidos, agenda por região, cafeterias e eventos em uma experiência organizada.',true);meta('og:type','website',true);meta('og:url',SITE,true);meta('og:image',SITE+'favicon.png?v=12',true);meta('twitter:card','summary');
  if(!document.querySelector('link[rel="canonical"]')){const l=document.createElement('link');l.rel='canonical';l.href=SITE;document.head.appendChild(l)}
  if(!document.querySelector('link[rel="manifest"]')){const l=document.createElement('link');l.rel='manifest';l.href='manifest.webmanifest?v=12';document.head.appendChild(l)}

  /* Checkout has a clear mental model */
  const checkout=document.querySelector('#checkout h2');if(checkout&&!document.querySelector('.nd-checkout-steps'))checkout.insertAdjacentHTML('afterend','<div class="nd-checkout-steps" aria-label="Etapas do pedido"><span><i>1</i>Sacola montada</span><span class="active"><i>2</i>Entrega e dados</span><span><i>3</i>Avaliação da equipe</span></div>');

  /* Product and hero image priorities */
  const hero=document.querySelector('.hero-media img');if(hero){hero.loading='eager';hero.fetchPriority='high';hero.decoding='async';hero.width=1200;hero.height=900}
  $$('img:not(.brand img):not(.hero-media img)').forEach(img=>{img.decoding='async';if(!img.loading)img.loading='lazy'});

  /* Better mobile navigation state */
  const menu=$('.mobile-menu'),nav=$('#nav');if(menu&&nav){const sync=()=>menu.setAttribute('aria-expanded',nav.classList.contains('open')?'true':'false');menu.addEventListener('click',()=>requestAnimationFrame(sync));$$('#nav a,#nav button').forEach(el=>el.addEventListener('click',()=>{nav.classList.remove('open');sync()}));}

  /* Focus management for modals/drawers: restore origin and trap Tab */
  let origin=null;const oldOpen=ND.open,oldClose=ND.close;
  ND.open=name=>{origin=document.activeElement;oldOpen(name);requestAnimationFrame(()=>{const panel=document.getElementById(name);if(!panel)return;panel.setAttribute('role',panel.classList.contains('drawer')?'dialog':panel.getAttribute('role')||'dialog');panel.setAttribute('aria-modal','true');const focusable=panel.querySelector('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])');focusable?.focus({preventScroll:true})})};
  ND.close=()=>{const open=document.querySelector('.modal.open,.drawer.open');if(open)open.removeAttribute('aria-modal');oldClose();if(origin&&document.contains(origin))origin.focus({preventScroll:true});origin=null};
  document.addEventListener('keydown',e=>{if(e.key!=='Tab')return;const panel=document.querySelector('.modal.open,.drawer.open');if(!panel)return;const list=[...panel.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(x=>x.offsetParent!==null);if(list.length<2)return;const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}});

  /* Avoid empty or malformed admin/client text causing broken cards */
  const trimInput=(id,max)=>{const el=document.getElementById(id);if(!el)return;el.maxLength=max;el.addEventListener('blur',()=>{el.value=el.value.trim().replace(/\s{2,}/g,' ')})};
  [['login-name',80],['login-email',160],['checkout-address',180],['event-location',120],['cafe-name',100],['cafe-owner',100],['cafe-contact',160],['cafe-location',120]].forEach(([id,max])=>trimInput(id,max));

  /* Friendly local-demo state indicator */
  const bar=$('.demo-bar');if(bar&&!bar.querySelector('.nd-demo-health')){const el=document.createElement('span');el.className='nd-demo-health';el.textContent='• ambiente de demonstração';el.title='Login, pedidos e mensagens desta versão ficam neste navegador.';bar.insertBefore(el,bar.querySelector('.nd-reset')||null)}

  /* Online/offline feedback; useful because product imagery is remote */
  const syncNetwork=()=>{document.documentElement.dataset.network=navigator.onLine?'online':'offline';if(!navigator.onLine)ND.toast?.('Você está offline. A demo local continua disponível, mas imagens externas podem não carregar.')};addEventListener('online',syncNetwork);addEventListener('offline',syncNetwork);syncNetwork();

  /* Structured data without inventing address, reviews or opening hours */
  if(!document.querySelector('#nd-schema')){const schema=document.createElement('script');schema.id='nd-schema';schema.type='application/ld+json';schema.textContent=JSON.stringify({'@context':'https://schema.org','@type':'Bakery',name:'Nossas Delícias',url:SITE,description:'Confeitaria artesanal com encomendas, atendimento a cafeterias e eventos.',areaServed:{'@type':'AdministrativeArea',name:'Rio de Janeiro'},sameAs:['https://www.instagram.com/nossas___delicias/']});document.head.appendChild(schema)}

  /* Smooth reveal only when useful, not on every element */
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches&&'IntersectionObserver'in window){const obs=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('visible');obs.unobserve(x.target)}}),{rootMargin:'0px 0px -8% 0px',threshold:.06});$$('.reveal:not(.visible)').forEach(x=>obs.observe(x))}

  /* Protect demo from accidental repeated destructive actions */
  document.addEventListener('click',e=>{const b=e.target.closest('[data-action="delete"],button');if(!b)return;if(b.dataset.ndLock==='1'){e.preventDefault();e.stopImmediatePropagation();return}if(b.matches('#place-order,#event-submit,#login-btn,#chat-send')){b.dataset.ndLock='1';setTimeout(()=>delete b.dataset.ndLock,b.id==='chat-send'?650:1300)}},true);

  /* Runtime consistency checks: fail softly instead of leaving blank panels */
  setTimeout(()=>{if(!document.querySelector('#product-grid .nd-product')&&s.data.products.some(p=>p.active!==false)){ND.renderProducts?.()}ND.updateHeader?.()},250);
})();
