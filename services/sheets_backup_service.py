import os
import json
from datetime import datetime

SHEET_TABLES = [
    "config",
    "contas_fixas",
    "cartoes",
    "dividas",
    "limites",
    "lancamentos",
    "parcelas",
    "resumo_mensal",
    "desejos",
    "faturas_cartao_credito",
]

class SheetsBackupService:
    def __init__(self, db_session):
        self.db = db_session
        self.sheet_id = os.getenv("GOOGLE_SHEETS_ID", "").strip()
        self.creds_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
        self.enabled = bool(self.sheet_id and self.creds_json)

    def _client(self):
        if not self.enabled:
            return None
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        info = json.loads(self.creds_json)
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        return build("sheets", "v4", credentials=creds, cache_discovery=False).spreadsheets()

    def _models(self):
        from models.database import (
            Config, ContaFixa, Cartao, Divida, Limite,
            Lancamento, Parcela, ResumoMensal
        )
        models = {
            "config": Config,
            "contas_fixas": ContaFixa,
            "cartoes": Cartao,
            "dividas": Divida,
            "limites": Limite,
            "lancamentos": Lancamento,
            "parcelas": Parcela,
            "resumo_mensal": ResumoMensal,
        }
        try:
            from models.database import Desejo
            models["desejos"] = Desejo
        except Exception:
            pass
        return models

    def _serialize_value(self, value):
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _parse_value(self, column, value):
        if value == "":
            return None
        from sqlalchemy import Integer, Float, Boolean, DateTime

        ctype = column.type
        try:
            if isinstance(ctype, Integer):
                return int(float(value))
            if isinstance(ctype, Float):
                return float(value)
            if isinstance(ctype, Boolean):
                return str(value).lower() in ["true", "1", "sim", "yes"]
            if isinstance(ctype, DateTime):
                try:
                    return datetime.fromisoformat(str(value))
                except Exception:
                    return datetime.utcnow()
        except Exception:
            return value
        return value

    def _ensure_sheets(self, service):
        meta = service.get(spreadsheetId=self.sheet_id).execute()
        existing = {s["properties"]["title"] for s in meta.get("sheets", [])}

        requests = []
        for name in SHEET_TABLES:
            if name not in existing:
                requests.append({"addSheet": {"properties": {"title": name}}})

        if requests:
            service.batchUpdate(
                spreadsheetId=self.sheet_id,
                body={"requests": requests}
            ).execute()

    def _write_tab(self, service, tab, rows):
        service.values().clear(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!A:Z"
        ).execute()

        if not rows:
            rows = [["sem_dados"]]

        service.values().update(
            spreadsheetId=self.sheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": rows}
        ).execute()

    def _faturas_rows(self):
        from models.database import Lancamento, Parcela

        rows = [[
            "tipo", "cartao", "mes_ref", "vencimento",
            "descricao", "valor", "parcela", "data"
        ]]

        lancs = (
            self.db.query(Lancamento)
            .filter(Lancamento.forma_pagamento == "cartao")
            .order_by(Lancamento.mes_ref, Lancamento.cartao, Lancamento.data)
            .all()
        )

        for l in lancs:
            rows.append([
                "compra",
                l.cartao or "",
                l.fatura_mes_ref or l.mes_ref,
                l.fatura_vencimento or "",
                l.descricao,
                round(l.valor or 0, 2),
                "",
                l.data.isoformat() if l.data else ""
            ])

        parcelas = (
            self.db.query(Parcela)
            .order_by(Parcela.mes_ref, Parcela.cartao, Parcela.parcela_atual)
            .all()
        )

        for p in parcelas:
            rows.append([
                "parcela",
                p.cartao,
                p.mes_ref,
                p.vencimento,
                p.descricao,
                round(p.valor or 0, 2),
                f"{p.parcela_atual}/{p.total_parcelas}",
                p.created_at.isoformat() if p.created_at else ""
            ])

        return rows

    def backup_all(self):
        if not self.enabled:
            return {"ok": False, "reason": "GOOGLE_SHEETS_ID ou GOOGLE_SERVICE_ACCOUNT_JSON ausente"}

        service = self._client()
        self._ensure_sheets(service)

        models = self._models()

        for tab, model in models.items():
            columns = [c.name for c in model.__table__.columns]
            rows = [columns]

            for obj in self.db.query(model).all():
                rows.append([self._serialize_value(getattr(obj, c)) for c in columns])

            self._write_tab(service, tab, rows)

        # Aba consolidada de faturas de cartão de crédito
        self._write_tab(service, "faturas_cartao_credito", self._faturas_rows())

        return {"ok": True, "updated_at": datetime.utcnow().isoformat()}

    def restore_all(self, replace=True):
        if not self.enabled:
            return {"ok": False, "reason": "GOOGLE_SHEETS_ID ou GOOGLE_SERVICE_ACCOUNT_JSON ausente"}

        service = self._client()
        self._ensure_sheets(service)
        models = self._models()

        restored = {}

        for tab, model in models.items():
            result = service.values().get(
                spreadsheetId=self.sheet_id,
                range=f"{tab}!A:Z"
            ).execute()

            values = result.get("values", [])
            if len(values) < 2:
                continue

            headers = values[0]
            cols_by_name = {c.name: c for c in model.__table__.columns}

            if replace:
                self.db.query(model).delete()

            count = 0
            for row in values[1:]:
                data = {}
                for i, h in enumerate(headers):
                    if h not in cols_by_name:
                        continue
                    v = row[i] if i < len(row) else ""
                    parsed = self._parse_value(cols_by_name[h], v)
                    if parsed is not None:
                        data[h] = parsed

                if data:
                    self.db.add(model(**data))
                    count += 1

            restored[tab] = count

        self.db.commit()
        return {"ok": True, "restored": restored}

    def restore_if_database_looks_fresh(self):
        """Restaura automaticamente da planilha no início.

        Nesta versão, se GOOGLE_SHEETS_RESTORE_ON_START=true, a planilha vira
        a fonte principal quando o Render reinicia. Isso resolve reset do SQLite.
        """
        if not self.enabled:
            return {"ok": False, "reason": "backup desativado"}

        if os.getenv("GOOGLE_SHEETS_RESTORE_ON_START", "true").lower() not in ["true", "1", "sim", "yes"]:
            return {"ok": False, "reason": "restore automático desativado"}

        try:
            service = self._client()
            self._ensure_sheets(service)

            # Testa se pelo menos uma aba principal tem dados reais.
            for tab in ["config", "contas_fixas", "cartoes", "dividas", "lancamentos", "desejos"]:
                result = service.values().get(
                    spreadsheetId=self.sheet_id,
                    range=f"{tab}!A:Z"
                ).execute()
                values = result.get("values", [])
                if len(values) >= 2:
                    return self.restore_all(replace=True)

            return {"ok": False, "reason": "planilha sem dados para restaurar"}

        except Exception as e:
            return {"ok": False, "error": str(e)}
