import json
from datetime import datetime


class ConversationStateService:
    """Stores guided Telegram interactions so they survive web worker restarts."""

    def __init__(self, db_session):
        self.db = db_session

    def get(self, chat_id):
        from models.database import InteracaoPendente

        row = (
            self.db.query(InteracaoPendente)
            .filter(
                InteracaoPendente.chat_id == str(chat_id),
                InteracaoPendente.ativo == True,
            )
            .order_by(InteracaoPendente.updated_at.desc())
            .first()
        )
        if not row:
            return {}
        try:
            payload = json.loads(row.payload or "{}")
        except Exception:
            payload = {}
        payload["awaiting"] = row.tipo
        return payload

    def set(self, chat_id, tipo, payload):
        from models.database import InteracaoPendente

        sid = str(chat_id)
        self.clear(sid, commit=False)
        payload = dict(payload or {})
        payload["awaiting"] = tipo
        row = InteracaoPendente(
            chat_id=sid,
            tipo=str(tipo),
            payload=json.dumps(payload, ensure_ascii=False),
            ativo=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(row)
        self.db.commit()
        return payload

    def clear(self, chat_id, commit=True):
        from models.database import InteracaoPendente

        rows = (
            self.db.query(InteracaoPendente)
            .filter(
                InteracaoPendente.chat_id == str(chat_id),
                InteracaoPendente.ativo == True,
            )
            .all()
        )
        for row in rows:
            row.ativo = False
            row.updated_at = datetime.utcnow()
        if commit:
            self.db.commit()
