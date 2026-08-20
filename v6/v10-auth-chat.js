(()=>{
  const {$,$$,state:s,money,esc}=ND;
  const EMAIL_RE=/^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const now=()=>new Date().toISOString();
  const normEmail=v=>String(v||'').trim().toLowerCase();
  const accountOrders=()=>s.user?.email?s.orders.filter(o=>normEmail(o.customer?.email)===normEmail(s.user.email)):[];
  const accountQuotes=()=>s.user?.email?s.quotes.filter(q=>normEmail(q.customer?.email)===normEmail(s.user.email)):[];

  s.auth=s.auth||{accounts:[],failures:{},sessionExpires:null};
  s.auth.accounts=s.auth.accounts||[];s.auth.failures=s.auth.failures||{};
  s.orders.forEach(o=>{o.messages=o.messages||[];o.messages.forEach((m,i)=>{m.id=m.id||`${o.id}-m${i+1}`;m.date=m.date||o.date||now();if(m.readByCustomer===undefined)m.readByCustomer=m.from!=='admin';if(m.readByAdmin===undefined)m.readByAdmin=m.from!=='customer';});});
  if(s.auth.sessionExpires&&Date.now()>s.auth.sessionExpires){s.user=null;s.auth.sessionExpires=null;}

  const bytesToB64=u=>btoa(String.fromCharCode(...u));
  const b64ToBytes=v=>Uint8Array.from(atob(v),c=>c.charCodeAt(0));
  async function hashPassword(password,saltB64){
    const enc=new TextEncoder(),salt=saltB64?b64ToBytes(saltB64):crypto.getRandomValues(new Uint8Array(16));
    const key=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveBits']);
    const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations:120000,hash:'SHA-256'},key,256);
    return{salt:bytesToB64(salt),hash:bytesToB64(new Uint8Array(bits))};
  }
  const secureEqual=(a,b)=>{if(a.length!==b.length)return false;let r=0;for(let i=0;i<a.length;i++)r|=a.charCodeAt(i)^b.charCodeAt(i);return r===0};

  const oldSave=ND.save;
  let channel=null;
  try{channel=new BroadcastChannel('nossas-delicias-demo-v10')}catch(_){channel=null}
  let syncing=false;
  ND.save=()=>{oldSave();if(!syncing)channel?.postMessage({type:'sync',at:Date.now()});};
  function applyFresh(){
    const fresh=JSON.parse(localStorage.getItem('nd_v6')||'null');if(!fresh)return;
    syncing=true;Object.keys(s).forEach(k=>delete s[k]);Object.assign(s,fresh);syncing=false;
    ND.updateHeader?.();
    if($('#account')?.classList.contains('open'))ND.renderAccount?.();
    if($('#chat')?.classList.contains('open'))renderChat();
    if(document.body.classList.contains('nd-admin-open'))ND.renderAdmin?.();
  }
  channel?.addEventListener('message',e=>{if(e.data?.type==='sync')applyFresh()});
  window.addEventListener('storage',e=>{if(e.key==='nd_v6')applyFresh()});

  function unreadCustomer(){return accountOrders().reduce((n,o)=>n+(o.messages||[]).filter(m=>m.from==='admin'&&!m.readByCustomer).length,0)}
  function unreadAdmin(){return s.orders.reduce((n,o)=>n+(o.messages||[]).filter(m=>m.from==='customer'&&!m.readByAdmin).length,0)}
  const oldHeader=ND.updateHeader;
  ND.updateHeader=()=>{
    oldHeader?.();
    const accountBtn=$('[data-open="account"]');
    if(accountBtn){
      const count=unreadCustomer();accountBtn.innerHTML=`Minha conta${count?` <span class="nd-msg-badge">${count}</span>`:''}`;
    }
    const loginBtn=$('[data-open="login"]');if(loginBtn)loginBtn.textContent=s.user?'Conta ativa':'Entrar';
    const adminBadge=$('#nd-new-orders');if(adminBadge){const pending=s.orders.filter(o=>o.status==='Aguardando avaliação').length,unread=unreadAdmin();adminBadge.textContent=pending+(unread?` • ${unread}`:'')}
  };

  function prepareLogin(){
    const box=$('#login');if(!box||$('#auth-password'))return;
    box.querySelector('h2').textContent='Acessar sua conta';
    box.querySelector('.muted').textContent='Demonstração local: a conta e os pedidos ficam apenas neste navegador. Em produção, autenticação, recuperação e sessão serão validadas no servidor.';
    const nameLabel=$('#login-name')?.closest('label'),phoneLabel=$('#login-phone')?.closest('label'),emailLabel=$('#login-email')?.closest('label');
    nameLabel?.classList.add('auth-register-only');phoneLabel?.classList.add('auth-register-only');
    emailLabel?.insertAdjacentHTML('beforebegin','<div class="nd-auth-tabs"><button type="button" data-auth-mode="login" class="active">Entrar</button><button type="button" data-auth-mode="register">Criar conta</button></div>');
    phoneLabel?.insertAdjacentHTML('afterend','<label>Senha<input id="auth-password" type="password" minlength="8" autocomplete="current-password" placeholder="Mínimo de 8 caracteres"></label><div id="auth-feedback" class="nd-auth-feedback" aria-live="polite"></div>');
    $('#login-btn').textContent='Entrar';
    $('#login-btn').insertAdjacentHTML('afterend','<button id="auth-forgot" class="link-btn nd-auth-forgot" type="button">Esqueci minha senha</button>');
    $$('[data-auth-mode]').forEach(b=>b.onclick=()=>setAuthMode(b.dataset.authMode));
    $('#auth-forgot').onclick=()=>{const em=normEmail($('#login-email').value);$('#auth-feedback').textContent=em&&s.auth.accounts.some(a=>a.email===em)?'Na versão real, enviaremos um link seguro por e-mail. O GitHub Pages não pode fazer recuperação de senha com segurança.':'Informe o e-mail da conta. A recuperação real depende do backend.'};
    setAuthMode('login');
  }
  let authMode='login';
  function setAuthMode(mode){authMode=mode;$$('[data-auth-mode]').forEach(b=>b.classList.toggle('active',b.dataset.authMode===mode));$$('.auth-register-only').forEach(e=>e.hidden=mode!=='register');$('#login-btn').textContent=mode==='register'?'Criar conta':'Entrar';$('#auth-password').autocomplete=mode==='register'?'new-password':'current-password';$('#auth-feedback').textContent=''}
  function validPassword(v){return v.length>=8&&/[A-Za-zÀ-ÿ]/.test(v)&&/\d/.test(v)}
  function failureState(email){return s.auth.failures[email]||{count:0,lockedUntil:0}}
  async function doAuth(){
    const feedback=$('#auth-feedback'),email=normEmail($('#login-email').value),password=$('#auth-password').value,name=$('#login-name').value.trim(),phone=$('#login-phone')?.value.trim()||'';
    feedback.textContent='';if(!EMAIL_RE.test(email))return feedback.textContent='Digite um e-mail válido.';
    if(!validPassword(password))return feedback.textContent='A senha precisa ter pelo menos 8 caracteres, com letra e número.';
    if(authMode==='register'){
      if(name.length<2)return feedback.textContent='Informe seu nome.';
      if(s.auth.accounts.some(a=>a.email===email))return feedback.textContent='Já existe uma conta local com este e-mail.';
      const pass=await hashPassword(password);s.auth.accounts.push({email,name,phone,...pass,createdAt:now()});s.user={name,email,phone};s.auth.sessionExpires=Date.now()+12*60*60*1000;ND.save();ND.audit('Conta demonstrativa criada',email);ND.close();ND.updateHeader();ND.toast('Conta criada e sessão iniciada');return;
    }
    const f=failureState(email);if(f.lockedUntil>Date.now())return feedback.textContent=`Muitas tentativas. Aguarde ${Math.ceil((f.lockedUntil-Date.now())/1000)}s.`;
    const a=s.auth.accounts.find(x=>x.email===email);if(!a){return feedback.textContent='Conta não encontrada neste navegador. Use “Criar conta”.'}
    const test=await hashPassword(password,a.salt);if(!secureEqual(test.hash,a.hash)){
      f.count=(f.count||0)+1;if(f.count>=5){f.count=0;f.lockedUntil=Date.now()+60000} s.auth.failures[email]=f;ND.save();return feedback.textContent=f.lockedUntil>Date.now()?'Muitas tentativas incorretas. Acesso bloqueado localmente por 60 segundos.':'Senha incorreta.';
    }
    delete s.auth.failures[email];s.user={name:a.name,email:a.email,phone:a.phone||''};s.auth.sessionExpires=Date.now()+12*60*60*1000;ND.save();ND.audit('Login demonstrativo',email);ND.close();ND.updateHeader();ND.toast('Sessão iniciada');
  }
  prepareLogin();if($('#login-btn'))$('#login-btn').onclick=()=>doAuth().catch(()=>{$('#auth-feedback').textContent='Não foi possível validar a conta neste navegador.'});

  ND.customerStats=()=>{const orders=accountOrders(),valid=orders.filter(o=>o.status!=='Cancelado'),spent=valid.reduce((a,o)=>a+Number(o.total||0),0);return{count:orders.length,spent,segment:s.profile==='cafe'?'Cafeteria':orders.length>=5||spent>=500?'VIP':orders.length>=2?'Recorrente':'Novo cliente'}};
  function orderList(list){return list.map(o=>{const unread=(o.messages||[]).filter(m=>m.from==='admin'&&!m.readByCustomer).length;return `<article class="order-card"><div class="order-top"><div><b>${esc(o.id)}</b><span class="status ${ND.slug(o.status)}">${esc(o.status)}</span>${unread?`<span class="nd-unread-pill">${unread} nova${unread>1?'s':''}</span>`:''}</div><strong>${money(o.total)}</strong></div><div class="muted">${esc(o.region||'')} • ${ND.fmt(o.delivery)} • ${esc(o.payment||'Aguardando')}</div><div class="nd-order-actions"><button data-cchat="${o.id}">Conversa</button><button data-repeat="${o.id}">Repetir</button></div></article>`}).join('')||'<div class="availability">Nenhum pedido ainda.</div>'}
  let accountTab='overview';
  ND.renderAccount=()=>{
    const e=$('#account-content');if(!e)return;
    if(!s.user){$('#account-title').textContent='Minha conta';e.innerHTML='<div class="availability">Entre para acompanhar apenas os seus pedidos, benefícios e conversas.</div><button class="primary" id="account-login">Entrar</button>';$('#account-login').onclick=()=>{ND.close();ND.open('login')};return}
    const orders=accountOrders(),quotes=accountQuotes(),st=ND.customerStats();$('#account-title').textContent=`Olá, ${esc(s.user.name.split(' ')[0])}!`;
    let body='';
    if(accountTab==='overview')body=`<div class="account-stats"><div><span>Pedidos</span><b>${st.count}</b></div><div><span>Total</span><b>${money(st.spent)}</b></div><div><span>Perfil</span><b>${st.segment}</b></div></div><h3>Pedidos recentes</h3>${orderList(orders.slice(0,3))}`;
    if(accountTab==='orders')body=`<h3>Todos os pedidos</h3>${orderList(orders)}`;
    if(accountTab==='promos'){const ps=s.data.promos.filter(p=>p.active&&st.count>=+p.minOrders&&st.spent>=+p.minSpend&&(p.segment==='all'||p.segment===s.profile));body=`<h3>Benefícios</h3>${ps.map(p=>`<div class="order-card"><b>${esc(p.code)} • ${esc(p.name)}</b><div class="muted">${p.type==='fixed'?money(p.value):p.value+'%'} de desconto</div></div>`).join('')||'<div class="availability">Continue comprando para liberar benefícios.</div>'}`}
    if(accountTab==='events')body=`<h3>Eventos</h3>${quotes.map(q=>`<div class="order-card"><b>${esc(q.id)} • ${esc(q.type)}</b><span class="status">${esc(q.status)}</span><div class="muted">${ND.fmt(q.date)} • ${q.people} pessoas • ${esc(q.location||'')}</div>${q.price?`<strong>${money(q.price)}</strong>`:''}</div>`).join('')||'<div class="availability">Nenhum orçamento.</div>'}`;
    if(accountTab==='profile')body=`<div class="form-grid"><label>Nome<input id="pf-name" value="${esc(s.user.name)}"></label><label>E-mail<input value="${esc(s.user.email)}" disabled></label><label>Telefone<input id="pf-phone" value="${esc(s.user.phone||'')}"></label></div><div class="nd-profile-actions"><button id="pf-save" class="primary">Salvar perfil</button><button id="pf-password" class="secondary">Trocar senha</button><button id="pf-logout" class="secondary">Sair</button></div>`;
    e.innerHTML=`<div class="nd-account-tabs">${[['overview','Visão geral'],['orders','Pedidos'],['promos','Benefícios'],['events','Eventos'],['profile','Perfil']].map(([k,l])=>`<button data-atab="${k}" class="${accountTab===k?'active':''}">${l}</button>`).join('')}</div>${body}`;
    $$('[data-atab]').forEach(b=>b.onclick=()=>{accountTab=b.dataset.atab;ND.renderAccount()});$$('[data-cchat]').forEach(b=>b.onclick=()=>openChat(b.dataset.cchat,'customer'));$$('[data-repeat]').forEach(b=>b.onclick=()=>repeatOwned(b.dataset.repeat));
    if($('#pf-save'))$('#pf-save').onclick=()=>{const a=s.auth.accounts.find(x=>x.email===normEmail(s.user.email));s.user.name=$('#pf-name').value.trim()||s.user.name;s.user.phone=$('#pf-phone').value.trim();if(a){a.name=s.user.name;a.phone=s.user.phone}ND.save();ND.toast('Perfil atualizado');ND.updateHeader();ND.renderAccount()};
    if($('#pf-logout'))$('#pf-logout').onclick=()=>{s.user=null;s.auth.sessionExpires=null;ND.save();ND.close();ND.updateHeader();ND.toast('Sessão encerrada')};
    if($('#pf-password'))$('#pf-password').onclick=changePassword;
  };
  function repeatOwned(id){const o=accountOrders().find(x=>x.id===id);if(!o)return ND.toast('Pedido indisponível');(o.items||[]).forEach(i=>{const x=s.cart.find(c=>c.id===i.id&&c.note===i.note);x?x.qty+=i.qty:s.cart.push({...i})});ND.save();ND.updateHeader();ND.toast('Itens adicionados à sacola')}
  async function changePassword(){const a=s.auth.accounts.find(x=>x.email===normEmail(s.user?.email));if(!a)return ND.toast('Crie uma nova conta local para definir senha');const current=prompt('Senha atual');if(current===null)return;const test=await hashPassword(current,a.salt);if(!secureEqual(test.hash,a.hash))return ND.toast('Senha atual incorreta');const next=prompt('Nova senha (8+ caracteres, com letra e número)');if(next===null)return;if(!validPassword(next))return ND.toast('A nova senha não atende aos requisitos');const pass=await hashPassword(next);a.salt=pass.salt;a.hash=pass.hash;ND.save();ND.audit('Senha local alterada',a.email);ND.toast('Senha alterada')}

  let activeChat=null,lastSentAt=0;
  function canOpenOrder(id,role){const o=s.orders.find(x=>x.id===id);if(!o)return null;if(role==='admin')return o;if(!s.user||normEmail(o.customer?.email)!==normEmail(s.user.email))return null;return o}
  function openChat(id,role='customer'){const o=canOpenOrder(id,role);if(!o)return ND.toast('Você não pode abrir esta conversa');activeChat={id,role};markRead(o,role);ND.close();ND.open('chat');renderChat()}
  ND.openChat=openChat;
  function markRead(o,role){let changed=false;(o.messages||[]).forEach(m=>{if(role==='admin'&&m.from==='customer'&&!m.readByAdmin){m.readByAdmin=true;changed=true}if(role==='customer'&&m.from==='admin'&&!m.readByCustomer){m.readByCustomer=true;changed=true}});if(changed)ND.save();ND.updateHeader()}
  function renderChat(){const o=canOpenOrder(activeChat?.id,activeChat?.role);if(!o)return;markRead(o,activeChat.role);$('#chat-title').textContent=`Pedido ${o.id}`;$('#chat-context').innerHTML=`<div><b>${esc(o.status)}</b><span>${esc(o.region||'')} • ${ND.fmt(o.delivery)}</span></div><strong>${money(o.total)}</strong>`;const msgs=o.messages||[];$('#chat-messages').innerHTML=msgs.length?msgs.map(m=>`<div class="msg ${m.from}"><small>${m.from==='admin'?'Nossas Delícias':m.from==='customer'?'Você':'Sistema'} • ${ND.when(m.date)}</small><p>${esc(m.text)}</p></div>`).join(''):'<div class="availability">Nenhuma mensagem ainda.</div>';const box=$('#chat-messages');box.scrollTop=box.scrollHeight;$('#chat-input').maxLength=500;$('#chat-input').placeholder=activeChat.role==='admin'?'Responder ao cliente…':'Escreva sobre este pedido…'}
  ND.renderActiveChat=renderChat;
  ND.sendMessage=(id,from,text)=>{const role=from==='admin'?'admin':'customer',o=canOpenOrder(id,role);text=String(text||'').trim();if(!o||!text||text.length>500)return false;const t=Date.now();if(t-lastSentAt<700)return false;lastSentAt=t;o.messages=o.messages||[];o.messages.push({id:`${o.id}-${t}`,from:role,text,date:now(),readByCustomer:role==='customer',readByAdmin:role==='admin'});ND.save();ND.updateHeader();return true};
  if($('#chat-send'))$('#chat-send').onclick=()=>{const t=$('#chat-input').value;if(!activeChat||!ND.sendMessage(activeChat.id,activeChat.role,t))return;$('#chat-input').value='';renderChat()};
  if($('#chat-input'))$('#chat-input').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('#chat-send').click()}};

  ND.adminInbox=selected=>{
    const conv=s.orders.filter(o=>(o.messages||[]).length).sort((a,b)=>(b.messages?.at(-1)?.date||b.date).localeCompare(a.messages?.at(-1)?.date||a.date)),current=s.orders.find(o=>o.id===selected)||conv[0];window.ND_INBOX=current?.id||null;if(current)markRead(current,'admin');
    return `<div class="nd-admin-heading"><div><h2>Conversas</h2><p>Mensagens ligadas ao pedido, com leitura e contexto preservados.</p></div><input id="nd-inbox-search" placeholder="Buscar cliente, pedido ou mensagem"></div><div class="nd-inbox"><aside id="nd-inbox-list">${conv.map(o=>{const last=o.messages.at(-1),unread=(o.messages||[]).filter(m=>m.from==='customer'&&!m.readByAdmin).length;return `<button data-inbox="${o.id}" data-inbox-text="${esc(`${o.id} ${o.customer?.name||''} ${last?.text||''}`.toLowerCase())}" class="${current?.id===o.id?'active':''}"><b>${esc(o.id)} • ${esc(o.customer?.name||'Cliente')}${unread?` <span class="nd-msg-badge">${unread}</span>`:''}</b><span>${esc(last?.text||'')}</span><small>${esc(o.status)} • ${last?ND.when(last.date):''}</small></button>`}).join('')||'<p class="muted">Sem conversas.</p>'}</aside><section>${current?`<header><b>${esc(current.id)} • ${esc(current.customer?.name||'Cliente')}</b><span>${esc(current.status)} • ${money(current.total)}</span></header><main>${(current.messages||[]).map(m=>`<div class="msg ${m.from}"><small>${m.from==='admin'?'Nossas Delícias':m.from==='customer'?'Cliente':'Sistema'} • ${ND.when(m.date)}</small><p>${esc(m.text)}</p></div>`).join('')}</main><footer><input id="nd-inbox-text" maxlength="500" placeholder="Responder ao cliente"><button id="nd-inbox-send">Enviar</button></footer>`:'<div class="availability">Selecione uma conversa.</div>'}</section></div>`;
  };
  const oldBind=ND.bindBusiness;
  ND.bindBusiness=()=>{oldBind?.();if($('#nd-inbox-search'))$('#nd-inbox-search').oninput=e=>{const q=e.target.value.trim().toLowerCase();$$('[data-inbox-text]').forEach(b=>b.style.display=b.dataset.inboxText.includes(q)?'':'none')};if($('#nd-inbox-send'))$('#nd-inbox-send').onclick=()=>{const t=$('#nd-inbox-text').value.trim();if(t&&window.ND_INBOX&&ND.sendMessage(window.ND_INBOX,'admin',t)){ND.audit('Mensagem enviada',window.ND_INBOX);ND.renderAdmin()}};};

  const oldOpen=ND.open;
  ND.open=name=>{oldOpen(name);if(name==='login')prepareLogin();if(name==='account')ND.renderAccount?.();};
  ND.updateHeader();ND.save();
})();
