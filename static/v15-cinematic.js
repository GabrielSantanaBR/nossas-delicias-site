(() => {
  'use strict';

  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = window.matchMedia('(pointer:fine)').matches;
  if (reduced) return;

  const clamp = (v, min, max) => Math.min(Math.max(v, min), max);
  const hero = document.querySelector('.hero-visual');
  const heroStage = document.querySelector('.hero-stage');
  let raf = 0;

  const syncHero = () => {
    raf = 0;
    if (!hero || !heroStage) return;
    const rect = heroStage.getBoundingClientRect();
    const progress = clamp((-rect.top + 40) / Math.max(rect.height, 1), 0, 1);
    hero.style.setProperty('--hero-y', `${(progress * 20).toFixed(2)}px`);
    hero.style.setProperty('--hero-rotate', `${(-1.1 + progress * 1.1).toFixed(3)}deg`);
    hero.style.setProperty('--hero-zoom', (progress * 0.025).toFixed(4));
  };
  const requestHero = () => {
    if (raf) return;
    raf = requestAnimationFrame(syncHero);
  };
  window.addEventListener('scroll', requestHero, { passive: true });
  window.addEventListener('resize', requestHero, { passive: true });
  syncHero();

  if (finePointer && hero) {
    hero.addEventListener('pointermove', (event) => {
      const rect = hero.getBoundingClientRect();
      const x = (event.clientX - rect.left) / rect.width - .5;
      const y = (event.clientY - rect.top) / rect.height - .5;
      hero.style.setProperty('--hero-x', `${(x * 7).toFixed(2)}px`);
      hero.style.setProperty('--hero-y', `${(y * 6).toFixed(2)}px`);
    });
    hero.addEventListener('pointerleave', () => {
      hero.style.setProperty('--hero-x', '0px');
      syncHero();
    });
  }

  if (finePointer) {
    document.querySelectorAll('.featured-product,.service-card,.mgmt-panel').forEach((card) => {
      card.dataset.tilt = 'true';
      card.addEventListener('pointermove', (event) => {
        const rect = card.getBoundingClientRect();
        const px = (event.clientX - rect.left) / rect.width - .5;
        const py = (event.clientY - rect.top) / rect.height - .5;
        const rx = clamp(-py * 5, -2.7, 2.7);
        const ry = clamp(px * 5, -2.7, 2.7);
        card.style.transform = `perspective(900px) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateY(-4px)`;
      });
      card.addEventListener('pointerleave', () => { card.style.transform = ''; });
    });

    document.querySelectorAll('.button,.cta,.cta-secondary,.ghost-button,.nav-cta').forEach((button) => {
      button.classList.add('nd-magnetic');
      button.addEventListener('pointermove', (event) => {
        const rect = button.getBoundingClientRect();
        const x = clamp((event.clientX - rect.left - rect.width / 2) * .12, -5, 5);
        const y = clamp((event.clientY - rect.top - rect.height / 2) * .12, -4, 4);
        button.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)`;
      });
      button.addEventListener('pointerleave', () => { button.style.transform = ''; });
    });
  }

  const headline = document.querySelector('.hero-copy h1');
  if (headline && !headline.dataset.motionReady) {
    headline.dataset.motionReady = 'true';
    const textNodes = [...headline.childNodes];
    let index = 0;
    textNodes.forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        const fragment = document.createDocumentFragment();
        node.textContent.split(/(\s+)/).forEach((part) => {
          if (!part.trim()) {
            fragment.appendChild(document.createTextNode(part));
            return;
          }
          const span = document.createElement('span');
          span.className = 'nd-word';
          span.style.setProperty('--word-delay', `${index * 55}ms`);
          span.textContent = part;
          index += 1;
          fragment.appendChild(span);
        });
        node.replaceWith(fragment);
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        node.classList.add('nd-word');
        node.style.setProperty('--word-delay', `${index * 55}ms`);
        index += 1;
      }
    });
    requestAnimationFrame(() => headline.classList.add('nd-headline-ready'));
  }

  const style = document.createElement('style');
  style.textContent = `
    .hero-copy h1 .nd-word{display:inline-block;opacity:0;transform:translateY(32px) rotate(1deg);filter:blur(7px)}
    .hero-copy h1.nd-headline-ready .nd-word{opacity:1;transform:none;filter:none;transition:opacity .78s cubic-bezier(.2,.75,.22,1) var(--word-delay),transform .85s cubic-bezier(.2,.75,.22,1) var(--word-delay),filter .7s ease var(--word-delay)}
  `;
  document.head.appendChild(style);
})();
