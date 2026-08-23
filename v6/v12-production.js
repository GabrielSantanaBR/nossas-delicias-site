(()=>{
  'use strict';
  const $=ND.$,$$=ND.$$,s=ND.state;
  const SITE='https://gabrielsantanabr.github.io/nossas-delicias-site/';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp=(value,min,max)=>Math.min(Math.max(value,min),max);

  const main=document.querySelector('main');if(main&&!main.id)main.id='conteudo';
  if(!document.querySelector('.skip-link')){const a=document.createElement('a');a.className='skip-link';a.href='#conteudo';a.textContent='Pular para o conteúdo';document.body.prepend(a)}
  if(!document.querySelector('.v13-scroll-progress')){const p=document.createElement('div');p.className='v13-scroll-progress';p.setAttribute('aria-hidden','true');p.innerHTML='<span></span>';document.body.prepend(p)}
  if(!document.querySelector('.v13-grain')){const grain=document.createElement('div');grain.className='v13-grain';grain.setAttribute('aria-hidden','true');document.body.append(grain)}

  const meta=(name,content,property=false)=>{let q=property?`meta[property="${name}"]`:`meta[name="${name}"]`,m=document.querySelector(q);if(!m){m=document.createElement('meta');m.setAttribute(property?'property':'name',name);document.head.appendChild(m)}m.content=content};
  meta('robots','index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1');meta('og:title','Nossas Delícias | Confeitaria, encomendas e eventos',true);meta('og:description','Cardápio, pedidos, agenda por região, cafeterias e eventos em uma experiência organizada.',true);meta('og:type','website',true);meta('og:url',SITE,true);meta('og:image',SITE+'favicon.png?v=12',true);meta('twitter:card','summary');
  if(!document.querySelector('link[rel="canonical"]')){const l=document.createElement('link');l.rel='canonical';l.href=SITE;document.head.appendChild(l)}

  const header=$('.header'),progress=$('.v13-scroll-progress span'),heroMedia=$('.hero-media'),cafePhoto=$('.cafe-photo');let ticking=false;
  const syncScroll=()=>{
    const y=scrollY||pageYOffset,scrollable=Math.max(document.documentElement.scrollHeight-innerHeight,1),ratio=clamp(y/scrollable,0,1);
    if(progress)progress.style.transform=`scaleX(${ratio})`;
    header?.classList.toggle('v13-scrolled',y>24);
    if(!reduced){
      if(heroMedia){const r=heroMedia.getBoundingClientRect(),center=r.top+r.height/2-innerHeight/2;heroMedia.style.setProperty('--v13-parallax',`${clamp(-center*.035,-28,28).toFixed(1)}px`)}
      if(cafePhoto){const r=cafePhoto.getBoundingClientRect(),center=r.top+r.height/2-innerHeight/2;cafePhoto.style.setProperty('--v13-parallax',`${clamp(-center*.025,-20,20).toFixed(1)}px`)}
    }
    ticking=false;
  };
  const requestSync=()=>{if(!ticking){ticking=true;requestAnimationFrame(syncScroll)}};
  addEventListener('scroll',requestSync,{passive:true});addEventListener('resize',requestSync);syncScroll();

  const story=$('#como-funciona');if(story){story.classList.add('v13-story-section');const cards=$$('#como-funciona .benefit-grid article');cards[0]?.classList.add('v13-active');if('IntersectionObserver'in window){const storyObs=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];if(!visible)return;cards.forEach(card=>card.classList.toggle('v13-active',card===visible.target))},{threshold:[.25,.45,.65],rootMargin:'-18% 0px -35% 0px'});cards.forEach(card=>storyObs.observe(card))}}

  $$('.benefit-grid,.event-stats,.trust').forEach(group=>group.classList.add('v13-stagger'));
  if(!reduced&&'IntersectionObserver'in window){
    const revealObs=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('visible');revealObs.unobserve(entry.target)}}),{rootMargin:'0px 0px -8% 0px',threshold:.07});$$('.reveal:not(.visible)').forEach(el=>revealObs.observe(el));
    const staggerObs=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){entry.target.classList.add('v13-in');staggerObs.unobserve(entry.target)}}),{threshold:.16});$$('.v13-stagger').forEach(el=>staggerObs.observe(el));
  }else{$$('.reveal').forEach(el=>el.classList.add('visible'));$$('.v13-stagger').forEach(el=>el.classList.add('v13-in'))}

  const checkout=document.querySelector('#checkout h2');if(checkout&&!document.querySelector('.nd-checkout-steps'))checkout.insertAdjacentHTML('afterend','<div class="nd-checkout-steps" aria-label="Etapas do pedido"><span><i>1</i>Sacola montada</span><span class="active"><i>2</i>Entrega e dados</span><span><i>3</i>Avaliação da equipe</span></div>');
  const hero=document.querySelector('.hero-media img');if(hero){hero.loading='eager';hero.fetchPriority='high';hero.decoding='async';hero.width=1200;hero.height=900}
  $$('img:not(.brand img):not(.hero-media img)').forEach(img=>{img.decoding='async';if(!img.loading)img.loading='lazy'});

  const menu=$('.mobile-menu'),nav=$('#nav');if(menu&&nav){const sync=()=>menu.setAttribute('aria-expanded',nav.classList.contains('open')?'true':'false');menu.addEventListener('click',()=>requestAnimationFrame(sync));$$('#nav a,#nav button').forEach(el=>el.addEventListener('click',()=>{nav.classList.remove('open');sync()}));document.addEventListener('keydown',event=>{if(event.key==='Escape'){nav.classList.remove('open');sync()}})}

  let origin=null;const oldOpen=ND.open,oldClose=ND.close;
  ND.open=name=>{origin=document.activeElement;oldOpen(name);requestAnimationFrame(()=>{const panel=document.getElementById(name);if(!panel)return;panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');const focusable=panel.querySelector('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])');focusable?.focus({preventScroll:true})})};
  ND.close=()=>{const open=document.querySelector('.modal.open,.drawer.open');if(open)open.removeAttribute('aria-modal');oldClose();if(origin&&document.contains(origin))origin.focus({preventScroll:true});origin=null};
  document.addEventListener('keydown',e=>{if(e.key!=='Tab')return;const panel=document.querySelector('.modal.open,.drawer.open');if(!panel)return;const list=[...panel.querySelectorAll('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])')].filter(x=>x.offsetParent!==null);if(list.length<2)return;const first=list[0],last=list.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}});

  const trimInput=(id,max)=>{const el=document.getElementById(id);if(!el)return;el.maxLength=max;el.addEventListener('blur',()=>{el.value=el.value.trim().replace(/\s{2,}/g,' ')})};[['login-name',80],['login-email',160],['checkout-address',180],['event-location',120],['cafe-name',100],['cafe-owner',100],['cafe-contact',160],['cafe-location',120]].forEach(([id,max])=>trimInput(id,max));

  const bar=$('.demo-bar');if(bar&&!bar.querySelector('.nd-demo-health')){const el=document.createElement('span');el.className='nd-demo-health';el.textContent='• ambiente de demonstração';el.title='Login, pedidos e mensagens desta versão ficam neste navegador.';bar.insertBefore(el,bar.querySelector('.nd-reset')||null)}
  const syncNetwork=()=>{document.documentElement.dataset.network=navigator.onLine?'online':'offline';if(!navigator.onLine)ND.toast?.('Você está offline. A demo local continua disponível, mas imagens externas podem não carregar.')};addEventListener('online',syncNetwork);addEventListener('offline',syncNetwork);syncNetwork();

  $$('.nd-product-media').forEach(media=>media.addEventListener('pointermove',event=>{const rect=media.getBoundingClientRect();media.style.setProperty('--mx',`${((event.clientX-rect.left)/rect.width)*100}%`);media.style.setProperty('--my',`${((event.clientY-rect.top)/rect.height)*100}%`)}));

  if(!document.querySelector('#nd-schema')){const schema=document.createElement('script');schema.id='nd-schema';schema.type='application/ld+json';schema.textContent=JSON.stringify({'@context':'https://schema.org','@type':'Bakery',name:'Nossas Delícias',url:SITE,description:'Confeitaria artesanal com encomendas, atendimento a cafeterias e eventos.',areaServed:{'@type':'AdministrativeArea',name:'Rio de Janeiro'},sameAs:['https://www.instagram.com/nossas___delicias/']});document.head.appendChild(schema)}
  document.addEventListener('click',e=>{const b=e.target.closest('[data-action="delete"],button');if(!b)return;if(b.dataset.ndLock==='1'){e.preventDefault();e.stopImmediatePropagation();return}if(b.matches('#place-order,#event-submit,#login-btn,#chat-send')){b.dataset.ndLock='1';setTimeout(()=>delete b.dataset.ndLock,b.id==='chat-send'?650:1300)}},true);
  setTimeout(()=>{if(!document.querySelector('#product-grid .nd-product')&&s.data.products.some(p=>p.active!==false)){ND.renderProducts?.()}ND.updateHeader?.()},250);
})();
