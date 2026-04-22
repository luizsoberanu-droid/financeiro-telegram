
from flask import Flask, request, jsonify, render_template
from datetime import datetime, date, timedelta
import json, os, calendar

app = Flask(__name__)
DATA_FILE = "data_store.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "receita_fixa": 5300,
        "receita_extra": 0,
        "contas": [],
        "cartoes": [
            {"nome": "samsung", "vencimento": 15, "melhor_dia_compra": 11},
            {"nome": "santander", "vencimento": 15, "melhor_dia_compra": 11},
            {"nome": "nubank", "vencimento": 1, "melhor_dia_compra": 30}
        ],
        "lancamentos": [],
        "parcelas": [],
        "limites": {"lazer": 100, "extras": 100, "combustivel": 320},
        "telegram_sessions": {}
    }

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

DATA = load_data()

CATEGORY_MAP = {
    "lazer": ["lanche", "passeio", "cinema", "sorvete", "hamburguer", "pizza", "açai", "acai"],
    "combustivel": ["gasolina", "etanol", "combustivel"],
    "extras": ["mercado", "farmacia", "farmácia", "remedio", "remédio", "compra"]
}

def norm(s): return s.strip().lower()

def infer_category(desc):
    d = norm(desc)
    for cat, words in CATEGORY_MAP.items():
        if d in words or any(w in d for w in words):
            return cat
    return "extras"

def previous_business_day(year, month, day):
    last_day = calendar.monthrange(year, month)[1]
    d = date(year, month, min(day, last_day))
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d

def card_by_name(name):
    n = norm(name)
    return next((c for c in DATA["cartoes"] if norm(c["nome"]) == n), None)

def effective_best_day(card_name, year, month):
    card = card_by_name(card_name)
    if not card:
        return None
    return previous_business_day(year, month, int(card["melhor_dia_compra"]))

def next_invoice_for_purchase(card_name, purchase_date):
    card = card_by_name(card_name)
    if not card:
        return None
    best_day = effective_best_day(card_name, purchase_date.year, purchase_date.month)
    if purchase_date <= best_day:
        month = purchase_date.month
        year = purchase_date.year
    else:
        month = 1 if purchase_date.month == 12 else purchase_date.month + 1
        year = purchase_date.year + 1 if purchase_date.month == 12 else purchase_date.year
    return {
        "ano": year,
        "mes": month,
        "vencimento": int(card["vencimento"]),
        "melhor_dia_utilizado": best_day.isoformat()
    }

def month_key_from_date(dt):
    return f"{dt.year:04d}-{dt.month:02d}"

def current_month():
    now = datetime.now().date()
    return month_key_from_date(now)

def add_purchase(descricao, valor, forma_pagamento="dinheiro", cartao=None, data_compra=None):
    descricao = norm(descricao)
    categoria = infer_category(descricao)
    dt = datetime.now().date() if data_compra is None else data_compra
    mes_ref = month_key_from_date(dt)
    fatura = None
    if forma_pagamento == "cartao" and cartao:
        fatura = next_invoice_for_purchase(cartao, dt)
        mes_ref = f"{fatura['ano']:04d}-{fatura['mes']:02d}"
    item = {
        "id": len(DATA["lancamentos"]) + 1,
        "data": dt.isoformat(),
        "descricao": descricao,
        "categoria": categoria,
        "valor": round(float(valor), 2),
        "forma_pagamento": forma_pagamento,
        "cartao": cartao,
        "mes_ref": mes_ref,
        "fatura": fatura
    }
    DATA["lancamentos"].append(item)
    save_data()
    return item

def add_installment(descricao, valor_parcela, total_parcelas, cartao, data_compra=None):
    dt = datetime.now().date() if data_compra is None else data_compra
    base_invoice = next_invoice_for_purchase(cartao, dt)
    created = []
    for i in range(total_parcelas):
        month = base_invoice["mes"] + i
        year = base_invoice["ano"]
        while month > 12:
            month -= 12
            year += 1
        rec = {
            "id": len(DATA["parcelas"]) + 1,
            "descricao": descricao,
            "cartao": cartao,
            "valor": round(float(valor_parcela), 2),
            "parcela_atual": i + 1,
            "total_parcelas": total_parcelas,
            "mes_ref": f"{year:04d}-{month:02d}",
            "vencimento": card_by_name(cartao)["vencimento"]
        }
        DATA["parcelas"].append(rec)
        created.append(rec)
    save_data()
    return created

def month_spend(month):
    totals = {}
    details = []
    for item in DATA["lancamentos"]:
        if item["mes_ref"] == month:
            totals[item["categoria"]] = totals.get(item["categoria"], 0) + item["valor"]
            details.append(item)
    return totals, details

def card_invoice_totals(month):
    totals = {}
    details = {}
    for item in DATA["lancamentos"]:
        if item.get("forma_pagamento") == "cartao" and item["mes_ref"] == month:
            c = item["cartao"] or "desconhecido"
            totals[c] = totals.get(c, 0) + item["valor"]
            details.setdefault(c, []).append(item)
    for p in DATA["parcelas"]:
        if p["mes_ref"] == month:
            c = p["cartao"]
            totals[c] = totals.get(c, 0) + p["valor"]
            details.setdefault(c, []).append(p)
    return totals, details

def analysis():
    m = current_month()
    cat_totals, details = month_spend(m)
    card_totals, card_details = card_invoice_totals(m)
    receita_total = DATA["receita_fixa"] + DATA.get("receita_extra", 0)
    gastos_mes = sum(cat_totals.values())
    saldo = receita_total - gastos_mes
    excedentes = []
    for cat, limite in DATA["limites"].items():
        gasto = cat_totals.get(cat, 0)
        if gasto > limite:
            excedentes.append({"categoria": cat, "excesso": round(gasto - limite, 2)})
    return {
        "mes": m,
        "receita_total": round(receita_total, 2),
        "gastos_mes": round(gastos_mes, 2),
        "saldo": round(saldo, 2),
        "categorias": cat_totals,
        "cartoes": card_totals,
        "excedentes": excedentes,
        "lancamentos": details,
        "detalhe_cartoes": card_details
    }

def parse_simple_message(msg):
    parts = msg.split()
    if len(parts) >= 2:
        try:
            val = float(parts[-1].replace(",", "."))
            desc = " ".join(parts[:-1])
            return desc, val
        except:
            return None, None
    return None, None

def session(chat_id):
    sid = str(chat_id)
    if sid not in DATA["telegram_sessions"]:
        DATA["telegram_sessions"][sid] = {}
    return DATA["telegram_sessions"][sid]

def list_cards_text():
    return "\n".join([f"- {c['nome']}" for c in DATA["cartoes"]])

def handle_telegram(chat_id, text):
    s = session(chat_id)
    msg = norm(text)

    if msg in ["status", "/status"]:
        a = analysis()
        return f"📊 Status\nReceita total: R$ {a['receita_total']:.2f}\nGastos do mês: R$ {a['gastos_mes']:.2f}\nSaldo: R$ {a['saldo']:.2f}"

    if msg in ["analise", "/analise"]:
        a = analysis()
        linhas = [
            "📈 Análise ampla",
            f"Mês: {a['mes']}",
            f"Receita total: R$ {a['receita_total']:.2f}",
            f"Gastos do mês: R$ {a['gastos_mes']:.2f}",
            f"Saldo: R$ {a['saldo']:.2f}",
        ]
        if a["cartoes"]:
            linhas.append("Cartões neste mês:")
            for nome, valor in a["cartoes"].items():
                linhas.append(f"- {nome}: R$ {valor:.2f}")
        if a["excedentes"]:
            linhas.append("Excedentes:")
            for e in a["excedentes"]:
                linhas.append(f"- {e['categoria']}: +R$ {e['excesso']:.2f}")
        else:
            linhas.append("✅ Nenhuma categoria excedeu o limite.")
        return "\n".join(linhas)

    if msg.startswith("extra ") or msg.startswith("/extra "):
        val = float(msg.split()[1].replace(",", "."))
        DATA["receita_extra"] = val
        save_data()
        a = analysis()
        return f"💰 Receita extra atualizada para R$ {val:.2f}\nReceita total do mês: R$ {a['receita_total']:.2f}"

    if s.get("awaiting") == "forma":
        s["forma"] = msg
        if msg in ["dinheiro", "pix", "debito", "débito"]:
            item = add_purchase(s["descricao"], s["valor"], "dinheiro", None)
            save_data()
            a = analysis()
            gasto_cat = a["categorias"].get(item["categoria"], 0)
            limite = DATA["limites"].get(item["categoria"], 0)
            restante = limite - gasto_cat
            return f"✅ Lançado em dinheiro.\nCategoria: {item['categoria']}\nTotal no mês: R$ {gasto_cat:.2f}\nRestante: R$ {restante:.2f}"
        elif msg in ["cartao", "cartão"]:
            s["awaiting"] = "cartao"
            save_data()
            return f"Qual cartão?\n{list_cards_text()}\nOu responda: novo"
        else:
            return "Responda: dinheiro, pix, débito ou cartao."

    if s.get("awaiting") == "cartao":
        if msg == "novo":
            s["awaiting"] = "novo_cartao_nome"
            save_data()
            return "Digite o nome do novo cartão."
        if not card_by_name(msg):
            return f"Cartão não encontrado.\nEscolha um existente:\n{list_cards_text()}\nOu responda: novo"
        item = add_purchase(s["descricao"], s["valor"], "cartao", msg)
        s.clear()
        save_data()
        fatura = item["fatura"]
        return (
            f"💳 Compra registrada\nDescrição: {item['descricao']}\nCategoria: {item['categoria']}\n"
            f"Cartão: {msg}\nValor: R$ {item['valor']:.2f}\n"
            f"Fatura: {fatura['mes']:02d}/{fatura['ano']} vence dia {fatura['vencimento']}\n"
            f"Melhor dia aplicado: {fatura['melhor_dia_utilizado']}"
        )

    if s.get("awaiting") == "novo_cartao_nome":
        s["novo_cartao_nome"] = msg
        s["awaiting"] = "novo_cartao_vencimento"
        save_data()
        return "Digite o dia de vencimento do novo cartão. Ex.: 12"

    if s.get("awaiting") == "novo_cartao_vencimento":
        s["novo_cartao_vencimento"] = int(msg)
        s["awaiting"] = "novo_cartao_melhor_dia"
        save_data()
        return "Digite o melhor dia de compra. Ex.: 8"

    if s.get("awaiting") == "novo_cartao_melhor_dia":
        DATA["cartoes"].append({
            "nome": s["novo_cartao_nome"],
            "vencimento": int(s["novo_cartao_vencimento"]),
            "melhor_dia_compra": int(msg)
        })
        save_data()
        # continue purchase
        item = add_purchase(s["descricao"], s["valor"], "cartao", s["novo_cartao_nome"])
        s.clear()
        save_data()
        return f"✅ Novo cartão criado e compra lançada em {item['cartao']}."

    if msg.startswith("parcela ") or msg.startswith("/parcela "):
        # formato: parcela samsung 134 3/10 tv
        parts = msg.replace("/", "").split()
        if len(parts) >= 5:
            cart = parts[1]
            valor = float(parts[2].replace(",", "."))
            frac = parts[3]
            total = int(frac.split("/")[1])
            desc = " ".join(parts[4:])
            if not card_by_name(cart):
                return "Cartão não encontrado para parcelado."
            criadas = add_installment(desc, valor, total, cart)
            primeira = criadas[0]
            ultima = criadas[-1]
            return (
                f"✅ Parcelado criado\n{desc}\nCartão: {cart}\nValor parcela: R$ {valor:.2f}\n"
                f"Total de parcelas: {total}\nPrimeira fatura: {primeira['mes_ref']}\nÚltima fatura: {ultima['mes_ref']}"
            )

    # compra guiada simples: "lanche 30"
    desc, val = parse_simple_message(msg.replace("/", ""))
    if desc and val is not None:
        s["descricao"] = desc
        s["valor"] = val
        s["awaiting"] = "forma"
        save_data()
        categoria = infer_category(desc)
        return f"Entendi: {desc} — R$ {val:.2f}\nCategoria sugerida: {categoria}\nFoi no dinheiro ou cartão?"

    return "Comandos: status, analise, extra 300, 'lanche 30', ou 'parcela samsung 134 3/10 tv'."

@app.route("/")
def home():
    return render_template("dashboard.html")

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "nexus-v49"})

@app.route("/api/status")
def api_status():
    return jsonify(analysis())

@app.route("/api/cartoes")
def api_cartoes():
    rows = []
    today = datetime.now().date()
    for c in DATA["cartoes"]:
        best = effective_best_day(c["nome"], today.year, today.month)
        rows.append({**c, "melhor_dia_utilizado": best.isoformat()})
    return jsonify(rows)

@app.route("/api/lancar", methods=["POST"])
def api_lancar():
    p = request.get_json()
    item = add_purchase(p["descricao"], p["valor"], p.get("forma_pagamento", "dinheiro"), p.get("cartao"))
    return jsonify(item)

@app.route("/api/parcelar", methods=["POST"])
def api_parcelar():
    p = request.get_json()
    criadas = add_installment(p["descricao"], p["valor"], p["total_parcelas"], p["cartao"])
    return jsonify({"ok": True, "parcelas_criadas": len(criadas)})

@app.route("/webhooks/telegram", methods=["POST"])
def telegram():
    data = request.get_json(silent=True) or {}
    msg = (((data.get("message") or {}).get("text")) or "").strip()
    chat_id = (((data.get("message") or {}).get("chat")) or {}).get("id", "web")
    reply = handle_telegram(chat_id, msg)
    return jsonify({"ok": True, "reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
