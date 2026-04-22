
from flask import Flask, request, jsonify, render_template
import requests
import os
from datetime import datetime, date, timedelta
import json, os, calendar

app = Flask(__name__)
DATA_FILE = "data_store.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN não configurado"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
        return r.ok, r.text
    except Exception as e:
        return False, str(e)


def default_data():
    return {
        "receita_fixa": 5300.0,
        "receita_extra": 0.0,
        "meta_reserva": 12000.0,
        "reserva_atual": 0.0,
        "modo": "ataque_rigido",
        "dividas": {
            "negativo": 2999.94,
            "ipva": 1161.0,
            "samsung": 134.0,
            "santander": 996.12,
            "nubank": 1006.05
        },
        "limites": {
            "lazer": 100.0,
            "combustivel": 320.0,
            "extras": 100.0
        },
        "contas_fixas": [
            {"id": 1, "nome": "casa", "valor": 732.92, "vencimento": 10, "categoria": "moradia", "pago": False},
            {"id": 2, "nome": "carro", "valor": 1469.70, "vencimento": 15, "categoria": "financiamento", "pago": False},
            {"id": 3, "nome": "condominio", "valor": 365.0, "vencimento": 5, "categoria": "moradia", "pago": False},
            {"id": 4, "nome": "faculdade", "valor": 360.0, "vencimento": 20, "categoria": "educacao", "pago": False},
            {"id": 5, "nome": "faculdade_esposa", "valor": 200.0, "vencimento": 20, "categoria": "educacao", "pago": False},
            {"id": 6, "nome": "internet", "valor": 220.0, "vencimento": 15, "categoria": "servicos", "pago": False},
            {"id": 7, "nome": "luz", "valor": 270.0, "vencimento": 25, "categoria": "servicos", "pago": False},
            {"id": 8, "nome": "ipva", "valor": 1161.0, "vencimento": 10, "categoria": "veiculo", "pago": False}
        ],
        "cartoes": [
            {"id": 1, "nome": "samsung", "vencimento": 15, "melhor_dia_compra": 11, "limite_ideal": 200.0, "pago": False},
            {"id": 2, "nome": "santander", "vencimento": 15, "melhor_dia_compra": 11, "limite_ideal": 200.0, "pago": False},
            {"id": 3, "nome": "nubank", "vencimento": 1, "melhor_dia_compra": 30, "limite_ideal": 200.0, "pago": False}
        ],
        "parcelas": [],
        "lancamentos": [],
        "telegram_sessions": {}
    }

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = default_data()
            # merge shallow
            base.update({k:v for k,v in data.items() if k in base})
            return base
        except Exception:
            return default_data()
    return default_data()

DATA = load_data()

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

def now_date():
    return datetime.now().date()

def month_key(dt):
    return f"{dt.year:04d}-{dt.month:02d}"

def month_name(key):
    y,m = key.split("-")
    nomes = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{nomes[int(m)-1].capitalize()}/{y}"

def normalize(text):
    return (text or "").strip().lower()

CATEGORY_MAP = {
    "lazer": ["lanche", "passeio", "cinema", "sorvete", "pizza", "hamburguer", "hambúrguer", "açai", "acai"],
    "combustivel": ["gasolina", "etanol", "combustivel", "combustível"],
    "extras": ["mercado", "farmacia", "farmácia", "remedio", "remédio", "compra"]
}

def infer_category(desc):
    d = normalize(desc)
    for cat, words in CATEGORY_MAP.items():
        if d in words or any(w in d for w in words):
            return cat
    return "extras"

def get_card(name):
    n = normalize(name)
    return next((c for c in DATA["cartoes"] if normalize(c["nome"]) == n), None)

def prev_business_day(year, month, day):
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, min(day, last_day))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def effective_best_day(card_name, dt):
    card = get_card(card_name)
    if not card:
        return None
    return prev_business_day(dt.year, dt.month, int(card["melhor_dia_compra"]))

def invoice_for_purchase(card_name, purchase_date):
    card = get_card(card_name)
    if not card:
        return None
    best = effective_best_day(card_name, purchase_date)
    if purchase_date <= best:
        y, m = purchase_date.year, purchase_date.month
    else:
        y = purchase_date.year + 1 if purchase_date.month == 12 else purchase_date.year
        m = 1 if purchase_date.month == 12 else purchase_date.month + 1
    return {"ano": y, "mes": m, "mes_ref": f"{y:04d}-{m:02d}", "vencimento": int(card["vencimento"]), "melhor_dia_utilizado": best.isoformat()}

def next_id(items):
    return max([x.get("id", 0) for x in items], default=0) + 1

def add_lancamento(descricao, valor, forma_pagamento="dinheiro", cartao=None, data_compra=None):
    dt = now_date() if data_compra is None else data_compra
    categoria = infer_category(descricao)
    fatura = None
    mes_ref = month_key(dt)
    if forma_pagamento == "cartao" and cartao:
        fatura = invoice_for_purchase(cartao, dt)
        mes_ref = fatura["mes_ref"]
    item = {
        "id": next_id(DATA["lancamentos"]),
        "data": dt.isoformat(),
        "mes_ref": mes_ref,
        "descricao": descricao,
        "categoria": categoria,
        "valor": round(float(valor),2),
        "forma_pagamento": forma_pagamento,
        "cartao": cartao,
        "fatura": fatura
    }
    DATA["lancamentos"].append(item)
    save_data()
    return item

def add_parcelado(descricao, valor_parcela, total_parcelas, cartao, data_compra=None):
    dt = now_date() if data_compra is None else data_compra
    info = invoice_for_purchase(cartao, dt)
    criadas = []
    for i in range(total_parcelas):
        y = info["ano"]
        m = info["mes"] + i
        while m > 12:
            m -= 12
            y += 1
        p = {
            "id": next_id(DATA["parcelas"]),
            "descricao": descricao,
            "cartao": cartao,
            "valor": round(float(valor_parcela), 2),
            "parcela_atual": i+1,
            "total_parcelas": total_parcelas,
            "mes_ref": f"{y:04d}-{m:02d}",
            "vencimento": get_card(cartao)["vencimento"]
        }
        DATA["parcelas"].append(p)
        criadas.append(p)
    save_data()
    return criadas

def totals_for_month(mref):
    cat = {}
    lancamentos = []
    for l in DATA["lancamentos"]:
        if l["mes_ref"] == mref:
            cat[l["categoria"]] = cat.get(l["categoria"], 0) + l["valor"]
            lancamentos.append(l)
    return cat, lancamentos

def card_totals_for_month(mref):
    totals = {}
    details = {}
    for l in DATA["lancamentos"]:
        if l["forma_pagamento"] == "cartao" and l["mes_ref"] == mref:
            c = l["cartao"] or "desconhecido"
            totals[c] = totals.get(c, 0) + l["valor"]
            details.setdefault(c, []).append(l)
    for p in DATA["parcelas"]:
        if p["mes_ref"] == mref:
            c = p["cartao"]
            totals[c] = totals.get(c, 0) + p["valor"]
            details.setdefault(c, []).append(p)
    return totals, details

def business_days_until_due(vencimento):
    today = now_date()
    target = date(today.year, today.month, min(vencimento, calendar.monthrange(today.year, today.month)[1]))
    if target < today:
        # next month
        year = today.year + 1 if today.month == 12 else today.year
        month = 1 if today.month == 12 else today.month + 1
        target = date(year, month, min(vencimento, calendar.monthrange(year, month)[1]))
    days = 0
    d = today
    while d < target:
        d += timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days

def fixed_total():
    return round(sum(c["valor"] for c in DATA["contas_fixas"]), 2)

def debt_total():
    return round(sum(DATA["dividas"].values()), 2)

def monthly_free_cash():
    receita_total = DATA["receita_fixa"] + DATA["receita_extra"]
    return round(receita_total - fixed_total(), 2)

def analyst_summary():
    receita_total = DATA["receita_fixa"] + DATA["receita_extra"]
    fixos = fixed_total()
    dividas = debt_total()
    meta_3m = round(dividas / 3, 2)
    livres = receita_total - fixos
    status = "🔴 crítica controlável" if livres < meta_3m else "🟡 apertada mas recuperável"
    linhas = [
        "📊 Diagnóstico financeiro",
        f"Receita total: R$ {receita_total:.2f}",
        f"Comprometido fixo: R$ {fixos:.2f}",
        f"Dívida total: R$ {dividas:.2f}",
        f"Meta em 3 meses: R$ {meta_3m:.2f}/mês",
        f"Caixa livre antes dos variáveis: R$ {livres:.2f}",
        f"Situação: {status}"
    ]
    if livres < meta_3m:
        linhas += [
            "",
            "Plano sugerido:",
            "- segurar lazer em até R$ 100",
            "- evitar novo cartão",
            "- gerar renda extra de pelo menos R$ 300",
            "- priorizar Nubank, Santander, Samsung e IPVA"
        ]
    else:
        linhas += [
            "",
            "Plano sugerido:",
            "- manter controle rígido",
            "- usar sobra para atacar a dívida",
            "- zerando o negativo, começar reserva"
        ]
    return "\n".join(linhas)

def overall_analysis():
    mref = month_key(now_date())
    cat, lancs = totals_for_month(mref)
    cards, details = card_totals_for_month(mref)
    receita_total = DATA["receita_fixa"] + DATA["receita_extra"]
    gastos_mes = round(sum(cat.values()), 2)
    saldo = round(receita_total - gastos_mes, 2)
    excedentes = []
    for nome, limite in DATA["limites"].items():
        gasto = cat.get(nome, 0)
        if gasto > limite:
            excedentes.append({"categoria": nome, "excesso": round(gasto-limite,2)})
    proximas = []
    for c in DATA["contas_fixas"]:
        if not c.get("pago", False):
            dias = business_days_until_due(int(c["vencimento"]))
            if dias <= 3:
                proximas.append({"nome": c["nome"], "dias_uteis": dias, "valor": c["valor"]})
    return {
        "mes": mref,
        "mes_nome": month_name(mref),
        "receita_total": round(receita_total,2),
        "receita_fixa": round(DATA["receita_fixa"],2),
        "receita_extra": round(DATA["receita_extra"],2),
        "gastos_mes": gastos_mes,
        "saldo": saldo,
        "categorias": cat,
        "lancamentos": lancs,
        "cartoes_mes": cards,
        "detalhe_cartoes": details,
        "excedentes": excedentes,
        "contas_fixas": DATA["contas_fixas"],
        "cartoes": DATA["cartoes"],
        "parcelas": DATA["parcelas"],
        "divida_total": debt_total(),
        "reserva_atual": DATA["reserva_atual"],
        "meta_reserva": DATA["meta_reserva"],
        "proximas_contas": proximas,
        "analista": analyst_summary()
    }

def session(chat_id):
    sid = str(chat_id)
    DATA["telegram_sessions"].setdefault(sid, {})
    return DATA["telegram_sessions"][sid]

def cards_list():
    return "\n".join([f"- {c['nome']}" for c in DATA["cartoes"]])

def handle_telegram(chat_id, message):
    s = session(chat_id)
    msg = normalize(message)

    if msg in ["status", "/status"]:
        a = overall_analysis()
        return f"📊 Status\nReceita total: R$ {a['receita_total']:.2f}\nGastos do mês: R$ {a['gastos_mes']:.2f}\nSaldo: R$ {a['saldo']:.2f}\nDívida total: R$ {a['divida_total']:.2f}"

    if msg in ["analise", "/analise"]:
        return overall_analysis()["analista"]

    if msg in ["plano", "/plano"]:
        div = debt_total()
        meta = round(div/3,2)
        return f"🔥 Plano atual\nDívida total: R$ {div:.2f}\nMeta mensal em 3 meses: R$ {meta:.2f}\nLazer recomendado: até R$ 100\nCartão variável: evitar"

    if msg in ["contas", "/contas"]:
        linhas = ["📅 Contas fixas"]
        for c in DATA["contas_fixas"]:
            status = "paga" if c.get("pago", False) else "aberta"
            linhas.append(f"- {c['nome']} | R$ {c['valor']:.2f} | vence {c['vencimento']} | {status}")
        return "\n".join(linhas)

    if msg.startswith("pagar ") or msg.startswith("/pagar "):
        alvo = normalize(msg.split(" ",1)[1])
        for c in DATA["contas_fixas"]:
            if normalize(c["nome"]) == alvo:
                c["pago"] = True
                save_data()
                return f"✅ {alvo} marcado como pago."
        for c in DATA["cartoes"]:
            if normalize(c["nome"]) == alvo:
                c["pago"] = True
                save_data()
                return f"✅ cartão {alvo} marcado como pago."
        return "Não encontrei essa conta/cartão."

    if msg.startswith("extra ") or msg.startswith("/extra "):
        try:
            val = float(msg.split()[1].replace(",","."))
            DATA["receita_extra"] = val
            save_data()
            return f"💰 Receita extra atualizada para R$ {val:.2f}"
        except:
            return "Use: extra 300"

    if s.get("awaiting") == "forma":
        s["forma"] = msg
        if msg in ["dinheiro", "pix", "debito", "débito"]:
            item = add_lancamento(s["descricao"], s["valor"], "dinheiro")
            s.clear()
            a = overall_analysis()
            gasto_cat = a["categorias"].get(item["categoria"], 0)
            limite = DATA["limites"].get(item["categoria"], 0)
            restante = round(limite - gasto_cat, 2)
            save_data()
            if restante >= 0:
                return f"✅ Lançado em dinheiro.\nCategoria: {item['categoria']}\nTotal: R$ {gasto_cat:.2f}\nRestante: R$ {restante:.2f}"
            return f"⚠️ Lançado em dinheiro.\nCategoria: {item['categoria']}\nTotal: R$ {gasto_cat:.2f}\nExcesso: R$ {abs(restante):.2f}"
        if msg in ["cartao", "cartão"]:
            s["awaiting"] = "cartao"
            save_data()
            return f"Qual cartão?\n{cards_list()}\nOu responda: novo"
        return "Responda: dinheiro, pix, débito ou cartao."

    if s.get("awaiting") == "cartao":
        if msg == "novo":
            s["awaiting"] = "novo_cartao_nome"
            save_data()
            return "Digite o nome do novo cartão."
        card = get_card(msg)
        if not card:
            return f"Cartão não encontrado.\nEscolha um existente:\n{cards_list()}\nOu responda: novo"
        item = add_lancamento(s["descricao"], s["valor"], "cartao", card["nome"])
        s.clear()
        return f"💳 Compra registrada\nDescrição: {item['descricao']}\nCartão: {item['cartao']}\nValor: R$ {item['valor']:.2f}\nFatura: {item['fatura']['mes_ref']} vence dia {item['fatura']['vencimento']}\nMelhor dia aplicado: {item['fatura']['melhor_dia_utilizado']}"

    if s.get("awaiting") == "novo_cartao_nome":
        s["novo_nome"] = msg
        s["awaiting"] = "novo_cartao_venc"
        save_data()
        return "Digite o vencimento do cartão. Ex.: 12"

    if s.get("awaiting") == "novo_cartao_venc":
        s["novo_venc"] = int(msg)
        s["awaiting"] = "novo_cartao_melhor"
        save_data()
        return "Digite o melhor dia de compra. Ex.: 8"

    if s.get("awaiting") == "novo_cartao_melhor":
        DATA["cartoes"].append({
            "id": next_id(DATA["cartoes"]),
            "nome": s["novo_nome"],
            "vencimento": int(s["novo_venc"]),
            "melhor_dia_compra": int(msg),
            "limite_ideal": 200.0,
            "pago": False
        })
        save_data()
        item = add_lancamento(s["descricao"], s["valor"], "cartao", s["novo_nome"])
        s.clear()
        save_data()
        return f"✅ Novo cartão criado e compra lançada em {item['cartao']}."

    if msg.startswith("parcela ") or msg.startswith("/parcela "):
        # parcela samsung 134 10 tv
        parts = msg.replace("/","").split()
        if len(parts) >= 5:
            cart = parts[1]
            valor = float(parts[2].replace(",","."))
            total = int(parts[3].split("/")[1]) if "/" in parts[3] else int(parts[3])
            desc = " ".join(parts[4:])
            if not get_card(cart):
                return "Cartão não encontrado para parcelado."
            criadas = add_parcelado(desc, valor, total, cart)
            return f"✅ Parcelado criado\n{desc}\nCartão: {cart}\nParcelas: {len(criadas)}\nPrimeira fatura: {criadas[0]['mes_ref']}"

    parts = msg.replace("/","").split()
    if len(parts) >= 2:
        try:
            valor = float(parts[-1].replace(",","."))
            descricao = " ".join(parts[:-1])
            s["descricao"] = descricao
            s["valor"] = valor
            s["awaiting"] = "forma"
            save_data()
            return f"Entendi: {descricao} — R$ {valor:.2f}\nCategoria sugerida: {infer_category(descricao)}\nFoi no dinheiro ou cartão?"
        except:
            pass

    return "Comandos: status, analise, plano, contas, extra 300, pagar casa, ou lance 'lanche 30'."

@app.route("/")
def home():
    return render_template("dashboard.html")

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "nexus-v5.1-elite"})

@app.route("/api/status")
def api_status():
    return jsonify(overall_analysis())

@app.route("/api/add_extra", methods=["POST"])
def api_add_extra():
    DATA["receita_extra"] = float(request.json.get("valor", 0))
    save_data()
    return jsonify({"ok": True})

@app.route("/api/add_conta_fixa", methods=["POST"])
def api_add_conta():
    p = request.get_json()
    DATA["contas_fixas"].append({
        "id": next_id(DATA["contas_fixas"]),
        "nome": p["nome"],
        "valor": float(p["valor"]),
        "vencimento": int(p["vencimento"]),
        "categoria": p.get("categoria", "geral"),
        "pago": False
    })
    save_data()
    return jsonify({"ok": True})

@app.route("/api/add_cartao", methods=["POST"])
def api_add_cartao():
    p = request.get_json()
    DATA["cartoes"].append({
        "id": next_id(DATA["cartoes"]),
        "nome": p["nome"],
        "vencimento": int(p["vencimento"]),
        "melhor_dia_compra": int(p["melhor_dia_compra"]),
        "limite_ideal": float(p.get("limite_ideal", 200)),
        "pago": False
    })
    save_data()
    return jsonify({"ok": True})

@app.route("/api/lancar", methods=["POST"])
def api_lancar():
    p = request.get_json()
    item = add_lancamento(p["descricao"], p["valor"], p.get("forma_pagamento", "dinheiro"), p.get("cartao"))
    return jsonify(item)

@app.route("/api/parcelar", methods=["POST"])
def api_parcelar():
    p = request.get_json()
    criadas = add_parcelado(p["descricao"], p["valor"], int(p["total_parcelas"]), p["cartao"])
    return jsonify({"ok": True, "parcelas": criadas})

@app.route("/api/marcar_pago", methods=["POST"])
def api_pagar():
    p = request.get_json()
    tipo = p.get("tipo")
    nome = normalize(p.get("nome"))
    if tipo == "conta":
        for c in DATA["contas_fixas"]:
            if normalize(c["nome"]) == nome:
                c["pago"] = True
                save_data()
                return jsonify({"ok": True})
    if tipo == "cartao":
        for c in DATA["cartoes"]:
            if normalize(c["nome"]) == nome:
                c["pago"] = True
                save_data()
                return jsonify({"ok": True})
    return jsonify({"ok": False, "erro": "não encontrado"}), 404

@app.route("/webhooks/telegram", methods=["POST"])
def telegram():
    data = request.get_json(silent=True) or {}
    text = (((data.get("message") or {}).get("text")) or "").strip()
    chat_id = (((data.get("message") or {}).get("chat")) or {}).get("id")
    if not text or not chat_id:
        return jsonify({"ok": True})
    reply = handle_telegram(chat_id, text)
    ok, detail = telegram_send(chat_id, reply)
    status = 200 if ok else 500
    return jsonify({"ok": ok, "detail": detail[:300] if isinstance(detail, str) else str(detail)[:300]}), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
