(() => {
  'use strict';

  const root = document.documentElement;
  const body = document.body;
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const header = document.querySelector('[data-site-header]');
  const progress = document.querySelector('[data-scroll-progress]');
  const nav = document.querySelector('[data-site-nav]');
  const navToggle = document.querySelector('[data-nav-toggle]');
  const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

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
  }

  let ticking = false;
  const syncScrollState = () => {
    const scrollTop = window.scrollY || window.pageYOffset;
    const scrollable = Math.max(document.documentElement.scrollHeight - window.innerHeight, 1);
    const ratio = clamp(scrollTop / scrollable, 0, 1);
    if (progress) progress.style.transform = `scaleX(${ratio})`;
    if (header) header.classList.toggle('is-scrolled', scrollTop > 22);
    root.style.setProperty('--page-scroll', ratio.toFixed(4));

    if (!prefersReducedMotion) {
      document.querySelectorAll('[data-parallax]').forEach((node) => {
        const rect = node.getBoundingClientRect();
        if (rect.bottom < -120 || rect.top > window.innerHeight + 120) return;
        const strength = Number(node.dataset.parallax || 0.08);
        const center = rect.top + rect.height / 2 - window.innerHeight / 2;
        const offset = clamp(-center * strength, -42, 42);
        node.style.setProperty('--parallax-y', `${offset.toFixed(2)}px`);
      });
    }
    ticking = false;
  };

  const requestScrollSync = () => {
    if (!ticking) {
      ticking = true;
      window.requestAnimationFrame(syncScrollState);
    }
  };
  window.addEventListener('scroll', requestScrollSync, { passive: true });
  window.addEventListener('resize', requestScrollSync);
  syncScrollState();

  const revealNodes = [...document.querySelectorAll('[data-reveal]')];
  if (revealNodes.length) {
    if (prefersReducedMotion || !('IntersectionObserver' in window)) {
      revealNodes.forEach((node) => node.classList.add('is-visible'));
    } else {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.14, rootMargin: '0px 0px -8% 0px' });
      revealNodes.forEach((node) => observer.observe(node));
    }
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
        const eased = 1 - Math.pow(1 - value, 3);
        node.textContent = `${Math.round(target * eased)}${suffix}`;
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
