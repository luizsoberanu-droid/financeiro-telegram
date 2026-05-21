from flask import Blueprint, request, jsonify
import os
import re
import unicodedata
import requests

from models.database import get_db
from services.ai_service import NexusAI

telegram_bp = Blueprint('telegram', __name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
SESSIONS = {}


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


def _session(chat_id):
    sid = str(chat_id)
    if sid not in SESSIONS:
        SESSIONS[sid] = {}
    return SESSIONS[sid]


def _clear_session(chat_id):
    SESSIONS[str(chat_id)] = {}


def _normalizar(text):
    text = (text or "").lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _extrair_valor(text):
    msg = _normalizar(text)
    msg = re.sub(r"\d+\s*x", "", msg)
    padrao = r"(?:r\$\s*)?(\d+(?:[\.\s]\d{3})*(?:,\d{2})?|\d+(?:[\.,]\d{2})?)"
    candidatos = []
    for raw in re.findall(padrao, msg):
        try:
            candidatos.append(float(raw.replace(".", "").replace(" ", "").replace(",", ".")))
        except ValueError:
            pass
    return max([v for v in candidatos if v > 0], default=0)


def _extrair_valor_desejo(text):
    valor = _extrair_valor(text)
    if valor <= 0:
        return 0

    msg = _normalizar(text)
    tem_sinal_preco = (
        "r$" in msg
        or " reais" in msg
        or re.search(r"\b(de|por|preco|preço|valor|custa|custe)\s+(r\$\s*)?\d", msg)
    )
    if valor < 50 and not tem_sinal_preco:
        return 0
    return valor


def _limpar_nome(text):
    nome = text or ""
    nome = re.sub(r"(?i)\br\$?\s*\d+(?:[\.\s]\d{3})*(?:[,.]\d{2})?\b", " ", nome)
    nome = re.sub(r"(?i)\b\d+\s*x\b", " ", nome)
    termos = [
        "comprei", "gastei", "paguei", "lancar", "lançar", "lance", "lança",
        "registre", "registrar", "gasto", "quero comprar", "desejo comprar",
        "adicionar desejo", "adiciona desejo", "salvar desejo", "guardar desejo",
        "colocar na lista de desejos", "coloca na lista de desejos", "adicionar na lista de desejos",
        "guardar na lista de desejos", "na lista de desejos", "lista de desejos", "lista de desejo",
        "adiciona", "adicionar", "coloca", "colocar", "salva", "salvar", "guardar",
        "de", "por", "no cartao", "no cartão", "cartao", "cartão", "credito", "crédito",
        "dinheiro", "pix", "debito", "débito",
    ]
    for termo in termos:
        nome = re.sub(r"(?i)\b" + re.escape(termo) + r"\b", " ", nome)
    nome = re.sub(r"\s+", " ", nome).strip(" -:,.;")
    return nome or "item"


def _forma_pagamento(text):
    msg = _normalizar(text)
    if any(t in msg for t in ["dinheiro", "pix", "debito"]):
        return "dinheiro"
    if any(t in msg for t in ["cartao", "credito"]):
        return "cartao"
    return None


def _cartoes(db):
    from models.database import Cartao
    return db.query(Cartao).order_by(Cartao.nome).all()


def _identificar_cartao(db, text):
    msg = _normalizar(text)
    for c in _cartoes(db):
        if _normalizar(c.nome) in msg:
            return c
    return None


def _listar_cartoes(db):
    cartoes = _cartoes(db)
    if not cartoes:
        return "Nenhum cartao cadastrado."
    return "\n".join([f"- {c.nome}" for c in cartoes])


def _formatar_limites(db):
    from services.card_limit_service import CardLimitService

    resumo = CardLimitService(db).resumo_limites()
    linhas = [
        "NEXUS limite inteligente do cartao",
        "",
        f"Limite real informado: R$ {resumo['limite_total_real']:.2f}",
        f"Limite seguro do mes: R$ {resumo['limite_total_seguro_mes']:.2f}",
        f"Uso atual no mes: R$ {resumo['uso_total_mes']:.2f}",
        f"Disponivel seguro este mes: R$ {resumo['disponivel_seguro_mes']:.2f}",
        "",
        "Por cartao:",
    ]
    for c in resumo.get("cartoes", []):
        linhas.append(
            f"- {c['nome']}: real R$ {c['limite_real']:.2f} | seguro R$ {c['limite_ideal']:.2f} | usado R$ {c['uso_mes']:.2f}"
        )
    linhas += ["", resumo["leitura"]]
    return "\n".join(linhas)


def _salvar_lancamento(db, chat_id, descricao, valor, forma_pagamento, cartao_nome=None):
    from services.finance_service import FinanceService

    if forma_pagamento == "cartao":
        cartao = _identificar_cartao(db, cartao_nome or "")
        if not cartao:
            s = _session(chat_id)
            s.update({
                "awaiting": "cartao_lancamento",
                "descricao": descricao,
                "valor": valor,
            })
            return "Qual cartao de credito voce usou?\n" + _listar_cartoes(db)
        cartao_nome = cartao.nome

    item = FinanceService(db).add_lancamento(descricao, valor, forma_pagamento, cartao_nome)
    _clear_session(chat_id)

    linhas = [
        "Lancamento salvo no banco.",
        f"Descricao: {item.descricao}",
        f"Valor: R$ {item.valor:.2f}",
        f"Categoria: {item.categoria}",
        f"Forma: {'cartao de credito' if forma_pagamento == 'cartao' else 'dinheiro/pix/debito'}",
    ]
    if item.cartao:
        linhas.append(f"Cartao: {item.cartao}")
        linhas.append(f"Fatura: {item.fatura_mes_ref or item.mes_ref}")
        linhas.append("")
        linhas.append(_formatar_limites(db))
    return "\n".join(linhas)


def _salvar_desejo(db, nome, valor):
    from models.database import Desejo
    from services.wishlist_advisor_service import WishlistAdvisorService, classificar_prioridade

    prioridade = classificar_prioridade(nome)
    existente = db.query(Desejo).filter(Desejo.nome.ilike(nome)).first()
    if existente:
        existente.valor = float(valor)
        existente.prioridade = prioridade
        acao = "Item atualizado na lista de desejos."
    else:
        db.add(Desejo(nome=nome, valor=float(valor), prioridade=prioridade))
        acao = "Item salvo na lista de desejos."
    db.commit()

    svc = WishlistAdvisorService(db)
    plano = svc.diagnostico_compra(nome, valor)
    analise = svc.analisar_compra(nome, valor)
    return (
        f"{acao}\n"
        f"Item: {nome}\n"
        f"Valor: R$ {float(valor):.2f}\n"
        f"Prioridade: {prioridade.upper()}\n\n"
        f"Decisao: {plano['decisao']}\n"
        f"Melhor caminho: {plano['melhor_caminho']}\n"
        f"Quando comprar: {plano['quando_comprar']}\n\n"
        + analise
    )


def _tratar_pendencia(db, chat_id, text):
    s = _session(chat_id)
    awaiting = s.get("awaiting")
    if not awaiting:
        return None

    if awaiting == "forma_pagamento_lancamento":
        forma = _forma_pagamento(text)
        if not forma:
            return "Foi em dinheiro/pix/debito ou no cartao de credito?"
        cartao_nome = text if forma == "cartao" else None
        return _salvar_lancamento(db, chat_id, s["descricao"], s["valor"], forma, cartao_nome)

    if awaiting == "cartao_lancamento":
        return _salvar_lancamento(db, chat_id, s["descricao"], s["valor"], "cartao", text)

    if awaiting == "cartao_limite":
        cartao = _identificar_cartao(db, text)
        if not cartao:
            return "Qual cartao? Escolha um destes:\n" + _listar_cartoes(db)
        from services.card_limit_service import CardLimitService
        CardLimitService(db).atualizar_limite_real(cartao.nome, s["limite_real"])
        _clear_session(chat_id)
        return "Limite real registrado.\n\n" + _formatar_limites(db)

    if awaiting == "valor_desejo":
        valor = _extrair_valor_desejo(text)
        if valor <= 0:
            return f"Qual valor devo considerar para {s['nome_desejo']}?"
        _clear_session(chat_id)
        return _salvar_desejo(db, s["nome_desejo"], valor)

    return None


def _tratar_limite_cartao(db, chat_id, text):
    msg = _normalizar(text)
    valor = _extrair_valor(text)

    if "limite" not in msg and "quanto posso gastar no cartao" not in msg:
        return None

    if valor <= 0:
        return _formatar_limites(db)

    cartao = _identificar_cartao(db, text)
    if not cartao:
        s = _session(chat_id)
        s.update({"awaiting": "cartao_limite", "limite_real": valor})
        return f"Esse limite real de R$ {valor:.2f} e de qual cartao?\n" + _listar_cartoes(db)

    from services.card_limit_service import CardLimitService
    result = CardLimitService(db).atualizar_limite_real(cartao.nome, valor)
    if not result.get("ok"):
        return "Nao encontrei esse cartao. Cadastre no painel ou me diga um destes:\n" + _listar_cartoes(db)
    return "Limite real registrado.\n\n" + _formatar_limites(db)


def _tratar_desejo(db, chat_id, text):
    msg = _normalizar(text)
    termos_desejo = [
        "lista de desejo", "lista de desejos", "adicionar desejo", "adiciona",
        "adicionar", "salvar desejo", "salva desejo", "guardar desejo",
        "coloca", "colocar", "quero comprar", "desejo comprar", "guardar desejo",
    ]
    if not any(t in msg for t in termos_desejo):
        return None
    if "posso comprar" in msg:
        return None

    valor = _extrair_valor_desejo(text)
    nome = _limpar_nome(text)
    if valor <= 0:
        try:
            from services.wishlist_advisor_service import buscar_preco_mercado_livre
            preco_info = buscar_preco_mercado_livre(nome)
            if preco_info.get("ok") and preco_info.get("preco_mediano"):
                valor = float(preco_info["preco_mediano"])
                return _salvar_desejo(db, nome, valor)
        except Exception as e:
            print(f"Aviso: nao consegui estimar preco do desejo: {e}")

        s = _session(chat_id)
        s.update({"awaiting": "valor_desejo", "nome_desejo": nome})
        return f"Entendi o desejo: {nome}. Nao consegui estimar o preco agora. Qual valor devo considerar?"

    return _salvar_desejo(db, nome, valor)


def _tratar_lancamento(db, chat_id, text):
    msg = _normalizar(text)
    valor = _extrair_valor(text)
    if valor <= 0:
        return None

    if any(t in msg for t in ["quero comprar", "posso comprar", "investir", "limite"]):
        return None

    termos_gasto = ["comprei", "gastei", "paguei", "lancar", "lanca", "registrar", "gasto"]
    formato_curto = bool(re.match(r"^[a-z0-9\sçãõáéíóúâêôü,-]+\s+\d", msg))
    if not any(t in msg for t in termos_gasto) and not formato_curto:
        return None

    descricao = _limpar_nome(text)
    forma = _forma_pagamento(text)
    if not forma:
        s = _session(chat_id)
        s.update({
            "awaiting": "forma_pagamento_lancamento",
            "descricao": descricao,
            "valor": valor,
        })
        return f"Entendi: {descricao} - R$ {valor:.2f}. Foi em dinheiro/pix/debito ou no cartao de credito?"

    cartao_nome = text if forma == "cartao" else None
    return _salvar_lancamento(db, chat_id, descricao, valor, forma, cartao_nome)


def tratar_integracoes(db, chat_id, text):
    for handler in [_tratar_pendencia, _tratar_limite_cartao, _tratar_desejo, _tratar_lancamento]:
        resposta = handler(db, chat_id, text)
        if resposta:
            return resposta
    return None


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
        return (
            "NEXUS modo analista patrimonial\n\n"
            f"Receita: R$ {saldo['receita_total']:.2f}\n"
            f"Saldo projetado: R$ {saldo['saldo_projetado']:.2f}\n"
            f"Divida ajustada: R$ {dividas['total_divida']:.2f}\n"
            f"Reserva: R$ {saldo['reserva_atual']:.2f} de R$ {saldo['meta_reserva']:.2f}\n\n"
            "Me diga um objetivo, um gasto, um limite real de cartao ou um item da lista de desejos que eu analiso e salvo."
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
        reply = tratar_integracoes(db, chat_id, text) or resposta_ia_segura(db, chat_id, text)
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
