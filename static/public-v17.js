(() => {
  'use strict';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduced) return;

  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const heroImage = document.querySelector('.hero-photo-shell img');
  const portfolioImages = [...document.querySelectorAll('.portfolio-media img')];
  let frame = 0;

  const sync = () => {
    frame = 0;
    if (heroImage) {
      const box = heroImage.parentElement.getBoundingClientRect();
      if (box.bottom > -120 && box.top < window.innerHeight + 120) {
        const center = box.top + box.height / 2 - window.innerHeight / 2;
        heroImage.style.setProperty('--public17-hero-y', `${clamp(-center * .022, -16, 16).toFixed(1)}px`);
      }
    }
    portfolioImages.forEach((image) => {
      const card = image.closest('.portfolio-card');
      if (!card) return;
      const box = card.getBoundingClientRect();
      if (box.bottom < -120 || box.top > window.innerHeight + 120) return;
      const center = box.top + box.height / 2 - window.innerHeight / 2;
      image.style.setProperty('--public17-portfolio-y', `${clamp(-center * .018, -14, 14).toFixed(1)}px`);
    });
  };

  const requestSync = () => {
    if (!frame) frame = window.requestAnimationFrame(sync);
  };
  window.addEventListener('scroll', requestSync, { passive: true });
  window.addEventListener('resize', requestSync, { passive: true });
  sync();
})();
