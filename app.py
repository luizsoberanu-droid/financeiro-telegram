from flask import Flask, request, jsonify, render_template
import json, os, requests, calendar
from datetime import datetime, date, timedelta

app = Flask(__name__)
DATA_FILE = "data_store.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN nao configurado"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "receita_fixa": 5300,
        "receita_extra": 0,
        "reserva_atual": 0,
        "reserva_meta": 12000,
        "contas": [
            {"nome": "casa", "valor": 732.92, "vencimento": 10, "pago": False},
            {"nome": "carro", "valor": 1469.70, "vencimento": 15, "pago": False},
            {"nome": "condominio", "valor": 365, "vencimento": 5, "pago": False},
            {"nome": "faculdade", "valor": 360, "vencimento": 20, "pago": False},
            {"nome": "faculdade_esposa", "valor": 200, "vencimento": 20, "pago": False},
            {"nome": "internet", "valor": 220, "vencimento": 15, "pago": False},
            {"nome": "luz", "valor": 270, "vencimento": 25, "pago": False},
            {"nome": "ipva", "valor": 1161, "vencimento": 10, "pago": False}
        ],
        "cartoes": [
            {"nome": "samsung", "vencimento": 15, "melhor_dia_compra": 11},
            {"nome": "santander", "vencimento": 15, "melhor_dia_compra": 11},
            {"nome": "nubank", "vencimento": 1, "melhor_dia_compra": 30}
        ],
        "lancamentos": [],
        "parcelas": [],
        "limites": {"lazer": 100, "extras": 100, "combustivel": 320},
        "dividas": {
            "negativo": 2999.94,
            "ipva": 1161,
            "samsung": 134,
            "santander": 996.12,
            "nubank": 1006.05
        },
        "telegram_sessions": {}
    }

DATA = load_data()

CATEGORY_MAP = {
    "lazer": ["lanche", "passeio", "cinema", "sorvete", "hamburguer", "pizza", "acai", "bar", "restaurante"],
    "combustivel": ["gasolina", "etanol", "combustivel"],
    "extras": ["mercado", "farmacia", "remedio", "compra", "pix", "uber", "ifood"]
}

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

def norm(s):
    return s.strip().lower()

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
    return month_key_from_date(datetime.now().date())

def current_date():
    return datetime.now().date()

def add_purchase(descricao, valor, forma_pagamento="dinheiro", cartao=None, data_compra=None):
    descricao = norm(descricao)
    categoria = infer_category(descricao)
    dt = current_date() if data_compra is None else data_compra
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
    dt = current_date() if data_compra is None else data_compra
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

def total_contas_abertas():
    return sum(c["valor"] for c in DATA["contas"] if not c.get("pago"))

def total_dividas():
    return round(sum(DATA.get("dividas", {}).values()), 2)

def card_invoice_totals(month):
    totals = {}
    for item in DATA["lancamentos"]:
        if item.get("forma_pagamento") == "cartao" and item["mes_ref"] == month:
            c = item["cartao"] or "desconhecido"
            totals[c] = totals.get(c, 0) + item["valor"]
    for p in DATA["parcelas"]:
        if p["mes_ref"] == month:
            c = p["cartao"]
            totals[c] = totals.get(c, 0) + p["valor"]
    return totals

def monthly_income():
    return round(DATA["receita_fixa"] + DATA.get("receita_extra", 0), 2)

def analysis():
    m = current_month()
    cat_totals, details = month_spend(m)
    receita_total = monthly_income()
    gastos_mes = sum(cat_totals.values())
    contas_abertas = total_contas_abertas()
    saldo = receita_total - gastos_mes - contas_abertas
    excedentes = []
    for cat, limite in DATA["limites"].items():
        gasto = cat_totals.get(cat, 0)
        if gasto > limite:
            excedentes.append({"categoria": cat, "excesso": round(gasto - limite, 2)})
    return {
        "mes": m,
        "receita_total": round(receita_total, 2),
        "gastos_mes": round(gastos_mes, 2),
        "contas_abertas": round(contas_abertas, 2),
        "saldo": round(saldo, 2),
        "categorias": cat_totals,
        "cartoes": card_invoice_totals(m),
        "excedentes": excedentes,
        "lancamentos": details,
        "divida_total": total_dividas(),
        "reserva_atual": round(DATA.get("reserva_atual", 0), 2),
        "reserva_meta": round(DATA.get("reserva_meta", 0), 2)
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

def parse_posso_gastar(msg):
    parts = msg.split()
    if len(parts) >= 4 and parts[0] == "posso" and parts[1] == "gastar":
        try:
            val = float(parts[2].replace(",", "."))
            desc = " ".join(parts[3:])
            return desc, val
        except:
            return None, None
    return None, None

def get_session(chat_id):
    sid = str(chat_id)
    if sid not in DATA["telegram_sessions"]:
        DATA["telegram_sessions"][sid] = {}
    return DATA["telegram_sessions"][sid]

def clear_session(chat_id):
    DATA["telegram_sessions"][str(chat_id)] = {}
    save_data()

def list_cards_text():
    return "\n".join([f"- {c['nome']}" for c in DATA["cartoes"]])

def upcoming_accounts_text():
    abertas = [c for c in DATA["contas"] if not c.get("pago")]
    if not abertas:
        return "Nenhuma conta aberta."
    abertas = sorted(abertas, key=lambda x: x["vencimento"])
    linhas = ["Contas abertas:"]
    for c in abertas:
        linhas.append(f"- {c['nome']} | R$ {c['valor']:.2f} | vence dia {c['vencimento']}")
    return "\n".join(linhas)

def mark_paid(name):
    n = norm(name)
    for c in DATA["contas"]:
        if norm(c["nome"]) == n:
            c["pago"] = True
            save_data()
            return f"Conta {c['nome']} marcada como paga."
    return "Conta não encontrada."

def current_mode():
    if total_dividas() > 0:
        return "recuperacao"
    if DATA.get("reserva_atual", 0) < DATA.get("reserva_meta", 0):
        return "reserva"
    return "crescimento"

def recommended_reserve_plan():
    meta = float(DATA.get("reserva_meta", 12000))
    prazo = 15
    faltante = max(meta - float(DATA.get("reserva_atual", 0)), 0)
    por_mes = round(faltante / prazo, 2) if prazo else faltante
    return meta, prazo, por_mes

def strict_plan_text():
    a = analysis()
    mode = current_mode()
    if mode == "recuperacao":
        target_3m = round(a["divida_total"] / 3, 2)
        target_4m = round(a["divida_total"] / 4, 2)
        return (
            "Plano critico atual\n"
            f"Divida total: R$ {a['divida_total']:.2f}\n"
            f"Meta agressiva para 3 meses: R$ {target_3m:.2f}/mes\n"
            f"Meta alternativa para 4 meses: R$ {target_4m:.2f}/mes\n"
            "Prioridade:\n- pagar contas abertas\n- nao fazer novas compras no cartao\n- usar renda extra para reduzir divida"
        )
    if mode == "reserva":
        meta, prazo, por_mes = recommended_reserve_plan()
        return (
            "Plano de reserva\n"
            f"Reserva atual: R$ {a['reserva_atual']:.2f}\n"
            f"Meta: R$ {meta:.2f}\n"
            f"Prazo maximo: {prazo} meses\n"
            f"Sugestao mensal: R$ {por_mes:.2f}"
        )
    return "Plano de crescimento: manter disciplina, reservar para viagem e investir com seguranca."

def can_spend_response(descricao, valor):
    a = analysis()
    categoria = infer_category(descricao)
    limite = DATA["limites"].get(categoria, 0)
    gasto_atual = a["categorias"].get(categoria, 0)
    novo_total_categoria = gasto_atual + valor
    novo_saldo = a["saldo"] - valor
    div = a["divida_total"]
    linhas = [
        f"Analise critica para gasto: {descricao} - R$ {valor:.2f}",
        f"Categoria: {categoria}",
        f"Gasto atual na categoria: R$ {gasto_atual:.2f}",
        f"Limite da categoria: R$ {limite:.2f}",
        f"Novo total da categoria: R$ {novo_total_categoria:.2f}",
        f"Saldo projetado apos esse gasto: R$ {novo_saldo:.2f}",
        f"Divida total atual: R$ {div:.2f}",
        ""
    ]
    if current_mode() == "recuperacao":
        if novo_saldo < 0 or novo_total_categoria > limite or div > 0:
            linhas.append("Nao recomendo esse gasto agora.")
            linhas.append("Voce esta em recuperacao e precisa de disciplina.")
            linhas.append("Se gastar, vai atrasar sua saida do negativo.")
        else:
            linhas.append("Tecnicamente cabe, mas nao e o ideal agora.")
    elif current_mode() == "reserva":
        if novo_total_categoria > limite:
            linhas.append("Nao recomendo. Esse gasto estoura o limite e atrasa sua reserva.")
        else:
            linhas.append("Pode gastar, mas com disciplina.")
    else:
        linhas.append("Pode gastar, mas sempre dentro do planejamento.")
    return "\n".join(linhas)

def monthly_advisor():
    a = analysis()
    mode = current_mode()
    if mode == "recuperacao":
        target_3m = round(a["divida_total"] / 3, 2)
        target_4m = round(a["divida_total"] / 4, 2)
        return (
            "Analise mensal estrategica\n"
            f"Receita total: R$ {a['receita_total']:.2f}\n"
            f"Contas abertas: R$ {a['contas_abertas']:.2f}\n"
            f"Gastos do mes: R$ {a['gastos_mes']:.2f}\n"
            f"Saldo projetado: R$ {a['saldo']:.2f}\n"
            f"Divida total: R$ {a['divida_total']:.2f}\n\n"
            f"Saida agressiva em 3 meses: R$ {target_3m:.2f}/mes\n"
            f"Saida alternativa em 4 meses: R$ {target_4m:.2f}/mes\n"
            "Acao do mes:\n- cortar lazer e extras ao minimo\n- nao aumentar cartao\n- usar qualquer renda extra para reduzir divida"
        )
    if mode == "reserva":
        meta, prazo, por_mes = recommended_reserve_plan()
        return (
            "Analise mensal estrategica\n"
            f"Reserva atual: R$ {a['reserva_atual']:.2f}\n"
            f"Meta: R$ {meta:.2f}\n"
            f"Prazo maximo: {prazo} meses\n"
            f"Sugestao mensal: R$ {por_mes:.2f}"
        )
    return "Analise mensal estrategica: voce ja pode focar em viagem e investimentos conservadores."

def ai_response(user_text):
    txt = norm(user_text)
    if "posso gastar" in txt:
        desc, val = parse_posso_gastar(txt)
        if desc and val is not None:
            return can_spend_response(desc, val)
    if "economizar" in txt or "onde cortar" in txt:
        a = analysis()
        return (
            "Onde cortar agora:\n"
            "- lazer no maximo R$ 100\n"
            "- evitar compras novas no cartao\n"
            "- priorizar contas abertas e divida\n"
            "- usar renda extra para reduzir o rombo\n"
            f"Hoje sua divida total esta em R$ {a['divida_total']:.2f}."
        )
    if "investir" in txt:
        if current_mode() != "crescimento":
            return "Ainda nao e hora de investir. Primeiro saia do negativo e conclua a reserva."
        return "Agora sim faz sentido pensar em Tesouro Selic, CDB com liquidez, ETFs e FIIs."
    if "reserva" in txt:
        meta, prazo, por_mes = recommended_reserve_plan()
        return (
            f"Meta de reserva: R$ {meta:.2f}\n"
            f"Prazo maximo: {prazo} meses\n"
            f"Sugestao base: R$ {por_mes:.2f}/mes\n"
            "Enquanto houver divida, a prioridade e quitar."
        )
    if "plano" in txt or "mes" in txt:
        return monthly_advisor()
    a = analysis()
    return (
        "IA Financeira\n"
        f"Receita total: R$ {a['receita_total']:.2f}\n"
        f"Contas abertas: R$ {a['contas_abertas']:.2f}\n"
        f"Gastos do mes: R$ {a['gastos_mes']:.2f}\n"
        f"Saldo projetado: R$ {a['saldo']:.2f}\n"
        f"Divida total: R$ {a['divida_total']:.2f}\n\n"
        "Minha leitura:\n- foco total em sair do negativo\n- evitar novas compras parceladas\n- usar qualquer renda extra para reduzir divida\n- manter lazer no minimo"
    )

def handle_telegram(chat_id, text):
    s = get_session(chat_id)
    msg = norm(text)

    if msg.startswith("ia ") or msg in ["ia", "me ajuda", "me oriente", "o que faço agora", "como economizar", "investir", "reserva"]:
        question = msg[3:] if msg.startswith("ia ") else msg
        return ai_response(question)

    desc_pg, val_pg = parse_posso_gastar(msg)
    if desc_pg and val_pg is not None:
        return can_spend_response(desc_pg, val_pg)

    if msg in ["status", "/status"]:
        a = analysis()
        return (
            f"Status\nReceita total: R$ {a['receita_total']:.2f}\n"
            f"Contas abertas: R$ {a['contas_abertas']:.2f}\n"
            f"Gastos do mes: R$ {a['gastos_mes']:.2f}\n"
            f"Saldo projetado: R$ {a['saldo']:.2f}\n"
            f"Divida total: R$ {a['divida_total']:.2f}"
        )

    if msg in ["analise", "/analise", "análise", "analise do mes", "analise do mês"]:
        return monthly_advisor()

    if msg in ["plano", "/plano"]:
        return strict_plan_text()

    if msg in ["contas", "/contas"]:
        return upcoming_accounts_text()

    if msg.startswith("pagar ") or msg.startswith("/pagar "):
        name = msg.replace("/", "", 1).split(" ", 1)[1]
        return mark_paid(name)

    if msg.startswith("extra ") or msg.startswith("/extra "):
        val = float(msg.split()[1].replace(",", "."))
        DATA["receita_extra"] = val
        save_data()
        a = analysis()
        return f"Receita extra atualizada para R$ {val:.2f}\nReceita total do mes: R$ {a['receita_total']:.2f}"

    if s.get("awaiting") == "forma":
        if msg in ["dinheiro", "pix", "debito", "débito"]:
            item = add_purchase(s["descricao"], s["valor"], "dinheiro", None)
            clear_session(chat_id)
            a = analysis()
            gasto_cat = a["categorias"].get(item["categoria"], 0)
            limite = DATA["limites"].get(item["categoria"], 0)
            restante = limite - gasto_cat
            return (
                f"Lancado em dinheiro.\nCategoria: {item['categoria']}\n"
                f"Total no mes em {item['categoria']}: R$ {gasto_cat:.2f}\n"
                f"Restante do limite: R$ {restante:.2f}"
            )
        elif msg in ["cartao", "cartão"]:
            s["awaiting"] = "cartao"
            save_data()
            return f"Qual cartao?\n{list_cards_text()}\nOu responda: novo"
        else:
            return "Responda: dinheiro, pix, debito ou cartao."

    if s.get("awaiting") == "cartao":
        if msg == "novo":
            s["awaiting"] = "novo_cartao_nome"
            save_data()
            return "Digite o nome do novo cartao."
        if not card_by_name(msg):
            return f"Cartao nao encontrado.\nEscolha um existente:\n{list_cards_text()}\nOu responda: novo"
        item = add_purchase(s["descricao"], s["valor"], "cartao", msg)
        clear_session(chat_id)
        fatura = item["fatura"]
        return (
            f"Compra registrada\nDescricao: {item['descricao']}\nCategoria: {item['categoria']}\n"
            f"Cartao: {msg}\nValor: R$ {item['valor']:.2f}\n"
            f"Fatura: {fatura['mes']:02d}/{fatura['ano']} vence dia {fatura['vencimento']}\n"
            f"Melhor dia aplicado: {fatura['melhor_dia_utilizado']}"
        )

    if s.get("awaiting") == "novo_cartao_nome":
        s["novo_cartao_nome"] = msg
        s["awaiting"] = "novo_cartao_vencimento"
        save_data()
        return "Digite o dia de vencimento do novo cartao. Ex.: 12"

    if s.get("awaiting") == "novo_cartao_vencimento":
        try:
            s["novo_cartao_vencimento"] = int(msg)
            s["awaiting"] = "novo_cartao_melhor_dia"
            save_data()
            return "Digite o melhor dia de compra. Ex.: 8"
        except:
            return "Digite apenas o numero do dia de vencimento."

    if s.get("awaiting") == "novo_cartao_melhor_dia":
        try:
            DATA["cartoes"].append({
                "nome": s["novo_cartao_nome"],
                "vencimento": int(s["novo_cartao_vencimento"]),
                "melhor_dia_compra": int(msg)
            })
            save_data()
            item = add_purchase(s["descricao"], s["valor"], "cartao", s["novo_cartao_nome"])
            clear_session(chat_id)
            return f"Novo cartao criado e compra lancada em {item['cartao']}."
        except:
            return "Digite apenas o numero do melhor dia de compra."

    if msg.startswith("parcela ") or msg.startswith("/parcela "):
        parts = msg.replace("/", "").split()
        if len(parts) >= 5:
            cart = parts[1]
            valor = float(parts[2].replace(",", "."))
            total = int(parts[3])
            desc = " ".join(parts[4:])
            if not card_by_name(cart):
                return "Cartao nao encontrado para parcelado."
            criadas = add_installment(desc, valor, total, cart)
            primeira = criadas[0]
            ultima = criadas[-1]
            return (
                f"Parcelado criado\n{desc}\nCartao: {cart}\nValor parcela: R$ {valor:.2f}\n"
                f"Total de parcelas: {total}\nPrimeira fatura: {primeira['mes_ref']}\nUltima fatura: {ultima['mes_ref']}"
            )

    desc, val = parse_simple_message(msg.replace("/", ""))
    if desc and val is not None:
        s["descricao"] = desc
        s["valor"] = val
        s["awaiting"] = "forma"
        save_data()
        categoria = infer_category(desc)
        return f"Entendi: {desc} - R$ {val:.2f}\nCategoria sugerida: {categoria}\nFoi no dinheiro ou cartao?"

    return (
        "Exemplos:\n"
        "- status\n"
        "- analise\n"
        "- plano\n"
        "- contas\n"
        "- pagar casa\n"
        "- extra 300\n"
        "- ia como economizar\n"
        "- ia posso gastar 50 lanche\n"
        "- ia plano do mes\n"
        "- lanche 30\n"
        "- parcela samsung 134 10 tv"
    )

@app.route("/")
def home():
    return render_template("dashboard.html")

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "nexus-v53"})

@app.route("/api/status")
def api_status():
    return jsonify(analysis())

@app.route("/api/cartoes")
def api_cartoes():
    rows = []
    today = current_date()
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
    text = (((data.get("message") or {}).get("text")) or "").strip()
    chat_id = (((data.get("message") or {}).get("chat")) or {}).get("id")
    if not text or not chat_id:
        return jsonify({"ok": True})
    reply = handle_telegram(chat_id, text)
    ok, detail = telegram_send(chat_id, reply)
    return jsonify({"ok": ok, "detail": str(detail)[:200]})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
