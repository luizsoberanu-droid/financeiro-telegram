
let state = null;
let catChart = null;

function money(v){
  return new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v||0));
}
async function fetchStatus(){
  const res = await fetch('/api/status');
  state = await res.json();
  renderAll();
}
function renderCards(){
  const s = state.summary;
  const cards = [
    ['Receita total', money(s.receita_total)],
    ['Base de contas', money(s.base_contas)],
    ['Gasto lançado', money(s.gasto_lancado)],
    ['Saldo projetado', money(s.saldo_projetado)],
    ['Meta 3 meses', money(s.meta_ataque_mensal)]
  ];
  document.getElementById('cards').innerHTML = cards.map(c=>`
    <div class="stat">
      <div class="label">${c[0]}</div>
      <div class="value">${c[1]}</div>
    </div>
  `).join('');
  const badge = document.getElementById('statusBadge');
  badge.textContent = s.status;
  badge.className = 'badge ' + (s.status==='VERDE'?'verde':(s.status==='AMARELO'?'amarelo':'vermelho'));
}
function renderChart(){
  const totals = state.summary.category_totals || {};
  const labels = Object.keys(totals);
  const values = Object.values(totals);
  const ctx = document.getElementById('catChart');
  if(catChart){catChart.destroy();}
  if(labels.length === 0){ return; }
  catChart = new Chart(ctx,{
    type:'doughnut',
    data:{
      labels,
      datasets:[{
        data:values,
        borderWidth:1
      }]
    },
    options:{
      plugins:{legend:{position:'bottom', labels:{color:'#cfe7ff', boxWidth:14}}},
      maintainAspectRatio:false
    }
  });
}
function renderAnalysis(){
  document.getElementById('analysisText').textContent = state.analysis;
}
function renderAccounts(){
  const rows = state.accounts.map(a=>`
    <tr>
      <td><input value="${a.nome}" onchange="updateAccount('${a.id}','nome',this.value)"></td>
      <td><input type="number" step="0.01" value="${a.valor}" onchange="updateAccount('${a.id}','valor',this.value)"></td>
      <td><input type="number" value="${a.vencimento_dia}" onchange="updateAccount('${a.id}','vencimento_dia',this.value)"></td>
      <td>${a.status}</td>
      <td>${a.business_days_until>=0 ? a.business_days_until + ' úteis' : 'atrasada'}</td>
      <td><button class="small-btn" onclick="markPaid('${a.id}')">Marcar paga</button></td>
    </tr>
  `).join('');
  document.getElementById('accountsTable').innerHTML = `
    <table class="table">
      <thead><tr><th>Conta</th><th>Valor</th><th>Venc.</th><th>Status</th><th>Prazo</th><th>Ação</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}
function renderAlerts(){
  document.getElementById('alertsList').innerHTML = (state.alerts||[]).map(a=>`<li>${a}</li>`).join('') || '<li>Sem alertas críticos no momento.</li>';
}
function renderEntries(){
  const entries = [...(state.entries||[])].sort((a,b)=> a.date.localeCompare(b.date));
  const rows = entries.map(e=>`
    <tr>
      <td><input type="date" value="${e.date}" onchange="editEntry('${e.id}','date',this.value)"></td>
      <td><input value="${e.description}" onchange="editEntry('${e.id}','description',this.value)"></td>
      <td><input value="${e.category}" onchange="editEntry('${e.id}','category',this.value)"></td>
      <td><input type="number" step="0.01" value="${e.amount}" onchange="editEntry('${e.id}','amount',this.value)"></td>
    </tr>
  `).join('');
  document.getElementById('entriesTable').innerHTML = `
    <table class="table">
      <thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Valor</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}
function renderMonths(){
  const groups = state.monthlyGroups || {};
  const html = Object.keys(groups).sort().reverse().map(month=>{
    const items = groups[month].sort((a,b)=>a.date.localeCompare(b.date));
    const byCat = {};
    items.forEach(i=> byCat[i.category] = (byCat[i.category]||0)+Number(i.amount));
    const top = Object.entries(byCat).map(([k,v])=>`<div>${k}: ${money(v)}</div>`).join('');
    const list = items.map(i=>`<div>${i.date} — ${i.description} — ${money(i.amount)}</div>`).join('');
    return `<div class="month-box"><div class="month-title">${month}</div>${top}<hr style="border-color:rgba(34,211,238,.08)">${list}</div>`;
  }).join('');
  document.getElementById('monthlyHistory').innerHTML = html || '<div class="muted">Sem histórico ainda.</div>';
}
function fillEditable(){
  document.getElementById('receitaExtra').value = state.config.receita_extra || 0;
  document.getElementById('metaReserva').value = state.config.meta_reserva || 12000;
  document.getElementById('limiteLazer').value = state.limits.lazer || 100;
  document.getElementById('limiteCartao').value = state.limits.cartao || 200;
  document.getElementById('dataLanc').value = new Date().toISOString().slice(0,10);
}
function renderAll(){
  renderCards();
  renderChart();
  renderAnalysis();
  renderAccounts();
  renderAlerts();
  renderEntries();
  renderMonths();
  fillEditable();
}
async function saveConfig(){
  await fetch('/api/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    config:{
      receita_extra:Number(document.getElementById('receitaExtra').value||0),
      meta_reserva:Number(document.getElementById('metaReserva').value||12000)
    }
  })});
  fetchStatus();
}
async function saveLimits(){
  await fetch('/api/config',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    limits:{
      lazer:Number(document.getElementById('limiteLazer').value||100),
      cartao:Number(document.getElementById('limiteCartao').value||200)
    }
  })});
  fetchStatus();
}
async function addEntry(){
  await fetch('/api/entry',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    description: document.getElementById('desc').value,
    amount: Number(document.getElementById('valor').value||0),
    date: document.getElementById('dataLanc').value
  })});
  document.getElementById('desc').value='';
  document.getElementById('valor').value='';
  fetchStatus();
}
let editBuffer = {};
async function editEntry(id, field, value){
  editBuffer[id] = editBuffer[id] || {};
  editBuffer[id][field] = (field==='amount') ? Number(value) : value;
  await fetch('/api/entry/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(editBuffer[id])});
  fetchStatus();
}
async function updateAccount(id, field, value){
  let payload = {};
  payload[field] = (field==='valor' || field==='vencimento_dia') ? Number(value) : value;
  await fetch('/api/account/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  fetchStatus();
}
async function markPaid(id){
  await fetch('/api/account/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({paga:true})});
  fetchStatus();
}
fetchStatus();
