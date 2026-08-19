(()=>{
  const cropped='logo-nossas-delicias-horizontal.svg?v=7';
  document.querySelectorAll('.brand img, footer img').forEach(img=>{
    img.src=cropped;
    img.alt='Nossas Delícias';
  });

  const oldOpen=ND.openAdmin;
  if(oldOpen){
    ND.openAdmin=()=>{
      oldOpen();
      requestAnimationFrame(()=>{
        const brand=document.querySelector('.nd-admin-brand img');
        if(brand){
          brand.src=cropped;
          brand.alt='Nossas Delícias';
        }
        const content=document.querySelector('.nd-admin-content');
        if(content) content.scrollTop=0;
      });
    };
    const fab=document.querySelector('#admin-fab');
    if(fab) fab.onclick=ND.openAdmin;
  }

  const closeSide=()=>{
    if(window.innerWidth>900){
      document.querySelector('.nd-admin-side')?.classList.remove('open');
    }
  };
  window.addEventListener('resize',closeSide,{passive:true});

  document.addEventListener('keydown',e=>{
    if(e.key!=='Escape') return;
    const dialog=document.querySelector('.nd-admin-dialog');
    if(dialog){dialog.remove();return;}
    if(document.body.classList.contains('nd-admin-open')) ND.closeAdmin?.();
  });
})();
