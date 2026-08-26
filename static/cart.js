(() => {
  'use strict';
  const form = document.querySelector('#checkout-form');
  if (!form) return;
  const zip = form.querySelector('[name=zip_code]');
  const address = form.querySelector('[name=address]');
  const saved = form.querySelector('#saved-address');
  const date = form.querySelector('#delivery-date');
  const info = document.querySelector('#delivery-info');
  const coupon = form.querySelector('[name=promotion_code]');
  let timer;
  let controller;

  const lookup = async () => {
    const value = zip.value.replace(/\D/g, '');
    if (value.length !== 8) {
      date.disabled = true;
      date.innerHTML = '<option value="">Informe um CEP completo</option>';
      info.textContent = '';
      return;
    }
    controller?.abort();
    controller = new AbortController();
    date.disabled = true;
    date.innerHTML = '<option>Consultando disponibilidade…</option>';
    info.textContent = 'Verificando região e capacidade…';
    try {
      const response = await fetch(`/entrega/disponibilidade/?cep=${encodeURIComponent(value)}`, { signal: controller.signal, headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Região não atendida');
      date.innerHTML = '<option value="">Escolha a data</option>' + data.dates.map((item) => `<option value="${item.date}">${new Date(`${item.date}T12:00:00`).toLocaleDateString('pt-BR')} · ${item.start}–${item.end} · ${item.remaining} vaga${item.remaining === 1 ? '' : 's'}</option>`).join('');
      date.disabled = !data.dates.length;
      info.textContent = `${data.region} · entrega R$ ${data.fee.toFixed(2)} · pedido mínimo R$ ${data.minimum_order.toFixed(2)}`;
    } catch (error) {
      if (error.name === 'AbortError') return;
      date.innerHTML = '<option value="">Sem datas disponíveis</option>';
      info.textContent = error.message;
    }
  };

  zip.addEventListener('input', () => { window.clearTimeout(timer); timer = window.setTimeout(lookup, 350); });
  const applySaved = () => {
    const option = saved?.selectedOptions[0];
    if (!option?.dataset.zip) return;
    zip.value = option.dataset.zip;
    address.value = option.dataset.address;
    lookup();
  };
  saved?.addEventListener('change', applySaved);
  if (saved?.value) applySaved();
  document.querySelectorAll('[data-coupon]').forEach((button) => button.addEventListener('click', () => { coupon.value = button.dataset.coupon; coupon.focus(); }));
  if (zip.value.replace(/\D/g, '').length === 8) lookup();
})();
