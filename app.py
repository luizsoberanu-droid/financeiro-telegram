import os
from flask import Flask, render_template, send_from_directory, request
from models.database import init_db
from routes.api import api_bp
from routes.telegram import telegram_bp

app = Flask(__name__)

# Inicializar banco de dados com proteção contra erros
try:
    init_db()
    print("✅ Banco de dados inicializado")
except Exception as e:
    print(f"⚠️ Aviso: erro ao inicializar banco de dados: {e}")


def _env_true(name, default="false"):
    return os.getenv(name, default).lower() in ["true", "1", "sim", "yes"]


# Restaurar dados do Google Sheets quando o Render reiniciar com SQLite vazio/novo.
# So carrega bibliotecas do Google se a integracao estiver configurada.
if _env_true("GOOGLE_SHEETS_RESTORE_ON_START", "true") and os.getenv("GOOGLE_SHEETS_ID") and os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
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
else:
    print("ℹ️ Restore Google Sheets ignorado no boot para economizar memória.")

# Registrar blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(telegram_bp)

# Iniciar cron jobs somente quando habilitado. No Render Free, manter scheduler
# dentro do web worker costuma aumentar consumo de memoria e reinicios.
cron_scheduler = None
if _env_true("AURUM_ENABLE_INTERNAL_CRON", "false"):
    try:
        from utils.cron_jobs import iniciar_cron_jobs
        cron_scheduler = iniciar_cron_jobs(app)
        print("✅ Cron jobs iniciados")
    except Exception as e:
        print(f"⚠️ Aviso: cron jobs não iniciados: {e}")
else:
    print("ℹ️ Cron interno desligado. Use cron externo chamando os endpoints do app.")


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
        ) and _env_true("GOOGLE_SHEETS_BACKUP_EVERY_MUTATION", "false"):
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
