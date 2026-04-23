from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os

def iniciar_cron_jobs(app):
    """Inicia os cron jobs para alertas automáticos e relatório mensal"""
    scheduler = BackgroundScheduler()

    # Alertas diários às 9h da manhã
    scheduler.add_job(
        func=lambda: enviar_alertas_diarios(app),
        trigger=CronTrigger(hour=9, minute=0),
        id='alertas_diarios',
        name='Alertas Diários de Finanças',
        replace_existing=True
    )

    # Alertas de contas próximas do vencimento (às 8h)
    scheduler.add_job(
        func=lambda: enviar_alertas_vencimento(app),
        trigger=CronTrigger(hour=8, minute=0),
        id='alertas_vencimento',
        name='Alertas de Vencimento',
        replace_existing=True
    )

    # Relatório mensal no último dia do mês às 20h
    scheduler.add_job(
        func=lambda: gerar_relatorio_mensal(app),
        trigger=CronTrigger(day='last', hour=20, minute=0),
        id='relatorio_mensal',
        name='Relatório Mensal Automático',
        replace_existing=True
    )

    # Check-up semanal de dívidas (domingo às 10h)
    scheduler.add_job(
        func=lambda: enviar_checkup_dividas(app),
        trigger=CronTrigger(day_of_week='sun', hour=10, minute=0),
        id='checkup_dividas',
        name='Check-up Semanal de Dívidas',
        replace_existing=True
    )

    scheduler.start()
    print("✅ Cron jobs iniciados:")
    print("   • Alertas diários: 9h")
    print("   • Alertas vencimento: 8h")
    print("   • Relatório mensal: último dia do mês às 20h")
    print("   • Check-up dívidas: domingo às 10h")
    return scheduler

def enviar_alertas_diarios(app):
    """Envia alertas diários para todos os usuários"""
    with app.app_context():
        from models.database import SessionLocal, Config
        from services.alert_service import AlertService

        db = SessionLocal()
        try:
            alert_svc = AlertService(db)
            # Buscar chat_ids dos usuários (simplificado - usa default)
            alert_svc.verificar_todos_alertas("default")
            print(f"[{datetime.now()}] Alertas diários enviados")
        except Exception as e:
            print(f"[{datetime.now()}] Erro alertas diários: {e}")
        finally:
            db.close()

def enviar_alertas_vencimento(app):
    """Envia alertas de contas próximas do vencimento"""
    with app.app_context():
        from models.database import SessionLocal
        from services.alert_service import AlertService

        db = SessionLocal()
        try:
            alert_svc = AlertService(db)
            alert_svc._alerta_contas_vencimento("default")
            print(f"[{datetime.now()}] Alertas de vencimento enviados")
        except Exception as e:
            print(f"[{datetime.now()}] Erro alertas vencimento: {e}")
        finally:
            db.close()

def gerar_relatorio_mensal(app):
    """Gera e envia relatório mensal automático"""
    with app.app_context():
        from models.database import SessionLocal
        from services.pdf_service import PDFService
        from services.alert_service import telegram_send
        from datetime import datetime

        db = SessionLocal()
        try:
            svc = PDFService(db)
            mes_ref = datetime.now().strftime("%Y-%m")
            pdf_bytes = svc.gerar_relatorio_mensal(mes_ref)

            # Salvar PDF temporário
            filename = f"/tmp/relatorio_nexus_{mes_ref}.pdf"
            with open(filename, 'wb') as f:
                f.write(pdf_bytes)

            # Enviar via Telegram
            msg = (
                f"📊 RELATÓRIO MENSAL GERADO\n"
                f"Mês: {mes_ref}\n\n"
                f"O relatório financeiro do mês está pronto!\n"
                f"Acesse o painel para baixar."
            )
            telegram_send("default", msg)
            print(f"[{datetime.now()}] Relatório mensal gerado: {filename}")
        except Exception as e:
            print(f"[{datetime.now()}] Erro relatório mensal: {e}")
        finally:
            db.close()

def enviar_checkup_dividas(app):
    """Envia check-up semanal de dívidas"""
    with app.app_context():
        from models.database import SessionLocal
        from services.alert_service import AlertService

        db = SessionLocal()
        try:
            alert_svc = AlertService(db)
            alert_svc._alerta_divida("default")
            print(f"[{datetime.now()}] Check-up de dívidas enviado")
        except Exception as e:
            print(f"[{datetime.now()}] Erro check-up dívidas: {e}")
        finally:
            db.close()
