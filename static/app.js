let categoryChart;
let monthlyChart;

const money = (value) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);

async function fetchDashboard() {
  const res = await fetch('/api/dashboard');
  const data = await res.json();
  renderDashboard(data);
}

function renderDashboard(data) {
  const dash = data.dashboard;
  document.getElementById('incomeKpi').innerText = money(dash.income);
  document.getElementById('baseKpi').innerText = money(dash.base_total);
  document.getElementById('actualKpi').innerText = money(dash.actual_total);
  document.getElementById('balanceKpi').innerText = money(dash.projected_balance);
  document.getElementById('saveKpi').innerText = money(data.reserve_target_month);

  const traffic = document.getElementById('trafficLight');
  traffic.innerText = dash.traffic;
  traffic.style.color = dash.traffic === 'verde' ? '#02160c' : '#1d1600';
  traffic.style.background = dash.traffic === 'verde' ? '#4ef0a4' : (dash.traffic === 'amarelo' ? '#ffd65c' : '#ff6b9a');

  document.getElementById('reserveBar').style.width = `${Math.min(dash.reserve_progress, 100)}%`;
  document.getElementById('reserveNow').innerText = `Atual: ${money(dash.reserve_saved)}`;
  document.getElementById('reserveGoal').innerText = `Meta: ${money(data.profile.meta_reserva)}`;
  document.getElementById('diagnosisText').innerText = data.analysis.diagnosis;

  const tips = document.getElementById('tipsList');
  tips.innerHTML = '';
  data.analysis.economy_tips.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t;
    tips.appendChild(li);
  });

  const alerts = document.getElementById('alertsList');
  alerts.innerHTML = '';
  (dash.alerts.length ? dash.alerts : ['Sem alertas críticos no momento.']).forEach(a => {
    const li = document.createElement('li');
    li.textContent = a;
    alerts.appendChild(li);
  });

  renderEditors('fixedEditor', data.fixed_costs, 'fixed');
  renderEditors('variableEditor', data.variable_limits, 'variable');
  renderBills(data.bills);
  renderCategoryChart(dash.by_category, data.variable_limits, data.fixed_costs);
  renderMonthlyChart(data.monthly_totals);
}

function renderEditors(containerId, source, section) {
  const root = document.getElementById(containerId);
  root.innerHTML = '';
  Object.entries(source).forEach(([key, value]) => {
    const row = document.createElement('div');
    row.className = 'editor-row';
    row.innerHTML = `
      <span>${key}</span>
      <input id="${section}_${key}" type="number" step="0.01" value="${value}" />
      <button class="small-btn" onclick="saveField('${section}','${key}')">Salvar</button>
    `;
    root.appendChild(row);
  });
}

function renderBills(bills) {
  const root = document.getElementById('billsList');
  root.innerHTML = '';
  bills.forEach(bill => {
    const row = document.createElement('div');
    row.className = 'bill-row';
    row.innerHTML = `<strong>${bill.name}</strong><span>dia ${bill.due_day} · ${money(bill.amount)}</span><span>${bill.paid ? 'paga' : 'aberta'}</span>`;
    root.appendChild(row);
  });
}

function renderCategoryChart(byCategory, limits, fixed) {
  const merged = { ...fixed, ...limits, ...byCategory };
  const labels = Object.keys(merged);
  const values = labels.map(label => byCategory[label] || fixed[label] || limits[label] || 0);
  if (categoryChart) categoryChart.destroy();
  categoryChart = new Chart(document.getElementById('categoryChart'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ['#41f0ff','#8d7bff','#4ef0a4','#ffd65c','#ff6b9a','#6ea8ff','#4fd1c5','#f59e0b','#d946ef','#22c55e','#94a3b8']
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { labels: { color: '#ebf6ff' } } }
    }
  });
}

function renderMonthlyChart(monthlyTotals) {
  const labels = monthlyTotals.map(i => i.month);
  const values = monthlyTotals.map(i => i.total);
  if (!labels.length) {
    labels.push(new Date().toISOString().slice(0, 7));
    values.push(0);
  }
  if (monthlyChart) monthlyChart.destroy();
  monthlyChart = new Chart(document.getElementById('monthlyChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Gastos lançados',
        data: values,
        borderColor: '#41f0ff',
        backgroundColor: 'rgba(65,240,255,.18)',
        fill: true,
        tension: .28
      }]
    },
    options: {
      responsive: true,
      scales: {
        x: { ticks: { color: '#93abc6' }, grid: { color: 'rgba(255,255,255,.05)' } },
        y: { ticks: { color: '#93abc6' }, grid: { color: 'rgba(255,255,255,.05)' } }
      },
      plugins: { legend: { labels: { color: '#ebf6ff' } } }
    }
  });
}

async function saveField(section, key) {
  const input = document.getElementById(`${section}_${key}`);
  await fetch('/api/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section, key, value: input.value })
  });
  fetchDashboard();
}

async function quickUpdate(section, inputId) {
  const input = document.getElementById(inputId);
  await fetch('/api/update', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ section, key: 'guardar', value: input.value })
  });
  fetchDashboard();
}

async function createTransaction() {
  const category = document.getElementById('txCategory').value;
  const amount = document.getElementById('txAmount').value;
  const description = document.getElementById('txDesc').value;
  await fetch('/api/transaction', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, amount, description })
  });
  document.getElementById('txAmount').value = '';
  document.getElementById('txDesc').value = '';
  fetchDashboard();
}

fetchDashboard();
