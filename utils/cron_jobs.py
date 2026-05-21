from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os

def iniciar_cron_jobs(app):
    """Inicia os cron jobs para alertas automáticos e relatório mensal"""
    scheduler = BackgroundScheduler()

    # Atualiza histórico mensal diariamente às 23h55
    scheduler.add_job(
        func=lambda: atualizar_historico_mensal(app),
        trigger=CronTrigger(hour=23, minute=55),
        id='atualizar_historico_mensal',
        name='Atualizar Histórico Mensal',
        replace_existing=True
    )

    # Robô de 5 em 5 minutos para manter app ativo quando SELF_URL estiver configurada
    scheduler.add_job(
        func=lambda: ping_robo_5_minutos(),
        trigger=CronTrigger(minute='*/5'),
        id='ping_robo_5_minutos',
        name='Ping do Robô a cada 5 minutos',
        replace_existing=True
    )

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

    telegram_automations = os.getenv("TELEGRAM_AUTOMATIONS_ENABLED", "false").lower() in ["true", "1", "sim", "yes"]
    if not telegram_automations:
        for job_id in ["alertas_diarios", "alertas_vencimento", "relatorio_mensal", "checkup_dividas"]:
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass

    scheduler.start()
    print("✅ Cron jobs iniciados:")
    print("   • Histórico mensal: 23h55")
    print("   • Ping do app: a cada 5 minutos se SELF_URL estiver configurada")
    if telegram_automations:
        print("   • Alertas diários: 9h")
        print("   • Alertas vencimento: 8h")
        print("   • Relatório mensal: último dia do mês às 20h")
        print("   • Check-up dívidas: domingo às 10h")
    print("   Automações Telegram: " + ("ligadas" if telegram_automations else "desligadas"))
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


def atualizar_historico_mensal(app):
    """Salva o resumo do mês atual para histórico mensal"""
    with app.app_context():
        from models.database import SessionLocal
        from services.monthly_service import MonthlyService

        db = SessionLocal()
        try:
            MonthlyService(db).salvar_resumo_mes()
            print(f"[{datetime.now()}] Histórico mensal atualizado")
        except Exception as e:
            print(f"[{datetime.now()}] Erro ao atualizar histórico mensal: {e}")
        finally:
            db.close()


def ping_robo_5_minutos():
    """Faz ping no próprio app a cada 5 minutos se SELF_URL estiver configurada.

    Observação: em plano gratuito, o ideal continua sendo UptimeRobot externo,
    porque se o Render dormir totalmente o cron interno também dorme.
    """
    try:
        import os
        import requests
        url = os.getenv("SELF_URL", "").strip()
        if not url:
            return
        url = url.rstrip("/") + "/api/ping"
        requests.get(url, timeout=10)
        print(f"[{datetime.now()}] Ping 5 min OK")
    except Exception as e:
        print(f"[{datetime.now()}] Erro ping 5 min: {e}")
