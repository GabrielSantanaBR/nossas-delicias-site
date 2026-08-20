(()=>{
  try{
    const raw=localStorage.getItem('nd_v6');
    if(raw) JSON.parse(raw);
  }catch(err){
    try{
      const raw=localStorage.getItem('nd_v6');
      if(raw) localStorage.setItem(`nd_v6_recovery_${Date.now()}`,raw.slice(0,200000));
    }catch(_){}
    localStorage.removeItem('nd_v6');
    console.warn('Dados locais inválidos foram isolados para a demonstração iniciar com segurança.');
  }
})();
