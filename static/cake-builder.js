(() => {
  'use strict';
  const root = document.querySelector('[data-cake-builder]');
  if (!root) return;
  const form = root.querySelector('[data-cake-form]');
  const sections = [...root.querySelectorAll('[data-step]')];
  const tabs = [...root.querySelectorAll('[data-step-tab]')];
  const previous = root.querySelector('[data-step-prev]');
  const next = root.querySelector('[data-step-next]');
  const count = root.querySelector('[data-step-count]');
  const progressLabel = root.querySelector('[data-progress-label]');
  const progressBar = root.querySelector('[data-progress-bar]');
  const stage = root.querySelector('.cake-stage');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current = 1;

  const requiredInStep = (step) => [...sections[step - 1].querySelectorAll('[required]')];
  const validateStep = (step) => {
    const invalid = requiredInStep(step).find((input) => !input.checkValidity());
    if (!invalid) return true;
    invalid.reportValidity();
    const field = invalid.closest('.cake-choice-field, label');
    field?.classList.add('needs-attention');
    window.setTimeout(() => field?.classList.remove('needs-attention'), 800);
    return false;
  };

  const showStep = (step, validateForward = true) => {
    const bounded = Math.max(1, Math.min(step, sections.length));
    if (validateForward && bounded > current && !validateStep(current)) return;
    current = bounded;
    sections.forEach((section, index) => {
      const active = index + 1 === current;
      section.hidden = !active;
      section.classList.toggle('is-active', active);
    });
    tabs.forEach((tab, index) => {
      const number = index + 1;
      tab.classList.toggle('is-active', number === current);
      tab.classList.toggle('is-complete', number < current);
      if (number === current) tab.setAttribute('aria-current', 'step');
      else tab.removeAttribute('aria-current');
    });
    previous.disabled = current === 1;
    next.hidden = current === sections.length;
    count.textContent = `${current} / ${sections.length}`;
    progressLabel.textContent = `Etapa ${current} de ${sections.length}`;
    progressBar.style.width = `${(current / sections.length) * 100}%`;
    if (!reduced && window.innerWidth < 881) {
      root.querySelector('.cake-builder-head')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  previous?.addEventListener('click', () => showStep(current - 1, false));
  next?.addEventListener('click', () => showStep(current + 1));
  tabs.forEach((tab) => tab.addEventListener('click', () => {
    const target = Number(tab.dataset.stepTab);
    showStep(target, target > current);
  }));

  const summaryDefaults = {
    dough: 'Escolha uma massa', primary_filling: 'Escolha o recheio',
    secondary_filling: 'Opcional', complement: 'Opcional',
    frosting: 'Escolha a cobertura', decoration_style: 'Escolha o estilo',
  };
  const syncSummary = (input) => {
    const key = input.dataset.summary;
    if (!key || !input.checked) return;
    const output = root.querySelector(`[data-summary-value="${key}"]`);
    if (output) output.textContent = input.dataset.label || summaryDefaults[key];
    if (!stage) return;
    const color = input.dataset.color;
    if (key === 'dough' && color) stage.style.setProperty('--cake-dough', color);
    if (key === 'primary_filling' && color) stage.style.setProperty('--cake-fill-one', color);
    if (key === 'secondary_filling') stage.style.setProperty('--cake-fill-two', color || 'transparent');
    if (key === 'complement' && color && color !== 'transparent') stage.style.setProperty('--cake-complement', color);
    if (key === 'frosting' && color) stage.style.setProperty('--cake-frosting', color);
    if (key === 'decoration_style') stage.dataset.decorationStage = input.value;
    stage.classList.remove('is-changing');
    requestAnimationFrame(() => stage.classList.add('is-changing'));
  };
  root.querySelectorAll('[data-cake-choice],[data-decoration]').forEach((input) => {
    input.addEventListener('change', () => syncSummary(input));
    if (input.checked) syncSummary(input);
  });

  const file = form?.querySelector('input[type="file"]');
  const fileName = root.querySelector('[data-file-name]');
  file?.addEventListener('change', () => {
    if (fileName) fileName.textContent = file.files[0]?.name || 'Nenhum arquivo escolhido';
  });

  form?.addEventListener('submit', (event) => {
    for (let step = 1; step <= sections.length; step += 1) {
      if (!validateStep(step)) {
        event.preventDefault();
        showStep(step, false);
        return;
      }
    }
    const submit = form.querySelector('.cake-submit[type="submit"]');
    if (submit) {
      submit.disabled = true;
      submit.querySelector('span').textContent = 'Enviando composição…';
    }
  });

  const firstError = sections.findIndex((section) => section.querySelector('.errorlist'));
  showStep(firstError >= 0 ? firstError + 1 : 1, false);
})();
