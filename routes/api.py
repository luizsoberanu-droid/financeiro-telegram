from flask import Blueprint, request, jsonify, send_file
from models.database import get_db, init_db, SessionLocal
from services.finance_service import FinanceService
from services.ai_service import NexusAI, FinancialTools
from services.pdf_service import PDFService
from services.alert_service import AlertService
from utils.helpers import month_key
from sqlalchemy.orm import Session
from datetime import datetime
from io import BytesIO

api_bp = Blueprint('api', __name__)

def get_db_session() -> Session:
    return SessionLocal()

@api_bp.route('/health')
def health():
    return jsonify({"ok": True, "service": "nexus-ai-v2", "version": "2.2.0"})

@api_bp.route('/status')
def api_status():
    db = get_db_session()
    try:
        tools = FinancialTools(db)
        return jsonify(tools.get_saldo_atual())
    finally:
        db.close()

# ==================== CONTAS FIXAS ====================
@api_bp.route('/contas')
def api_contas():
    db = get_db_session()
    try:
        from models.database import ContaFixa
        contas = db.query(ContaFixa).all()
        return jsonify([{
            "id": c.id, "nome": c.nome, "valor": c.valor,
            "vencimento": c.vencimento, "categoria": c.categoria, "pago": c.pago
        } for c in contas])
    finally:
        db.close()

@api_bp.route('/add_conta_fixa', methods=['POST'])
def api_add_conta():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import ContaFixa
        conta = ContaFixa(
            nome=p["nome"],
            valor=float(p["valor"]),
            vencimento=int(p["vencimento"]),
            categoria=p.get("categoria", "geral")
        )
        db.add(conta)
        db.commit()
        return jsonify({"ok": True, "id": conta.id})
    finally:
        db.close()

@api_bp.route('/conta/<int:id>', methods=['DELETE'])
def api_delete_conta(id):
    db = get_db_session()
    try:
        from models.database import ContaFixa
        conta = db.query(ContaFixa).filter(ContaFixa.id == id).first()
        if conta:
            db.delete(conta)
            db.commit()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "erro": "nao encontrado"}), 404
    finally:
        db.close()

# ==================== CARTÕES ====================
@api_bp.route('/cartoes')
def api_cartoes():
    db = get_db_session()
    try:
        from models.database import Cartao
        cartoes = db.query(Cartao).all()
        return jsonify([{
            "id": c.id, "nome": c.nome, "vencimento": c.vencimento,
            "melhor_dia_compra": c.melhor_dia_compra, "limite_ideal": c.limite_ideal, "pago": c.pago
        } for c in cartoes])
    finally:
        db.close()

@api_bp.route('/add_cartao', methods=['POST'])
def api_add_cartao():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import Cartao
        cart = Cartao(
            nome=p["nome"],
            vencimento=int(p["vencimento"]),
            melhor_dia_compra=int(p["melhor_dia_compra"]),
            limite_ideal=float(p.get("limite_ideal", 200))
        )
        db.add(cart)
        db.commit()
        return jsonify({"ok": True, "id": cart.id})
    finally:
        db.close()

@api_bp.route('/cartao/<int:id>', methods=['DELETE'])
def api_delete_cartao(id):
    db = get_db_session()
    try:
        from models.database import Cartao
        cart = db.query(Cartao).filter(Cartao.id == id).first()
        if cart:
            db.delete(cart)
            db.commit()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "erro": "nao encontrado"}), 404
    finally:
        db.close()

# ==================== LANÇAMENTOS ====================
@api_bp.route('/lancamentos')
def api_lancamentos():
    db = get_db_session()
    try:
        from models.database import Lancamento
        mes_atual = month_key()
        lancs = db.query(Lancamento).filter(Lancamento.mes_ref == mes_atual).order_by(Lancamento.data.desc()).all()
        return jsonify([{
            "id": l.id, "data": l.data.isoformat(), "descricao": l.descricao,
            "categoria": l.categoria, "valor": l.valor,
            "forma_pagamento": l.forma_pagamento, "cartao": l.cartao
        } for l in lancs])
    finally:
        db.close()

@api_bp.route('/lancar', methods=['POST'])
def api_lancar():
    db = get_db_session()
    try:
        p = request.get_json()
        svc = FinanceService(db)
        item = svc.add_lancamento(
            p["descricao"], p["valor"],
            p.get("forma_pagamento", "dinheiro"),
            p.get("cartao"),
            p.get("categoria")
        )
        return jsonify({
            "id": item.id, "descricao": item.descricao, "valor": item.valor,
            "categoria": item.categoria, "mes_ref": item.mes_ref
        })
    finally:
        db.close()

@api_bp.route('/parcelar', methods=['POST'])
def api_parcelar():
    db = get_db_session()
    try:
        p = request.get_json()
        svc = FinanceService(db)
        criadas = svc.add_parcelado(
            p["descricao"], p["valor"], int(p["total_parcelas"]), p["cartao"]
        )
        return jsonify({"ok": True, "parcelas": len(criadas) if criadas else 0})
    finally:
        db.close()

# ==================== MARCAR PAGO ====================
@api_bp.route('/marcar_pago', methods=['POST'])
def api_pagar():
    db = get_db_session()
    try:
        p = request.get_json()
        tipo = p.get("tipo")
        id = p.get("id")
        pago = p.get("pago", True)

        if tipo == "conta":
            from models.database import ContaFixa
            conta = db.query(ContaFixa).filter(ContaFixa.id == id).first()
            if conta:
                conta.pago = pago
                db.commit()
                return jsonify({"ok": True})

        if tipo == "cartao":
            from models.database import Cartao
            cart = db.query(Cartao).filter(Cartao.id == id).first()
            if cart:
                cart.pago = pago
                db.commit()
                return jsonify({"ok": True})

        return jsonify({"ok": False, "erro": "nao encontrado"}), 404
    finally:
        db.close()

# ==================== DÍVIDAS ====================
@api_bp.route('/dividas')
def api_dividas():
    db = get_db_session()
    try:
        tools = FinancialTools(db)
        return jsonify(tools.get_analise_dividas())
    finally:
        db.close()

@api_bp.route('/divida', methods=['POST'])
def api_add_divida():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import Divida
        div = Divida(nome=p["nome"], valor=float(p["valor"]), ordem_prioridade=99)
        db.add(div)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

# ==================== RESERVA ====================
@api_bp.route('/reserva')
def api_reserva():
    db = get_db_session()
    try:
        tools = FinancialTools(db)
        return jsonify(tools.get_reserva_status())
    finally:
        db.close()

# ==================== PLANO ====================
@api_bp.route('/plano')
def api_plano():
    db = get_db_session()
    try:
        tools = FinancialTools(db)
        return jsonify(tools.get_plano_mensal())
    finally:
        db.close()

# ==================== CONFIGURAÇÕES ====================
@api_bp.route('/config', methods=['POST'])
def api_config():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import Config
        config = db.query(Config).first()
        if not config:
            config = Config()
            db.add(config)

        if "receita_fixa" in p:
            config.receita_fixa = float(p["receita_fixa"])
        if "receita_extra" in p:
            config.receita_extra = float(p["receita_extra"])
        if "meta_reserva" in p:
            config.meta_reserva = float(p["meta_reserva"])
        if "reserva_atual" in p:
            config.reserva_atual = float(p["reserva_atual"])

        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

@api_bp.route('/limites', methods=['POST'])
def api_limites():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import Limite

        for cat, val in p.items():
            lim = db.query(Limite).filter(Limite.categoria == cat).first()
            if lim:
                lim.valor = float(val)
            else:
                db.add(Limite(categoria=cat, valor=float(val)))
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

# ==================== RENDA EXTRA ====================
@api_bp.route('/add_extra', methods=['POST'])
def api_add_extra():
    db = get_db_session()
    try:
        p = request.get_json()
        from models.database import Config
        config = db.query(Config).first()
        config.receita_extra = float(p.get("valor", 0))
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

# ==================== PDF / RELATÓRIO ====================
@api_bp.route('/relatorio/pdf')
def api_relatorio_pdf():
    """Gera e retorna relatório mensal em PDF"""
    db = get_db_session()
    try:
        mes_ref = request.args.get('mes', datetime.now().strftime("%Y-%m"))
        svc = PDFService(db)
        pdf_bytes = svc.gerar_relatorio_mensal(mes_ref)

        return send_file(
            BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'relatorio_nexus_{mes_ref}.pdf'
        )
    finally:
        db.close()

@api_bp.route('/relatorio/html')
def api_relatorio_html():
    """Gera relatório mensal em HTML (fallback se reportlab não instalado)"""
    db = get_db_session()
    try:
        mes_ref = request.args.get('mes', datetime.now().strftime("%Y-%m"))
        svc = PDFService(db)
        html_bytes = svc.gerar_relatorio_mensal(mes_ref)

        return html_bytes, 200, {'Content-Type': 'text/html; charset=utf-8'}
    finally:
        db.close()

# ==================== ALERTAS ====================
@api_bp.route('/alertas/verificar', methods=['POST'])
def api_verificar_alertas():
    """Endpoint para verificar alertas (pode ser chamado por cron job externo)"""
    db = get_db_session()
    try:
        p = request.get_json() or {}
        chat_id = p.get("chat_id", "default")

        alert_svc = AlertService(db)
        alertas = alert_svc.verificar_todos_alertas(chat_id)

        return jsonify({
            "ok": True,
            "alertas_enviados": len(alertas),
            "tipos": alertas
        })
    finally:
        db.close()

@api_bp.route('/alertas/teste', methods=['POST'])
def api_testar_alertas():
    """Envia um alerta de teste"""
    db = get_db_session()
    try:
        p = request.get_json() or {}
        chat_id = p.get("chat_id", "default")

        from services.alert_service import telegram_send
        telegram_send(
            chat_id,
            "🧪 Teste de alerta do NEXUS AI!\n\n"
            "Se você recebeu esta mensagem, os alertas automáticos estão configurados corretamente."
        )

        return jsonify({"ok": True, "mensagem": "Alerta de teste enviado!"})
    finally:
        db.close()
