(()=>{
  'use strict';
  const shell=document.querySelector('[data-ops-shell]');
  if(!shell)return;
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const modules=[...document.querySelectorAll('[data-module]')];
  const nav=[...document.querySelectorAll('[data-module-target]')];
  const title=document.querySelector('[data-module-title]');
  const kicker=document.querySelector('[data-module-kicker]');
  const sidebar=document.querySelector('[data-ops-sidebar]');
  const menu=document.querySelector('[data-ops-menu]');
  const valid=new Set(modules.map(node=>node.dataset.module));
  const normalize=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();

  const animateCounters=(scope)=>{
    if(reduced)return;
    scope.querySelectorAll('[data-counter]').forEach(node=>{
      if(node.dataset.played)return;
      node.dataset.played='1';
      const target=Number(node.dataset.counter||0);
      const start=performance.now();
      const duration=650;
      const tick=now=>{
        const p=Math.min(1,(now-start)/duration);
        const eased=1-Math.pow(1-p,3);
        node.textContent=Math.round(target*eased).toLocaleString('pt-BR');
        if(p<1)requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  };

  const animateBars=(scope)=>{
    const bars=[...scope.querySelectorAll('[data-chart-bar]')];
    if(!bars.length)return;
    const max=Math.max(1,...bars.map(bar=>Number(bar.dataset.value||0)));
    requestAnimationFrame(()=>bars.forEach((bar,index)=>{
      const pct=Math.max(4,(Number(bar.dataset.value||0)/max)*100);
      if(reduced)bar.style.height=`${pct}%`;
      else setTimeout(()=>bar.style.height=`${pct}%`,index*75+80);
    }));
  };

  const activate=(key,{push=true}={})=>{
    if(!valid.has(key))key='overview';
    modules.forEach(node=>node.classList.toggle('is-active',node.dataset.module===key));
    nav.forEach(button=>button.classList.toggle('is-active',button.dataset.moduleTarget===key));
    const active=modules.find(node=>node.dataset.module===key);
    if(active){
      title.textContent=active.dataset.title||'Central de Gestão';
      kicker.textContent=active.dataset.kicker||'Nossas Delícias OS';
      animateCounters(active);
      animateBars(active);
      document.querySelector('.ops-main')?.scrollTo?.({top:0,behavior:'auto'});
      window.scrollTo({top:0,behavior:'auto'});
    }
    sidebar?.classList.remove('is-open');
    document.body.classList.remove('ops-menu-open');
    if(push&&location.hash!==`#${key}`)history.pushState(null,'',`#${key}`);
  };

  nav.forEach(button=>button.addEventListener('click',()=>activate(button.dataset.moduleTarget)));
  document.querySelectorAll('[data-module-jump]').forEach(button=>button.addEventListener('click',()=>activate(button.dataset.moduleJump)));
  addEventListener('hashchange',()=>activate(location.hash.slice(1)||'overview',{push:false}));
  activate(location.hash.slice(1)||'overview',{push:false});

  menu?.addEventListener('click',()=>{
    const open=!sidebar.classList.contains('is-open');
    sidebar.classList.toggle('is-open',open);
    document.body.classList.toggle('ops-menu-open',open);
  });
  document.addEventListener('click',event=>{
    if(innerWidth>980||!sidebar?.classList.contains('is-open'))return;
    if(sidebar.contains(event.target)||menu?.contains(event.target))return;
    sidebar.classList.remove('is-open');
  });

  document.querySelectorAll('[data-table-filter]').forEach(input=>{
    const table=document.getElementById(input.dataset.tableFilter);
    if(!table)return;
    const rows=[...table.querySelectorAll('tbody tr')];
    input.addEventListener('input',()=>{
      const q=normalize(input.value.trim());
      rows.forEach(row=>row.hidden=Boolean(q&&!normalize(row.textContent).includes(q)));
    });
  });
  document.querySelectorAll('[data-recipe-filter]').forEach(input=>{
    const cards=[...document.querySelectorAll('[data-recipe-card]')];
    input.addEventListener('input',()=>{
      const q=normalize(input.value.trim());
      cards.forEach(card=>card.hidden=Boolean(q&&!normalize(card.textContent).includes(q)));
    });
  });

  const threadButtons=[...document.querySelectorAll('[data-thread-target]')];
  const threadPanels=[...document.querySelectorAll('[data-thread-panel]')];
  const createMessageNode=message=>{
    const item=document.createElement('div');
    item.className=`ops-chat-msg ${message.from_team?'from-team':'from-client'}`;
    item.dataset.messageId=message.id;
    const meta=document.createElement('small');
    meta.textContent=`${message.author} · ${message.created_at}`;
    const body=document.createElement('p');
    body.textContent=message.body;
    item.append(meta,body);
    return item;
  };
  const renderThread=(panel,messages,{preserveScroll=false}={})=>{
    const box=panel?.querySelector('.ops-chat-box');
    if(!box)return;
    const nearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<90;
    const known=new Set([...box.querySelectorAll('[data-message-id]')].map(node=>node.dataset.messageId));
    if(!panel.dataset.loaded){
      box.replaceChildren();
      messages.forEach(message=>box.append(createMessageNode(message)));
      if(!messages.length){
        const empty=document.createElement('div');empty.className='ops-empty';empty.textContent='A conversa começa quando alguém envia a primeira mensagem.';box.append(empty);
      }
    }else{
      const fresh=messages.filter(message=>!known.has(String(message.id)));
      if(fresh.length)box.querySelector('.ops-empty')?.remove();
      fresh.forEach(message=>box.append(createMessageNode(message)));
    }
    panel.dataset.loaded='1';
    if(!preserveScroll||nearBottom)box.scrollTop=box.scrollHeight;
  };
  const loadThread=async(panel,{quiet=false}={})=>{
    if(!panel?.dataset.threadUrl||panel.dataset.loading==='1'||document.hidden)return;
    panel.dataset.loading='1';
    try{
      const response=await fetch(panel.dataset.threadUrl,{headers:{'X-Requested-With':'XMLHttpRequest'},credentials:'same-origin'});
      if(!response.ok)throw new Error('Não foi possível carregar a conversa.');
      const data=await response.json();
      renderThread(panel,data.messages,{preserveScroll:quiet});
      const button=threadButtons.find(item=>item.dataset.threadTarget===panel.id);
      button?.classList.remove('has-unread');
      button?.querySelector(':scope > i')?.remove();
    }catch(error){
      if(!quiet){const box=panel.querySelector('.ops-chat-box');if(box){box.textContent='';const warning=document.createElement('div');warning.className='ops-empty is-error';warning.textContent=error.message;box.append(warning);}}
    }finally{delete panel.dataset.loading;}
  };
  const openThread=id=>{
    threadButtons.forEach(button=>button.classList.toggle('is-active',button.dataset.threadTarget===id));
    threadPanels.forEach(panel=>panel.classList.toggle('is-active',panel.id===id));
    const panel=document.getElementById(id);
    loadThread(panel);
  };
  threadButtons.forEach(button=>button.addEventListener('click',()=>openThread(button.dataset.threadTarget)));
  if(threadButtons[0])openThread(threadButtons[0].dataset.threadTarget);

  document.querySelectorAll('[data-conversation-compose]').forEach(form=>{
    const textarea=form.querySelector('textarea');
    const button=form.querySelector('button');
    const feedback=form.querySelector('[data-chat-feedback]');
    const submit=async event=>{
      event.preventDefault();
      if(form.dataset.sending==='1'||!textarea.value.trim())return;
      form.dataset.sending='1';button.disabled=true;feedback.textContent='Enviando…';
      try{
        const response=await fetch(form.action,{method:'POST',body:new FormData(form),headers:{'X-Requested-With':'XMLHttpRequest'},credentials:'same-origin'});
        const data=await response.json();
        if(!response.ok)throw new Error(data.error||'Não foi possível enviar.');
        const panel=form.closest('[data-thread-panel]');
        renderThread(panel,[data.message],{preserveScroll:false});
        const preview=threadButtons.find(item=>item.dataset.threadTarget===panel.id)?.querySelector('[data-thread-preview]');
        if(preview)preview.textContent=data.message.body;
        textarea.value='';feedback.textContent='Mensagem enviada';textarea.focus();
        setTimeout(()=>{if(document.contains(feedback))feedback.textContent='Ctrl + Enter para enviar';},1800);
      }catch(error){feedback.textContent=error.message;feedback.classList.add('is-error');}
      finally{delete form.dataset.sending;button.disabled=false;}
    };
    form.addEventListener('submit',submit);
    textarea.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();form.requestSubmit();}});
  });
  setInterval(()=>{
    const messagesActive=document.querySelector('[data-module="messages"]')?.classList.contains('is-active');
    if(messagesActive&&!document.hidden)loadThread(document.querySelector('[data-thread-panel].is-active'),{quiet:true});
  },15000);

  document.querySelectorAll('.ops-inline-form').forEach(form=>{
    const select=form.querySelector('select');
    if(select){
      select.dataset.initial=select.value;
      select.addEventListener('change',()=>form.classList.toggle('is-dirty',select.value!==select.dataset.initial));
    }
  });

  const command=document.querySelector('[data-command]');
  const commandInput=document.querySelector('[data-command-input]');
  const results=document.querySelector('[data-command-results]');
  const commandOpen=document.querySelector('[data-command-open]');
  const commandClose=document.querySelector('[data-command-close]');
  const labels={
    overview:['Visão geral','Resumo do negócio e operação'],portfolio:['Portfólio & site','Vitrine, produtos e presença pública'],orders:['Pedidos','Fila, status e entregas'],messages:['Mensagens','Atendimento de clientes e parceiros'],privacy:['Privacidade','Solicitações LGPD e preferências de cookies'],cafes:['Cafeterias','Parcerias B2B e faturamento'],events:['Eventos','Orçamentos e pipeline'],logistics:['Logística','Rotas, capacidade e calendário'],data:['Dados & relatórios','Exportação e inteligência'],finance:['Financeiro','Caixa, recebíveis, despesas e lucro'],pricing:['Precificação','Custos, margem e simulador'],production:['Produção & estoque','Ingredientes, fichas e movimentações']
  };
  let visibleKeys=[];
  let selected=0;
  const renderCommand=()=>{
    if(!results)return;
    const q=normalize(commandInput?.value||'');
    visibleKeys=Object.keys(labels).filter(key=>!q||normalize(`${labels[key][0]} ${labels[key][1]}`).includes(q));
    selected=Math.min(selected,Math.max(0,visibleKeys.length-1));
    results.innerHTML=visibleKeys.map((key,index)=>`<button type="button" data-command-key="${key}" class="${index===selected?'is-selected':''}"><span>${labels[key][0]}</span><small>${labels[key][1]}</small></button>`).join('')||'<div class="ops-empty">Nenhum módulo encontrado.</div>';
    results.querySelectorAll('[data-command-key]').forEach(button=>button.addEventListener('click',()=>{activate(button.dataset.commandKey);closeCommand();}));
  };
  const openCommand=()=>{if(!command)return;command.hidden=false;selected=0;commandInput.value='';renderCommand();requestAnimationFrame(()=>commandInput.focus());};
  const closeCommand=()=>{if(command)command.hidden=true;};
  commandOpen?.addEventListener('click',openCommand);commandClose?.addEventListener('click',closeCommand);
  commandInput?.addEventListener('input',()=>{selected=0;renderCommand();});
  document.addEventListener('keydown',event=>{
    if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();command?.hidden?openCommand():closeCommand();return;}
    if(event.key==='Escape'){closeCommand();sidebar?.classList.remove('is-open');return;}
    if(command?.hidden)return;
    if(event.key==='ArrowDown'){event.preventDefault();selected=Math.min(selected+1,visibleKeys.length-1);renderCommand();}
    if(event.key==='ArrowUp'){event.preventDefault();selected=Math.max(selected-1,0);renderCommand();}
    if(event.key==='Enter'&&visibleKeys[selected]){event.preventDefault();activate(visibleKeys[selected]);closeCommand();}
  });

  if(!reduced&&'IntersectionObserver'in window){
    const reveal=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(!entry.isIntersecting)return;
      entry.target.classList.add('ops-in');
      reveal.unobserve(entry.target);
    }),{threshold:.08,rootMargin:'0px 0px -5% 0px'});
    document.querySelectorAll('.ops-panel,.ops-kpis article,.ops-module-card,.ops-business-card,.ops-event-card,.ops-day').forEach(node=>reveal.observe(node));
  }else document.querySelectorAll('.ops-panel,.ops-kpis article,.ops-module-card,.ops-business-card,.ops-event-card,.ops-day').forEach(node=>node.classList.add('ops-in'));

  document.querySelectorAll('form:not([data-conversation-compose])').forEach(form=>form.addEventListener('submit',()=>{
    const button=form.querySelector('button[type="submit"],button:not([type])');
    if(!button||button.dataset.loading==='1')return;
    button.dataset.loading='1';
    const original=button.textContent;
    button.textContent='Salvando…';
    setTimeout(()=>{if(document.contains(button)){button.textContent=original;delete button.dataset.loading;}},5000);
  }));
})();
