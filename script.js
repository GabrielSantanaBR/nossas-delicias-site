(()=>{
 const css=['v6/v6-public.css?v=7','v6/v6-admin.css?v=7','v6/v7-layout-fixes.css?v=7','v6/v7-logo-fixes.css?v=7'];
 css.forEach(h=>{const l=document.createElement('link');l.rel='stylesheet';l.href=h;document.head.appendChild(l)});
 const files=['v6/v6-state.js?v=7','v6/v6-shop.js?v=7','v6/v6-account.js?v=7','v6/v6-admin-core.js?v=7','v6/v6-admin-business.js?v=7','v6/v6-admin-reports.js?v=7','v6/v7-admin-polish.js?v=7','v6/v6-init.js?v=7'];
 const load=i=>{if(i>=files.length)return;const s=document.createElement('script');s.src=files[i];s.onload=()=>load(i+1);s.onerror=()=>console.error('Falha ao carregar',files[i]);document.body.appendChild(s)};
 load(0);
})();