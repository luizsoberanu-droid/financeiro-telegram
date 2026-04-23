from flask import Blueprint, request, jsonify
from models.database import get_db, init_db
from services.finance_service import FinanceService
from services.ai_service import NexusAI, FinancialTools
from utils.helpers import month_key

api_bp = Blueprint('api', __name__)

@api_bp.route('/health')
def health():
    return jsonify({"ok": True, "service": "nexus-ai-v2", "version": "2.0.0"})

@api_bp.route('/status')
def api_status():
    db = next(get_db())
    tools = FinancialTools(db)
    return jsonify(tools.get_saldo_atual())

@api_bp.route('/add_extra', methods=['POST'])
def api_add_extra():
    db = next(get_db())
    from models.database import Config
    config = db.query(Config).first()
    config.receita_extra = float(request.json.get("valor", 0))
    db.commit()
    return jsonify({"ok": True})

@api_bp.route('/lancar', methods=['POST'])
def api_lancar():
    db = next(get_db())
    p = request.get_json()
    svc = FinanceService(db)
    item = svc.add_lancamento(
        p["descricao"], p["valor"],
        p.get("forma_pagamento", "dinheiro"),
        p.get("cartao")
    )
    return jsonify({
        "id": item.id,
        "descricao": item.descricao,
        "valor": item.valor,
        "categoria": item.categoria,
        "mes_ref": item.mes_ref
    })

@api_bp.route('/parcelar', methods=['POST'])
def api_parcelar():
    db = next(get_db())
    p = request.get_json()
    svc = FinanceService(db)
    criadas = svc.add_parcelado(
        p["descricao"], p["valor"],
        int(p["total_parcelas"]), p["cartao"]
    )
    return jsonify({"ok": True, "parcelas": len(criadas) if criadas else 0})

@api_bp.route('/marcar_pago', methods=['POST'])
def api_pagar():
    db = next(get_db())
    p = request.get_json()
    tipo = p.get("tipo")
    nome = p.get("nome", "").strip().lower()

    if tipo == "conta":
        from models.database import ContaFixa
        conta = db.query(ContaFixa).filter(ContaFixa.nome.ilike(nome)).first()
        if conta:
            conta.pago = True
            db.commit()
            return jsonify({"ok": True})

    if tipo == "cartao":
        from models.database import Cartao
        cart = db.query(Cartao).filter(Cartao.nome.ilike(nome)).first()
        if cart:
            cart.pago = True
            db.commit()
            return jsonify({"ok": True})

    return jsonify({"ok": False, "erro": "nao encontrado"}), 404

@api_bp.route('/dividas')
def api_dividas():
    db = next(get_db())
    tools = FinancialTools(db)
    return jsonify(tools.get_analise_dividas())

@api_bp.route('/reserva')
def api_reserva():
    db = next(get_db())
    tools = FinancialTools(db)
    return jsonify(tools.get_reserva_status())

@api_bp.route('/plano')
def api_plano():
    db = next(get_db())
    tools = FinancialTools(db)
    return jsonify(tools.get_plano_mensal())
