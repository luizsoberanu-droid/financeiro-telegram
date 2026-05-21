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
import json

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
        try:
            from services.card_limit_service import CardLimitService
            CardLimitService(db).atualizar_limites_cartoes()
        except Exception as e:
            print(f"Aviso: limite ideal não recalculado: {e}")

        return jsonify(CardLimitService(db).resumo_limites().get("cartoes", []))
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
            limite_real=float(p.get("limite_real", p.get("limite_ideal", 0))),
            limite_ideal=float(p.get("limite_ideal", 200))
        )
        db.add(cart)
        db.commit()
        try:
            from services.card_limit_service import CardLimitService
            CardLimitService(db).atualizar_limites_cartoes()
        except Exception as e:
            print(f"Aviso: limite ideal nao recalculado apos criar cartao: {e}")
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

@api_bp.route('/divida/<int:id>', methods=['PUT'])
def api_update_divida(id):
    db = get_db_session()
    try:
        p = request.get_json() or {}
        from models.database import Divida
        div = db.query(Divida).filter(Divida.id == id).first()
        if not div:
            return jsonify({"ok": False, "erro": "divida nao encontrada"}), 404

        if "nome" in p and str(p["nome"]).strip():
            div.nome = str(p["nome"]).strip()
        if "valor" in p:
            div.valor = float(p["valor"])
        if "ordem_prioridade" in p:
            div.ordem_prioridade = int(p["ordem_prioridade"])

        db.commit()
        return jsonify({"ok": True, "id": div.id, "nome": div.nome, "valor": div.valor})
    finally:
        db.close()

@api_bp.route('/divida/<int:id>', methods=['DELETE'])
def api_delete_divida(id):
    db = get_db_session()
    try:
        from models.database import Divida
        div = db.query(Divida).filter(Divida.id == id).first()
        if not div:
            return jsonify({"ok": False, "erro": "divida nao encontrada"}), 404

        db.delete(div)
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


# ==================== CARTAO ALIMENTACAO ====================
@api_bp.route('/alimentacao')
def api_alimentacao():
    db = get_db_session()
    try:
        from services.benefit_service import BenefitCardService
        return jsonify(BenefitCardService(db).resumo())
    finally:
        db.close()

@api_bp.route('/alimentacao/config', methods=['POST'])
def api_alimentacao_config():
    db = get_db_session()
    try:
        from services.benefit_service import BenefitCardService
        p = request.get_json() or {}
        return jsonify(BenefitCardService(db).configurar(p))
    finally:
        db.close()

@api_bp.route('/alimentacao/movimento', methods=['POST'])
def api_alimentacao_movimento():
    db = get_db_session()
    try:
        from services.benefit_service import BenefitCardService
        p = request.get_json() or {}
        result = BenefitCardService(db).movimentar(
            p.get("tipo", "debito"),
            p.get("valor", 0),
            p.get("descricao")
        )
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
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

@api_bp.route('/relatorio/gerar', methods=['POST'])
def api_relatorio_telegram():
    db = get_db_session()
    try:
        p = request.get_json() or {}
        chat_id = p.get("chat_id", "default")
        mes_ref = datetime.now().strftime("%Y-%m")
        link = request.host_url.rstrip("/") + "/api/relatorio/pdf?mes=" + mes_ref
        from services.alert_service import telegram_send
        ok, detail = telegram_send(chat_id, "Relatorio mensal pronto para baixar:\n" + link)
        return jsonify({"ok": bool(ok), "detail": detail, "link": link})
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
        telegram_send(chat_id, "Teste de alerta do NEXUS AI!\n\n""Se voce recebeu esta mensagem, os alertas automaticos estao configurados corretamente.")

        return jsonify({"ok": True, "mensagem": "Alerta de teste enviado!"})
    finally:
        db.close()


# ==================== DESEJOS ====================

@api_bp.route('/desejos')
def api_list_desejos():
    db = get_db_session()
    try:
        from models.database import Desejo
        desejos = db.query(Desejo).order_by(Desejo.created_at.desc()).all()
        return jsonify([{
            "id": d.id,
            "nome": d.nome,
            "preco": round(d.valor or 0, 2),
            "valor": round(d.valor or 0, 2),
            "prioridade": d.prioridade or "media",
            "categoria": d.prioridade or "media",
            "comprado": bool(d.comprado),
            "created_at": d.created_at.isoformat() if d.created_at else ""
        } for d in desejos])
    finally:
        db.close()

@api_bp.route('/desejo', methods=['POST'])
def api_add_desejo():
    db = get_db_session()
    try:
        p = request.get_json() or {}
        from models.database import Desejo

        valor = p.get("valor", p.get("preco", 0))
        prioridade = p.get("prioridade", p.get("categoria", "media"))

        desejo = Desejo(
            nome=p["nome"],
            valor=float(valor),
            prioridade=str(prioridade)
        )

        db.add(desejo)
        db.commit()

        return jsonify({"ok": True, "id": desejo.id})

    finally:
        db.close()


# ==================== HISTÓRICO MENSAL ====================
@api_bp.route('/historico_mensal')
def api_historico_mensal():
    db = get_db_session()
    try:
        limite = int(request.args.get("limite", 12))
        from services.monthly_service import MonthlyService
        return jsonify(MonthlyService(db).historico(limite))
    finally:
        db.close()

@api_bp.route('/historico_mensal/atualizar', methods=['POST'])
def api_atualizar_historico_mensal():
    db = get_db_session()
    try:
        from services.monthly_service import MonthlyService
        dados = MonthlyService(db).salvar_resumo_mes()
        return jsonify({"ok": True, "resumo": dados})
    finally:
        db.close()


# ==================== BACKUP GOOGLE SHEETS ====================
@api_bp.route('/backup/google_sheets', methods=['POST'])
def api_backup_google_sheets():
    db = get_db_session()
    try:
        from services.sheets_backup_service import SheetsBackupService
        return jsonify(SheetsBackupService(db).backup_all())
    finally:
        db.close()

@api_bp.route('/restore/google_sheets', methods=['POST'])
def api_restore_google_sheets():
    db = get_db_session()
    try:
        from services.sheets_backup_service import SheetsBackupService
        return jsonify(SheetsBackupService(db).restore_all(replace=True))
    finally:
        db.close()


# ==================== COFRE DE SALVAMENTO ====================
@api_bp.route('/salvamento/status')
def api_salvamento_status():
    db = get_db_session()
    try:
        from services.save_vault_service import SaveVaultService
        return jsonify(SaveVaultService(db).status())
    finally:
        db.close()

@api_bp.route('/apontamentos')
def api_apontamentos():
    db = get_db_session()
    try:
        limite = int(request.args.get("limite", 20))
        from services.autosave_service import AutosaveService
        return jsonify({"ok": True, "apontamentos": AutosaveService(db).recentes(limite)})
    finally:
        db.close()

@api_bp.route('/salvamento/google_sheets', methods=['POST'])
def api_salvamento_google_sheets():
    db = get_db_session()
    try:
        from services.sheets_backup_service import SheetsBackupService
        return jsonify(SheetsBackupService(db).backup_all())
    finally:
        db.close()

@api_bp.route('/salvamento/restaurar_google_sheets', methods=['POST'])
def api_salvamento_restaurar_google_sheets():
    db = get_db_session()
    try:
        from services.sheets_backup_service import SheetsBackupService
        return jsonify(SheetsBackupService(db).restore_all(replace=True))
    finally:
        db.close()

@api_bp.route('/salvamento/snapshot')
def api_salvamento_snapshot():
    db = get_db_session()
    try:
        from services.save_vault_service import SaveVaultService
        payload = SaveVaultService(db).snapshot()
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        filename = "nexus_snapshot_" + datetime.now().strftime("%Y-%m-%d_%H-%M") + ".json"
        return send_file(
            BytesIO(raw),
            mimetype='application/json',
            as_attachment=True,
            download_name=filename
        )
    finally:
        db.close()

@api_bp.route('/salvamento/restaurar_snapshot', methods=['POST'])
def api_salvamento_restaurar_snapshot():
    db = get_db_session()
    try:
        from services.save_vault_service import SaveVaultService
        p = request.get_json() or {}
        snapshot = p.get("snapshot", p)
        return jsonify(SaveVaultService(db).restore_snapshot(snapshot, replace=bool(p.get("replace", True))))
    finally:
        db.close()

@api_bp.route('/cartoes/recalcular_limites', methods=['POST'])
def api_recalcular_limites_cartoes():
    db = get_db_session()
    try:
        from services.card_limit_service import CardLimitService
        return jsonify({"ok": True, "cartoes": CardLimitService(db).atualizar_limites_cartoes()})
    finally:
        db.close()


@api_bp.route('/desejo/<int:id>', methods=['DELETE'])
def api_delete_desejo(id):
    db = get_db_session()
    try:
        from models.database import Desejo
        d = db.query(Desejo).filter(Desejo.id == id).first()
        if not d:
            return jsonify({"ok": False, "erro": "desejo nao encontrado"}), 404
        db.delete(d)
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()

@api_bp.route('/desejos/analise')
def api_analise_desejos():
    db = get_db_session()
    try:
        from models.database import Desejo
        from services.wishlist_advisor_service import WishlistAdvisorService

        svc = WishlistAdvisorService(db)
        desejos = db.query(Desejo).order_by(Desejo.created_at.desc()).all()

        rows = []
        for d in desejos:
            prioridade = d.prioridade or "media"
            # Usa valor já salvo para não ficar consultando internet toda hora
            texto = svc.analisar_compra(d.nome, d.valor or 0)
            diag = svc.diagnostico_compra(d.nome, d.valor or 0)
            resumo = diag.get("decisao", "Aguardar")
            rows.append({
                "id": d.id,
                "nome": d.nome,
                "valor": round(d.valor or 0, 2),
                "prioridade": prioridade,
                "resumo": resumo,
                "melhor_caminho": diag.get("melhor_caminho"),
                "quando_comprar": diag.get("quando_comprar"),
                "pagamento_recomendado": diag.get("pagamento_recomendado"),
                "parcelas_recomendadas": diag.get("parcelas_recomendadas"),
                "valor_parcela_recomendado": diag.get("valor_parcela_recomendado"),
                "analise": texto
            })

        return jsonify({"ok": True, "desejos": rows})
    finally:
        db.close()
