
import os
from typing import Optional
import requests

class TelegramNotifier:
    def __init__(self):
        self.provider = os.getenv("TELEGRAM_PROVIDER", "log").lower()
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.default_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""

    def send(self, body: str, chat_id: Optional[int | str] = None) -> dict:
        chat_id = chat_id or self.default_chat_id
        if self.provider == "telegram" and self.bot_token and chat_id:
            url = f"{self.base_url}/sendMessage"
            resp = requests.post(url, json={"chat_id": chat_id, "text": body}, timeout=20)
            try:
                payload = resp.json()
            except Exception:
                payload = {"raw_text": resp.text}
            return {"ok": resp.ok, "provider": "telegram", "response": payload}
        print(f"[TELEGRAM-LOG] chat_id={chat_id} body={body}")
        return {"ok": True, "provider": "log", "response": None}
