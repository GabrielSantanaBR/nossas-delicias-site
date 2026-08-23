(()=>{
  'use strict';
  const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduced)return;
  const fine=matchMedia('(pointer:fine)').matches;
  const clamp=(v,min,max)=>Math.min(Math.max(v,min),max);
  const hero=document.querySelector('.hero');
  const heroMedia=document.querySelector('.hero-media');
  let raf=0;

  const sync=()=>{
    raf=0;
    if(!hero||!heroMedia)return;
    const r=hero.getBoundingClientRect();
    const p=clamp((-r.top+35)/Math.max(r.height,1),0,1);
    heroMedia.style.setProperty('--v15-hero-r',`${(-1+p).toFixed(3)}deg`);
    heroMedia.style.setProperty('--v15-zoom',(p*.025).toFixed(4));
  };
  const request=()=>{if(!raf)raf=requestAnimationFrame(sync)};
  addEventListener('scroll',request,{passive:true});addEventListener('resize',request,{passive:true});sync();

  if(fine&&heroMedia){
    heroMedia.addEventListener('pointermove',e=>{
      const r=heroMedia.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
      heroMedia.style.setProperty('--v15-hero-x',`${(x*7).toFixed(2)}px`);
      heroMedia.style.setProperty('--v15-hero-y',`${(y*6).toFixed(2)}px`);
    });
    heroMedia.addEventListener('pointerleave',()=>{heroMedia.style.setProperty('--v15-hero-x','0px');heroMedia.style.setProperty('--v15-hero-y','0px')});
  }

  const headline=document.querySelector('.hero h1');
  if(headline&&!headline.dataset.v15Ready){
    headline.dataset.v15Ready='1';let index=0;
    [...headline.childNodes].forEach(node=>{
      if(node.nodeType===Node.TEXT_NODE){
        const frag=document.createDocumentFragment();
        node.textContent.split(/(\s+)/).forEach(part=>{
          if(!part.trim()){frag.appendChild(document.createTextNode(part));return}
          const span=document.createElement('span');span.className='v15-word';span.style.setProperty('--word-delay',`${index*52}ms`);span.textContent=part;index++;frag.appendChild(span);
        });
        node.replaceWith(frag);
      }else if(node.nodeType===Node.ELEMENT_NODE){node.classList.add('v15-word');node.style.setProperty('--word-delay',`${index*52}ms`);index++}
    });
    requestAnimationFrame(()=>headline.classList.add('v15-headline-ready'));
  }

  if(fine){
    const setupTilt=card=>{
      card.addEventListener('pointermove',e=>{
        const r=card.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;
        const rx=clamp(-y*5,-2.6,2.6),ry=clamp(x*5,-2.6,2.6);
        card.style.transform=`perspective(900px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateY(-4px)`;
      });
      card.addEventListener('pointerleave',()=>card.style.transform='');
    };
    document.querySelectorAll('.audience,.benefit-grid article').forEach(setupTilt);
    const bindProducts=()=>document.querySelectorAll('.nd-product:not([data-v15-tilt])').forEach(card=>{card.dataset.v15Tilt='1';setupTilt(card)});
    bindProducts();
    new MutationObserver(bindProducts).observe(document.getElementById('product-grid')||document.body,{childList:true,subtree:true});

    document.querySelectorAll('.primary,.secondary,.button,.light-btn,.cart-btn').forEach(btn=>{
      btn.classList.add('nd-magnetic');
      btn.addEventListener('pointermove',e=>{const r=btn.getBoundingClientRect(),x=clamp((e.clientX-r.left-r.width/2)*.11,-5,5),y=clamp((e.clientY-r.top-r.height/2)*.11,-4,4);btn.style.transform=`translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)`});
      btn.addEventListener('pointerleave',()=>btn.style.transform='');
    });
  }
})();
