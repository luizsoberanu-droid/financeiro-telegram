import json
import math
import os
from copy import deepcopy
from datetime import date, datetime, timedelta
from flask import Flask, jsonify, render_template, request
import requests

app = Flask(__name__)

DATA_FILE = os.getenv('DATA_FILE', 'data_store.json')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'COLOQUE_SEU_TOKEN_AQUI')
PORT = int(os.getenv('PORT', os.getenv('APP_PORT', '5000')))

DEFAULT_DATA = {
    "config": {
        "modo": "ataque_rigido",
        "renda_fixa": 5300.0,
        "beneficio_alimentacao": 1361.0,
        "meta_reserva": 12000.0,
        "reserva_atual": 0.0,
        "meta_viagem_habilitada": False,
        "alerta_dias_uteis": 3,
        "prazo_divida_meses": 3,
        "lazer_limite": 100.0,
        "cartao_limite": 200.0,
        "extras_limite": 100.0,
        "receita_extra": 0.0
    },
    "categorias": {
        "casa": 732.92,
        "carro": 1469.70,
        "condominio": 365.0,
        "faculdade": 560.0,
        "luz": 270.0,
        "internet": 220.0,
        "combustivel": 320.0,
        "cachorro": 140.0,
        "assinaturas": 119.8,
        "manutencao": 100.0,
        "lazer": 0.0,
        "extras": 0.0,
        "cartao": 0.0,
        "iptu": 0.0
    },
    "limites": {
        "lazer": 100.0,
        "extras": 100.0,
        "cartao": 200.0,
        "combustivel": 320.0
    },
    "dividas": {
        "negativo": 2999.94,
        "ipva": 1161.0,
        "samsung": 134.0,
        "santander": 996.12,
        "nubank": 1006.05
    },
    "contas": [
        {"nome": "casa", "valor": 732.92, "vencimento": 10, "pago": False},
        {"nome": "carro", "valor": 1469.70, "vencimento": 15, "pago": False},
        {"nome": "condominio", "valor": 365.0, "vencimento": 7, "pago": False},
        {"nome": "faculdade_usuario", "valor": 360.0, "vencimento": 10, "pago": False},
        {"nome": "faculdade_esposa", "valor": 200.0, "vencimento": 10, "pago": False},
        {"nome": "internet", "valor": 220.0, "vencimento": 20, "pago": False},
        {"nome": "luz", "valor": 270.0, "vencimento": 25, "pago": False},
        {"nome": "ipva", "valor": 1161.0, "vencimento": 5, "pago": False},
        {"nome": "iptu", "valor": 0.0, "vencimento": 12, "pago": False}
    ],
    "lancamentos": []
}

ALIASES = {
    "lanche": "lazer",
    "passeio": "lazer",
    "cinema": "lazer",
    "sorvete": "lazer",
    "pizza": "lazer",
    "gasolina": "combustivel",
    "etanol": "combustivel",
    "moto": "combustivel",
    "carro": "combustivel",
    "netflix": "assinaturas",
    "amazon": "assinaturas",
    "prime": "assinaturas",
    "crunchyroll": "assinaturas",
    "fortnite": "assinaturas",
    "internet": "internet",
    "celular": "internet",
    "iptu": "iptu",
}


def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return deepcopy(DEFAULT_DATA)


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_float(v):
    if isinstance(v, (int, float)):
        return float(v)
    return float(str(v).replace('R$', '').replace('.', '').replace(',', '.').strip()) if ',' in str(v) and str(v).count(',')==1 and str(v).count('.')>=1 else float(str(v).replace('R$', '').replace(',', '.').strip())


def business_days_until_due(due_day, ref=None):
    ref = ref or date.today()
    year, month = ref.year, ref.month
    try:
        due = date(year, month, int(due_day))
    except ValueError:
        # handle short months
        if month == 12:
            due = date(year, month, 31)
        else:
            due = date(year, month + 1, 1) - timedelta(days=1)
    if due < ref:
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        try:
            due = date(year, month, int(due_day))
        except ValueError:
            if month == 12:
                due = date(year, month, 31)
            else:
                due = date(year, month + 1, 1) - timedelta(days=1)

    days = 0
    d = ref
    while d < due:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days, due.isoformat()


def month_key(dt=None):
    dt = dt or datetime.now()
    return dt.strftime('%Y-%m')


def ensure_month_reset(data):
    # marks all contas unpaid on first access of a new month if needed
    mk = month_key()
    if data.get('_last_month') != mk:
        for c in data['contas']:
            c['pago'] = False
        data['_last_month'] = mk
        save_data(data)


def monthly_launches(data, mk=None):
    mk = mk or month_key()
    return [x for x in data['lancamentos'] if x['mes'] == mk]


def sum_by_category(data, categoria, mk=None):
    return round(sum(x['valor'] for x in monthly_launches(data, mk) if x['categoria'] == categoria), 2)


def calc(data):
    ensure_month_reset(data)
    receita_total = round(data['config']['renda_fixa'] + data['config'].get('receita_extra', 0.0), 2)
    base_fixos = sum(v for k, v in data['categorias'].items() if k not in ['lazer', 'extras', 'cartao'])
    gasto_lazer = sum_by_category(data, 'lazer')
    gasto_extras = sum_by_category(data, 'extras')
    gasto_comb = sum_by_category(data, 'combustivel')
    gasto_cartao = max(data['categorias'].get('cartao', 0.0), sum_by_category(data, 'cartao'))
    base_variavel_editavel = 0.0
    total = round(base_fixos + base_variavel_editavel + gasto_lazer + gasto_extras + gasto_comb + gasto_cartao, 2)
    saldo = round(receita_total - total, 2)
    divida_total = round(sum(data['dividas'].values()), 2)
    meta_mensal_divida = round(divida_total / max(1, int(data['config'].get('prazo_divida_meses', 3))), 2)
    meta_reserva_sugerida = 0.0
    if divida_total <= 0:
        min_monthly = data['config']['meta_reserva'] / 15
        target_monthly = data['config']['meta_reserva'] / 12
        meta_reserva_sugerida = round(target_monthly if saldo >= target_monthly else min(target_monthly, max(min_monthly, saldo * 0.6 if saldo > 0 else 0)), 2)
    return {
        'receita_total': receita_total,
        'gasto_total': total,
        'saldo': saldo,
        'divida_total': divida_total,
        'meta_mensal_divida': meta_mensal_divida,
        'meta_reserva_sugerida': meta_reserva_sugerida,
        'gasto_lazer': gasto_lazer,
        'gasto_extras': gasto_extras,
        'gasto_combustivel': gasto_comb,
        'gasto_cartao': gasto_cartao,
    }


def analyse(data):
    c = calc(data)
    msgs = []
    status = 'verde'
    if c['divida_total'] > 0:
        if c['saldo'] < c['meta_mensal_divida']:
            msgs.append('Você não está gerando caixa suficiente para zerar a dívida no prazo de 3 meses.')
            status = 'vermelho'
        else:
            msgs.append('Você está dentro do plano de ataque para sair do negativo.')
            status = 'amarelo'
    if c['gasto_lazer'] > data['limites']['lazer']:
        exced = round(c['gasto_lazer'] - data['limites']['lazer'], 2)
        msgs.append(f'Lazer passou R$ {exced:.2f} do limite.')
        status = 'vermelho'
    if c['gasto_cartao'] > data['limites']['cartao']:
        exced = round(c['gasto_cartao'] - data['limites']['cartao'], 2)
        msgs.append(f'Cartão passou R$ {exced:.2f} do limite.')
        status = 'vermelho'
    if c['gasto_extras'] > data['limites']['extras']:
        exced = round(c['gasto_extras'] - data['limites']['extras'], 2)
        msgs.append(f'Extras passou R$ {exced:.2f} do limite.')
        status = 'vermelho'
    if not msgs:
        msgs.append('Sem alertas críticos no momento.')
    return {'status': status, 'mensagens': msgs}


def add_launch(data, descricao, valor, categoria=None, dt=None):
    categoria = categoria or ALIASES.get(descricao.lower(), descricao.lower())
    if categoria not in data['categorias']:
        categoria = 'extras'
    dt = dt or datetime.now()
    item = {
        'data': dt.strftime('%Y-%m-%d'),
        'mes': dt.strftime('%Y-%m'),
        'descricao': descricao.lower(),
        'valor': round(float(valor), 2),
        'categoria': categoria
    }
    data['lancamentos'].append(item)
    save_data(data)
    return item


def category_feedback(data, categoria):
    gasto = sum_by_category(data, categoria)
    limite = data['limites'].get(categoria)
    if limite is None:
        return f'Categoria {categoria}: gasto do mês R$ {gasto:.2f}.'
    restante = round(limite - gasto, 2)
    if restante < 0:
        return f'⚠️ {categoria.capitalize()}\nGasto no mês: R$ {gasto:.2f}\nLimite: R$ {limite:.2f}\nExcesso: R$ {abs(restante):.2f}'
    return f'✅ {categoria.capitalize()}\nGasto no mês: R$ {gasto:.2f}\nLimite: R$ {limite:.2f}\nRestante: R$ {restante:.2f}'


def upcoming_bills(data):
    alerts = []
    for conta in data['contas']:
        days, due_iso = business_days_until_due(conta['vencimento'])
        if not conta.get('pago', False) and days <= data['config']['alerta_dias_uteis']:
            alerts.append({**conta, 'dias_uteis': days, 'data_vencimento_iso': due_iso})
    alerts.sort(key=lambda x: x['dias_uteis'])
    return alerts


def mark_paid(data, nome):
    nome = nome.lower().strip()
    for conta in data['contas']:
        if conta['nome'].lower() == nome:
            conta['pago'] = True
            save_data(data)
            return True
    return False


def update_config_or_limit(data, campo, valor):
    campo = campo.lower().strip()
    if campo in data['config']:
        data['config'][campo] = valor
    elif campo in data['limites']:
        data['limites'][campo] = valor
    elif campo in data['categorias']:
        data['categorias'][campo] = valor
    else:
        return False
    save_data(data)
    return True


def plan_text(data):
    c = calc(data)
    a = analyse(data)
    prazo = data['config']['prazo_divida_meses']
    return (
        f"🔥 MODO ATAQUE RÍGIDO\n\n"
        f"Dívida total: R$ {c['divida_total']:.2f}\n"
        f"Meta mensal: R$ {c['meta_mensal_divida']:.2f}\n"
        f"Saldo livre estimado: R$ {c['saldo']:.2f}\n"
        f"Prazo alvo: {prazo} meses\n\n"
        f"Diagnóstico: {a['mensagens'][0]}"
    )


def status_text(data):
    c = calc(data)
    return (
        f"📊 STATUS\n\n"
        f"Receita total: R$ {c['receita_total']:.2f}\n"
        f"Gasto total: R$ {c['gasto_total']:.2f}\n"
        f"Saldo: R$ {c['saldo']:.2f}\n"
        f"Dívida total: R$ {c['divida_total']:.2f}\n"
        f"Meta mensal da dívida: R$ {c['meta_mensal_divida']:.2f}\n"
        f"Lazer: R$ {c['gasto_lazer']:.2f}/{data['limites']['lazer']:.2f}\n"
        f"Cartão: R$ {c['gasto_cartao']:.2f}/{data['limites']['cartao']:.2f}"
    )


def analysis_text(data):
    a = analyse(data)
    c = calc(data)
    base = [
        "📈 ANÁLISE",
        "",
        f"Receita total: R$ {c['receita_total']:.2f}",
        f"Gasto total: R$ {c['gasto_total']:.2f}",
        f"Saldo: R$ {c['saldo']:.2f}",
        f"Dívida total: R$ {c['divida_total']:.2f}",
        "",
    ]
    for m in a['mensagens']:
        base.append(f"- {m}")
    return '\n'.join(base)


def process_message(data, msg):
    raw = msg.strip()
    msg = raw.lower().strip()
    parts = msg.split()

    if msg.startswith('/status'):
        return status_text(data)
    if msg.startswith('/plano'):
        return plan_text(data)
    if msg.startswith('/analise'):
        return analysis_text(data)
    if msg.startswith('/contas') or msg.startswith('/vencimentos'):
        alerts = upcoming_bills(data)
        if not alerts:
            return '✅ Nenhuma conta próxima do vencimento dentro da janela de alerta.'
        lines = ['🔔 CONTAS PRÓXIMAS']
        for c in alerts:
            lines.append(f"{c['nome']} — R$ {c['valor']:.2f} — vence em {c['dias_uteis']} dias úteis")
        return '\n'.join(lines)
    if msg.startswith('/pagar '):
        nome = raw.split(' ', 1)[1]
        ok = mark_paid(data, nome)
        return f'✅ Conta {nome} marcada como paga.' if ok else '❌ Conta não encontrada.'
    if msg.startswith('/extra ') or msg.startswith('/receitaextra '):
        valor = parse_float(parts[1])
        data['config']['receita_extra'] += valor
        save_data(data)
        return f"💰 Receita extra adicionada: R$ {valor:.2f}\nReceita extra acumulada: R$ {data['config']['receita_extra']:.2f}"
    if msg.startswith('/editar '):
        if len(parts) < 3:
            return 'Uso: /editar campo valor'
        campo = parts[1]
        valor = parse_float(parts[2])
        ok = update_config_or_limit(data, campo, valor)
        return f'✏️ {campo} atualizado para R$ {valor:.2f}' if ok else '❌ Campo não encontrado.'
    if msg.startswith('/divida '):
        if len(parts) < 3:
            return 'Uso: /divida nome valor'
        nome = parts[1]
        valor = parse_float(parts[2])
        data['dividas'][nome] = valor
        save_data(data)
        return f'💣 Dívida {nome} atualizada para R$ {valor:.2f}'
    if msg.startswith('/posso '):
        if len(parts) < 3:
            return 'Uso: /posso valor categoria'
        valor = parse_float(parts[1])
        cat = ALIASES.get(parts[2], parts[2])
        gasto_atual = sum_by_category(data, cat)
        limite = data['limites'].get(cat)
        if limite is None:
            return 'Categoria sem limite configurado.'
        if gasto_atual + valor > limite:
            excesso = gasto_atual + valor - limite
            return f'❌ Não recomendado. Você estoura {cat} em R$ {excesso:.2f}.'
        restante = limite - (gasto_atual + valor)
        return f'⚠️ Pode, mas restará apenas R$ {restante:.2f} para {cat} neste mês.'

    # natural input: descricao valor
    if len(parts) >= 2:
        try:
            valor = parse_float(parts[-1])
            descricao = ' '.join(parts[:-1])
            categoria = ALIASES.get(parts[0], ALIASES.get(descricao, parts[0]))
            item = add_launch(data, descricao, valor, categoria)
            return f"{category_feedback(data, item['categoria'])}\n\nÚltimo lançamento: {item['descricao']} — R$ {item['valor']:.2f}"
        except Exception:
            pass

    return 'Comando não reconhecido. Use /status, /plano, /analise, /contas, /pagar, /extra, /editar ou envie algo como lanche 25.'


@app.route('/')
def home():
    return render_template('dashboard.html')


@app.route('/api/health')
def health():
    return jsonify({"ok": True, "service": "nexus-dark-v43"})


@app.route('/api/status')
def api_status():
    data = load_data()
    c = calc(data)
    a = analyse(data)
    current_month = month_key()
    launches = monthly_launches(data, current_month)
    grouped = {}
    for item in launches:
        grouped.setdefault(item['categoria'], []).append(item)
    cat_totals = {k: round(sum(x['valor'] for x in v), 2) for k, v in grouped.items()}
    upcoming = upcoming_bills(data)
    return jsonify({
        'calc': c,
        'analysis': a,
        'data': data,
        'month': current_month,
        'launches': launches,
        'grouped': grouped,
        'category_totals': cat_totals,
        'upcoming_bills': upcoming,
    })


@app.route('/api/update', methods=['POST'])
def api_update():
    data = load_data()
    payload = request.get_json(force=True)
    field = payload.get('field')
    value = parse_float(payload.get('value', 0))
    ok = update_config_or_limit(data, field, value)
    return jsonify({'ok': ok})


@app.route('/api/launch', methods=['POST'])
def api_launch():
    data = load_data()
    payload = request.get_json(force=True)
    item = add_launch(data, payload.get('descricao', 'extra'), parse_float(payload.get('valor', 0)), payload.get('categoria'))
    return jsonify({'ok': True, 'item': item})


@app.route('/api/pay', methods=['POST'])
def api_pay():
    data = load_data()
    payload = request.get_json(force=True)
    ok = mark_paid(data, payload.get('nome', ''))
    return jsonify({'ok': ok})


@app.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = load_data()
    payload = request.get_json(force=True, silent=True) or {}
    msg = payload.get('message', {})
    text = msg.get('text', '')
    chat_id = msg.get('chat', {}).get('id')
    if text and chat_id and TOKEN and TOKEN != 'COLOQUE_SEU_TOKEN_AQUI':
        response = process_message(data, text)
        try:
            requests.post(
                f'https://api.telegram.org/bot{TOKEN}/sendMessage',
                json={'chat_id': chat_id, 'text': response}, timeout=15
            )
        except Exception:
            pass
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
