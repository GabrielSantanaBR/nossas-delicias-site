(() => {
  'use strict';
  document.querySelector('#pay-form')?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const button = form.querySelector('button');
    button.disabled = true;
    button.textContent = 'Abrindo pagamento…';
    try {
      const response = await fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await response.json();
      if (!response.ok || !data.checkout_url) throw new Error(data.error || 'Pagamento indisponível.');
      window.location.href = data.checkout_url;
    } catch (error) {
      const status = form.querySelector('[data-payment-status]');
      if (status) status.textContent = error.message;
      button.disabled = false;
      button.textContent = 'Pagar com Mercado Pago';
    }
  });

  const chat = document.querySelector('[data-order-chat]');
  const form = document.querySelector('#chat-form');
  if (!chat || !form) return;
  const status = document.querySelector('#chat-status');
  const box = document.querySelector('#messages');
  const input = document.querySelector('#chat-input');
  const userId = Number(chat.dataset.userId);
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  let socket;
  let retries = 0;
  let timer;
  const setStatus = (text) => { status.textContent = text; };
  const connect = () => {
    socket = new WebSocket(`${scheme}://${window.location.host}${chat.dataset.socketPath}`);
    socket.onopen = () => { retries = 0; setStatus('Online'); input.disabled = false; };
    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.error) { setStatus(data.error); return; }
      const message = document.createElement('p');
      if (data.sender_id === userId) message.className = 'mine';
      const author = document.createElement('b');
      author.textContent = data.sender_id === userId ? 'Você' : 'Nossas Delícias';
      const text = document.createElement('span');
      text.textContent = data.message;
      message.append(author, text);
      box.append(message);
      box.scrollTop = box.scrollHeight;
    };
    socket.onclose = () => {
      input.disabled = true;
      if (retries >= 5) { setStatus('Offline'); return; }
      setStatus('Reconectando');
      retries += 1;
      window.clearTimeout(timer);
      timer = window.setTimeout(connect, Math.min(1000 * 2 ** retries, 12000));
    };
    socket.onerror = () => setStatus('Instável');
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ message }));
    input.value = '';
  });
  connect();
  box.scrollTop = box.scrollHeight;
})();
