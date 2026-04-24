from flask import Flask, render_template, send_from_directory
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

@app.route("/")
def home():
    try:
        return render_template("dashboard.html")
    except Exception as e:
        return f"""
        <h1>🚀 NEXUS AI v2.2</h1>
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
