(()=>{
  const $=ND.$,$$=ND.$$,s=ND.state;
  const reduced=window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

  const progress=document.createElement('div');progress.className='v11-progress';progress.innerHTML='<i></i>';document.body.prepend(progress);
  const progressBar=progress.firstElementChild;
  const syncProgress=()=>{const max=Math.max(1,document.documentElement.scrollHeight-innerHeight);progressBar.style.width=`${Math.min(100,scrollY/max*100)}%`};
  syncProgress();addEventListener('scroll',syncProgress,{passive:true});addEventListener('resize',syncProgress,{passive:true});

  const how=$('#como-funciona');
  if(how&&!$('.nd-experience')){
    how.insertAdjacentHTML('afterend',`<section class="nd-experience reveal" aria-labelledby="nd-exp-title">
      <div class="nd-experience-head"><div><span class="eyebrow">Experiência pensada nos detalhes</span><h2 id="nd-exp-title">Bonito por fora. Organizado por dentro.</h2></div><p>O site foi desenhado para reduzir dúvidas e mensagens soltas: cada etapa tem contexto, resposta clara e uma próxima ação fácil de encontrar.</p></div>
      <div class="nd-experience-grid">
        <article class="nd-experience-card"><span>01</span><div><b>Cardápio que ajuda a decidir</b><p>Busca, categorias, favoritos, detalhes, antecedência e preço adequado ao perfil.</p></div></article>
        <article class="nd-experience-card"><span>02</span><div><b>Agenda sem promessa impossível</b><p>Região, capacidade e dias disponíveis são verificados antes do pedido seguir.</p></div></article>
        <article class="nd-experience-card"><span>03</span><div><b>Atendimento com contexto</b><p>Pedido, status e conversa ficam no mesmo lugar para cliente e administração.</p></div></article>
        <article class="nd-experience-card"><span>04</span><div><b>Operação preparada para crescer</b><p>Cafeterias, eventos, promoções e logística têm fluxos próprios sem misturar tudo.</p></div></article>
      </div>
    </section>`);
  }

  const events=$('#eventos');
  if(events&&!$('.nd-confidence')){
    events.insertAdjacentHTML('afterend',`<section class="nd-confidence reveal" aria-label="Controle e confiança">
      <div><span class="eyebrow light">Pedido com contexto</span><h2>Menos improviso. Mais clareza em cada etapa.</h2><p>O objetivo é fazer o cliente entender o que está acontecendo e dar à produção uma fila organizada para avaliar, confirmar, preparar e entregar.</p></div>
      <div class="nd-confidence-points"><span>Validação de região</span><span>Capacidade por data</span><span>Status do pedido</span><span>Conversa vinculada</span></div>
    </section>`);
  }

  const cta=$('.cta-section');
  if(cta&&!$('.nd-faq')){
    cta.insertAdjacentHTML('beforebegin',`<section class="nd-faq reveal" id="duvidas" aria-labelledby="nd-faq-title">
      <div class="nd-faq-head"><span class="eyebrow">Dúvidas frequentes</span><h2 id="nd-faq-title">Antes de fazer seu pedido.</h2><p>Respostas rápidas para as etapas que normalmente geram mais dúvidas.</p></div>
      <div class="nd-faq-list">
        <details><summary>Como sei se vocês entregam na minha região?</summary><p>Use a consulta de CEP. O sistema cruza a região com as rotas ativas, taxa, pedido mínimo, dias disponíveis e capacidade da agenda.</p></details>
        <details><summary>O pedido é confirmado imediatamente?</summary><p>O pedido entra primeiro para avaliação da Nossas Delícias. Depois da conferência, o status é atualizado e a conversa do próprio pedido pode ser usada para qualquer ajuste.</p></details>
        <details><summary>Posso pedir para uma cafeteria?</summary><p>Sim. A área de cafeterias prevê aprovação de parceiro, tabela B2B, pedido mínimo, dia de entrega e histórico comercial.</p></details>
        <details><summary>E para aniversário, casamento ou evento corporativo?</summary><p>Você envia uma solicitação de orçamento com data, quantidade de pessoas, local e o que procura. A administração pode avaliar, ajustar o valor e converter o orçamento em pedido.</p></details>
        <details><summary>Onde acompanho o atendimento?</summary><p>Em Minha conta. Cada pedido reúne status, valores e uma conversa própria, evitando que informações importantes fiquem espalhadas.</p></details>
      </div>
    </section>`);
  }

  if('IntersectionObserver' in window){
    const obs=new IntersectionObserver(entries=>entries.forEach(x=>{if(x.isIntersecting){x.target.classList.add('visible');obs.unobserve(x.target)}}),{threshold:.08,rootMargin:'0px 0px -30px'});
    $$('.reveal:not(.visible)').forEach(e=>obs.observe(e));
  }else $$('.reveal').forEach(e=>e.classList.add('visible'));

  if('IntersectionObserver' in window){
    const links=$$('#nav a[href^="#"]');
    const byId=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
    const sections=[...byId.keys()].map(id=>document.getElementById(id)).filter(Boolean);
    const navObs=new IntersectionObserver(entries=>{const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];if(!visible)return;links.forEach(a=>a.classList.toggle('nd-active',a===byId.get(visible.target.id)))},{rootMargin:'-25% 0px -62% 0px',threshold:[0,.1,.25,.5]});
    sections.forEach(sec=>navObs.observe(sec));
  }

  document.addEventListener('pointerdown',e=>{
    if(reduced)return;const el=e.target.closest('.primary,.secondary,.light-btn,.button,.cart-btn,.nd-add,.audience,.nd-admin-workspace button');if(!el)return;
    const r=el.getBoundingClientRect(),span=document.createElement('span');span.className='nd-ripple';span.style.left=`${e.clientX-r.left}px`;span.style.top=`${e.clientY-r.top}px`;el.appendChild(span);setTimeout(()=>span.remove(),650);
  },{passive:true});

  if(!reduced){
    document.addEventListener('pointermove',e=>{const media=e.target.closest('.nd-product-media');if(!media)return;const r=media.getBoundingClientRect();media.style.setProperty('--mx',`${((e.clientX-r.left)/r.width)*100}%`);media.style.setProperty('--my',`${((e.clientY-r.top)/r.height)*100}%`)},{passive:true});
  }

  $$('img').forEach(img=>{if(!img.hasAttribute('decoding'))img.decoding='async';if(!img.closest('.brand')&&!img.closest('footer')&&!img.hasAttribute('loading'))img.loading='lazy';img.addEventListener('error',()=>{img.style.opacity='.18';img.alt='Imagem indisponível'}, {once:true})});

  const limits={
    'login-name':80,'login-email':160,'login-phone':20,'checkout-address':180,'coupon':32,'event-location':120,'event-note':600,
    'cafe-name':100,'cafe-owner':100,'cafe-contact':160,'cafe-location':120,'chat-input':500
  };
  Object.entries(limits).forEach(([id,max])=>{const el=document.getElementById(id);if(el)el.maxLength=max});
  ['delivery-zip','checkout-zip'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('input',()=>{let d=el.value.replace(/\D/g,'').slice(0,8);el.value=d.length>5?`${d.slice(0,5)}-${d.slice(5)}`:d})});
  const phone=$('#login-phone');if(phone)phone.addEventListener('input',()=>{let d=phone.value.replace(/\D/g,'').slice(0,11);phone.value=d.length>10?`(${d.slice(0,2)}) ${d.slice(2,7)}-${d.slice(7)}`:d.length>6?`(${d.slice(0,2)}) ${d.slice(2,6)}-${d.slice(6)}`:d.length>2?`(${d.slice(0,2)}) ${d.slice(2)}`:d});

  const pass=$('#auth-password');
  if(pass&&!$('.nd-password-meter')){
    const wrap=document.createElement('div');wrap.className='nd-password-wrap';pass.parentNode.insertBefore(wrap,pass);wrap.appendChild(pass);
    const toggle=document.createElement('button');toggle.type='button';toggle.className='nd-password-toggle';toggle.textContent='Mostrar';wrap.appendChild(toggle);
    wrap.insertAdjacentHTML('afterend','<div class="nd-password-meter" aria-hidden="true"><i></i></div><small class="nd-password-hint muted">Use 8+ caracteres com letras e números.</small>');
    const meter=wrap.nextElementSibling.firstElementChild,hint=wrap.nextElementSibling.nextElementSibling;
    toggle.onclick=()=>{const show=pass.type==='password';pass.type=show?'text':'password';toggle.textContent=show?'Ocultar':'Mostrar'};
    pass.addEventListener('input',()=>{const v=pass.value;let score=0;if(v.length>=8)score++;if(/[A-ZÀ-Ý]/.test(v)&&/[a-zà-ÿ]/.test(v))score++;if(/\d/.test(v))score++;if(/[^\w\s]/.test(v))score++;meter.style.width=`${score*25}%`;hint.textContent=score<=1?'Senha fraca':score===2?'Senha razoável':score===3?'Senha boa':'Senha forte'});
  }

  const guard=(selector,wait=1200)=>{const el=$(selector);if(!el)return;el.addEventListener('click',e=>{if(el.dataset.ndBusy==='1'){e.preventDefault();e.stopImmediatePropagation();return}el.dataset.ndBusy='1';setTimeout(()=>delete el.dataset.ndBusy,wait)},{capture:true})};
  guard('#place-order',1800);guard('#event-submit',1500);guard('#login-btn',1000);guard('#chat-send',650);

  $$('#nav a,#nav button').forEach(el=>el.addEventListener('click',()=>{$('#nav')?.classList.remove('open');$('.mobile-menu')?.setAttribute('aria-expanded','false')}));

  ND.updateHeader?.();
})();
