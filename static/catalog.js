(() => {
  'use strict';
  document.querySelectorAll('.add-cart').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const status = form.querySelector('.form-status');
    const button = form.querySelector('button');
    button.disabled = true;
    status.textContent = 'Adicionando…';
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível adicionar.');
      status.textContent = 'Adicionado à sacola.';
      const count = document.querySelector('.nav-count');
      if (count && data.count !== undefined) count.textContent = data.count;
      window.setTimeout(() => { status.textContent = ''; }, 2600);
    } catch (error) {
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }));

  document.querySelectorAll('.favorite-toggle').forEach((form) => form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button');
    button.disabled = true;
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Não foi possível atualizar.');
      button.classList.toggle('is-favorite', data.favorite);
      button.textContent = data.favorite ? '♥' : '♡';
      button.setAttribute('aria-label', data.favorite ? 'Remover dos favoritos' : 'Adicionar aos favoritos');
    } catch (error) {
      button.title = error.message;
    } finally {
      button.disabled = false;
    }
  }));
})();
