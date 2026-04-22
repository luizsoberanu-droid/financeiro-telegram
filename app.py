from flask import Flask, request, render_template, jsonify
import requests

app = Flask(__name__)

TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

DATA = {
    "receita": 5300,
    "fixos": {
        "casa": 732.92,
        "carro": 1469.70,
        "condominio": 365,
        "faculdade": 560,
    },
    "variaveis": {
        "luz": 270,
        "internet": 220,
        "combustivel": 320,
        "cachorro": 140,
        "assinaturas": 120,
        "manutencao": 100
    },
    "cartao": 0,
    "reserva": 0,
    "meta_reserva": 12000
}

def calcular():
    fixos = sum(DATA["fixos"].values())
    variaveis = sum(DATA["variaveis"].values())
    total = fixos + variaveis + DATA["cartao"]
    saldo = DATA["receita"] - total

    meta = 300 if saldo > 500 else 200

    return {
        "fixos": round(fixos,2),
        "variaveis": round(variaveis,2),
        "total": round(total,2),
        "saldo": round(saldo,2),
        "meta": meta
    }

def resposta_status():
    c = calcular()
    return f"""
📊 NEXUS STATUS

Receita: R$ {DATA['receita']}
Fixos: R$ {c['fixos']}
Variáveis: R$ {c['variaveis']}
Cartão: R$ {DATA['cartao']}

Saldo: R$ {c['saldo']}

🎯 Guardar: R$ {c['meta']}
"""

def resposta_previsao():
    c = calcular()
    return f"""
📈 PREVISÃO

Gasto total: R$ {c['total']}
Saldo final: R$ {c['saldo']}

💡 Sugestão:
Guardar R$ {c['meta']}
"""

def resposta_meta():
    return f"""
🎯 RESERVA

Meta: R$ {DATA['meta_reserva']}
Atual: R$ {DATA['reserva']}

Foque em guardar todo mês
"""

def processar(msg):
    msg = msg.lower()

    if "/status" in msg:
        return resposta_status()

    if "/previsao" in msg:
        return resposta_previsao()

    if "/meta" in msg:
        return resposta_meta()

    if "/cartao" in msg:
        valor = float(msg.split()[1])
        DATA["cartao"] = valor
        return f"💳 Cartão atualizado: R$ {valor}"

    if "/editar" in msg:
        partes = msg.split()
        cat = partes[1]
        valor = float(partes[2])
        if cat in DATA["variaveis"]:
            DATA["variaveis"][cat] = valor
        return f"✏️ {cat} atualizado para R$ {valor}"

    return "Comando não reconhecido"

@app.route('/')
def dashboard():
    return render_template("dashboard.html")

@app.route('/api/status')
def api_status():
    c = calcular()
    return jsonify({**c, **DATA})

@app.route('/webhooks/telegram', methods=['POST'])
def telegram():
    data = request.get_json()
    msg = data['message']['text']
    chat_id = data['message']['chat']['id']

    resposta = processar(msg)

    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": resposta}
    )

    return {"ok": True}

if __name__ == "__main__":
    app.run()
