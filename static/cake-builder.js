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
  const validationAlert = root.querySelector('[data-cake-validation]');
  const stage = root.querySelector('.cake-stage');
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const draftKey = 'nd-cake-builder-selections-v1';
  let current = 1;

  const requiredInStep = (step) => [...sections[step - 1].querySelectorAll('[required]:not([disabled])')];
  const announceValidation = (message = '') => {
    if (!validationAlert) return;
    validationAlert.hidden = !message;
    validationAlert.textContent = message;
  };
  const attentionFor = (input) => input.closest('.cake-choice-field, label, .cake-inline-fields') || input;
  const validateStep = (step) => {
    const inputs = requiredInStep(step);
    const radioNames = [...new Set(inputs.filter((input) => input.type === 'radio').map((input) => input.name))];
    const missingRadio = radioNames
      .map((name) => inputs.find((input) => input.name === name))
      .find((input) => !inputs.some((candidate) => candidate.name === input.name && candidate.checked));
    const invalid = missingRadio || inputs.find((input) => input.type !== 'radio' && !input.checkValidity());
    if (!invalid) {
      announceValidation();
      return true;
    }
    if (!missingRadio) invalid.reportValidity();
    const field = attentionFor(invalid);
    field?.classList.add('needs-attention');
    window.setTimeout(() => field?.classList.remove('needs-attention'), 800);
    announceValidation(missingRadio ? 'Escolha uma opção para continuar esta etapa.' : 'Revise o campo destacado para continuar.');
    field?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'center' });
    return false;
  };

  const firstInvalidUntil = (target) => {
    for (let step = 1; step < target; step += 1) {
      if (!validateStep(step)) return step;
    }
    return null;
  };

  const showStep = (step, validateForward = true) => {
    const bounded = Math.max(1, Math.min(step, sections.length));
    if (validateForward && bounded > current) {
      const invalidStep = firstInvalidUntil(bounded);
      if (invalidStep) {
        if (invalidStep !== current) showStep(invalidStep, false);
        return;
      }
    }
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

  const saveBrowserDraft = () => {
    try {
      const draft = {};
      root.querySelectorAll('[data-cake-choice]:checked, [data-decoration]:checked').forEach((input) => {
        draft[input.name] = input.value;
      });
      const guestCount = form?.querySelector('[name="guest_count"]');
      if (guestCount?.value) draft.guest_count = guestCount.value;
      window.sessionStorage.setItem(draftKey, JSON.stringify(draft));
    } catch (_) {
      // Storage is a convenience only; the server remains authoritative.
    }
  };

  const restoreBrowserDraft = () => {
    if (!form) return;
    try {
      const draft = JSON.parse(window.sessionStorage.getItem(draftKey) || '{}');
      Object.entries(draft).forEach(([name, value]) => {
        const escapedName = CSS.escape(name);
        const current = form.querySelector(`[name="${escapedName}"]:checked`);
        const defaultOptionalChoice = current
          && current.value === ''
          && ['secondary_filling', 'complement'].includes(name);
        if (current && !defaultOptionalChoice) return;
        const input = form.querySelector(`[name="${escapedName}"][value="${CSS.escape(String(value))}"]`);
        if (input) {
          input.checked = true;
          syncSummary(input);
        }
      });
      const guestCount = form.querySelector('[name="guest_count"]');
      if (guestCount && draft.guest_count && (!guestCount.value || guestCount.value === guestCount.defaultValue)) {
        guestCount.value = draft.guest_count;
      }
    } catch (_) {
      // Private browser settings may disable sessionStorage.
    }
  };

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
    input.addEventListener('change', () => {
      syncSummary(input);
      saveBrowserDraft();
      announceValidation();
    });
    if (input.checked) syncSummary(input);
  });
  form?.querySelectorAll('input, textarea').forEach((input) => {
    input.addEventListener('input', () => {
      input.removeAttribute('aria-invalid');
      announceValidation();
      if (input.name === 'guest_count') saveBrowserDraft();
    });
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

  restoreBrowserDraft();
  const firstError = sections.findIndex((section) => section.querySelector('.errorlist'));
  showStep(firstError >= 0 ? firstError + 1 : 1, false);
})();
