
async function loadStatus() {
  const s = await fetch('/api/status').then(r => r.json());
  document.getElementById('receita').innerText = 'R$ ' + s.receita_total.toFixed(2);
  document.getElementById('gastos').innerText = 'R$ ' + s.gastos_mes.toFixed(2);
  document.getElementById('saldo').innerText = 'R$ ' + s.saldo.toFixed(2);

  let lines = [
    `Mês: ${s.mes}`,
    `Receita total: R$ ${s.receita_total.toFixed(2)}`,
    `Gastos do mês: R$ ${s.gastos_mes.toFixed(2)}`,
    `Saldo: R$ ${s.saldo.toFixed(2)}`
  ];
  if (Object.keys(s.cartoes).length) {
    lines.push('');
    lines.push('Faturas do mês:');
    for (const [k,v] of Object.entries(s.cartoes)) lines.push(`- ${k}: R$ ${v.toFixed(2)}`);
  }
  if (s.excedentes.length) {
    lines.push('');
    lines.push('Excedentes:');
    s.excedentes.forEach(e => lines.push(`- ${e.categoria}: +R$ ${e.excesso.toFixed(2)}`));
  }
  document.getElementById('analise').innerText = lines.join('\n');
}

async function loadCards() {
  const cards = await fetch('/api/cartoes').then(r => r.json());
  const tbody = document.querySelector('#tbl-cartoes tbody');
  const select = document.getElementById('cartao');
  const pselect = document.getElementById('p_cartao');
  tbody.innerHTML = '';
  select.innerHTML = '<option value="">Selecione o cartão</option>';
  pselect.innerHTML = '<option value="">Selecione o cartão</option>';
  for (const c of cards) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${c.nome}</td><td>${c.vencimento}</td><td>${c.melhor_dia_compra}</td><td>${c.melhor_dia_utilizado}</td>`;
    tbody.appendChild(tr);
    for (const sel of [select, pselect]) {
      const opt = document.createElement('option');
      opt.value = c.nome;
      opt.innerText = c.nome;
      sel.appendChild(opt);
    }
  }
}

async function lancar() {
  const descricao = document.getElementById('descricao').value;
  const valor = parseFloat(document.getElementById('valor').value);
  const forma_pagamento = document.getElementById('forma').value;
  const cartao = document.getElementById('cartao').value || null;
  await fetch('/api/lancar', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({descricao, valor, forma_pagamento, cartao})
  });
  await loadStatus();
  alert('Compra lançada.');
}

async function parcelar() {
  const descricao = document.getElementById('p_desc').value;
  const valor = parseFloat(document.getElementById('p_valor').value);
  const total_parcelas = parseInt(document.getElementById('p_total').value);
  const cartao = document.getElementById('p_cartao').value;
  await fetch('/api/parcelar', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({descricao, valor, total_parcelas, cartao})
  });
  await loadStatus();
  alert('Parcelado criado.');
}

loadStatus();
loadCards();
