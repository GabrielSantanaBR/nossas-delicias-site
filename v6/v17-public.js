(()=>{
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp=(value,min,max)=>Math.min(Math.max(value,min),max);

  document.querySelector('#admin-fab')?.remove();
  document.querySelector('#admin')?.remove();
  document.querySelector('.nd-system-showcase')?.remove();
  document.querySelectorAll('a[href="#sistema"]').forEach(node=>node.remove());

  const reveals=[...document.querySelectorAll('.reveal')];
  if(reduced||!('IntersectionObserver'in window)){
    reveals.forEach(node=>node.classList.add('visible'));
  }else{
    const observer=new IntersectionObserver(entries=>{
      entries.forEach(entry=>{
        if(!entry.isIntersecting)return;
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      });
    },{threshold:.09,rootMargin:'0px 0px -7% 0px'});
    reveals.forEach(node=>observer.observe(node));
  }

  if(reduced)return;
  const heroImage=document.querySelector('.hero-media>img');
  const portfolioImages=[...document.querySelectorAll('.nd-portfolio-card img')];
  let raf=0;
  const sync=()=>{
    raf=0;
    if(heroImage){
      const box=heroImage.parentElement.getBoundingClientRect();
      if(box.bottom>-120&&box.top<innerHeight+120){
        const center=box.top+box.height/2-innerHeight/2;
        heroImage.style.setProperty('--v17-hero-image-y',`${clamp(-center*.022,-16,16).toFixed(1)}px`);
      }
    }
    portfolioImages.forEach(image=>{
      const card=image.closest('.nd-portfolio-card');
      if(!card)return;
      const box=card.getBoundingClientRect();
      if(box.bottom<-120||box.top>innerHeight+120)return;
      const center=box.top+box.height/2-innerHeight/2;
      image.style.setProperty('--v17-portfolio-y',`${clamp(-center*.018,-14,14).toFixed(1)}px`);
    });
  };
  const request=()=>{if(!raf)raf=requestAnimationFrame(sync)};
  addEventListener('scroll',request,{passive:true});
  addEventListener('resize',request,{passive:true});
  sync();
})();
