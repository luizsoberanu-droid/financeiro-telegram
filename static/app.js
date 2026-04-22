
let state = null;
let catChart = null;

function money(v){ return new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(Number(v||0)); }
async function api(path, opts={}){ const r = await fetch(path,{headers:{'Content-Type':'application/json'},...opts}); return r.json(); }
async function fetchStatus(){ state = await api('/api/status'); renderAll(); }

function renderCards(){
  const s=state.summary;
  const cards=[
    ['Receita total', money(s.receita_total)],
    ['Contas fixas', money(s.base_contas)],
    ['Faturas cartões', money(s.faturas_cartoes)],
    ['Gastos lançados', money(s.gasto_lancado)],
    ['Saldo projetado', money(s.saldo_projetado)],
    ['Meta 3 meses', money(s.meta_ataque_mensal)],
  ];
  document.getElementById('cards').innerHTML = cards.map(c=>`<div class="stat"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join('');
  const badge=document.getElementById('statusBadge'); badge.textContent=s.status; badge.className='badge '+(s.status==='VERDE'?'verde':(s.status==='AMARELO'?'amarelo':'vermelho'));
}

function renderChart(){
  const totals=state.summary.category_totals||{}; const labels=Object.keys(totals); const values=Object.values(totals);
  const ctx=document.getElementById('catChart'); if(catChart){catChart.destroy();}
  if(labels.length===0){ return; }
  catChart=new Chart(ctx,{type:'doughnut',data:{labels,datasets:[{data:values}]},options:{plugins:{legend:{display:false}},maintainAspectRatio:false}});
}
function renderAnalysis(){ document.getElementById('analysisText').textContent = state.analysis; }
function renderAlerts(){ document.getElementById('alertsList').innerHTML = (state.alerts||[]).map(a=>`<li>${a}</li>`).join('') || '<li>Sem alertas críticos no momento.</li>'; }

function renderAccounts(){
  const rows=(state.accounts||[]).map(a=>`<tr>
    <td><input value="${a.nome}" onchange="updateAccount('${a.id}','nome',this.value)"></td>
    <td><input type="number" step="0.01" value="${a.valor}" onchange="updateAccount('${a.id}','valor',this.value)"></td>
    <td><input type="number" value="${a.vencimento_dia}" onchange="updateAccount('${a.id}','vencimento_dia',this.value)"></td>
    <td>${a.status}</td>
    <td>${a.business_days_until>=0 ? a.business_days_until+' úteis':'atrasada'}</td>
    <td><div class='actions-inline'><button class="small-btn" onclick="markPaidAccount('${a.id}')">Paga</button><button class="small-btn alt" onclick="markOpenAccount('${a.id}')">Aberta</button></div></td>
  </tr>`).join('');
  document.getElementById('accountsTable').innerHTML = `<table class="table"><thead><tr><th>Conta</th><th>Valor</th><th>Venc.</th><th>Status</th><th>Prazo</th><th>Ação</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderCardsTable(){
  const rows=(state.cardsList||[]).map(c=>`<tr>
    <td><input value="${c.nome}" onchange="updateCard('${c.id}','nome',this.value)"></td>
    <td><input type="number" step="0.01" value="${c.fatura_atual}" onchange="updateCard('${c.id}','fatura_atual',this.value)"></td>
    <td><input type="number" value="${c.vencimento_dia}" onchange="updateCard('${c.id}','vencimento_dia',this.value)"></td>
    <td><input type="number" step="0.01" value="${c.limite_ideal}" onchange="updateCard('${c.id}','limite_ideal',this.value)"></td>
    <td>${c.status}</td>
    <td><div class='actions-inline'><button class="small-btn" onclick="markPaidCard('${c.id}')">Pago</button><button class="small-btn alt" onclick="markOpenCard('${c.id}')">Aberto</button></div></td>
  </tr>`).join('');
  document.getElementById('cardsTable').innerHTML = `<table class="table"><thead><tr><th>Cartão</th><th>Fatura</th><th>Venc.</th><th>Limite ideal</th><th>Status</th><th>Ação</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderInstallments(){
  const rows=(state.installments||[]).map(i=>`<tr>
    <td><input value="${i.descricao}" onchange="updateInstallment('${i.id}','descricao',this.value)"></td>
    <td><input value="${i.cartao_id}" onchange="updateInstallment('${i.id}','cartao_id',this.value)"></td>
    <td><input type="number" step="0.01" value="${i.valor_parcela}" onchange="updateInstallment('${i.id}','valor_parcela',this.value)"></td>
    <td><input type="number" value="${i.parcela_atual}" onchange="updateInstallment('${i.id}','parcela_atual',this.value)"></td>
    <td><input type="number" value="${i.total_parcelas}" onchange="updateInstallment('${i.id}','total_parcelas',this.value)"></td>
    <td><input type="number" value="${i.vencimento_dia}" onchange="updateInstallment('${i.id}','vencimento_dia',this.value)"></td>
  </tr>`).join('');
  document.getElementById('installmentsTable').innerHTML = `<table class="table"><thead><tr><th>Descrição</th><th>Cartão</th><th>Valor</th><th>Atual</th><th>Total</th><th>Venc.</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderEntries(){
  const entries=[...(state.entries||[])].sort((a,b)=>a.date.localeCompare(b.date));
  const rows=entries.map(e=>`<tr>
    <td><input type="date" value="${e.date}" onchange="editEntry('${e.id}','date',this.value)"></td>
    <td><input value="${e.description}" onchange="editEntry('${e.id}','description',this.value)"></td>
    <td><input value="${e.category}" onchange="editEntry('${e.id}','category',this.value)"></td>
    <td><input type="number" step="0.01" value="${e.amount}" onchange="editEntry('${e.id}','amount',this.value)"></td>
  </tr>`).join('');
  document.getElementById('entriesTable').innerHTML=`<table class="table"><thead><tr><th>Data</th><th>Descrição</th><th>Categoria</th><th>Valor</th></tr></thead><tbody>${rows}</tbody></table>`;
}

function renderMonths(){
  const box=document.getElementById('monthsBox');
  const groups=state.monthlyGroups||{};
  const months=Object.keys(groups).sort().reverse();
  box.innerHTML = months.map(m=>{
    const items=groups[m];
    const total=items.reduce((s,e)=>s+Number(e.amount||0),0);
    return `<div class="month-box"><div class="month-title">${m} — ${money(total)}</div>${items.map(e=>`<div>${e.date} — ${e.description} — ${e.category} — ${money(e.amount)}</div>`).join('')}</div>`;
  }).join('') || '<div class="muted">Sem histórico ainda.</div>';
}

function fillForms(){
  document.getElementById('receitaExtra').value = state.config.receita_extra || 0;
  document.getElementById('metaReserva').value = state.config.meta_reserva || 12000;
  document.getElementById('limiteLazer').value = state.limits.lazer || 100;
  document.getElementById('limiteCartao').value = state.limits.cartao || 200;
}

function renderAll(){ renderCards(); renderChart(); renderAnalysis(); renderAlerts(); renderAccounts(); renderCardsTable(); renderInstallments(); renderEntries(); renderMonths(); fillForms(); }

async function saveConfig(){
  await api('/api/config',{method:'PUT',body:JSON.stringify({config:{receita_extra:Number(receitaExtra.value||0), meta_reserva:Number(metaReserva.value||12000)}})});
  fetchStatus();
}
async function saveLimits(){
  await api('/api/config',{method:'PUT',body:JSON.stringify({limits:{lazer:Number(limiteLazer.value||100), cartao:Number(limiteCartao.value||200)}})});
  fetchStatus();
}
async function addEntry(){
  await api('/api/entry',{method:'POST',body:JSON.stringify({description:desc.value, amount:Number(valor.value||0), date:dataLanc.value||undefined})});
  desc.value=''; valor.value=''; fetchStatus();
}
async function editEntry(id,field,value){ const p={}; p[field]= field==='amount' ? Number(value) : value; await api('/api/entry/'+id,{method:'PUT',body:JSON.stringify(p)}); fetchStatus(); }
async function updateAccount(id,field,value){ const p={}; p[field]= ['valor','vencimento_dia'].includes(field) ? Number(value) : value; await api('/api/account/'+id,{method:'PUT',body:JSON.stringify(p)}); fetchStatus(); }
async function markPaidAccount(id){ await api('/api/account/'+id,{method:'PUT',body:JSON.stringify({paga:true})}); fetchStatus(); }
async function addAccount(){ await api('/api/account',{method:'POST',body:JSON.stringify({nome:newAccNome.value, valor:Number(newAccValor.value||0), vencimento_dia:Number(newAccVenc.value||1)})}); newAccNome.value=''; newAccValor.value=''; newAccVenc.value=''; fetchStatus(); }
async function updateCard(id,field,value){ const p={}; p[field]= ['fatura_atual','vencimento_dia','limite_ideal'].includes(field) ? Number(value) : value; await api('/api/card/'+id,{method:'PUT',body:JSON.stringify(p)}); fetchStatus(); }
async function markPaidCard(id){ await api('/api/card/'+id,{method:'PUT',body:JSON.stringify({paga:true})}); fetchStatus(); }
async function addCard(){ await api('/api/card',{method:'POST',body:JSON.stringify({nome:newCardNome.value, fatura_atual:Number(newCardValor.value||0), vencimento_dia:Number(newCardVenc.value||1)})}); newCardNome.value=''; newCardValor.value=''; newCardVenc.value=''; fetchStatus(); }
async function updateInstallment(id,field,value){ const p={}; p[field]= ['valor_parcela','parcela_atual','total_parcelas','vencimento_dia'].includes(field) ? Number(value) : value; await api('/api/installment/'+id,{method:'PUT',body:JSON.stringify(p)}); fetchStatus(); }
async function addInstallment(){
  const pt=(newInstAtual.value||'1/1').split('/');
  await api('/api/installment',{method:'POST',body:JSON.stringify({descricao:newInstDesc.value, cartao_id:newInstCard.value, valor_parcela:Number(newInstValor.value||0), parcela_atual:Number(pt[0]||1), total_parcelas:Number(pt[1]||1), vencimento_dia:25})});
  newInstDesc.value=''; newInstCard.value=''; newInstValor.value=''; newInstAtual.value=''; fetchStatus();
}

document.addEventListener('DOMContentLoaded', fetchStatus);

async function markOpenAccount(id){ await api('/api/account/'+id,{method:'PUT',body:JSON.stringify({paga:false})}); fetchStatus(); }
async function markOpenCard(id){ await api('/api/card/'+id,{method:'PUT',body:JSON.stringify({paga:false})}); fetchStatus(); }
