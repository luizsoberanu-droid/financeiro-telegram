
from flask import Flask, request, jsonify, render_template, redirect
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
        {"id":"casa","nome":"Casa","valor":732.92,"vencimento_dia":10,"paga":False,"ativa":True},
        {"id":"carro","nome":"Carro","valor":1469.70,"vencimento_dia":5,"paga":False,"ativa":True},
        {"id":"condominio","nome":"Condomínio","valor":365.00,"vencimento_dia":12,"paga":False,"ativa":True},
        {"id":"faculdade_usuario","nome":"Faculdade usuário","valor":360.00,"vencimento_dia":7,"paga":False,"ativa":True},
        {"id":"faculdade_esposa","nome":"Faculdade esposa","valor":200.00,"vencimento_dia":7,"paga":False,"ativa":True},
        {"id":"internet","nome":"Internet e redes móveis","valor":220.00,"vencimento_dia":15,"paga":False,"ativa":True},
        {"id":"ipva","nome":"IPVA","valor":1161.00,"vencimento_dia":10,"paga":False,"ativa":True}
    ],
    "debts": {
        "negativo": 2999.94,
        "ipva": 1161.0,
        "samsung": 134.0,
        "santander": 996.12,
        "nubank": 1006.05
    },
    "entries": [],
    "reminders_log": []
}

SMART_MAP = {
    "lanche":"lazer", "passeio":"lazer", "cinema":"lazer", "sorvete":"lazer", "pizza":"lazer",
    "gasolina":"combustivel_carro", "etanol":"combustivel_carro",
    "moto":"combustivel_moto",
    "netflix":"assinaturas", "amazon":"assinaturas", "prime":"assinaturas", "crunchyroll":"assinaturas", "fortnite":"assinaturas",
    "cartao":"cartao", "nubank":"cartao", "santander":"cartao", "samsung":"cartao",
    "mercado":"extras", "farmacia":"extras", "remedio":"extras",
    "luz":"luz"
}

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # merge missing defaults
    for k,v in DEFAULT_DATA.items():
        if k not in data:
            data[k] = v
    return data

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def month_key(dt=None):
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m")

def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
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
    return [e for e in data["entries"] if e.get("month")==ym]

def monthly_category_totals(data, ym=None):
    totals={}
    for e in current_month_entries(data, ym):
        cat=e["category"]
        totals[cat]=round(totals.get(cat,0)+float(e["amount"]),2)
    return totals

def calculate_summary(data, ym=None):
    ym = ym or month_key()
    receita_total = float(data["config"]["receita_fixa"]) + float(data["config"].get("receita_extra",0))
    active_fixed = [a for a in data["fixed_accounts"] if a.get("ativa", True)]
    base_contas = round(sum(float(a["valor"]) for a in active_fixed),2)
    category_totals = monthly_category_totals(data, ym)
    gasto_lancado = round(sum(category_totals.values()),2)
    total_obrigacoes = round(base_contas + gasto_lancado,2)
    saldo = round(receita_total - total_obrigacoes,2)
    total_divida = round(sum(float(v) for v in data["debts"].values()),2)
    meta_3m = round(total_divida/3,2) if total_divida>0 else 0.0
    status = "VERDE" if saldo >= meta_3m else ("AMARELO" if saldo > 0 else "VERMELHO")
    return {
        "receita_total": receita_total,
        "base_contas": base_contas,
        "gasto_lancado": gasto_lancado,
        "saldo_projetado": saldo,
        "meta_ataque_mensal": meta_3m,
        "status": status,
        "category_totals": category_totals,
        "total_divida": total_divida
    }


def ai_analysis(data, ym=None):
    s = calculate_summary(data, ym)
    limits = data["limits"]
    extras = []
    for cat, total in s["category_totals"].items():
        lim = limits.get(cat)
        if lim is not None and total > lim:
            extras.append((cat, round(total - lim, 2)))

    receita_total = s["receita_total"]
    livre = s["saldo_projetado"]
    base = s["base_contas"]
    gasto = s["gasto_lancado"]
    total_divida = s["total_divida"]
    meta3 = s["meta_ataque_mensal"]

    linhas = []
    linhas.append(f"Receita total do mês: R$ {receita_total:.2f}")
    linhas.append(f"Base de contas: R$ {base:.2f}")
    linhas.append(f"Gastos lançados: R$ {gasto:.2f}")
    linhas.append(f"Saldo projetado: R$ {livre:.2f}")
    linhas.append(f"Dívida total atual: R$ {total_divida:.2f}")

    if livre <= 0:
        linhas.append("Situação: crítica. Você está sem margem mensal e precisa cortar gastos imediatamente.")
    elif livre < meta3:
        falta = max(0, meta3 - livre)
        linhas.append("Situação: fora do plano de quitação em 3 meses.")
        linhas.append(f"Falta gerar R$ {falta:.2f} de caixa neste mês para sustentar a meta agressiva.")
    else:
        linhas.append("Situação: dentro do plano de ataque. Continue protegendo o caixa e evitando novos parcelamentos.")

    if extras:
        linhas.append("Você passou do recomendado nestas categorias:")
        for cat, exc in extras:
            linhas.append(f"- {cat}: R$ {exc:.2f} acima")
    else:
        linhas.append("Nenhuma categoria estourou o limite recomendado neste mês.")

    alerts = due_alerts(data)
    if alerts:
        linhas.append("Contas que exigem atenção:")
        for a in alerts[:5]:
            linhas.append(f"- {a}")

    if total_divida > 0:
        linhas.append(f"Meta mensal para zerar em 3 meses: R$ {meta3:.2f}")

    if total_divida > 0 or livre <= meta3:
        linhas.append("Prioridade agora: pagar contas, segurar categorias variáveis e atacar dívidas. Reserva continua em espera.")
    else:
        target_months = 12
        mensal = max(data["config"]["meta_reserva"] / target_months, 200.0)
        sugestao = min(livre * 0.4, mensal)
        linhas.append(f"Sugestão de reserva: guardar R$ {sugestao:.2f}/mês.")

    linhas.append("Ação prática do mês:")
    linhas.append("- Evite novos gastos no cartão")
    linhas.append("- Mantenha lazer no mínimo")
    linhas.append("- Priorize contas próximas do vencimento e dívidas mais críticas")

    return "
".join(linhas)

def smart_category(desc):
    tokens = desc.lower().replace("/", " ").replace("-", " ").split()
    for t in tokens:
        if t in SMART_MAP:
            return SMART_MAP[t]
    return "extras"

def add_entry(data, description, amount, date_str=None, category=None):
    amount = float(amount)
    d = parse_date(date_str) if date_str else date.today()
    cat = category or smart_category(description)
    eid = f"e{int(datetime.now().timestamp()*1000)}"
    entry = {
        "id": eid,
        "date": d.isoformat(),
        "month": d.strftime("%Y-%m"),
        "description": description,
        "category": cat,
        "amount": amount
    }
    data["entries"].append(entry)
    save_data(data)
    return entry

def upcoming_accounts(data):
    out=[]
    today = date.today()
    for acc in data["fixed_accounts"]:
        if not acc.get("ativa", True):
            continue
        due = date(today.year, today.month, int(acc["vencimento_dia"]))
        # if date passed by more than 20 days, consider next month? keep current for overdue
        bd = business_days_until(due)
        status = "atrasada" if (due < today and not acc["paga"]) else ("paga" if acc["paga"] else "aberta")
        out.append({
            **acc,
            "due_date": due.isoformat(),
            "business_days_until": bd,
            "status": status
        })
    return sorted(out, key=lambda x: (x["status"]=="atrasada", x["business_days_until"] if x["business_days_until"]>=0 else 999), reverse=False)

def due_alerts(data):
    alerts=[]
    for acc in upcoming_accounts(data):
        if acc["status"] == "paga":
            continue
        if acc["status"] == "atrasada":
            alerts.append(f"{acc['nome']} está atrasada.")
        elif 0 <= acc["business_days_until"] <= int(data["config"].get("dias_uteis_alerta",3)):
            alerts.append(f"{acc['nome']} vence em {acc['business_days_until']} dia(s) útil(eis).")
    return alerts

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
        f"Base de contas: R$ {s['base_contas']:.2f}\n"
        f"Gasto lançado: R$ {s['gasto_lancado']:.2f}\n"
        f"Saldo projetado: R$ {s['saldo_projetado']:.2f}\n"
        f"Dívida total: R$ {s['total_divida']:.2f}\n"
        f"Meta ataque mensal: R$ {s['meta_ataque_mensal']:.2f}\n"
        f"Semáforo: {s['status']}"
    )

def command_plan(data):
    s = calculate_summary(data)
    if s["saldo_projetado"] >= s["meta_ataque_mensal"]:
        msg = "🟢 Dentro do plano."
    else:
        falta = max(0, s["meta_ataque_mensal"] - max(0,s["saldo_projetado"]))
        msg = f"🔴 Fora do plano. Falta gerar R$ {falta:.2f} de caixa neste mês."
    return (
        f"🔥 PLANO\n"
        f"Dívida total: R$ {s['total_divida']:.2f}\n"
        f"Prazo alvo: 3 meses\n"
        f"Meta mensal: R$ {s['meta_ataque_mensal']:.2f}\n"
        f"{msg}"
    )

def command_analysis(data):
    return "🤖 ANÁLISE\n" + ai_analysis(data)

def command_accounts(data):
    lines=["📅 CONTAS"]
    for acc in upcoming_accounts(data):
        lines.append(f"{acc['nome']} — R$ {float(acc['valor']):.2f} — vence dia {acc['vencimento_dia']} — {acc['status']}")
    return "\n".join(lines)


def parse_message(data, text):
    txt = (text or "").strip()
    low = txt.lower().strip()
    cmd = low[1:] if low.startswith("/") else low

    if cmd in ("status",):
        return command_status(data)
    if cmd in ("plano",):
        return command_plan(data)
    if cmd in ("analise", "análise"):
        return command_analysis(data)
    if cmd in ("contas", "vencimentos"):
        return command_accounts(data)

    if cmd.startswith("extra ") or cmd.startswith("receitaextra "):
        parts = cmd.split()
        if len(parts) >= 2:
            val = float(parts[1].replace(",", "."))
            data["config"]["receita_extra"] = val
            save_data(data)
            s = calculate_summary(data)
            return f"💰 Receita extra atualizada para R$ {val:.2f}
Receita total do mês: R$ {s['receita_total']:.2f}"

    if cmd.startswith("editar "):
        parts = txt.replace("/", "", 1).split()
        if len(parts) >= 3:
            campo = parts[1].lower()
            valor = float(parts[2].replace(",", "."))
            if campo in data["limits"]:
                data["limits"][campo] = valor
                save_data(data)
                return f"✏️ Limite de {campo} atualizado para R$ {valor:.2f}"
            if campo == "reserva":
                data["config"]["reserva_atual"] = valor
                save_data(data)
                return f"🛡️ Reserva atual atualizada para R$ {valor:.2f}"

    if cmd.startswith("pagar "):
        name = cmd.replace("pagar", "", 1).strip()
        for acc in data["fixed_accounts"]:
            if name and name in acc["nome"].lower():
                acc["paga"] = True
                save_data(data)
                return f"✅ Conta marcada como paga: {acc['nome']}"
        return "Conta não encontrada."

    if cmd.startswith("posso "):
        parts = cmd.split()
        if len(parts) >= 3:
            valor = float(parts[1].replace(",", "."))
            categoria = smart_category(" ".join(parts[2:]))
            atual = monthly_category_totals(data).get(categoria, 0.0)
            limite = data["limits"].get(categoria)
            if limite is None:
                return f"ℹ️ Categoria {categoria} não tem limite cadastrado."
            novo_total = atual + valor
            if novo_total > limite:
                excesso = novo_total - limite
                return f"❌ Não recomendado. {categoria} iria para R$ {novo_total:.2f}, acima do limite de R$ {limite:.2f} por R$ {excesso:.2f}."
            restante = limite - novo_total
            return f"⚠️ Pode, mas {categoria} ficará em R$ {novo_total:.2f} de R$ {limite:.2f}. Restante: R$ {restante:.2f}."

    parts = txt.split()
    if len(parts) == 1 and cmd in ("status","plano","analise","análise","contas","vencimentos"):
        return parse_message(data, "/" + cmd)

    if len(parts) >= 2:
        try:
            amount = float(parts[-1].replace(",", "."))
            desc = " ".join(parts[:-1])
            e = add_entry(data, desc, amount)
            totals = monthly_category_totals(data)
            total_cat = totals.get(e["category"], 0.0)
            limite = data["limits"].get(e["category"])
            resp = [f"✅ Lançado: {e['description']} — R$ {e['amount']:.2f}", f"Categoria: {e['category']}", f"Total no mês: R$ {total_cat:.2f}"]
            if limite is not None:
                restante = limite - total_cat
                if restante >= 0:
                    resp.append(f"Restante no limite: R$ {restante:.2f}")
                else:
                    resp.append(f"🚨 Passou R$ {abs(restante):.2f} do limite.")
            return "\n".join(resp)
        except Exception:
            pass
    return "Comando não reconhecido."

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "service": "nexus-dark-v45"})

@app.route("/api/status")
def api_status():
    data = load_data()
    summary = calculate_summary(data)
    alerts = due_alerts(data)
    months = {}
    for e in data["entries"]:
        months.setdefault(e["month"], []).append(e)
    return jsonify({
        "summary": summary,
        "config": data["config"],
        "limits": data["limits"],
        "debts": data["debts"],
        "accounts": upcoming_accounts(data),
        "alerts": alerts,
        "analysis": ai_analysis(data),
        "entries": current_month_entries(data),
        "monthlyGroups": months
    })

@app.route("/api/entry", methods=["POST"])
def api_entry():
    data = load_data()
    payload = request.get_json(force=True)
    entry = add_entry(data, payload.get("description",""), payload.get("amount",0), payload.get("date"), payload.get("category"))
    return jsonify({"ok": True, "entry": entry})

@app.route("/api/entry/<entry_id>", methods=["PUT"])
def api_entry_edit(entry_id):
    data = load_data()
    payload = request.get_json(force=True)
    for e in data["entries"]:
        if e["id"] == entry_id:
            e["description"] = payload.get("description", e["description"])
            e["category"] = payload.get("category", e["category"])
            e["amount"] = float(payload.get("amount", e["amount"]))
            e["date"] = payload.get("date", e["date"])
            e["month"] = e["date"][:7]
            save_data(data)
            return jsonify({"ok": True, "entry": e})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/account/<acc_id>", methods=["PUT"])
def api_account_edit(acc_id):
    data = load_data()
    payload = request.get_json(force=True)
    for a in data["fixed_accounts"]:
        if a["id"] == acc_id:
            for key in ["nome","valor","vencimento_dia","paga","ativa"]:
                if key in payload:
                    a[key] = payload[key]
            save_data(data)
            return jsonify({"ok": True, "account": a})
    return jsonify({"ok": False, "error": "not found"}), 404

@app.route("/api/config", methods=["PUT"])
def api_config():
    data = load_data()
    payload = request.get_json(force=True)
    for section in ["config", "limits", "debts"]:
        if section in payload:
            for k,v in payload[section].items():
                data[section][k] = v
    save_data(data)
    return jsonify({"ok": True})

@app.route("/webhooks/telegram", methods=["POST"])
def telegram_webhook():
    data = load_data()
    payload = request.get_json(force=True)
    if "message" not in payload:
        return jsonify({"ok": True})
    msg = payload["message"].get("text","")
    chat_id = payload["message"]["chat"]["id"]
    resp = parse_message(data, msg)
    telegram_send(resp, chat_id)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
