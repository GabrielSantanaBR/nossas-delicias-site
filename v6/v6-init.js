(()=>{const {$,$$,state:s}=ND;
$('.mobile-menu').onclick=()=>$('#nav').classList.toggle('open');
let searchBtn=$('.nd-search');if(searchBtn)searchBtn.onclick=()=>{let q=prompt('Buscar no cardápio:','');if(q!==null&&$('#catalog-search')){$('#catalog-search').value=q;$('#catalog-search').dispatchEvent(new Event('input'));location.hash='#cardapio'}};
const reveal=new IntersectionObserver(es=>es.forEach(e=>e.isIntersecting&&e.target.classList.add('visible')),{threshold:.08});$$('.reveal').forEach(e=>reveal.observe(e));
let reset=document.createElement('button');reset.className='nd-reset';reset.textContent='Resetar demo';reset.onclick=()=>{if(confirm('Apagar os dados salvos desta demonstração?')){localStorage.removeItem('nd_v6');location.reload()}};$('.demo-bar')?.appendChild(reset);
ND.save();ND.updateHeader?.();ND.renderFilters?.();ND.renderProducts?.();
})();