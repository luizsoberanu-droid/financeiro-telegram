import re
from flask import Blueprint, request, jsonify
import os
import requests
from models.database import get_db
from services.ai_service import NexusAI, FinancialTools
from services.finance_service import FinanceService
from services.alert_service import AlertService

telegram_bp = Blueprint('telegram', __name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN não configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},  # Limite Telegram
            timeout=20,
        )
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def get_ai_response(chat_id, message):
    db = next(get_db())
    ai = NexusAI(db)
    return ai.process(message, chat_id)

@telegram_bp.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    message_obj = data.get("message") or {}
    text = (message_obj.get("text") or "").strip()
    chat_id = (message_obj.get("chat") or {}).get("id")

    if not text or not chat_id:
        return jsonify({"ok": True})

    chat_id = str(chat_id)
    msg_lower = text.lower()
    db = next(get_db())

    # Comandos rápidos (não precisam de IA)
    if msg_lower in ["historico", "/historico", "histórico"]:
        from services.monthly_service import MonthlyService
        hist = MonthlyService(db).historico(6)
        if not hist:
            telegram_send(chat_id, "Ainda não há histórico mensal.")
            return jsonify({"ok": True})

        lines = ["📅 HISTÓRICO MENSAL"]
        for h in hist:
            lines.append(
                f"{h['mes_ref']} | Saldo: R$ {h['saldo_projetado']:.2f} | "
                f"Dívida ajustada: R$ {h['divida_ajustada']:.2f}"
            )
        telegram_send(chat_id, "\n".join(lines))
        return jsonify({"ok": True})

    if msg_lower in ["status", "/status"]:
        tools = FinancialTools(db)
        s = tools.get_saldo_atual()
        reply = (
            f"📊 STATUS ATUAL\n"
            f"Receita: {s['receita_total']:.2f}\n"
            f"Gastos: {s['gastos_mes']:.2f}\n"
            f"Saldo: {s['saldo_projetado']:.2f}\n"
            f"Dívida: {s.get('divida_total', 0):.2f}"
        )
        telegram_send(chat_id, reply)
        return jsonify({"ok": True})

    if msg_lower in ["contas", "/contas"]:
        from models.database import ContaFixa
        contas = db.query(ContaFixa).all()
        lines = ["📋 CONTAS FIXAS"]
        for c in contas:
            status = "✅ Paga" if c.pago else "⏳ Aberta"
            lines.append(f"• {c.nome}: R$ {c.valor:.2f} (dia {c.vencimento}) {status}")
        telegram_send(chat_id, "\n".join(lines))
        return jsonify({"ok": True})

    if msg_lower in ["dividas", "/dividas"]:
        tools = FinancialTools(db)
        d = tools.get_analise_dividas()
        lines = [f"💳 DÍVIDAS - Total: R$ {d['total_divida']:.2f}"]
        for det in d['detalhes']:
            lines.append(f"• {det['nome']}: R$ {det['valor']:.2f}")
        lines.append(f"\n🎯 Meta 3 meses: R$ {d['meta_3_meses']:.2f}/mês")
        telegram_send(chat_id, "\n".join(lines))
        return jsonify({"ok": True})

    if msg_lower in ["reserva", "/reserva"]:
        tools = FinancialTools(db)
        r = tools.get_reserva_status()
        reply = (
            f"🏦 RESERVA DE EMERGÊNCIA\n"
            f"Atual: R$ {r['atual']:.2f}\n"
            f"Meta: R$ {r['meta']:.2f}\n"
            f"Progresso: {r['percentual']:.1f}%\n"
            f"Faltante: R$ {r['faltante']:.2f}\n"
            f"Sugestão mensal: R$ {r['sugestao_mensal']:.2f}"
        )
        telegram_send(chat_id, reply)
        return jsonify({"ok": True})

    if msg_lower in ["plano", "/plano"]:
        tools = FinancialTools(db)
        p = tools.get_plano_mensal()
        lines = [
            f"📈 PLANO MENSAL",
            f"Receita: R$ {p['receita_total']:.2f}",
            f"Contas: R$ {p['contas_fixas']:.2f}",
            f"Gastos: R$ {p['gastos_variaveis']:.2f}",
            f"Saldo: R$ {p['saldo_projetado']:.2f}",
            f"\n🎯 Ações:",
        ]
        for acao in p['acoes_recomendadas']:
            lines.append(acao)
        telegram_send(chat_id, "\n".join(lines))
        return jsonify({"ok": True})

    if msg_lower in ["alertas", "/alertas"]:
        alert_svc = AlertService(db, lambda cid, msg: telegram_send(cid, msg))
        alertas = alert_svc.verificar_todos_alertas(chat_id)
        if not alertas:
            telegram_send(chat_id, "✅ Nenhum alerta no momento. Sua situação está sob controle!")
        return jsonify({"ok": True})

    if msg_lower.startswith("pagar ") or msg_lower.startswith("/pagar "):
        alvo = msg_lower.split(" ", 1)[1].strip()
        from models.database import ContaFixa, Cartao

        conta = db.query(ContaFixa).filter(ContaFixa.nome.ilike(alvo)).first()
        if conta:
            conta.pago = True
            db.commit()
            telegram_send(chat_id, f"✅ {conta.nome.upper()} marcado como pago!")
            return jsonify({"ok": True})

        cart = db.query(Cartao).filter(Cartao.nome.ilike(alvo)).first()
        if cart:
            cart.pago = True
            db.commit()
            telegram_send(chat_id, f"✅ Cartão {cart.nome.upper()} marcado como pago!")
            return jsonify({"ok": True})

        telegram_send(chat_id, "❌ Conta ou cartão não encontrado.")
        return jsonify({"ok": True})

    if msg_lower.startswith("extra ") or msg_lower.startswith("/extra "):
        try:
            val = float(msg_lower.split()[1].replace(",", "."))
            svc = FinanceService(db)
            abatimentos, restante = svc.aplicar_extra(val)

            lines = [f"💰 Renda extra: R$ {val:.2f}"]
            if abatimentos:
                lines.append("\n📉 Aplicado em dívidas:")
                for ab in abatimentos:
                    lines.append(f"• {ab['nome']}: -R$ {ab['abatido']:.2f} (resta R$ {ab['restante']:.2f})")
            if restante > 0:
                lines.append(f"\n💵 Sobrou: R$ {restante:.2f}")

            telegram_send(chat_id, "\n".join(lines))
            return jsonify({"ok": True})
        except:
            telegram_send(chat_id, "Use: extra 300")
            return jsonify({"ok": True})

    # Lançamento rápido: "descricao valor"
    parts = text.split()
    if len(parts) >= 2:
        try:
            valor = float(parts[-1].replace(",", "."))
            descricao = " ".join(parts[:-1])
            svc = FinanceService(db)
            item = svc.add_lancamento(descricao, valor)

            reply = (
                f"✅ Lançado: {item.descricao}\n"
                f"Valor: R$ {item.valor:.2f}\n"
                f"Categoria: {item.categoria}\n"
                f"Mês: {item.mes_ref}"
            )
            telegram_send(chat_id, reply)
            return jsonify({"ok": True})
        except:
            pass

    # TUDO MAIS: Usar IA avançada
    reply = get_ai_response(chat_id, text)
    telegram_send(chat_id, reply)
    return jsonify({"ok": True})


def adicionar_desejo_por_ia(db, texto):
    from models.database import Desejo

    padroes = [
        r"adicionar desejo (.+?) (\d+[,.]?\d*)",
        r"quero comprar (.+?) de (\d+[,.]?\d*)",
        r"coloca na lista de desejos (.+?) (\d+[,.]?\d*)",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto.lower())
        if m:
            nome = m.group(1).strip()
            valor = float(m.group(2).replace(",", "."))

            desejo = Desejo(nome=nome, valor=valor)
            db.add(desejo)
            db.commit()

            return f"🎯 Desejo adicionado: {nome} - R$ {valor:.2f}"

    return None
