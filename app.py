
from flask import Flask, request, jsonify, render_template
import os, json, requests
from datetime import datetime, date, timedelta

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "data_store.json")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

DEFAULT_DATA = {
    "config": {
        "receita_fixa": 5300.0,
        "receita_extra": 0.0,
        "meta_reserva": 12000.0,
        "reserva_atual": 0.0,
        "modo": "ataque_rigido",
        "dias_uteis_alerta": 3
    },
    "limits": {
        "lazer": 100.0,
        "cartao": 200.0,
        "extras": 100.0,
        "luz": 300.0,
        "assinaturas": 120.0,
        "combustivel_carro": 250.0,
        "combustivel_moto": 70.0
    },
    "fixed_accounts": [
        {"id":"casa","nome":"Casa","valor":732.92,"vencimento_dia":10,"categoria":"moradia","paga":False,"ativa":True},
        {"id":"carro","nome":"Carro","valor":1469.70,"vencimento_dia":5,"categoria":"financiamento","paga":False,"ativa":True},
        {"id":"condominio","nome":"Condomínio","valor":365.00,"vencimento_dia":12,"categoria":"moradia","paga":False,"ativa":True},
        {"id":"faculdade_usuario","nome":"Faculdade usuário","valor":360.00,"vencimento_dia":7,"categoria":"educacao","paga":False,"ativa":True},
        {"id":"faculdade_esposa","nome":"Faculdade esposa","valor":200.00,"vencimento_dia":7,"categoria":"educacao","paga":False,"ativa":True},
        {"id":"internet","nome":"Internet e redes móveis","valor":220.00,"vencimento_dia":15,"categoria":"servicos","paga":False,"ativa":True},
        {"id":"ipva","nome":"IPVA","valor":1161.00,"vencimento_dia":10,"categoria":"imposto","paga":False,"ativa":True}
    ],
    "cards": [
        {"id":"nubank","nome":"Nubank","fatura_atual":1006.05,"vencimento_dia":12,"limite_ideal":300.0,"paga":False,"ativa":True},
        {"id":"santander","nome":"Santander","fatura_atual":996.12,"vencimento_dia":18,"limite_ideal":300.0,"paga":False,"ativa":True},
        {"id":"samsung","nome":"Samsung","fatura_atual":134.00,"vencimento_dia":25,"limite_ideal":150.0,"paga":False,"ativa":True}
    ],
    "installments": [
        {"id":"parc_samsung_1","descricao":"Samsung","cartao_id":"samsung","valor_parcela":134.00,"parcela_atual":1,"total_parcelas":1,"vencimento_dia":25,"ativa":True}
    ],
    "debts": {
        "negativo": 2999.94,
        "ipva": 1161.0,
        "samsung": 134.0,
        "santander": 996.12,
        "nubank": 1006.05
    },
    "entries": []
}

SMART_MAP = {
    "lanche":"lazer", "passeio":"lazer", "cinema":"lazer", "sorvete":"lazer", "pizza":"lazer",
    "gasolina":"combustivel_carro", "etanol":"combustivel_carro",
    "moto":"combustivel_moto",
    "netflix":"assinaturas", "amazon":"assinaturas", "prime":"assinaturas", "crunchyroll":"assinaturas", "fortnite":"assinaturas",
    "cartao":"cartao", "nubank":"cartao", "santander":"cartao", "samsung":"cartao",
    "mercado":"extras", "farmacia":"extras", "remedio":"extras", "iptu":"extras",
    "luz":"luz"
}

def slug(txt):
    return ''.join(c.lower() if c.isalnum() else '_' for c in txt).strip('_') or f"id_{int(datetime.now().timestamp())}"

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # shallow merge lists if missing
    for k,v in DEFAULT_DATA.items():
        if k not in data:
            data[k] = v
    return data

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def month_key(dt=None):
    dt = dt or datetime.now()
    return dt.strftime('%Y-%m')

def parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except Exception:
        return date.today()

def business_days_until(target):
    today = date.today()
    if target < today:
        return -1
    d = today
    count = 0
    while d < target:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return count

def current_month_entries(data, ym=None):
    ym = ym or month_key()
    return [e for e in data.get('entries', []) if e.get('month') == ym]

def monthly_category_totals(data, ym=None):
    totals = {}
    for e in current_month_entries(data, ym):
        cat = e['category']
        totals[cat] = round(totals.get(cat, 0) + float(e['amount']), 2)
    return totals

def upcoming_accounts(data):
    out=[]
    today=date.today()
    for acc in data.get('fixed_accounts', []):
        if not acc.get('ativa', True):
            continue
        try:
            due = date(today.year, today.month, int(acc['vencimento_dia']))
        except Exception:
            continue
        bd = business_days_until(due)
        status = 'atrasada' if (due < today and not acc.get('paga')) else ('paga' if acc.get('paga') else 'aberta')
        out.append({**acc,'tipo':'conta','due_date':due.isoformat(),'business_days_until':bd,'status':status})
    return out

def upcoming_cards(data):
    out=[]
    today=date.today()
    for c in data.get('cards', []):
        if not c.get('ativa', True):
            continue
        try:
            due = date(today.year, today.month, int(c['vencimento_dia']))
        except Exception:
            continue
        bd = business_days_until(due)
        status = 'atrasada' if (due < today and not c.get('paga')) else ('paga' if c.get('paga') else 'aberta')
        out.append({**c,'tipo':'cartao','due_date':due.isoformat(),'business_days_until':bd,'status':status})
    return out

def due_alerts(data):
    alerts=[]
    dias = int(data['config'].get('dias_uteis_alerta', 3))
    for item in upcoming_accounts(data) + upcoming_cards(data):
        if item['status'] == 'paga':
            continue
        label = item['nome']
        if item['tipo'] == 'cartao':
            label = f"Cartão {label}"
        if item['status'] == 'atrasada':
            alerts.append(f"{label} está atrasado(a).")
        elif 0 <= item['business_days_until'] <= dias:
            alerts.append(f"{label} vence em {item['business_days_until']} dia(s) útil(eis).")
    return alerts

def calculate_summary(data, ym=None):
    ym = ym or month_key()
    receita_total = float(data['config']['receita_fixa']) + float(data['config'].get('receita_extra', 0))
    base_contas = round(sum(float(a['valor']) for a in data.get('fixed_accounts', []) if a.get('ativa', True)), 2)
    faturas = round(sum(float(c['fatura_atual']) for c in data.get('cards', []) if c.get('ativa', True) and not c.get('paga')), 2)
    category_totals = monthly_category_totals(data, ym)
    gasto_lancado = round(sum(category_totals.values()), 2)
    total_obrigacoes = round(base_contas + faturas + gasto_lancado, 2)
    saldo = round(receita_total - total_obrigacoes, 2)
    total_divida = round(sum(float(v) for v in data.get('debts', {}).values()), 2)
    meta_3m = round(total_divida / 3, 2) if total_divida > 0 else 0.0
    status = 'VERDE' if saldo >= meta_3m else ('AMARELO' if saldo > 0 else 'VERMELHO')
    return {
        'receita_total': receita_total,
        'base_contas': base_contas,
        'faturas_cartoes': faturas,
        'gasto_lancado': gasto_lancado,
        'saldo_projetado': saldo,
        'meta_ataque_mensal': meta_3m,
        'status': status,
        'category_totals': category_totals,
        'total_divida': total_divida
    }

def ai_analysis(data, ym=None):
    s = calculate_summary(data, ym)
    extras=[]
    for cat,total in s['category_totals'].items():
        lim = data.get('limits', {}).get(cat)
        if lim is not None and total > lim:
            extras.append((cat, round(total-lim, 2)))
    lines=[]
    lines.append(f"Receita total do mês: R$ {s['receita_total']:.2f}")
    lines.append(f"Base de contas fixas: R$ {s['base_contas']:.2f}")
    lines.append(f"Faturas de cartões abertas: R$ {s['faturas_cartoes']:.2f}")
    lines.append(f"Gastos lançados: R$ {s['gasto_lancado']:.2f}")
    lines.append(f"Saldo projetado: R$ {s['saldo_projetado']:.2f}")
    lines.append(f"Dívida total atual: R$ {s['total_divida']:.2f}")
    if s['saldo_projetado'] <= 0:
        lines.append("Situação: crítica. Você não está gerando caixa suficiente nem para segurar o mês.")
    elif s['saldo_projetado'] < s['meta_ataque_mensal']:
        falta = s['meta_ataque_mensal'] - s['saldo_projetado']
        lines.append(f"Situação: fora do plano de quitar em 3 meses. Falta gerar R$ {falta:.2f} neste mês.")
    else:
        lines.append("Situação: dentro do plano agressivo. Proteja o caixa e não crie novas dívidas.")
    if extras:
        lines.append("Categorias acima do limite:")
        for cat, exc in extras:
            lines.append(f"- {cat}: R$ {exc:.2f} acima")
    alerts = due_alerts(data)
    if alerts:
        lines.append("Alertas de vencimento:")
        for a in alerts[:5]:
            lines.append(f"- {a}")
    if data.get('cards'):
        abertas = [c for c in data['cards'] if c.get('ativa', True) and not c.get('paga')]
        if abertas:
            lines.append("Cartões exigindo atenção:")
            for c in abertas:
                lines.append(f"- {c['nome']}: R$ {float(c['fatura_atual']):.2f}, vence dia {c['vencimento_dia']}")
    lines.append("Ação prática do mês:")
    lines.append("- Priorize contas fixas e cartões antes de qualquer gasto variável")
    lines.append("- Mantenha lazer no mínimo")
    lines.append("- Evite novos parcelamentos")
    return "\n".join(lines)

def smart_category(desc):
    tokens = desc.lower().replace('/', ' ').replace('-', ' ').split()
    for t in tokens:
        if t in SMART_MAP:
            return SMART_MAP[t]
    return 'extras'

def add_entry(data, description, amount, date_str=None, category=None):
    amount=float(amount)
    d = parse_date(date_str) if date_str else date.today()
    cat = category or smart_category(description)
    eid = f"e{int(datetime.now().timestamp()*1000)}"
    entry = {'id':eid,'date':d.isoformat(),'month':d.strftime('%Y-%m'),'description':description,'category':cat,'amount':amount}
    data['entries'].append(entry)
    save_data(data)
    return entry

def telegram_send(text, chat_id=None):
    if not TOKEN:
        return
    cid = chat_id or CHAT_ID
    if not cid:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=15)
    except Exception:
        pass

def command_status(data):
    s = calculate_summary(data)
    return (
        f"📊 STATUS\n"
        f"Receita total: R$ {s['receita_total']:.2f}\n"
        f"Contas fixas: R$ {s['base_contas']:.2f}\n"
        f"Faturas de cartões: R$ {s['faturas_cartoes']:.2f}\n"
        f"Gastos lançados: R$ {s['gasto_lancado']:.2f}\n"
        f"Saldo projetado: R$ {s['saldo_projetado']:.2f}\n"
        f"Dívida total: R$ {s['total_divida']:.2f}\n"
        f"Meta ataque mensal: R$ {s['meta_ataque_mensal']:.2f}\n"
        f"Semáforo: {s['status']}"
    )

def command_plan(data):
    s = calculate_summary(data)
    if s['saldo_projetado'] >= s['meta_ataque_mensal']:
        msg='🟢 Dentro do plano.'
    else:
        falta = max(0, s['meta_ataque_mensal'] - max(0, s['saldo_projetado']))
        msg=f"🔴 Fora do plano. Falta gerar R$ {falta:.2f} de caixa neste mês."
    return f"🔥 PLANO\nDívida total: R$ {s['total_divida']:.2f}\nPrazo alvo: 3 meses\nMeta mensal: R$ {s['meta_ataque_mensal']:.2f}\n{msg}"

def command_accounts(data):
    lines=['📅 CONTAS FIXAS']
    for acc in upcoming_accounts(data):
        lines.append(f"{acc['nome']} — R$ {float(acc['valor']):.2f} — vence dia {acc['vencimento_dia']} — {acc['status']}")
    return '\n'.join(lines)

def command_cards(data):
    lines=['💳 CARTÕES']
    for c in upcoming_cards(data):
        lines.append(f"{c['nome']} — fatura R$ {float(c['fatura_atual']):.2f} — vence dia {c['vencimento_dia']} — {c['status']}")
    return '\n'.join(lines)

def command_installments(data):
    lines=['🧾 PARCELAS']
    for p in data.get('installments', []):
        if not p.get('ativa', True):
            continue
        restantes = max(0, int(p['total_parcelas']) - int(p['parcela_atual']))
        lines.append(f"{p['descricao']} — {p['parcela_atual']}/{p['total_parcelas']} — R$ {float(p['valor_parcela']):.2f} — restam {restantes}")
    return '\n'.join(lines)

def parse_message(data, text):
    txt = (text or '').strip()
    low = txt.lower().strip()
    cmd = low[1:] if low.startswith('/') else low

    if cmd in ('status',): return command_status(data)
    if cmd in ('plano',): return command_plan(data)
    if cmd in ('analise', 'análise'): return '🤖 ANÁLISE\n' + ai_analysis(data)
    if cmd in ('contas','vencimentos'): return command_accounts(data)
    if cmd in ('cartoes','cartões'): return command_cards(data)
    if cmd in ('parcelas','parcelados'): return command_installments(data)

    if cmd.startswith('extra ') or cmd.startswith('receitaextra '):
        parts = cmd.split()
        if len(parts) >= 2:
            val = float(parts[1].replace(',', '.'))
            data['config']['receita_extra'] = val
            save_data(data)
            s = calculate_summary(data)
            return f"💰 Receita extra atualizada para R$ {val:.2f}\nReceita total do mês: R$ {s['receita_total']:.2f}"

    if cmd.startswith('conta '):
        # conta academia 200 vence 10
        parts = cmd.split()
        if 'vence' in parts and len(parts) >= 4:
            vence_idx = parts.index('vence')
            try:
                valor = float(parts[vence_idx-1].replace(',', '.'))
                nome = ' '.join(parts[1:vence_idx-1])
                venc = int(parts[vence_idx+1])
                new = {"id": slug(nome), "nome": nome.title(), "valor": valor, "vencimento_dia": venc, "categoria": "manual", "paga": False, "ativa": True}
                data['fixed_accounts'].append(new)
                save_data(data)
                return f"✅ Conta criada: {new['nome']} — R$ {valor:.2f} — vence dia {venc}"
            except Exception:
                pass

    if cmd.startswith('cartao '):
        # cartao nubank 1000 vence 12
        parts = cmd.split()
        if 'vence' in parts and len(parts) >= 4:
            vence_idx = parts.index('vence')
            try:
                valor = float(parts[vence_idx-1].replace(',', '.'))
                nome = ' '.join(parts[1:vence_idx-1])
                venc = int(parts[vence_idx+1])
                new = {"id": slug(nome), "nome": nome.title(), "fatura_atual": valor, "vencimento_dia": venc, "limite_ideal": 300.0, "paga": False, "ativa": True}
                found = False
                for c in data['cards']:
                    if c['id'] == new['id']:
                        c.update(new)
                        found=True
                if not found:
                    data['cards'].append(new)
                save_data(data)
                return f"✅ Cartão atualizado: {new['nome']} — fatura R$ {valor:.2f} — vence dia {venc}"
            except Exception:
                pass

    if cmd.startswith('parcela '):
        # parcela samsung 134 3/10 tv vence 25
        parts = cmd.split()
        try:
            cartao = parts[1]
            valor = float(parts[2].replace(',', '.'))
            atual,total = parts[3].split('/')
            venc = 25
            desc_parts = parts[4:]
            if 'vence' in desc_parts:
                vi = desc_parts.index('vence')
                desc = ' '.join(desc_parts[:vi])
                venc = int(desc_parts[vi+1])
            else:
                desc = ' '.join(desc_parts) or cartao
            new = {"id": f"parc_{slug(desc)}_{int(datetime.now().timestamp())}", "descricao": desc.title(), "cartao_id": slug(cartao), "valor_parcela": valor, "parcela_atual": int(atual), "total_parcelas": int(total), "vencimento_dia": venc, "ativa": True}
            data['installments'].append(new)
            save_data(data)
            return f"✅ Parcela criada: {new['descricao']} — {atual}/{total} — R$ {valor:.2f}"
        except Exception:
            pass

    if cmd.startswith('editar '):
        parts = txt.replace('/', '', 1).split()
        if len(parts) >= 3:
            campo = parts[1].lower(); valor = float(parts[2].replace(',', '.'))
            if campo in data['limits']:
                data['limits'][campo] = valor; save_data(data)
                return f"✏️ Limite de {campo} atualizado para R$ {valor:.2f}"
            if campo == 'reserva':
                data['config']['reserva_atual'] = valor; save_data(data)
                return f"🛡️ Reserva atual atualizada para R$ {valor:.2f}"

    if cmd.startswith('pagar '):
        name = cmd.replace('pagar', '', 1).strip()
        for acc in data['fixed_accounts']:
            if name and name in acc['nome'].lower():
                acc['paga'] = True; save_data(data)
                return f"✅ Conta marcada como paga: {acc['nome']}"
        for c in data['cards']:
            if name and name in c['nome'].lower():
                c['paga'] = True; save_data(data)
                return f"✅ Cartão marcado como pago: {c['nome']}"
        return 'Conta ou cartão não encontrado.'

    if cmd.startswith('posso '):
        parts = cmd.split()
        if len(parts) >= 3:
            valor = float(parts[1].replace(',', '.')); categoria = smart_category(' '.join(parts[2:]))
            atual = monthly_category_totals(data).get(categoria, 0.0)
            limite = data['limits'].get(categoria)
            if limite is None: return f"ℹ️ Categoria {categoria} não tem limite cadastrado."
            novo_total = atual + valor
            if novo_total > limite:
                excesso = novo_total - limite
                return f"❌ Não recomendado. {categoria} iria para R$ {novo_total:.2f}, acima do limite de R$ {limite:.2f} por R$ {excesso:.2f}."
            restante = limite - novo_total
            return f"⚠️ Pode, mas {categoria} ficará em R$ {novo_total:.2f} de R$ {limite:.2f}. Restante: R$ {restante:.2f}."

    parts = txt.split()
    if len(parts) >= 2:
        try:
            amount = float(parts[-1].replace(',', '.'))
            desc = ' '.join(parts[:-1])
            e = add_entry(data, desc, amount)
            totals = monthly_category_totals(data)
            total_cat = totals.get(e['category'], 0.0)
            limite = data['limits'].get(e['category'])
            resp = [f"✅ Lançado: {e['description']} — R$ {e['amount']:.2f}", f"Categoria: {e['category']}", f"Total no mês: R$ {total_cat:.2f}"]
            if limite is not None:
                restante = limite - total_cat
                if restante >= 0: resp.append(f"Restante no limite: R$ {restante:.2f}")
                else: resp.append(f"🚨 Passou R$ {abs(restante):.2f} do limite.")
            return '\n'.join(resp)
        except Exception:
            pass
    return 'Comando não reconhecido.'

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'service': 'nexus-dark-v47'})

@app.route('/api/status')
def api_status():
    data = load_data()
    months={}
    for e in data.get('entries', []):
        months.setdefault(e['month'], []).append(e)
    return jsonify({
        'summary': calculate_summary(data),
        'config': data['config'],
        'limits': data['limits'],
        'debts': data['debts'],
        'accounts': upcoming_accounts(data),
        'cardsList': upcoming_cards(data),
        'installments': data.get('installments', []),
        'alerts': due_alerts(data),
        'analysis': ai_analysis(data),
        'entries': current_month_entries(data),
        'monthlyGroups': months
    })

@app.route('/api/entry', methods=['POST'])
def api_entry():
    data = load_data(); payload = request.get_json(force=True)
    entry = add_entry(data, payload.get('description',''), payload.get('amount',0), payload.get('date'), payload.get('category'))
    return jsonify({'ok': True, 'entry': entry})

@app.route('/api/entry/<entry_id>', methods=['PUT'])
def api_entry_edit(entry_id):
    data = load_data(); payload = request.get_json(force=True)
    for e in data.get('entries', []):
        if e['id'] == entry_id:
            e['description'] = payload.get('description', e['description'])
            e['category'] = payload.get('category', e['category'])
            e['amount'] = float(payload.get('amount', e['amount']))
            e['date'] = payload.get('date', e['date'])
            e['month'] = e['date'][:7]
            save_data(data)
            return jsonify({'ok': True, 'entry': e})
    return jsonify({'ok': False, 'error': 'not found'}), 404

@app.route('/api/account', methods=['POST'])
def api_account_add():
    data = load_data(); p = request.get_json(force=True)
    acc = {
        'id': slug(p.get('nome','conta')),
        'nome': p.get('nome','Conta'),
        'valor': float(p.get('valor',0)),
        'vencimento_dia': int(p.get('vencimento_dia',1)),
        'categoria': p.get('categoria','manual'),
        'paga': bool(p.get('paga',False)),
        'ativa': bool(p.get('ativa',True))
    }
    data['fixed_accounts'].append(acc); save_data(data)
    return jsonify({'ok': True, 'account': acc})

@app.route('/api/account/<acc_id>', methods=['PUT'])
def api_account_edit(acc_id):
    data = load_data(); p = request.get_json(force=True)
    for a in data.get('fixed_accounts', []):
        if a['id'] == acc_id:
            for key in ['nome','valor','vencimento_dia','categoria','paga','ativa']:
                if key in p: a[key] = p[key]
            save_data(data)
            return jsonify({'ok': True, 'account': a})
    return jsonify({'ok': False, 'error': 'not found'}), 404

@app.route('/api/card', methods=['POST'])
def api_card_add():
    data = load_data(); p = request.get_json(force=True)
    card = {
        'id': slug(p.get('nome','cartao')),
        'nome': p.get('nome','Cartão'),
        'fatura_atual': float(p.get('fatura_atual',0)),
        'vencimento_dia': int(p.get('vencimento_dia',1)),
        'limite_ideal': float(p.get('limite_ideal',300)),
        'paga': bool(p.get('paga',False)),
        'ativa': bool(p.get('ativa',True))
    }
    data['cards'].append(card); save_data(data)
    return jsonify({'ok': True, 'card': card})

@app.route('/api/card/<card_id>', methods=['PUT'])
def api_card_edit(card_id):
    data = load_data(); p = request.get_json(force=True)
    for c in data.get('cards', []):
        if c['id'] == card_id:
            for key in ['nome','fatura_atual','vencimento_dia','limite_ideal','paga','ativa']:
                if key in p: c[key] = p[key]
            save_data(data)
            return jsonify({'ok': True, 'card': c})
    return jsonify({'ok': False, 'error': 'not found'}), 404

@app.route('/api/installment', methods=['POST'])
def api_installment_add():
    data = load_data(); p = request.get_json(force=True)
    inst = {
        'id': f"inst_{int(datetime.now().timestamp()*1000)}",
        'descricao': p.get('descricao','Parcela'),
        'cartao_id': p.get('cartao_id',''),
        'valor_parcela': float(p.get('valor_parcela',0)),
        'parcela_atual': int(p.get('parcela_atual',1)),
        'total_parcelas': int(p.get('total_parcelas',1)),
        'vencimento_dia': int(p.get('vencimento_dia',1)),
        'ativa': bool(p.get('ativa',True))
    }
    data['installments'].append(inst); save_data(data)
    return jsonify({'ok': True, 'installment': inst})

@app.route('/api/installment/<inst_id>', methods=['PUT'])
def api_installment_edit(inst_id):
    data = load_data(); p = request.get_json(force=True)
    for inst in data.get('installments', []):
        if inst['id'] == inst_id:
            for key in ['descricao','cartao_id','valor_parcela','parcela_atual','total_parcelas','vencimento_dia','ativa']:
                if key in p: inst[key] = p[key]
            save_data(data)
            return jsonify({'ok': True, 'installment': inst})
    return jsonify({'ok': False, 'error': 'not found'}), 404

@app.route('/api/config', methods=['PUT'])
def api_config():
    data = load_data(); p = request.get_json(force=True)
    for sec in ['config','limits','debts']:
        if sec in p:
            for k,v in p[sec].items():
                data[sec][k] = v
    save_data(data)
    return jsonify({'ok': True})

@app.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = load_data(); payload = request.get_json(force=True)
    if 'message' not in payload:
        return jsonify({'ok': True})
    msg = payload['message'].get('text',''); chat_id = payload['message']['chat']['id']
    resp = parse_message(data, msg)
    telegram_send(resp, chat_id)
    return jsonify({'ok': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
