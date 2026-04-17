const money = (n) => new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL'}).format(n || 0);
const pct = (n) => `${((n || 0) * 100).toFixed(1)}%`;

function statusClass(status){
  const key = (status || '').toLowerCase();
  if(key.includes('estour')) return 'status-estourado';
  if(key.includes('alert')) return 'status-alerta';
  return 'status-ok';
}

async function loadDashboard(){
  const data = await fetch('/api/dashboard').then(r => r.json());
  document.getElementById('totalLimit').textContent = money(data.total_limit);
  document.getElementById('totalSpent').textContent = money(data.total_spent);
  document.getElementById('totalRemaining').textContent = money(data.total_remaining);
  document.getElementById('usedPct').textContent = pct(data.used_pct);

  const categoryList = document.getElementById('categoryList');
  categoryList.innerHTML = '';
  data.categories.forEach(item => {
    const div = document.createElement('div');
    div.className = 'category-item';
    const used = Math.max(0, Math.min(100, (item.used_pct || 0) * 100));
    div.innerHTML = `
      <div class="category-head">
        <strong>${item.category}</strong>
        <span class="status-pill ${statusClass(item.status)}">${item.status}</span>
      </div>
      <div class="progress"><div style="width:${used}%"></div></div>
      <div class="meta">
        <span>Gasto: ${money(item.spent)}</span>
        <span>Limite: ${money(item.limit)}</span>
        <span>Saldo: ${money(item.remaining)}</span>
      </div>
    `;
    categoryList.appendChild(div);
  });

  const billsList = document.getElementById('billsList');
  billsList.innerHTML = '';
  if(!data.bills_due?.length){
    billsList.innerHTML = `<div class="bill-item"><div class="bill-head"><strong>Nenhuma conta crítica nos próximos 7 dias</strong></div></div>`;
  } else {
    data.bills_due.forEach(bill => {
      const div = document.createElement('div');
      div.className = 'bill-item';
      div.innerHTML = `
        <div class="bill-head">
          <strong>${bill.name}</strong>
          <span class="status-pill ${bill.days_left <= 1 ? 'status-estourado' : 'status-alerta'}">${bill.days_left} dia(s)</span>
        </div>
        <div class="meta">
          <span>Vencimento: ${bill.due_date}</span>
          <span>Valor: ${money(bill.amount)}</span>
          <span>Categoria: ${bill.category}</span>
        </div>
      `;
      billsList.appendChild(div);
    });
  }

  const lastLaunches = document.getElementById('lastLaunches');
  lastLaunches.innerHTML = '';
  if(!data.last_launches?.length){
    lastLaunches.innerHTML = `<div class="bill-item"><strong>Sem lançamentos recentes.</strong></div>`;
  } else {
    data.last_launches.forEach(item => {
      const div = document.createElement('div');
      div.className = 'bill-item';
      div.innerHTML = `
        <div class="bill-head">
          <strong>${item.category}</strong>
          <span class="status-pill ${item.entry_type === 'receita' ? 'status-ok' : 'status-alerta'}">${item.entry_type}</span>
        </div>
        <div class="meta">
          <span>Data: ${item.date}</span>
          <span>Valor: ${money(item.value)}</span>
          <span>${item.description || 'Sem descrição'}</span>
        </div>
      `;
      lastLaunches.appendChild(div);
    });
  }
}

document.getElementById('launchForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  payload.amount = Number(payload.amount || 0);
  payload.channel = 'painel';
  const res = await fetch('/api/launch', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  document.getElementById('launchResponse').textContent = data.message || data.error || JSON.stringify(data, null, 2);
  e.target.reset();
  loadDashboard();
});

document.getElementById('tgForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  const res = await fetch('/api/telegram-test', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  document.getElementById('tgResponse').textContent = data.reply || JSON.stringify(data, null, 2);
  e.target.reset();
  loadDashboard();
});

document.getElementById('refreshBtn').addEventListener('click', loadDashboard);

loadDashboard();
