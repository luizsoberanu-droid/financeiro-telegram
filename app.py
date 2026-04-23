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
    except:
        return """
        <h1>🚀 NEXUS AI v2.0</h1>
        <p>Assistente financeiro com IA real</p>
        <p><a href="/api/status">Ver status</a></p>
        <hr>
        <h3>Configuração no Render:</h3>
        <ul>
            <li><b>GROQ_API_KEY</b> - Cadastre em <a href="https://console.groq.com">console.groq.com</a> (grátis, sem cartão)</li>
            <li><b>GOOGLE_API_KEY</b> - Alternativa: <a href="https://aistudio.google.com">aistudio.google.com</a></li>
            <li><b>TELEGRAM_BOT_TOKEN</b> - Do @BotFather</li>
        </ul>
        <h3>Comandos Telegram:</h3>
        <ul>
            <li><code>status</code> - Ver situação financeira</li>
            <li><code>contas</code> - Listar contas fixas</li>
            <li><code>dividas</code> - Ver dívidas</li>
            <li><code>reserva</code> - Status da reserva</li>
            <li><code>plano</code> - Plano mensal</li>
            <li><code>alertas</code> - Verificar alertas</li>
            <li><code>pagar [nome]</code> - Marcar conta como paga</li>
            <li><code>extra [valor]</code> - Registrar renda extra</li>
            <li><code>[descricao] [valor]</code> - Lançar gasto rápido</li>
            <li>Qualquer outra mensagem → IA analisa e responde!</li>
        </ul>
        """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
