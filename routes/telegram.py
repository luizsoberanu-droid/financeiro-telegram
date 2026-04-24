from flask import Blueprint, request, jsonify
import os
import re
import requests

from models.database import get_db
from services.ai_service import NexusAI, FinancialTools
from services.finance_service import FinanceService
from services.alert_service import AlertService

telegram_bp = Blueprint('telegram', __name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SESSIONS = {}

def telegram_send(chat_id, text):
    if not TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN não configurado"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": str(text)[:4000]},
            timeout=20,
        )
        return r.ok, r.text
    except Exception as e:
        return False, str(e)

def session(chat_id):
    sid = str(chat_id)
    if sid not in SESSIONS:
        SESSIONS[sid] = {}
    return SESSIONS[sid]

def clear_session(chat_id):
    SESSIONS[str(chat_id)] = {}

def backup_sheets_silencioso(db):
    try:
        from services.sheets_backup_service import SheetsBackupService
        SheetsBackupService(db).backup_all()
    except Exception as e:
        print(f"⚠️ Backup Sheets falhou: {e}")

def listar_cartoes(db):
    from models.database import Cartao
    cartoes = db.query(Cartao).all()
    if not cartoes:
        return "Nenhum cartão cadastrado."
    return "\n".join([f"- {c.nome}" for c in cartoes])

def existe_cartao(db, nome):
    from models.database import Cartao
    return db.query(Cartao).filter(Cartao.nome.ilike(nome)).first()

def fallback_financeiro(db, message):
    """IA modo disciplina pesada: funciona mesmo se Google/Groq falhar."""
    try:
        tools = FinancialTools(db)
        saldo = tools.get_saldo_atual()
        dividas = tools.get_analise_dividas()

        txt = (message or "").lower()
        linhas = [
            "🧠 NEXUS — MODO DISCIPLINA PESADA",
            "",
            f"Receita: R$ {saldo.get('receita_total', 0):.2f}",
            f"Contas pendentes: R$ {saldo.get('contas_pendentes', 0):.2f}",
            f"Gastos do mês: R$ {saldo.get('gastos_mes', 0):.2f}",
            f"Parcelas do mês: R$ {saldo.get('parcelas_mes', 0):.2f}",
            f"Saldo projetado: R$ {saldo.get('saldo_projetado', 0):.2f}",
            f"Dívida ajustada: R$ {dividas.get('total_divida', 0):.2f}",
            ""
        ]

        if "gastar" in txt or "posso" in txt or "comprar" in txt or "lanche" in txt or "passeio" in txt:
            if dividas.get("total_divida", 0) > 0 or saldo.get("saldo_projetado", 0) <= 0:
                linhas += [
                    "Resposta direta: NÃO recomendo gastar.",
                    "Você está em fase de recuperação. Cada real fora do essencial empurra sua dívida para frente.",
                    "Regra de hoje: só essencial, nada de impulso, nada de cartão novo.",
                    "Próximo passo: segurar o gasto e direcionar qualquer sobra para dívida."
                ]
            else:
                linhas += [
                    "Talvez caiba, mas eu ainda não trataria como dinheiro livre.",
                    "Se for essencial, faça. Se for lazer/impulso, segure."
                ]
        elif "divida" in txt or "dívida" in txt or "negativo" in txt:
            meta = dividas.get("meta_3_meses", 0)
            linhas += [
                "Plano de ataque contra dívida:",
                f"- Meta agressiva em 3 meses: R$ {meta:.2f}/mês",
                "- cortar lazer ao mínimo",
                "- congelar parcelamentos novos",
                "- renda extra vai direto para dívida",
                "- revisar fatura antes de qualquer compra"
            ]
        elif "limite" in txt and "cart" in txt:
            try:
                from services.card_limit_service import CardLimitService
                cards = CardLimitService(db).atualizar_limites_cartoes()
                linhas.append("Limite ideal recalculado:")
                for c in cards:
                    linhas.append(f"- {c['nome']}: R$ {c['limite_ideal']:.2f}")
            except Exception:
                linhas.append("Regra: com dívida, cartão deve ficar no máximo em 5% da renda total.")
        else:
            linhas += [
                "Orientação rígida:",
                "- registre todo gasto",
                "- evite cartão",
                "- acompanhe contas abertas",
                "- não compre desejos enquanto houver dívida",
                "- use a planilha como histórico, mas decida pelo saldo projetado"
            ]

        return "\n".join(linhas)
    except Exception as e:
        return f"Estou ativo, mas tive erro ao consultar dados: {e}. Use 'status', 'plano' ou lance gasto como 'lanche 20'."

def resposta_ia_segura(db, chat_id, text):
    try:
        ai = NexusAI(db)
        resp = ai.process(text, chat_id)
        if resp and str(resp).strip():
            return resp
    except Exception as e:
        print(f"⚠️ IA externa falhou, usando fallback: {e}")
    return fallback_financeiro(db, text)

def adicionar_desejo_por_ia(db, texto):
    from models.database import Desejo

    padroes = [
        r"adicionar desejo (.+?) (\d+[,.]?\d*)",
        r"quero comprar (.+?) de (\d+[,.]?\d*)",
        r"quero comprar (.+?) por (\d+[,.]?\d*)",
        r"coloca na lista de desejos (.+?) (\d+[,.]?\d*)",
    ]

    for padrao in padroes:
        m = re.search(padrao, texto.lower())
        if m:
            nome = m.group(1).strip()
            valor = float(m.group(2).replace(",", "."))

            desejo = Desejo(nome=nome, valor=valor, prioridade="media")
            db.add(desejo)
            db.commit()
            backup_sheets_silencioso(db)

            return (
                f"🎯 Desejo adicionado à lista:\n"
                f"Item: {nome}\n"
                f"Valor: R$ {valor:.2f}\n\n"
                "Vou considerar esse desejo antes de liberar novos gastos."
            )

    return None

def tratar_fluxo_lancamento(db, chat_id, msg_lower):
    s = session(chat_id)

    if s.get("awaiting") == "forma_pagamento":
        if msg_lower in ["dinheiro", "pix", "debito", "débito"]:
            svc = FinanceService(db)
            item = svc.add_lancamento(s["descricao"], s["valor"], "dinheiro")
            clear_session(chat_id)
            backup_sheets_silencioso(db)
            return (
                f"✅ Lançado em dinheiro/pix\n"
                f"Descrição: {item.descricao}\n"
                f"Valor: R$ {item.valor:.2f}\n"
                f"Categoria: {item.categoria}\n"
                f"Mês: {item.mes_ref}"
            )

        if msg_lower in ["cartao", "cartão", "credito", "crédito", "cartao de credito", "cartão de crédito"]:
            s["awaiting"] = "cartao"
            return "Qual cartão?\n" + listar_cartoes(db)

        return "Responda: dinheiro, pix, débito ou cartão."

    if s.get("awaiting") == "cartao":
        cart = existe_cartao(db, msg_lower)
        if not cart:
            return "Cartão não encontrado. Escolha um destes:\n" + listar_cartoes(db)

        svc = FinanceService(db)
        item = svc.add_lancamento(s["descricao"], s["valor"], "cartao", cart.nome)
        clear_session(chat_id)
        backup_sheets_silencioso(db)
        return (
            f"💳 Lançado no cartão\n"
            f"Descrição: {item.descricao}\n"
            f"Valor: R$ {item.valor:.2f}\n"
            f"Cartão: {cart.nome}\n"
            f"Fatura: {item.fatura_mes_ref or item.mes_ref}\n"
            f"Vencimento: dia {item.fatura_vencimento or cart.vencimento}"
        )

    return None

@telegram_bp.route('/webhooks/telegram', methods=['POST'])
def telegram_webhook():
    data = request.get_json(silent=True) or {}
    message_obj = data.get("message") or {}
    text = (message_obj.get("text") or "").strip()
    chat_id = (message_obj.get("chat") or {}).get("id")

    if not text or not chat_id:
        return jsonify({"ok": True})

    chat_id = str(chat_id)
    msg_lower = text.lower().strip()

    db_gen = get_db()
    db = next(db_gen)

    try:
        fluxo = tratar_fluxo_lancamento(db, chat_id, msg_lower)
        if fluxo:
            telegram_send(chat_id, fluxo)
            return jsonify({"ok": True})

        # Análise inteligente de desejos: consulta preço médio e simula à vista/parcelado
        if msg_lower.startswith(("quero comprar", "comprar ", "analisa compra de", "analisar compra de")):
            try:
                from services.wishlist_advisor_service import WishlistAdvisorService, limpar_query
                produto = limpar_query(msg_lower)
                resposta = WishlistAdvisorService(db).analisar_compra(produto)
                telegram_send(chat_id, resposta)
                return jsonify({"ok": True})
            except Exception as e:
                print(f"⚠️ Erro análise desejo: {e}")

        resp_desejo = adicionar_desejo_por_ia(db, msg_lower)
        if resp_desejo:
            telegram_send(chat_id, resp_desejo)
            return jsonify({"ok": True})

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
                f"Receita: R$ {s['receita_total']:.2f}\n"
                f"Gastos: R$ {s['gastos_mes']:.2f}\n"
                f"Parcelas: R$ {s.get('parcelas_mes', 0):.2f}\n"
                f"Contas: R$ {s.get('contas_pendentes', 0):.2f}\n"
                f"Saldo: R$ {s['saldo_projetado']:.2f}\n"
                f"Dívida ajustada: R$ {s.get('divida_total', 0):.2f}"
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
            lines = [
                "💳 DÍVIDAS",
                f"Total ajustado: R$ {d['total_divida']:.2f}",
                f"Bruta: R$ {d.get('divida_bruta', 0):.2f}",
            ]
            for det in d['detalhes']:
                lines.append(f"• {det['nome']}: R$ {det['valor']:.2f}")
            lines.append(f"\n🎯 Meta 3 meses: R$ {d['meta_3_meses']:.2f}/mês")
            telegram_send(chat_id, "\n".join(lines))
            return jsonify({"ok": True})

        if msg_lower in ["limites", "limite cartao", "limite cartão", "/limites"]:
            from services.card_limit_service import CardLimitService
            cards = CardLimitService(db).atualizar_limites_cartoes()
            backup_sheets_silencioso(db)
            lines = ["💳 LIMITE IDEAL DOS CARTÕES"]
            for c in cards:
                lines.append(f"• {c['nome']}: R$ {c['limite_ideal']:.2f}")
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
                "📈 PLANO MENSAL",
                f"Receita: R$ {p['receita_total']:.2f}",
                f"Contas: R$ {p['contas_fixas']:.2f}",
                f"Gastos: R$ {p['gastos_variaveis']:.2f}",
                f"Saldo: R$ {p['saldo_projetado']:.2f}",
                "\n🎯 Ações:",
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

        if msg_lower in ["backup", "/backup", "backup planilha"]:
            from services.sheets_backup_service import SheetsBackupService
            result = SheetsBackupService(db).backup_all()
            telegram_send(chat_id, "Backup Google Sheets: " + ("OK" if result.get("ok") else str(result)))
            return jsonify({"ok": True})

        if msg_lower.startswith("pagar ") or msg_lower.startswith("/pagar "):
            alvo = msg_lower.split(" ", 1)[1].strip()
            from models.database import ContaFixa, Cartao

            conta = db.query(ContaFixa).filter(ContaFixa.nome.ilike(alvo)).first()
            if conta:
                conta.pago = True
                db.commit()
                backup_sheets_silencioso(db)
                telegram_send(chat_id, f"✅ {conta.nome.upper()} marcado como pago!")
                return jsonify({"ok": True})

            cart = db.query(Cartao).filter(Cartao.nome.ilike(alvo)).first()
            if cart:
                cart.pago = True
                db.commit()
                backup_sheets_silencioso(db)
                telegram_send(chat_id, f"✅ Cartão {cart.nome.upper()} marcado como pago!")
                return jsonify({"ok": True})

            telegram_send(chat_id, "❌ Conta ou cartão não encontrado.")
            return jsonify({"ok": True})

        if msg_lower.startswith("extra ") or msg_lower.startswith("/extra "):
            try:
                val = float(msg_lower.split()[1].replace(",", "."))
                svc = FinanceService(db)
                abatimentos, restante = svc.aplicar_extra(val)
                backup_sheets_silencioso(db)

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

        if msg_lower.startswith("parcela ") or msg_lower.startswith("/parcela "):
            try:
                parts = msg_lower.replace("/", "").split()
                cartao = parts[1]
                valor = float(parts[2].replace(",", "."))
                total = int(parts[3])
                desc = " ".join(parts[4:]) or "parcelado"
                svc = FinanceService(db)
                parcelas = svc.add_parcelado(desc, valor, total, cartao)
                if not parcelas:
                    telegram_send(chat_id, "Cartão não encontrado para parcelar.")
                    return jsonify({"ok": True})
                backup_sheets_silencioso(db)
                telegram_send(chat_id, f"✅ Parcelado criado: {desc}\nCartão: {cartao}\n{total}x de R$ {valor:.2f}\nPrimeira fatura: {parcelas[0].mes_ref}")
                return jsonify({"ok": True})
            except:
                telegram_send(chat_id, "Use: parcela nubank 100 3 descricao")
                return jsonify({"ok": True})

        # Lançamento rápido: "descricao valor" agora pergunta forma de pagamento
        parts = text.split()
        if len(parts) >= 2:
            try:
                valor = float(parts[-1].replace(",", "."))
                descricao = " ".join(parts[:-1])
                s = session(chat_id)
                s["descricao"] = descricao
                s["valor"] = valor
                s["awaiting"] = "forma_pagamento"
                telegram_send(chat_id, f"Entendi: {descricao} - R$ {valor:.2f}\nFoi em dinheiro/pix ou cartão?")
                return jsonify({"ok": True})
            except Exception:
                pass

        reply = resposta_ia_segura(db, chat_id, text)
        telegram_send(chat_id, reply)
        return jsonify({"ok": True})

    except Exception as e:
        telegram_send(chat_id, f"Estou ativo, mas tive um erro interno: {e}")
        return jsonify({"ok": True, "error": str(e)})
    finally:
        try:
            next(db_gen, None)
        except Exception:
            pass
