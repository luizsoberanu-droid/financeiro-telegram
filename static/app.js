
let catChart, cardChart;

function money(v){ return 'R$ ' + Number(v).toFixed(2); }

async function carregar(){
  const s = await fetch('/api/status').then(r=>r.json());

  document.getElementById('receitaTotal').innerText = money(s.receita_total);
  document.getElementById('gastosMes').innerText = money(s.gastos_mes);
  document.getElementById('saldoMes').innerText = money(s.saldo);
  document.getElementById('dividaTotal').innerText = money(s.divida_total);
  document.getElementById('analista').innerText = s.analista;

  const cp = document.getElementById('contasProximas');
  cp.innerHTML = '';
  if(!s.proximas_contas.length){
    cp.innerHTML = '<li>Nenhuma conta crítica nos próximos 3 dias úteis.</li>';
  } else {
    s.proximas_contas.forEach(c=>{
      const li = document.createElement('li');
      li.innerText = `${c.nome} — ${money(c.valor)} — ${c.dias_uteis} dia(s) útil(eis)`;
      cp.appendChild(li);
    });
  }

  // cards select
  const selects = [document.getElementById('cartao'), document.getElementById('pCartao')];
  selects.forEach(sel => sel.innerHTML = '<option value="">Selecione o cartão</option>');
  const tbodyCart = document.querySelector('#tblCartoes tbody');
  tbodyCart.innerHTML = '';
  s.cartoes.forEach(c=>{
    selects.forEach(sel=>{
      const opt = document.createElement('option');
      opt.value = c.nome; opt.innerText = c.nome;
      sel.appendChild(opt);
    });
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${c.nome}</td><td>${c.vencimento}</td><td>${c.melhor_dia_compra}</td><td>${c.pago ? 'pago':'aberto'}</td><td><button onclick="marcarPago('cartao','${c.nome}')">Pagar</button></td>`;
    tbodyCart.appendChild(tr);
  });

  const tbodyContas = document.querySelector('#tblContas tbody');
  tbodyContas.innerHTML = '';
  s.contas_fixas.forEach(c=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${c.nome}</td><td>${money(c.valor)}</td><td>${c.vencimento}</td><td>${c.pago ? 'paga':'aberta'}</td><td><button onclick="marcarPago('conta','${c.nome}')">Pagar</button></td>`;
    tbodyContas.appendChild(tr);
  });

  const tbodyLanc = document.querySelector('#tblLanc tbody');
  tbodyLanc.innerHTML = '';
  s.lancamentos.forEach(l=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${l.data}</td><td>${l.descricao}</td><td>${l.categoria}</td><td>${l.forma_pagamento}</td><td>${l.cartao || '-'}</td><td>${money(l.valor)}</td><td>${l.mes_ref}</td>`;
    tbodyLanc.appendChild(tr);
  });

  const tbodyParc = document.querySelector('#tblParcelas tbody');
  tbodyParc.innerHTML = '';
  s.parcelas.forEach(p=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${p.descricao}</td><td>${p.cartao}</td><td>${p.parcela_atual}/${p.total_parcelas}</td><td>${money(p.valor)}</td><td>${p.mes_ref}</td>`;
    tbodyParc.appendChild(tr);
  });

  // charts
  const catLabels = Object.keys(s.categorias);
  const catVals = Object.values(s.categorias);
  if(catChart) catChart.destroy();
  catChart = new Chart(document.getElementById('catChart'), {
    type: 'bar',
    data: {labels: catLabels, datasets:[{label:'Gastos por categoria', data: catVals}]},
    options: {plugins:{legend:{display:false}}, scales:{y:{beginAtZero:true}}}
  });

  const cardLabels = Object.keys(s.cartoes_mes);
  const cardVals = Object.values(s.cartoes_mes);
  if(cardChart) cardChart.destroy();
  cardChart = new Chart(document.getElementById('cardChart'), {
    type: 'doughnut',
    data: {labels: cardLabels, datasets:[{data: cardVals}]},
    options: {}
  });
}

async function salvarExtra(){
  const valor = parseFloat(document.getElementById('extraValor').value || 0);
  await fetch('/api/add_extra',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({valor})});
  carregar();
}

async function lancar(){
  const descricao = document.getElementById('desc').value;
  const valor = parseFloat(document.getElementById('val').value || 0);
  const forma_pagamento = document.getElementById('forma').value;
  const cartao = document.getElementById('cartao').value || null;
  await fetch('/api/lancar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descricao,valor,forma_pagamento,cartao})});
  carregar();
}

async function addConta(){
  const nome = document.getElementById('contaNome').value;
  const valor = parseFloat(document.getElementById('contaValor').value || 0);
  const vencimento = parseInt(document.getElementById('contaVenc').value || 1);
  const categoria = document.getElementById('contaCat').value;
  await fetch('/api/add_conta_fixa',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,valor,vencimento,categoria})});
  carregar();
}

async function addCartao(){
  const nome = document.getElementById('novoCartaoNome').value;
  const vencimento = parseInt(document.getElementById('novoCartaoVenc').value || 1);
  const melhor_dia_compra = parseInt(document.getElementById('novoCartaoMelhor').value || 1);
  await fetch('/api/add_cartao',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nome,vencimento,melhor_dia_compra})});
  carregar();
}

async function parcelar(){
  const descricao = document.getElementById('pDesc').value;
  const valor = parseFloat(document.getElementById('pValor').value || 0);
  const total_parcelas = parseInt(document.getElementById('pTotal').value || 1);
  const cartao = document.getElementById('pCartao').value;
  await fetch('/api/parcelar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({descricao,valor,total_parcelas,cartao})});
  carregar();
}

async function marcarPago(tipo, nome){
  await fetch('/api/marcar_pago',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tipo,nome})});
  carregar();
}

carregar();
