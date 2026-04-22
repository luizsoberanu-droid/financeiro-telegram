let catChart;

async function fetchStatus() {
  const res = await fetch('/api/status');
  return await res.json();
}

function money(v) {
  return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(v || 0);
}

function renderSemaforo(status, msgs) {
  const el = document.getElementById('semaforo');
  const text = document.getElementById('analiseText');
  const colorMap = { verde: 'green', amarelo: 'yellow', vermelho: 'red' };
  const labelMap = { verde: '🟢 Dentro do plano', amarelo: '🟡 Atenção', vermelho: '🔴 Fora do plano' };
  el.innerHTML = `<span class="badge ${colorMap[status] || 'yellow'}">${labelMap[status] || status}</span>`;
  text.innerHTML = msgs.map(m => `<div>• ${m}</div>`).join('');
}

function renderCategoryChart(categoryTotals) {
  const labels = Object.keys(categoryTotals);
  const values = Object.values(categoryTotals);
  const ctx = document.getElementById('catChart');
  if (catChart) catChart.destroy();
  catChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        borderWidth: 0,
        backgroundColor: [
          '#00f5ff','#ff2fd1','#ffcc33','#3df58c','#ff5c70','#9a7dff','#4cc9f0','#f72585','#80ed99','#ffd166'
        ]
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } }
    }
  });
}

function renderEditGrid(data) {
  const fields = {
    renda_fixa: data.data.config.renda_fixa,
    receita_extra: data.data.config.receita_extra,
    lazer: data.data.limites.lazer,
    extras: data.data.limites.extras,
    cartao: data.data.limites.cartao,
    combustivel: data.data.limites.combustivel,
    iptu: data.data.categorias.iptu,
    luz: data.data.categorias.luz,
    internet: data.data.categorias.internet
  };
  const container = document.getElementById('editGrid');
  container.innerHTML = Object.entries(fields).map(([k,v]) => `
    <div class="edit-item">
      <label>${k}</label>
      <input id="edit_${k}" value="${v}">
      <button onclick="saveField('${k}')">Salvar</button>
    </div>
  `).join('');
}

async function saveField(field) {
  const value = document.getElementById(`edit_${field}`).value;
  await fetch('/api/update', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({field, value})
  });
  refreshAll();
}

async function createLaunch() {
  const descricao = document.getElementById('desc').value;
  const valor = document.getElementById('valor').value;
  await fetch('/api/launch', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({descricao, valor})
  });
  document.getElementById('desc').value='';
  document.getElementById('valor').value='';
  refreshAll();
}

function renderBills(upcoming) {
  const box = document.getElementById('contasBox');
  if (!upcoming.length) {
    box.innerHTML = 'Nenhuma conta em alerta agora.';
    return;
  }
  box.innerHTML = upcoming.map(c => `
    <div class="bill-line">
      <div>${c.nome} — ${money(c.valor)}</div>
      <div><span class="badge ${c.dias_uteis<=1?'red':'yellow'}">${c.dias_uteis} dias úteis</span>
      <button onclick="markPaid('${c.nome}')">Pagar</button></div>
    </div>
  `).join('');
}

async function markPaid(nome) {
  await fetch('/api/pay', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({nome})
  });
  refreshAll();
}

function renderCatBox(categoryTotals, limits) {
  const box = document.getElementById('catBox');
  const entries = Object.entries(categoryTotals);
  if (!entries.length) {
    box.innerHTML = 'Nenhum lançamento no mês atual.';
    return;
  }
  box.innerHTML = entries.map(([cat,val]) => {
    const limit = limits[cat];
    let extra = '';
    if (typeof limit === 'number') {
      const rest = limit - val;
      extra = rest >= 0 ? ` · Restante ${money(rest)}` : ` · Excesso ${money(Math.abs(rest))}`;
    }
    return `<div class="bill-line"><div>${cat}</div><div>${money(val)}${extra}</div></div>`;
  }).join('');
}

function renderMonthDetail(grouped) {
  const box = document.getElementById('monthDetail');
  const cats = Object.keys(grouped);
  if (!cats.length) {
    box.innerHTML = 'Sem lançamentos neste mês.';
    return;
  }
  box.innerHTML = cats.map(cat => {
    const total = grouped[cat].reduce((acc, item) => acc + item.valor, 0);
    const lines = grouped[cat].map(item => `
      <div class="detail-line">
        <div>${item.data} — ${item.descricao}</div>
        <div>${money(item.valor)}</div>
      </div>
    `).join('');
    return `<div class="detail-group"><div class="detail-title">${cat} — total ${money(total)}</div>${lines}</div>`;
  }).join('');
}

async function refreshAll() {
  const data = await fetchStatus();
  document.getElementById('receitaTotal').textContent = money(data.calc.receita_total);
  document.getElementById('saldo').textContent = money(data.calc.saldo);
  document.getElementById('divida').textContent = money(data.calc.divida_total);
  document.getElementById('metaDivida').textContent = money(data.calc.meta_mensal_divida);
  renderSemaforo(data.analysis.status, data.analysis.mensagens);
  renderCategoryChart(data.category_totals);
  renderEditGrid(data);
  renderBills(data.upcoming_bills);
  renderCatBox(data.category_totals, data.data.limites);
  renderMonthDetail(data.grouped);
}

refreshAll();
