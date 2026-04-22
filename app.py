import json
import os
from datetime import datetime, date
from pathlib import Path
from flask import Flask, jsonify, render_template, request
import requests

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / 'data_store.json'

app = Flask(__name__)

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
DEFAULT_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

DEFAULT_DATA = {
    'profile': {
        'nome': 'NEXUS DARK V4',
        'renda_liquida': 5300.0,
        'beneficio_alimentacao': 1361.0,
        'meta_reserva': 12000.0,
        'reserva_atual': 0.0,
        'sugestao_guardar_inicial': 300.0,
        'prioridade': 'controlar_gastos'
    },
    'fixed_costs': {
        'casa': 732.92,
        'carro': 1469.70,
        'condominio': 365.0,
        'faculdade_usuario': 360.0,
        'faculdade_esposa': 200.0,
        'internet_redes_moveis': 220.0,
    },
    'variable_limits': {
        'luz': 300.0,
        'combustivel_carro': 250.0,
        'combustivel_moto': 70.0,
        'cachorro': 140.0,
        'assinaturas': 119.80,
        'manutencao_veiculos': 100.0,
        'cartao': 0.0,
        'extras': 0.0,
        'lazer': 0.0,
    },
    'categories': {
        'combustivel_carro': 'Combustível Carro',
        'combustivel_moto': 'Combustível Moto',
        'cartao': 'Cartão',
        'luz': 'Luz',
        'cachorro': 'Cachorro',
        'assinaturas': 'Assinaturas',
        'manutencao_veiculos': 'Manutenção Veículos',
        'extras': 'Extras',
        'lazer': 'Lazer',
        'guardar': 'Reserva',
    },
    'bills': [
        {'name': 'Casa', 'amount': 732.92, 'due_day': 10, 'active': True, 'paid': False},
        {'name': 'Carro', 'amount': 1469.70, 'due_day': 15, 'active': True, 'paid': False},
        {'name': 'Condomínio', 'amount': 365.0, 'due_day': 8, 'active': True, 'paid': False},
        {'name': 'Faculdade Usuário', 'amount': 360.0, 'due_day': 5, 'active': True, 'paid': False},
        {'name': 'Faculdade Esposa', 'amount': 200.0, 'due_day': 5, 'active': True, 'paid': False},
        {'name': 'Internet e Redes Móveis', 'amount': 220.0, 'due_day': 12, 'active': True, 'paid': False},
    ],
    'transactions': [],
    'monthly_saved_goal_override': None,
}


def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    save_data(DEFAULT_DATA)
    return json.loads(json.dumps(DEFAULT_DATA))


def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def current_month_key():
    now = datetime.now()
    return f'{now.year:04d}-{now.month:02d}'


def normalize_key(text):
    return (
        text.strip().lower()
        .replace('á', 'a').replace('à', 'a').replace('ã', 'a').replace('â', 'a')
        .replace('é', 'e').replace('ê', 'e').replace('í', 'i')
        .replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u')
        .replace('ç', 'c').replace(' ', '_')
    )


def month_transactions(data, month=None):
    month = month or current_month_key()
    return [t for t in data['transactions'] if t.get('month') == month]


def totals_by_category(data, month=None):
    results = {}
    for t in month_transactions(data, month):
        cat = t['category']
        results[cat] = results.get(cat, 0.0) + float(t['amount'])
    return results


def active_bills_total(data):
    return round(sum(float(b['amount']) for b in data['bills'] if b.get('active', True)), 2)


def fixed_costs_total(data):
    return round(sum(float(v) for v in data['fixed_costs'].values()), 2)


def variable_limits_total(data):
    return round(sum(float(v) for v in data['variable_limits'].values()), 2)


def monthly_actual_total(data):
    return round(sum(float(t['amount']) for t in month_transactions(data)), 2)


def reserve_target_for_month(data):
    c = compute_dashboard(data)
    if data.get('monthly_saved_goal_override') is not None:
        return float(data['monthly_saved_goal_override'])
    if c['free_after_base'] >= 900:
        return 500.0
    if c['free_after_base'] >= 650:
        return 400.0
    if c['free_after_base'] >= 450:
        return 300.0
    if c['free_after_base'] >= 250:
        return 200.0
    return 100.0


def monthly_saved_so_far(data):
    return round(sum(float(t['amount']) for t in month_transactions(data) if t['category'] == 'guardar'), 2)


def compute_dashboard(data):
    income = float(data['profile']['renda_liquida'])
    fixed_total = fixed_costs_total(data)
    base_variable_total = variable_limits_total(data)
    month_total_by_cat = totals_by_category(data)
    actual_total = monthly_actual_total(data)
    reserve_saved = float(data['profile'].get('reserva_atual', 0))
    base_cost_without_optional_savings = fixed_total + base_variable_total
    free_after_base = round(income - base_cost_without_optional_savings, 2)
    reserve_suggestion = data.get('monthly_saved_goal_override') or data['profile'].get('sugestao_guardar_inicial', 300.0)
    reserve_suggestion = float(reserve_suggestion)

    today = date.today().day
    month_progress = min(max(today / 30.0, 0.05), 1)
    projected_total = round(actual_total / month_progress, 2) if actual_total > 0 else base_cost_without_optional_savings
    projected_balance = round(income - projected_total, 2)

    reserve_progress = 0.0
    meta_reserva = float(data['profile']['meta_reserva'])
    if meta_reserva > 0:
        reserve_progress = round((reserve_saved / meta_reserva) * 100, 1)

    if projected_balance >= reserve_suggestion and free_after_base > 0:
        traffic = 'verde'
    elif projected_balance >= 0:
        traffic = 'amarelo'
    else:
        traffic = 'vermelho'

    alerts = []
    for cat, limit in data['variable_limits'].items():
        spent = month_total_by_cat.get(cat, 0.0)
        if limit > 0:
            usage = (spent / limit) * 100 if limit else 0
            if usage >= 100:
                alerts.append(f'Limite estourado em {data["categories"].get(cat, cat)}.')
            elif usage >= 85:
                alerts.append(f'{data["categories"].get(cat, cat)} já usou {usage:.0f}% do limite.')

    for bill in data['bills']:
        if bill.get('active', True) and not bill.get('paid', False):
            due_day = int(bill.get('due_day', 1))
            if 0 <= due_day - today <= 3:
                alerts.append(f'Conta próxima do vencimento: {bill["name"]}.')

    return {
        'income': round(income, 2),
        'fixed_total': fixed_total,
        'variable_base_total': base_variable_total,
        'base_total': round(base_cost_without_optional_savings, 2),
        'actual_total': actual_total,
        'projected_total': projected_total,
        'projected_balance': projected_balance,
        'free_after_base': free_after_base,
        'reserve_goal_month': round(reserve_suggestion, 2),
        'reserve_saved': round(reserve_saved, 2),
        'reserve_progress': reserve_progress,
        'traffic': traffic,
        'alerts': alerts,
        'by_category': month_total_by_cat,
        'monthly_saved_so_far': monthly_saved_so_far(data),
    }


def build_analysis(data):
    dash = compute_dashboard(data)
    if dash['projected_balance'] < 0:
        diagnosis = 'Você está em risco de fechar o mês negativo. Prioridade total em cortar variáveis e cartão.'
    elif dash['projected_balance'] < dash['reserve_goal_month']:
        diagnosis = 'Você está estável, mas ainda sem folga suficiente para acelerar a reserva.'
    else:
        diagnosis = 'Você está em fase de estabilização positiva. Foque em pagar tudo e guardar um pouco todo mês.'

    economy_tips = []
    if data['variable_limits'].get('assinaturas', 0) > 0:
        economy_tips.append('Revise assinaturas e mantenha só as que realmente usam.')
    economy_tips.append('Evite deixar o cartão consumir a sobra do mês.')
    economy_tips.append('Mantenha o uso do carro só para passeios e deslocamentos necessários.')

    return {
        'diagnosis': diagnosis,
        'economy_tips': economy_tips,
    }


def human_money(value):
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def telegram_text_status(data):
    dash = compute_dashboard(data)
    return (
        '📊 STATUS DO MÊS\n\n'
        f'Receita: {human_money(dash["income"])}\n'
        f'Base de contas: {human_money(dash["base_total"])}\n'
        f'Gasto lançado: {human_money(dash["actual_total"])}\n'
        f'Saldo projetado: {human_money(dash["projected_balance"])}\n\n'
        f'🎯 Guardar este mês: {human_money(reserve_target_for_month(data))}\n'
        f'🛡️ Reserva atual: {human_money(dash["reserve_saved"])}'
    )


def telegram_text_prediction(data):
    dash = compute_dashboard(data)
    return (
        '📈 PREVISÃO DO MÊS\n\n'
        f'Gasto projetado: {human_money(dash["projected_total"])}\n'
        f'Saldo final projetado: {human_money(dash["projected_balance"])}\n\n'
        f'Sugestão de reserva: {human_money(reserve_target_for_month(data))}'
    )


def telegram_text_analysis(data):
    dash = compute_dashboard(data)
    analysis = build_analysis(data)
    return (
        '🤖 ANÁLISE FINANCEIRA\n\n'
        f'Renda líquida: {human_money(dash["income"])}\n'
        f'Custo base: {human_money(dash["base_total"])}\n'
        f'Saldo livre base: {human_money(dash["free_after_base"])}\n\n'
        f'Diagnóstico: {analysis["diagnosis"]}'
    )


def telegram_text_reserve(data):
    dash = compute_dashboard(data)
    months = 0
    monthly = max(reserve_target_for_month(data), 1)
    remaining = max(float(data['profile']['meta_reserva']) - float(data['profile']['reserva_atual']), 0)
    if monthly > 0:
        months = int((remaining + monthly - 1) // monthly)
    return (
        '🛡️ RESERVA DE EMERGÊNCIA\n\n'
        f'Meta total: {human_money(float(data["profile"]["meta_reserva"]))}\n'
        f'Valor guardado: {human_money(float(data["profile"]["reserva_atual"]))}\n'
        f'Sugestão deste mês: {human_money(reserve_target_for_month(data))}\n'
        f'Tempo estimado: {months} meses'
    )


def telegram_text_invest(data):
    if float(data['profile']['reserva_atual']) < float(data['profile']['meta_reserva']):
        return (
            '📈 INVESTIMENTOS\n\n'
            'Antes de investir em risco, conclua a reserva de emergência.\n'
            'Prioridade atual: liquidez diária e disciplina mensal.\n\n'
            'Depois da reserva, use a análise atualizada para escolher renda fixa e ações.'
        )
    return (
        '📈 INVESTIMENTOS\n\n'
        'Reserva concluída. O próximo passo é montar uma alocação conservadora.\n'
        'Para ações e ETFs, a recomendação ideal deve usar dados atualizados do mercado no momento da decisão.'
    )


def send_telegram(chat_id, text):
    if not TOKEN:
        return
    requests.post(
        f'https://api.telegram.org/bot{TOKEN}/sendMessage',
        json={'chat_id': chat_id, 'text': text},
        timeout=20,
    )


def record_transaction(data, category, amount, source='telegram', description=''):
    key = normalize_key(category)
    data['transactions'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'month': current_month_key(),
        'category': key,
        'amount': float(amount),
        'source': source,
        'description': description,
    })
    if key == 'guardar':
        data['profile']['reserva_atual'] = round(float(data['profile'].get('reserva_atual', 0)) + float(amount), 2)
    save_data(data)


def update_named_value(data, key, value):
    key = normalize_key(key)
    if key in data['fixed_costs']:
        data['fixed_costs'][key] = float(value)
        save_data(data)
        return True, f'Conta fixa {key} atualizada para {human_money(float(value))}.'
    if key in data['variable_limits']:
        data['variable_limits'][key] = float(value)
        save_data(data)
        return True, f'Limite {key} atualizado para {human_money(float(value))}.'
    if key == 'meta_reserva':
        data['profile']['meta_reserva'] = float(value)
        save_data(data)
        return True, f'Meta da reserva atualizada para {human_money(float(value))}.'
    if key == 'guardar':
        data['monthly_saved_goal_override'] = float(value)
        save_data(data)
        return True, f'Meta mensal para guardar atualizada para {human_money(float(value))}.'
    return False, 'Categoria não encontrada para edição.'


def pay_bill(data, name):
    target = normalize_key(name)
    for bill in data['bills']:
        if normalize_key(bill['name']) == target:
            bill['paid'] = True
            save_data(data)
            return True, f'✅ Conta marcada como paga: {bill["name"]}.'
    return False, 'Conta não encontrada.'


def parse_message(text, data):
    msg = text.strip()
    low = msg.lower()

    if low.startswith('/status'):
        return telegram_text_status(data)
    if low.startswith('/previsao'):
        return telegram_text_prediction(data)
    if low.startswith('/analise'):
        return telegram_text_analysis(data)
    if low.startswith('/reserva') or low.startswith('/meta'):
        return telegram_text_reserve(data)
    if low.startswith('/investir'):
        return telegram_text_invest(data)
    if low.startswith('/limites'):
        lines = ['📋 LIMITES']
        for k, v in data['variable_limits'].items():
            lines.append(f'{data["categories"].get(k, k)}: {human_money(float(v))}')
        return '\n'.join(lines)
    if low.startswith('/contas'):
        lines = ['🧾 CONTAS']
        for b in data['bills']:
            status = 'paga' if b.get('paid') else 'aberta'
            lines.append(f'{b["name"]} - dia {b["due_day"]} - {human_money(float(b["amount"]))} - {status}')
        return '\n'.join(lines)
    if low.startswith('/guardar '):
        parts = msg.split(maxsplit=1)
        value = float(parts[1].replace(',', '.'))
        record_transaction(data, 'guardar', value, description='Aporte manual')
        return f'🛡️ Guardado {human_money(value)}. Reserva total: {human_money(float(data["profile"]["reserva_atual"]))}.'
    if low.startswith('/cartao '):
        parts = msg.split()
        value = float(parts[1].replace(',', '.'))
        data['variable_limits']['cartao'] = value
        save_data(data)
        return f'💳 Cartão do mês ajustado para {human_money(value)}.'
    if low.startswith('/editar '):
        parts = msg.split()
        if len(parts) >= 3:
            key = parts[1]
            value = float(parts[2].replace(',', '.'))
            _, response = update_named_value(data, key, value)
            return response
    if low.startswith('/pagar '):
        ok, response = pay_bill(data, msg.split(maxsplit=1)[1])
        return response

    parts = msg.split()
    if len(parts) >= 2:
        maybe_amount = parts[-1].replace(',', '.')
        try:
            amount = float(maybe_amount)
            category = ' '.join(parts[:-1])
            key = normalize_key(category)
            record_transaction(data, key, amount, description='Lançamento rápido')
            dash = compute_dashboard(data)
            limit = data['variable_limits'].get(key, 0.0)
            spent = dash['by_category'].get(key, 0.0)
            text = f'✅ Lançado em {data["categories"].get(key, category.title())}: {human_money(amount)}.'
            if limit > 0:
                remaining = limit - spent
                text += f'\nTotal no mês: {human_money(spent)}\nRestante do limite: {human_money(remaining)}'
            return text
        except ValueError:
            pass

    return 'Comando não reconhecido. Use /status, /analise, /previsao, /reserva, /limites ou mande algo como gasolina 70.'


@app.route('/')
def home():
    return render_template('dashboard.html')


@app.route('/api/health')
def health():
    return jsonify({'ok': True, 'service': 'nexus-dark-v4'})


@app.route('/api/dashboard')
def api_dashboard():
    data = load_data()
    dash = compute_dashboard(data)
    analysis = build_analysis(data)
    monthly_totals = []
    months = sorted({t['month'] for t in data['transactions']})[-6:]
    for m in months:
        month_sum = sum(float(t['amount']) for t in data['transactions'] if t['month'] == m)
        monthly_totals.append({'month': m, 'total': round(month_sum, 2)})
    return jsonify({
        'dashboard': dash,
        'profile': data['profile'],
        'fixed_costs': data['fixed_costs'],
        'variable_limits': data['variable_limits'],
        'transactions': month_transactions(data)[-30:],
        'monthly_totals': monthly_totals,
        'analysis': analysis,
        'bills': data['bills'],
        'reserve_target_month': reserve_target_for_month(data),
    })


@app.route('/api/update', methods=['POST'])
def api_update():
    data = load_data()
    payload = request.get_json(force=True)
    section = payload.get('section')
    key = normalize_key(payload.get('key', ''))
    value = float(payload.get('value', 0))

    if section == 'fixed' and key in data['fixed_costs']:
        data['fixed_costs'][key] = value
    elif section == 'variable' and key in data['variable_limits']:
        data['variable_limits'][key] = value
    elif section == 'profile' and key in {'meta_reserva', 'renda_liquida', 'beneficio_alimentacao', 'reserva_atual'}:
        data['profile'][key] = value
    elif section == 'monthly_goal':
        data['monthly_saved_goal_override'] = value
    else:
        return jsonify({'ok': False, 'message': 'Campo inválido.'}), 400

    save_data(data)
    return jsonify({'ok': True})


@app.route('/api/transaction', methods=['POST'])
def api_transaction():
    data = load_data()
    payload = request.get_json(force=True)
    category = payload.get('category', '')
    amount = float(payload.get('amount', 0))
    description = payload.get('description', '')
    record_transaction(data, category, amount, source='panel', description=description)
    return jsonify({'ok': True})


@app.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = load_data()
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get('message', {})
    chat = message.get('chat', {})
    text = message.get('text', '')
    chat_id = chat.get('id') or DEFAULT_CHAT_ID
    if text and chat_id:
        response_text = parse_message(text, data)
        send_telegram(chat_id, response_text)
    return jsonify({'ok': True})


if __name__ == '__main__':
    port = int(os.getenv('PORT', os.getenv('APP_PORT', '5000')))
    app.run(host='0.0.0.0', port=port)
