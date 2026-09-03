(() => {
  'use strict';

  const root = document.documentElement;
  const body = document.body;
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const supportsFinePointer = window.matchMedia('(pointer: fine)').matches;
  const header = document.querySelector('[data-site-header]');
  const progress = document.querySelector('[data-scroll-progress]');
  const nav = document.querySelector('[data-site-nav]');
  const navToggle = document.querySelector('[data-nav-toggle]');
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
  const normalizePath = (path) => path.replace(/\/+$/, '') || '/';

  document.querySelectorAll('img[data-fallback-src]').forEach((image) => {
    const fallback = image.dataset.fallbackSrc;
    if (!fallback) return;
    image.addEventListener('error', () => {
      const fallbackUrl = new URL(fallback, window.location.origin).href;
      if (image.src === fallbackUrl) return;
      image.src = fallbackUrl;
      image.classList.add('is-fallback-visual');
    }, { once: true });
  });

  if (navToggle && nav) {
    const closeNav = () => {
      nav.classList.remove('is-open');
      navToggle.setAttribute('aria-expanded', 'false');
      body.classList.remove('nav-open');
    };
    navToggle.addEventListener('click', () => {
      const open = !nav.classList.contains('is-open');
      nav.classList.toggle('is-open', open);
      navToggle.setAttribute('aria-expanded', String(open));
      body.classList.toggle('nav-open', open);
    });
    nav.querySelectorAll('a').forEach((link) => link.addEventListener('click', closeNav));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeNav();
    });
    document.addEventListener('click', (event) => {
      if (!nav.classList.contains('is-open') || nav.contains(event.target) || navToggle.contains(event.target)) return;
      closeNav();
    });
  }

  if (nav) {
    const currentPath = normalizePath(window.location.pathname);
    nav.querySelectorAll('a[href]').forEach((link) => {
      const target = new URL(link.href, window.location.origin);
      if (target.origin !== window.location.origin) return;
      const linkPath = normalizePath(target.pathname);
      const active = linkPath === '/' ? currentPath === '/' : currentPath === linkPath || currentPath.startsWith(`${linkPath}/`);
      if (active) {
        link.classList.add('is-current');
        link.setAttribute('aria-current', 'page');
      }
    });
  }

  let ticking = false;
  const syncScrollState = () => {
    const scrollTop = window.scrollY || window.pageYOffset;
    const scrollable = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
    const ratio = clamp(scrollTop / scrollable, 0, 1);
    if (progress) progress.style.transform = `scaleX(${ratio})`;
    if (header) header.classList.toggle('is-scrolled', scrollTop > 22);
    root.style.setProperty('--page-scroll', ratio.toFixed(4));
    ticking = false;
  };
  const requestScrollSync = () => {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(syncScrollState);
    }
  };
  window.addEventListener('scroll', requestScrollSync, { passive: true });
  window.addEventListener('resize', requestScrollSync, { passive: true });
  syncScrollState();

  const revealNodes = [...document.querySelectorAll('[data-reveal]')];
  if (revealNodes.length) {
    revealNodes.forEach((node, index) => node.style.setProperty('--reveal-delay', `${Math.min(index * 55, 260)}ms`));
    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      revealNodes.forEach((node) => node.classList.add('is-visible'));
    } else {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          // Fast page jumps can move an item from below to above the viewport
          // without ever meeting the intersection threshold. Once it has been
          // reached, keep it visible instead of leaving an empty page section.
          if (!entry.isIntersecting && entry.boundingClientRect.top >= 0) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.12, rootMargin: '0px 0px -7% 0px' });
      revealNodes.forEach((node) => observer.observe(node));

      let revealTicking = false;
      const revealReachedNodes = () => {
        const revealLine = window.innerHeight * 0.93;
        revealNodes.forEach((node) => {
          if (node.classList.contains('is-visible')) return;
          if (node.getBoundingClientRect().top > revealLine) return;
          node.classList.add('is-visible');
          observer.unobserve(node);
        });
        revealTicking = false;
      };
      const requestRevealSync = () => {
        if (revealTicking) return;
        revealTicking = true;
        window.requestAnimationFrame(revealReachedNodes);
      };
      window.addEventListener('scroll', requestRevealSync, { passive: true });
      window.addEventListener('resize', requestRevealSync, { passive: true });
      revealReachedNodes();
    }
  }

  if (supportsFinePointer && !prefersReducedMotion) {
    document.querySelectorAll('.featured-product, .portfolio-card, .public-process-card, .service-card, .product.interactive').forEach((card) => {
      let frame = 0;
      card.addEventListener('pointermove', (event) => {
        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          const bounds = card.getBoundingClientRect();
          card.style.setProperty('--spot-x', `${((event.clientX - bounds.left) / bounds.width * 100).toFixed(1)}%`);
          card.style.setProperty('--spot-y', `${((event.clientY - bounds.top) / bounds.height * 100).toFixed(1)}%`);
        });
      }, { passive: true });
    });
  }

  const story = document.querySelector('[data-story]');
  if (story) {
    const steps = [...story.querySelectorAll('[data-story-step]')];
    const scenes = [...story.querySelectorAll('[data-story-scene]')];
    const activate = (key) => {
      steps.forEach((step) => step.classList.toggle('is-active', step.dataset.storyStep === key));
      scenes.forEach((scene) => {
        const active = scene.dataset.storyScene === key;
        scene.classList.toggle('is-active', active);
        scene.setAttribute('aria-hidden', String(!active));
      });
      story.dataset.active = key;
    };
    if (steps[0]) activate(steps[0].dataset.storyStep);
    if ('IntersectionObserver' in window) {
      const storyObserver = new IntersectionObserver((entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible) activate(visible.target.dataset.storyStep);
      }, { threshold: [0.35, 0.55, 0.72], rootMargin: '-18% 0px -38% 0px' });
      steps.forEach((step) => storyObserver.observe(step));
    }
  }

  document.querySelectorAll('[data-counter]').forEach((node) => {
    const target = Number(node.dataset.counter);
    if (!Number.isFinite(target) || target <= 0 || prefersReducedMotion) return;
    const suffix = node.dataset.counterSuffix || '';
    let played = false;
    const play = () => {
      if (played) return;
      played = true;
      const start = performance.now();
      const duration = 850;
      const animate = (now) => {
        const value = clamp((now - start) / duration, 0, 1);
        node.textContent = `${Math.round(target * (1 - Math.pow(1 - value, 3)))}${suffix}`;
        if (value < 1) requestAnimationFrame(animate);
      };
      requestAnimationFrame(animate);
    };
    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          play();
          observer.disconnect();
        }
      }, { threshold: 0.5 });
      observer.observe(node);
    } else play();
  });

  const catalogSearch = document.querySelector('[data-catalog-search]');
  if (catalogSearch) {
    const cards = [...document.querySelectorAll('[data-product-card]')];
    const sections = [...document.querySelectorAll('[data-category-section]')];
    const normalize = (value) => String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const filterCatalog = () => {
      const query = normalize(catalogSearch.value.trim());
      cards.forEach((card) => {
        const haystack = normalize(card.dataset.search || card.textContent);
        card.hidden = Boolean(query && !haystack.includes(query));
      });
      sections.forEach((section) => {
        section.hidden = ![...section.querySelectorAll('[data-product-card]')].some((card) => !card.hidden);
      });
    };
    catalogSearch.addEventListener('input', filterCatalog);
  }

  document.querySelectorAll('[data-scroll-to]').forEach((trigger) => {
    trigger.addEventListener('click', (event) => {
      const target = document.querySelector(trigger.dataset.scrollTo);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth', block: 'start' });
    });
  });
})();
