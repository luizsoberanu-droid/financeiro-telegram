
import os
from pathlib import Path
from datetime import date
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
from apscheduler.schedulers.background import BackgroundScheduler

from spreadsheet_engine import FinanceWorkbook
from notifier import TelegramNotifier

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
WORKBOOK_PATH = BASE_DIR / os.getenv("WORKBOOK_PATH", "financeiro_telegram_premium.xlsx")

app = Flask(__name__)
engine = FinanceWorkbook(WORKBOOK_PATH)
notifier = TelegramNotifier()
scheduler = BackgroundScheduler()

def reminder_job():
    body = engine.bills_message(days_ahead=engine.alert_days())
    if "Nenhuma conta" in body:
        return
    notifier.send(body)

if os.getenv("ENABLE_SCHEDULER", "false").lower() == "true":
    scheduler.add_job(reminder_job, "cron", hour=int(os.getenv("REMINDER_HOUR", "8")), minute=0, id="daily_bill_reminders", replace_existing=True)
    scheduler.start()

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/download/workbook")
def download_workbook():
    return send_file(WORKBOOK_PATH, as_attachment=True)

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "service": "financeiro-telegram-premium"})

@app.get("/api/dashboard")
def api_dashboard():
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    data = engine.month_summary(month)
    data["bills_due"] = engine.due_bills(days_ahead=7)
    data["last_launches"] = engine.last_launches(limit=8)
    return jsonify(data)

@app.get("/api/category/<path:name>")
def api_category(name):
    month = request.args.get("month") or date.today().strftime("%Y-%m")
    return jsonify(engine.category_summary(name, month))

@app.post("/api/launch")
def api_launch():
    payload = request.get_json(force=True, silent=True) or {}
    category = payload.get("category", "")
    amount = float(payload.get("amount", 0))
    description = payload.get("description", "")
    channel = payload.get("channel", "painel")
    entry_type = payload.get("entry_type", "gasto")
    if not category or amount <= 0:
        return jsonify({"ok": False, "error": "Informe categoria e valor maior que zero."}), 400
    result = engine.add_launch(category=category, amount=amount, description=description, channel=channel, entry_type=entry_type)
    return jsonify({"ok": True, "message": result.message, "result": result.__dict__})

@app.post("/api/telegram-test")
def api_telegram_test():
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message", "")
    reply, data = engine.parse_telegram_message(message)
    return jsonify({"ok": True, "reply": reply, "data": data})

@app.get("/api/reminders")
def api_reminders():
    days = int(request.args.get("days", engine.alert_days()))
    bills = engine.due_bills(days_ahead=days)
    return jsonify({"ok": True, "count": len(bills), "bills": bills})

@app.post("/api/send-reminders")
def api_send_reminders():
    days = int((request.get_json(force=True, silent=True) or {}).get("days", engine.alert_days()))
    body = engine.bills_message(days_ahead=days)
    result = notifier.send(body)
    return jsonify({"ok": True, "send_result": result, "body": body})

@app.post("/webhooks/telegram")
def telegram_webhook():
    payload = request.get_json(force=True, silent=True) or {}
    message = payload.get("message") or payload.get("edited_message") or {}
    text = message.get("text", "")
    chat = message.get("chat", {}) or {}
    chat_id = chat.get("id")
    if not text:
        return jsonify({"ok": True, "ignored": True})
    reply, _ = engine.parse_telegram_message(text)
    if chat_id:
        notifier.send(reply, chat_id=chat_id)
    return jsonify({"ok": True, "reply": reply})

if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "5000"))
    debug = os.getenv("APP_DEBUG", "true").lower() == "true"
    app.run(host=host, port=port, debug=debug)
