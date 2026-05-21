from flask import Blueprint, request, jsonify
import os
import requests

from models.database import get_db
from services.ai_service import NexusAI

telegram_bp = Blueprint('telegram', __name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()


def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN nao configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": str(text)[:4000]},
            timeout=20,
        )
        return r.ok, r.text
    except Exception as e:
        return False, str(e)


def resposta_ia_segura(db, chat_id, text):
    try:
        resposta = NexusAI(db).process(text, chat_id)
        if resposta and str(resposta).strip():
            return resposta
    except Exception as e:
        print(f"Aviso: IA externa falhou no Telegram, usando fallback: {e}")

    try:
        tools = NexusAI(db).tools
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()
        plano = tools.get_plano_mensal()
        return (
            "NEXUS modo analista patrimonial\n\n"
            f"Receita: R$ {saldo['receita_total']:.2f}\n"
            f"Saldo projetado: R$ {saldo['saldo_projetado']:.2f}\n"
            f"Divida ajustada: R$ {dividas['total_divida']:.2f}\n"
            f"Reserva: R$ {saldo['reserva_atual']:.2f} de R$ {saldo['meta_reserva']:.2f}\n\n"
            "Leitura direta: antes de buscar crescimento agressivo, o app vai priorizar quitar dividas, montar reserva "
            "e controlar parcelamentos. Depois disso, eu monto uma estrategia de investimento diversificada.\n\n"
            "Proximo passo: me diga sua meta em valor e prazo. Exemplo: quero juntar entrada para casa de R$ 1.000.000 em 8 anos."
        )
    except Exception as e:
        return f"Estou ativo, mas nao consegui consultar seus dados agora: {e}"


@telegram_bp.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    message_obj = data.get("message") or {}
    text = (message_obj.get("text") or "").strip()
    chat_id = (message_obj.get("chat") or {}).get("id")

    if not text or not chat_id:
        return jsonify({"ok": True})

    chat_id = str(chat_id)
    db_gen = get_db()
    db = next(db_gen)

    try:
        reply = resposta_ia_segura(db, chat_id, text)
        telegram_send(chat_id, reply)
        return jsonify({"ok": True, "mode": "analista_ia"})
    except Exception as e:
        telegram_send(chat_id, f"Estou ativo, mas tive um erro interno: {e}")
        return jsonify({"ok": True, "error": str(e)})
    finally:
        try:
            next(db_gen, None)
        except Exception:
            pass
