(()=>{
 const css=['v6/v6-public.css?v=17','v6/v7-layout-fixes.css?v=17','v6/v7-logo-fixes.css?v=17','v6/v7-sticky-header.css?v=17','v6/v10-auth-chat.css?v=17','v6/v11-premium.css?v=17','v6/v12-production.css?v=17','v6/v15-cinematic.css?v=17','v6/v17-public.css?v=17'];
 css.forEach(h=>{if(document.querySelector(`link[href="${h}"]`))return;const l=document.createElement('link');l.rel='stylesheet';l.href=h;document.head.appendChild(l)});
 const files=['v6/v10-preflight.js?v=17','v6/v6-state.js?v=17','v6/v6-shop.js?v=17','v6/v6-account.js?v=17','v6/v10-auth-chat.js?v=17','v6/v10-stability.js?v=17','v6/v11-premium.js?v=17','v6/v12-production.js?v=17','v6/v17-public.js?v=17','v6/v6-init.js?v=17'];
 const load=i=>{if(i>=files.length)return;const s=document.createElement('script');s.src=files[i];s.onload=()=>load(i+1);s.onerror=()=>console.error('Falha ao carregar',files[i]);document.body.appendChild(s)};
 load(0);
})();