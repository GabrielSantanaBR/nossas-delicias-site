(() => {
  'use strict';

  const decorate = (img) => {
    if (!img || img.dataset.ndFallbackBound === '1') return;
    img.dataset.ndFallbackBound = '1';
    const fallback = () => {
      const parent = img.parentElement;
      if (!parent) return;
      parent.classList.add('nd-media-fallback');
      const alt = (img.getAttribute('alt') || 'Nossas Delícias').trim();
      parent.dataset.fallbackLabel = alt.slice(0, 54);
      img.hidden = true;
    };
    img.addEventListener('error', fallback, { once: true });
    if (img.complete && img.naturalWidth === 0) fallback();
  };

  const bind = (root = document) => root.querySelectorAll('img').forEach(decorate);
  bind();

  if ('MutationObserver' in window) {
    new MutationObserver((entries) => {
      entries.forEach((entry) => entry.addedNodes.forEach((node) => {
        if (!(node instanceof Element)) return;
        if (node.matches('img')) decorate(node);
        bind(node);
      }));
    }).observe(document.body, { childList: true, subtree: true });
  }
})();
