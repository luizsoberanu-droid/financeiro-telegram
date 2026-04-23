from flask import Flask, render_template
from models.database import init_db
from routes.api import api_bp
from routes.telegram import telegram_bp
import os

app = Flask(__name__)

# Inicializar banco de dados
init_db()

# Registrar blueprints
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(telegram_bp)

@app.route("/")
def home():
    try:
        return render_template("dashboard.html")
    except Exception as e:
        return f"""
        <h1>🚀 NEXUS AI v2.1</h1>
        <p>Erro ao carregar dashboard: {str(e)}</p>
        <p><a href="/api/status">Ver status API</a></p>
        """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
