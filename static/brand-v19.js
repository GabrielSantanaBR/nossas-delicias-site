(() => {
  "use strict";

  const root = document.documentElement;
  root.classList.add("brand-v19-ready");

  const normalizePath = (path) => {
    const value = path.replace(/\/+$/, "");
    return value || "/";
  };

  const currentPath = normalizePath(window.location.pathname);
  document.querySelectorAll(".site-nav > a[href]").forEach((link) => {
    const target = new URL(link.href, window.location.origin);
    if (target.origin !== window.location.origin) return;
    const linkPath = normalizePath(target.pathname);
    const isCurrent = linkPath === "/" ? currentPath === "/" : currentPath === linkPath || currentPath.startsWith(`${linkPath}/`);
    if (!isCurrent) return;
    link.classList.add("is-current");
    link.setAttribute("aria-current", "page");
  });

  const revealGroups = [
    ".featured-grid [data-reveal]",
    ".portfolio-grid [data-reveal]",
    ".public-process-grid [data-reveal]",
    ".service-grid [data-reveal]",
    ".catalog-grid [data-reveal]",
    ".cake-trust [data-reveal]",
  ];
  revealGroups.forEach((selector) => {
    document.querySelectorAll(selector).forEach((item, index) => {
      item.style.setProperty("--reveal-delay", `${Math.min(index * 70, 280)}ms`);
    });
  });

  const supportsPointer = window.matchMedia("(pointer: fine)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!supportsPointer || reducedMotion) return;

  const interactiveCards = document.querySelectorAll(
    ".featured-product, .portfolio-card, .public-process-card, .service-card, .product.interactive, .panel"
  );

  interactiveCards.forEach((card) => {
    let animationFrame = 0;
    card.addEventListener("pointermove", (event) => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
      animationFrame = requestAnimationFrame(() => {
        const bounds = card.getBoundingClientRect();
        const x = ((event.clientX - bounds.left) / bounds.width) * 100;
        const y = ((event.clientY - bounds.top) / bounds.height) * 100;
        card.style.setProperty("--spot-x", `${x.toFixed(2)}%`);
        card.style.setProperty("--spot-y", `${y.toFixed(2)}%`);
        card.classList.add("is-interacting");
      });
    }, { passive: true });
    card.addEventListener("pointerleave", () => {
      if (animationFrame) cancelAnimationFrame(animationFrame);
      card.classList.remove("is-interacting");
    }, { passive: true });
  });
})();
