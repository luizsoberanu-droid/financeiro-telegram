from flask import Flask, request, jsonify, render_template
from datetime import datetime, date, timedelta
import json, os, calendar, requests

app = Flask(__name__)
DATA_FILE = "data_store.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

# =========================
# BASE
# =========================

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN não configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=20,
        )
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
            for k, v in data.items():
                if k in base:
                    base[k] = v
            return base
        except Exception:
            return default_data()
    return default_data()

DATA = load_data()

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(DATA, f, ensure_ascii=False, indent=2)

# =========================
# HELPERS
# =========================

def now_date():
    return datetime.now().date()

def month_key(dt):
    return f"{dt.year:04d}-{dt.month:02d}"

def month_name(key):
    y, m = key.split("-")
    nomes = ["janeiro","fevereiro","março","abril","maio","junho","julho","agosto","setembro","outubro","novembro","dezembro"]
    return f"{nomes[int(m)-1].capitalize()}/{y}"

def normalize(text):
    return (text or "").strip().lower()

def next_id(items):
    return max([x.get("id", 0) for x in items], default=0) + 1

CATEGORY_MAP = {
    "lazer": ["lanche", "passeio", "cinema", "sorvete", "pizza", "hamburguer", "hambúrguer", "açai", "acai"],
    "combustivel": ["gasolina", "etanol", "combustivel", "combustível"],
    "extras": ["mercado", "farmacia", "farmácia", "remedio", "remédio", "compra", "pix", "uber", "ifood"]
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
    return {
        "ano": y,
        "mes": m,
        "mes_ref": f"{y:04d}-{m:02d}",
        "vencimento": int(card["vencimento"]),
        "melhor_dia_utilizado": best.isoformat()
    }

def business_days_until_due(vencimento):
    today = now_date()
    target = date(today.year, today.month, min(vencimento, calendar.monthrange(today.year, today.month)[1]))
    if target < today:
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

def fixed_open_total():
    return round(sum(c["valor"] for c in DATA["contas_fixas"] if not c.get("pago", False)), 2)

def debt_total():
    return round(sum(DATA["dividas"].values()), 2)

def monthly_income():
    return round(DATA["receita_fixa"] + DATA["receita_extra"], 2)

def current_mode():
    if debt_total() > 0:
        return "recuperacao"
    if DATA["reserva_atual"] < DATA["meta_reserva"]:
        return "reserva"
    return "crescimento"

# =========================
# DADOS / LANÇAMENTOS
# =========================

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
        "valor": round(float(valor), 2),
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
            "parcela_atual": i + 1,
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

# =========================
# ANÁLISE
# =========================

def analyst_summary():
    receita_total = monthly_income()
    fixos = fixed_total()
    dividas = debt_total()
    meta_3m = round(dividas / 3, 2) if dividas > 0 else 0
    livres = receita_total - fixos
    status = "critica controlavel" if dividas > 0 and livres < meta_3m else "apertada mas recuperavel" if dividas > 0 else "estavel"
    linhas = [
        "Diagnostico financeiro",
        f"Receita total: R$ {receita_total:.2f}",
        f"Comprometido fixo: R$ {fixos:.2f}",
        f"Divida total: R$ {dividas:.2f}",
        f"Meta em 3 meses: R$ {meta_3m:.2f}/mes",
        f"Caixa livre antes dos variaveis: R$ {livres:.2f}",
        f"Situacao: {status}"
    ]
    if dividas > 0:
        linhas += [
            "",
            "Plano sugerido:",
            "- segurar lazer em ate R$ 100",
            "- evitar novo cartao",
            "- gerar renda extra",
            "- priorizar Nubank, Santander, Samsung, IPVA e negativo"
        ]
    else:
        linhas += [
            "",
            "Plano sugerido:",
            "- manter controle rigido",
            "- formar reserva",
            "- depois abrir meta de viagem e investimento"
        ]
    return "\n".join(linhas)

def overall_analysis():
    mref = month_key(now_date())
    cat, lancs = totals_for_month(mref)
    cards, details = card_totals_for_month(mref)
    receita_total = monthly_income()
    gastos_mes = round(sum(cat.values()), 2)
    contas_abertas = fixed_open_total()
    saldo = round(receita_total - gastos_mes - contas_abertas, 2)
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
        "receita_total": round(receita_total, 2),
        "receita_fixa": round(DATA["receita_fixa"], 2),
        "receita_extra": round(DATA["receita_extra"], 2),
        "gastos_mes": gastos_mes,
        "contas_abertas": contas_abertas,
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
        "analista": analyst_summary(),
        "modo_atual": current_mode()
    }

def reserve_plan():
    faltante = max(DATA["meta_reserva"] - DATA["reserva_atual"], 0)
    prazo = 15
    por_mes = round(faltante / prazo, 2) if prazo else faltante
    return faltante, prazo, por_mes

def can_spend_response(descricao, valor):
    a = overall_analysis()
    categoria = infer_category(descricao)
    limite = DATA["limites"].get(categoria, 0)
    gasto_atual = a["categorias"].get(categoria, 0)
    novo_total = gasto_atual + valor
    novo_saldo = a["saldo"] - valor
    linhas = [
        f"Analise critica para gasto: {descricao} - R$ {valor:.2f}",
        f"Categoria: {categoria}",
        f"Gasto atual na categoria: R$ {gasto_atual:.2f}",
        f"Limite da categoria: R$ {limite:.2f}",
        f"Novo total da categoria: R$ {novo_total:.2f}",
        f"Saldo projetado apos esse gasto: R$ {novo_saldo:.2f}",
        f"Divida total atual: R$ {a['divida_total']:.2f}",
        ""
    ]
    if current_mode() == "recuperacao":
        if novo_saldo < 0 or novo_total > limite or a["divida_total"] > 0:
            linhas += [
                "Nao recomendo esse gasto agora.",
                "Voce esta em recuperacao e precisa de disciplina.",
                "Se gastar, vai atrasar sua saida do negativo."
            ]
        else:
            linhas += ["Tecnicamente cabe, mas eu evitaria."]
    elif current_mode() == "reserva":
        if novo_total > limite:
            linhas += ["Nao recomendo. Esse gasto estoura o limite e atrasa sua reserva."]
        else:
            linhas += ["Pode gastar, mas com disciplina."]
    else:
        linhas += ["Pode gastar, mas sempre dentro do planejamento."]
    return "\n".join(linhas)

def monthly_advisor():
    a = overall_analysis()
    mode = current_mode()
    if mode == "recuperacao":
        meta3 = round(a["divida_total"]/3,2) if a["divida_total"] > 0 else 0
        meta4 = round(a["divida_total"]/4,2) if a["divida_total"] > 0 else 0
        return (
            "Analise mensal estrategica\n"
            f"Receita total: R$ {a['receita_total']:.2f}\n"
            f"Comprometido fixo: R$ {fixed_total():.2f}\n"
            f"Gastos do mes: R$ {a['gastos_mes']:.2f}\n"
            f"Saldo atual do mes: R$ {a['saldo']:.2f}\n"
            f"Divida total: R$ {a['divida_total']:.2f}\n\n"
            f"Saida agressiva em 3 meses: R$ {meta3:.2f}/mes\n"
            f"Saida alternativa em 4 meses: R$ {meta4:.2f}/mes\n"
            "Acao do mes:\n- cortar lazer e extras ao minimo\n- nao aumentar cartao\n- usar qualquer renda extra para reduzir divida"
        )
    elif mode == "reserva":
        faltante, prazo, por_mes = reserve_plan()
        return (
            "Plano de reserva\n"
            f"Reserva atual: R$ {DATA['reserva_atual']:.2f}\n"
            f"Meta da reserva: R$ {DATA['meta_reserva']:.2f}\n"
            f"Faltante: R$ {faltante:.2f}\n"
            f"Prazo maximo: {prazo} meses\n"
            f"Sugestao mensal: R$ {por_mes:.2f}"
        )
    else:
        return (
            "Plano de crescimento\n"
            "Voce ja saiu do negativo e concluiu a reserva.\n"
            "Agora priorize meta de viagem e investimentos conservadores."
        )

def aplicar_extra_na_divida(valor):
    restante = round(float(valor), 2)
    ordem = ["nubank", "santander", "samsung", "ipva", "negativo"]
    abatimentos = []

    for nome in ordem:
        atual = float(DATA["dividas"].get(nome, 0))
        if atual <= 0:
            continue
        abatido = min(atual, restante)
        DATA["dividas"][nome] = round(atual - abatido, 2)
        restante = round(restante - abatido, 2)
        abatimentos.append((nome, abatido, DATA["dividas"][nome]))
        if restante <= 0:
            break

    save_data()
    return abatimentos, restante

def ai_response(user_text):
    txt = user_text.lower()
    a = overall_analysis()

    receita = a["receita_total"]
    contas = sum(c["valor"] for c in DATA["contas_fixas"] if not c.get("pago", False))
    gastos = a["gastos_mes"]
    saldo = a["saldo"]
    divida = a["divida_total"]
    reserva = a["reserva_atual"]

    resposta = []

    resposta.append("Análise financeira completa")
    resposta.append("")
    resposta.append(f"Receita: R$ {receita:.2f}")
    resposta.append(f"Contas abertas: R$ {contas:.2f}")
    resposta.append(f"Gastos do mes: R$ {gastos:.2f}")
    resposta.append(f"Saldo projetado: R$ {saldo:.2f}")
    resposta.append(f"Divida total: R$ {divida:.2f}")
    resposta.append("")

    if divida > 0:
        resposta.append("Situacao atual: NEGATIVO")
    elif reserva < DATA["meta_reserva"]:
        resposta.append("Situacao atual: CONSTRUINDO RESERVA")
    else:
        resposta.append("Situacao atual: ESTAVEL / CRESCIMENTO")

    resposta.append("")

    if "gastar" in txt or "posso" in txt or "quanto posso" in txt:
        if divida > 0:
            resposta.append("Resposta direta: NAO recomendo gastar.")
            resposta.append("Voce ainda esta pagando erros passados.")
            resposta.append("Cada gasto agora prolonga sua recuperacao.")
        elif saldo < 0:
            resposta.append("Resposta direta: NAO pode gastar.")
            resposta.append("Seu saldo ja esta comprometido.")
        else:
            resposta.append("Voce ate pode gastar, mas com controle.")
            resposta.append("Se nao for essencial, eu evitaria.")

    elif "divida" in txt or "dívida" in txt or "negativo" in txt:
        meta_3 = divida / 3 if divida > 0 else 0
        resposta.append("Plano direto para sair da divida:")
        resposta.append(f"- Meta agressiva (3 meses): R$ {meta_3:.2f}/mes")
        resposta.append("- Cortar lazer quase totalmente")
        resposta.append("- NAO usar cartao")
        resposta.append("- Usar qualquer renda extra para divida")
        resposta.append("- Priorizar contas que vencem primeiro")

    elif "economizar" in txt or "cortar" in txt:
        resposta.append("Onde voce deve cortar imediatamente:")
        resposta.append("- Lazer")
        resposta.append("- Compras por impulso")
        resposta.append("- Cartao de credito")
        resposta.append("- Extras nao essenciais")

    elif "reserva" in txt:
        meta = DATA["meta_reserva"]
        faltante = meta - reserva
        mensal = faltante / 12 if faltante > 0 else 0
        resposta.append("Plano de reserva:")
        resposta.append(f"- Meta: R$ {meta:.2f}")
        resposta.append(f"- Falta: R$ {faltante:.2f}")
        resposta.append(f"- Sugestao mensal: R$ {mensal:.2f}")

    elif "investir" in txt:
        if divida > 0:
            resposta.append("Ainda NAO e hora de investir.")
            resposta.append("Voce precisa sair da divida primeiro.")
        else:
            resposta.append("Agora sim faz sentido investir.")
            resposta.append("Sugestoes:")
            resposta.append("- Tesouro Selic")
            resposta.append("- CDB com liquidez")
            resposta.append("- ETFs no longo prazo")

    else:
        resposta.append("Minha recomendacao geral:")
        resposta.append("- Priorize sair do negativo")
        resposta.append("- Controle rigoroso de gastos")
        resposta.append("- Nao trate sobra como dinheiro livre")
        resposta.append("- Disciplina agora define seu futuro financeiro")

    return "\n".join(resposta)

# =========================
# TELEGRAM
# =========================

def session(chat_id):
    sid = str(chat_id)
    DATA["telegram_sessions"].setdefault(sid, {})
    return DATA["telegram_sessions"][sid]

def cards_list():
    return "\n".join([f"- {c['nome']}" for c in DATA["cartoes"]])

def handle_telegram(chat_id, message):
    s = session(chat_id)
    msg = normalize(message)

    palavras_ia = [
        "gastar", "posso", "quanto", "divida", "dívida",
        "negativo", "economizar", "cortar", "investir",
        "reserva", "dinheiro", "plano", "ajuda", "como",
        "conta", "salario", "salário", "mês", "mes"
    ]

    if any(p in msg for p in palavras_ia):
        return ai_response(msg)

    if msg.startswith("posso gastar"):
        try:
            parts = msg.split()
            valor = float(parts[2].replace(",", "."))
            descricao = " ".join(parts[3:])
            return can_spend_response(descricao, valor)
        except Exception:
            return "Use: posso gastar 50 lanche"

    if msg in ["status", "/status"]:
        a = overall_analysis()
        return f"Status\nReceita total: R$ {a['receita_total']:.2f}\nGastos do mes: R$ {a['gastos_mes']:.2f}\nSaldo: R$ {a['saldo']:.2f}\nDivida total: R$ {a['divida_total']:.2f}"

    if msg in ["analise", "/analise", "análise", "analise do mes", "analise do mês"]:
        return monthly_advisor()

    if msg in ["plano", "/plano"]:
        return monthly_advisor()

    if msg in ["contas", "/contas"]:
        linhas = ["Contas fixas"]
        for c in DATA["contas_fixas"]:
            status = "paga" if c.get("pago", False) else "aberta"
            linhas.append(f"- {c['nome']} | R$ {c['valor']:.2f} | vence {c['vencimento']} | {status}")
        return "\n".join(linhas)

    if msg.startswith("pagar ") or msg.startswith("/pagar "):
        alvo = normalize(msg.split(" ", 1)[1])
        for c in DATA["contas_fixas"]:
            if normalize(c["nome"]) == alvo:
                c["pago"] = True
                save_data()
                return f"{alvo} marcado como pago."
        for c in DATA["cartoes"]:
            if normalize(c["nome"]) == alvo:
                c["pago"] = True
                save_data()
                return f"Cartao {alvo} marcado como pago."
        return "Nao encontrei essa conta/cartao."

    if msg.startswith("extra ") or msg.startswith("/extra "):
        try:
            val = float(msg.split()[1].replace(",", "."))
            DATA["receita_extra"] = round(DATA.get("receita_extra", 0) + val, 2)
            abatimentos, restante = aplicar_extra_na_divida(val)
            save_data()

            linhas = [f"Receita extra registrada: R$ {val:.2f}", ""]
            if abatimentos:
                linhas.append("Valor aplicado automaticamente na divida:")
                for nome, abatido, saldo_restante in abatimentos:
                    linhas.append(f"- {nome}: abatido R$ {abatido:.2f} | restante R$ {saldo_restante:.2f}")
            else:
                linhas.append("Nenhuma divida foi abatida.")

            if restante > 0:
                linhas.append("")
                linhas.append(f"Sobrou R$ {restante:.2f} apos quitar as dividas priorizadas.")

            linhas.append("")
            linhas.append(f"Divida total atual: R$ {debt_total():.2f}")
            return "\n".join(linhas)
        except:
            return "Use: extra 300"

    if s.get("awaiting") == "forma":
        if msg in ["dinheiro", "pix", "debito", "débito"]:
            item = add_lancamento(s["descricao"], s["valor"], "dinheiro")
            s.clear()
            a = overall_analysis()
            gasto_cat = a["categorias"].get(item["categoria"], 0)
            limite = DATA["limites"].get(item["categoria"], 0)
            restante = round(limite - gasto_cat, 2)
            save_data()
            if restante >= 0:
                return f"Lancado em dinheiro.\nCategoria: {item['categoria']}\nTotal: R$ {gasto_cat:.2f}\nRestante: R$ {restante:.2f}"
            return f"Lancado em dinheiro.\nCategoria: {item['categoria']}\nTotal: R$ {gasto_cat:.2f}\nExcesso: R$ {abs(restante):.2f}"
        if msg in ["cartao", "cartão"]:
            s["awaiting"] = "cartao"
            save_data()
            return f"Qual cartao?\n{cards_list()}\nOu responda: novo"
        return "Responda: dinheiro, pix, debito ou cartao."

    if s.get("awaiting") == "cartao":
        if msg == "novo":
            s["awaiting"] = "novo_cartao_nome"
            save_data()
            return "Digite o nome do novo cartao."
        card = get_card(msg)
        if not card:
            return f"Cartao nao encontrado.\nEscolha um existente:\n{cards_list()}\nOu responda: novo"
        item = add_lancamento(s["descricao"], s["valor"], "cartao", card["nome"])
        s.clear()
        return f"Compra registrada\nDescricao: {item['descricao']}\nCartao: {item['cartao']}\nValor: R$ {item['valor']:.2f}\nFatura: {item['fatura']['mes_ref']} vence dia {item['fatura']['vencimento']}\nMelhor dia aplicado: {item['fatura']['melhor_dia_utilizado']}"

    if s.get("awaiting") == "novo_cartao_nome":
        s["novo_nome"] = msg
        s["awaiting"] = "novo_cartao_venc"
        save_data()
        return "Digite o vencimento do cartao. Ex.: 12"

    if s.get("awaiting") == "novo_cartao_venc":
        try:
            s["novo_venc"] = int(msg)
            s["awaiting"] = "novo_cartao_melhor"
            save_data()
            return "Digite o melhor dia de compra. Ex.: 8"
        except:
            return "Digite apenas o numero do vencimento."

    if s.get("awaiting") == "novo_cartao_melhor":
        try:
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
            return f"Novo cartao criado e compra lancada em {item['cartao']}."
        except:
            return "Digite apenas o numero do melhor dia de compra."

    if msg.startswith("parcela ") or msg.startswith("/parcela "):
        parts = msg.replace("/", "").split()
        if len(parts) >= 5:
            cart = parts[1]
            valor = float(parts[2].replace(",", "."))
            total = int(parts[3].split("/")[1]) if "/" in parts[3] else int(parts[3])
            desc = " ".join(parts[4:])
            if not get_card(cart):
                return "Cartao nao encontrado para parcelado."
            criadas = add_parcelado(desc, valor, total, cart)
            return f"Parcelado criado\n{desc}\nCartao: {cart}\nParcelas: {len(criadas)}\nPrimeira fatura: {criadas[0]['mes_ref']}"

    parts = msg.replace("/", "").split()
    if len(parts) >= 2:
        try:
            valor = float(parts[-1].replace(",", "."))
            descricao = " ".join(parts[:-1])
            s["descricao"] = descricao
            s["valor"] = valor
            s["awaiting"] = "forma"
            save_data()
            return f"Entendi: {descricao} - R$ {valor:.2f}\nCategoria sugerida: {infer_category(descricao)}\nFoi no dinheiro ou cartao?"
        except:
            pass

    return "Me pergunte algo sobre sua situacao financeira ou lance um gasto."

# =========================
# ROTAS DO PAINEL
# =========================

@app.route("/")
def home():
    try:
        return render_template("dashboard.html")
    except:
        return jsonify({"ok": True, "message": "Painel preservado. App atualizado para IA e Telegram."})

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "nexus-bank-final"})

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
    return jsonify({"ok": False, "erro": "nao encontrado"}), 404

# =========================
# WEBHOOK TELEGRAM
# =========================

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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
