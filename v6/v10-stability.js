(()=>{
  const {$,state:s}=ND;

  const currentSave=ND.save;
  ND.save=()=>{
    try{return currentSave()}
    catch(err){console.error(err);ND.toast?.('Não foi possível salvar localmente. Libere espaço do navegador e tente novamente.');return false}
  };

  if(s.user?.email&&!s.auth?.accounts?.some(a=>String(a.email||'').toLowerCase()===String(s.user.email||'').toLowerCase())){
    s.user=null;s.auth.sessionExpires=null;ND.save();
  }

  const currentOpen=ND.open;
  ND.open=name=>{
    if(name==='login'&&s.user) return currentOpen('account');
    return currentOpen(name);
  };

  const oldStatus=ND.setStatus;
  if(oldStatus)ND.setStatus=(id,status)=>{
    oldStatus(id,status);
    const o=s.orders.find(x=>x.id===id),m=o?.messages?.at(-1);
    if(m?.from==='system'){m.readByCustomer=false;m.readByAdmin=true;m.id=m.id||`${id}-${Date.now()}`;ND.save();ND.updateHeader?.()}
  };

  const oldPaid=ND.markPaid;
  if(oldPaid)ND.markPaid=id=>{
    oldPaid(id);
    const o=s.orders.find(x=>x.id===id),m=o?.messages?.at(-1);
    if(m?.from==='system'){m.readByCustomer=false;m.readByAdmin=true;m.id=m.id||`${id}-${Date.now()}`;ND.save();ND.updateHeader?.()}
  };

  window.addEventListener('error',event=>{
    if(String(event?.filename||'').includes('nossas-delicias')) ND.toast?.('Uma parte da interface encontrou um erro. Recarregue a página se algo não responder.');
  });
  window.addEventListener('unhandledrejection',()=>ND.toast?.('Não foi possível concluir uma operação. Tente novamente.'));

  const account=$('[data-open="account"]');
  if(account)account.setAttribute('aria-label','Minha conta e mensagens');
  ND.updateHeader?.();
})();
