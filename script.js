(()=>{
 const css=['v6/v6-public.css?v=12','v6/v6-admin.css?v=12','v6/v7-layout-fixes.css?v=12','v6/v7-logo-fixes.css?v=12','v6/v7-sticky-header.css?v=12','v6/v10-auth-chat.css?v=12','v6/v11-premium.css?v=12','v6/v12-production.css?v=12'];
 css.forEach(h=>{if(document.querySelector(`link[href="${h}"]`))return;const l=document.createElement('link');l.rel='stylesheet';l.href=h;document.head.appendChild(l)});
 const files=['v6/v10-preflight.js?v=12','v6/v6-state.js?v=12','v6/v6-shop.js?v=12','v6/v6-account.js?v=12','v6/v6-admin-core.js?v=12','v6/v6-admin-business.js?v=12','v6/v6-admin-reports.js?v=12','v6/v7-admin-polish.js?v=12','v6/v10-auth-chat.js?v=12','v6/v10-stability.js?v=12','v6/v11-premium.js?v=12','v6/v12-production.js?v=12','v6/v6-init.js?v=12'];
 const load=i=>{if(i>=files.length)return;const s=document.createElement('script');s.src=files[i];s.onload=()=>load(i+1);s.onerror=()=>console.error('Falha ao carregar',files[i]);document.body.appendChild(s)};
 load(0);
})();