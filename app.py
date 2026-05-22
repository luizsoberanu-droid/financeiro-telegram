from flask import Flask, render_template, send_from_directory, request
from models.database import init_db
from routes.api import api_bp
from routes.telegram import telegram_bp
import os

app = Flask(__name__)

# Inicializar banco de dados com proteção contra erros
try:
    init_db()
    print("✅ Banco de dados inicializado")
except Exception as e:
    print(f"⚠️ Aviso: erro ao inicializar banco de dados: {e}")


# Restaurar dados do Google Sheets quando o Render reiniciar com SQLite vazio/novo
try:
    from models.database import SessionLocal
    from services.sheets_backup_service import SheetsBackupService

    db_restore = SessionLocal()
    try:
        result_restore = SheetsBackupService(db_restore).restore_if_database_looks_fresh()
        if result_restore.get("ok"):
            print(f"✅ Dados restaurados do Google Sheets: {result_restore}")
        else:
            print(f"ℹ️ Restore Google Sheets não aplicado: {result_restore}")
    finally:
        db_restore.close()
except Exception as e:
    print(f"⚠️ Aviso: restore Google Sheets não executado: {e}")

# Registrar blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(telegram_bp)

# Iniciar cron jobs com proteção — só inicia se o scheduler estiver disponível
cron_scheduler = None
try:
    from utils.cron_jobs import iniciar_cron_jobs
    cron_scheduler = iniciar_cron_jobs(app)
    print("✅ Cron jobs iniciados")
except Exception as e:
    print(f"⚠️ Aviso: cron jobs não iniciados: {e}")


@app.after_request
def backup_google_sheets_after_mutation(response):
    """Autosave e backup automatico apos alteracoes, sem afetar o painel se falhar."""
    try:
        if request.method in ["POST", "PUT", "DELETE"] and (
            request.path.startswith("/api/") or request.path.startswith("/webhooks/")
        ):
            from models.database import SessionLocal
            from services.autosave_service import AutosaveService

            db_auto = SessionLocal()
            try:
                AutosaveService(db_auto).registrar_request(request, response)
            finally:
                db_auto.close()
    except Exception as e:
        print(f"Aviso: autosave de apontamento falhou sem bloquear app: {e}")

    try:
        if request.method in ["POST", "PUT", "DELETE"] and (
            request.path.startswith("/api/") or request.path.startswith("/webhooks/")
        ):
            from models.database import SessionLocal
            from services.sheets_backup_service import SheetsBackupService

            db_bkp = SessionLocal()
            try:
                SheetsBackupService(db_bkp).backup_all()
            finally:
                db_bkp.close()
    except Exception as e:
        print(f"⚠️ Backup Google Sheets falhou sem bloquear app: {e}")
    return response

@app.route("/api/ping")
def ping():
    return {"ok": True, "service": "aurum-capital", "ping": "alive"}

@app.route("/")
def home():
    try:
        return render_template("dashboard.html")
    except Exception as e:
        return f"""
        <h1>Aurum Capital v2.2</h1>
        <p>Erro ao carregar dashboard: {str(e)}</p>
        <p><a href="/api/status">Ver status API</a></p>
        """

@app.route("/manifest.json")
def manifest():
    return send_from_directory('templates', 'manifest.json', mimetype='application/manifest+json')

@app.route("/sw.js")
def service_worker():
    return send_from_directory('templates', 'sw.js', mimetype='application/javascript')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
