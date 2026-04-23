let catChart, cardChart;
async function getData(){ return await fetch('/api/data').then(r=>r.json()); }
async function getStatus(){ return await fetch('/api/status').then(r=>r.json()); }
async function loadAll(){
  const data = await getData();
  const s = await getStatus();
  document.getElementById('receita').innerText='R$ '+s.receita_total.toFixed(2);
  document.getElementById('contas').innerText='R$ '+s.contas_abertas.toFixed(2);
  document.getElementById('saldo').innerText='R$ '+s.saldo.toFixed(2);
  document.getElementById('divida').innerText='R$ '+s.divida_total.toFixed(2);
  document.getElementById('reserva').innerText='R$ '+s.reserva_atual.toFixed(2)+' / R$ '+s.reserva_meta.toFixed(2);
  document.getElementById('modo').innerText=s.modo;
  document.getElementById('extra_valor').value = data.receita_extra || 0;
  document.getElementById('reserva_atual').value = data.reserva_atual || 0;
  document.getElementById('reserva_meta').value = data.reserva_meta || 12000;
  fillCards(data.cartoes);
  fillContas(data.contas);
  fillParcelas(data.parcelas);
  fillLancamentos(s.lancamentos);
  fillAnalise(s);
  drawCharts(s);
}
function fillCards(cards){
  const tbody = document.querySelector('#cartoes_table tbody');
  const select1 = document.getElementById('cartao_select');
  const select2 = document.getElementById('p_cartao');
  tbody.innerHTML=''; select1.innerHTML='<option value="">Selecione o cartão</option>'; select2.innerHTML='<option value="">Selecione o cartão</option>';
  cards.forEach(c=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${c.nome}</td><td>${c.vencimento}</td><td>${c.melhor_dia_compra}</td><td>-</td>`;
    tbody.appendChild(tr);
    [select1,select2].forEach(sel=>{ const o=document.createElement('option'); o.value=c.nome; o.innerText=c.nome; sel.appendChild(o);});
  });
}
function fillContas(contas){
  const tbody=document.querySelector('#contas_table tbody'); tbody.innerHTML='';
  contas.forEach(c=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${c.nome}</td><td>R$ ${Number(c.valor).toFixed(2)}</td><td>${c.vencimento}</td><td>${c.categoria||''}</td><td class="${c.pago?'status-paid':'status-open'}">${c.pago?'paga':'aberta'}</td><td><button onclick="toggleConta(${c.id})">${c.pago?'Reabrir':'Marcar paga'}</button></td>`;
    tbody.appendChild(tr);
  });
}
function fillParcelas(parcelas){
  const tbody=document.querySelector('#parcelas_table tbody'); tbody.innerHTML='';
  parcelas.forEach(p=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${p.descricao}</td><td>${p.cartao}</td><td>${p.parcela_atual}/${p.total_parcelas}</td><td>R$ ${Number(p.valor).toFixed(2)}</td><td>${p.mes_ref}</td>`;
    tbody.appendChild(tr);
  });
}
function fillLancamentos(lanc){
  const tbody=document.querySelector('#lanc_table tbody'); tbody.innerHTML='';
  lanc.forEach(l=>{
    const tr=document.createElement('tr');
    tr.innerHTML=`<td>${l.data}</td><td>${l.descricao}</td><td>${l.categoria}</td><td>R$ ${Number(l.valor).toFixed(2)}</td><td>${l.forma_pagamento}</td><td>${l.cartao||''}</td>`;
    tbody.appendChild(tr);
  });
}
function fillAnalise(s){
  let lines = [`Mês: ${s.mes}`,`Receita total: R$ ${s.receita_total.toFixed(2)}`,`Contas abertas: R$ ${s.contas_abertas.toFixed(2)}`,`Gastos do mês: R$ ${s.gastos_mes.toFixed(2)}`,`Saldo projetado: R$ ${s.saldo.toFixed(2)}`,`Dívida total: R$ ${s.divida_total.toFixed(2)}`,`Reserva atual: R$ ${s.reserva_atual.toFixed(2)}`];
  if (s.excedentes.length){ lines.push('', 'Excedentes:'); s.excedentes.forEach(e=>lines.push(`- ${e.categoria}: +R$ ${e.excesso.toFixed(2)}`)); }
  if (Object.keys(s.cartoes).length){ lines.push('', 'Cartões/faturas:'); Object.entries(s.cartoes).forEach(([k,v])=>lines.push(`- ${k}: R$ ${Number(v).toFixed(2)}`)); }
  document.getElementById('analise').innerText = lines.join('\n');
}
function drawCharts(s){
  const catLabels=Object.keys(s.categorias), catValues=Object.values(s.categorias);
  const cardLabels=Object.keys(s.cartoes), cardValues=Object.values(s.cartoes);
  if(catChart) catChart.destroy(); if(cardChart) cardChart.destroy();
  catChart = new Chart(document.getElementById('catChart'), {type:'bar', data:{labels:catLabels,datasets:[{label:'Gastos por categoria', data:catValues}]}, options:{responsive:true, plugins:{legend:{display:false}}}});
  cardChart = new Chart(document.getElementById('cardChart'), {type:'doughnut', data:{labels:cardLabels,datasets:[{label:'Faturas', data:cardValues}]}, options:{responsive:true}});
}
async function salvarExtra(){ await fetch('/api/set_extra',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({valor:document.getElementById('extra_valor').value})}); loadAll(); }
async function salvarReserva(){ await fetch('/api/set_reserva',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({atual:document.getElementById('reserva_atual').value, meta:document.getElementById('reserva_meta').value})}); loadAll(); }
async function addConta(){ await fetch('/api/add_conta',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:document.getElementById('conta_nome').value,valor:document.getElementById('conta_valor').value,vencimento:document.getElementById('conta_vencimento').value,categoria:document.getElementById('conta_categoria').value})}); loadAll(); }
async function addCartao(){ await fetch('/api/add_cartao',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome:document.getElementById('cartao_nome').value,vencimento:document.getElementById('cartao_vencimento').value,melhor_dia_compra:document.getElementById('cartao_melhor').value})}); loadAll(); }
async function lancar(){ await fetch('/api/lancar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descricao:document.getElementById('descricao').value,valor:document.getElementById('valor').value,forma_pagamento:document.getElementById('forma').value,cartao:document.getElementById('cartao_select').value||null})}); loadAll(); }
async function parcelar(){ await fetch('/api/parcelar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descricao:document.getElementById('p_desc').value,valor:document.getElementById('p_valor').value,total_parcelas:document.getElementById('p_total').value,cartao:document.getElementById('p_cartao').value})}); loadAll(); }
async function toggleConta(id){ await fetch('/api/toggle_conta/'+id,{method:'POST'}); loadAll(); }
loadAll();
